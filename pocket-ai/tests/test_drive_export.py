"""Drive client and export service, against an in-memory Drive.

The client code under test is the production path — query building, multipart and
resumable uploads, 308 continuation, backoff, token refresh — with only the network
replaced.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.app.core.config import Settings
from backend.app.models import Artifact, ArtifactKind, ExportManifest, ExportStatus
from backend.app.services import drive_client as dc
from backend.app.services.artifacts import build_artifacts
from backend.app.services.drive_client import (
    DriveClient,
    DriveError,
    ResumableInterrupted,
    escape_query_value,
)
from backend.app.services.drive_storage import APP_TAG, DriveStorageService
from backend.app.services.google_auth import Credentials, GoogleOAuthFlow
from backend.app.services.ingest import content_hash
from tests.fake_drive import FakeDrive


@pytest.fixture
def drive() -> FakeDrive:
    return FakeDrive()


@pytest.fixture
def drive_settings(tmp_path) -> Settings:
    return Settings(
        media_root=tmp_path / "media",
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_token_path=tmp_path / "creds" / "token.json",
        drive_root_folder_name="Pocket.ai Studio",
        app_env="test",
    )


@pytest.fixture
def authorized_flow(drive_settings, drive) -> GoogleOAuthFlow:
    flow = GoogleOAuthFlow(drive_settings, transport=drive.transport)
    flow.store.save(
        Credentials(
            access_token=drive.access_token,
            refresh_token="refresh-1",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    return flow


@pytest.fixture
def client(authorized_flow, drive) -> DriveClient:
    async def no_sleep(_seconds):  # backoff without the wall clock
        return None

    return DriveClient(authorized_flow, transport=drive.transport, sleep=no_sleep)


@pytest.fixture
def storage(drive_settings, authorized_flow, client) -> DriveStorageService:
    return DriveStorageService(drive_settings, oauth=authorized_flow, client=client)


class TestQueryEscaping:
    def test_apostrophes_are_escaped(self):
        """ "Priya's 1:1" would otherwise terminate the quoted value early."""
        assert escape_query_value("Priya's 1:1") == "Priya\\'s 1:1"

    def test_backslashes_are_escaped_first(self):
        assert escape_query_value("a\\b") == "a\\\\b"

    async def test_a_name_with_an_apostrophe_round_trips(self, client, drive):
        parent = drive.add_folder("parent")
        folder_id = await client.ensure_folder("Priya's 1:1", parent=parent)

        assert await client.ensure_folder("Priya's 1:1", parent=parent) == folder_id


class TestFolders:
    async def test_ensure_folder_is_idempotent(self, client, drive):
        first = await client.ensure_folder("Pocket.ai Studio")
        second = await client.ensure_folder("Pocket.ai Studio")

        assert first == second
        assert len([f for f in drive.files.values() if f.name == "Pocket.ai Studio"]) == 1

    async def test_folders_nest_under_their_parent(self, client, drive):
        root = await client.ensure_folder("Pocket.ai Studio")
        year = await client.ensure_folder("2026", parent=root)

        assert drive.files[year].parents == [root]


class TestRetryBehaviour:
    async def test_retries_on_429(self, client, drive):
        drive.failures.append((429, {"error": {"message": "slow down"}}))
        assert await client.ensure_folder("Pocket.ai Studio")

    async def test_retries_on_500(self, client, drive):
        drive.failures.append((500, {"error": {"message": "backend error"}}))
        assert await client.ensure_folder("Pocket.ai Studio")

    async def test_retries_on_rate_limit_403(self, client, drive):
        drive.failures.append((403, {"error": {"errors": [{"reason": "userRateLimitExceeded"}]}}))
        assert await client.ensure_folder("Pocket.ai Studio")

    async def test_does_not_retry_a_permission_403(self, client, drive):
        """Retrying a permission error just delays a message the user needs."""
        drive.failures.extend(
            [(403, {"error": {"errors": [{"reason": "insufficientFilePermissions"}]}})] * 6
        )
        with pytest.raises(DriveError, match="403"):
            await client.ensure_folder("Pocket.ai Studio")

    async def test_gives_up_after_max_attempts(self, client, drive):
        drive.failures.extend([(500, {"error": {"message": "down"}})] * (dc.MAX_ATTEMPTS + 2))
        with pytest.raises(DriveError):
            await client.ensure_folder("Pocket.ai Studio")

    async def test_401_triggers_a_refresh_then_succeeds(self, client, drive, authorized_flow):
        """A token can die before its stated expiry; one refresh beats failing."""
        authorized_flow.store.save(
            authorized_flow.store.load().model_copy(update={"access_token": "stale-token"})
        )

        assert await client.ensure_folder("Pocket.ai Studio")
        assert drive.token_refreshes == 1

    async def test_honours_retry_after(self, authorized_flow, drive):
        seen: list[float] = []

        async def record(seconds):
            seen.append(seconds)

        client = DriveClient(authorized_flow, transport=drive.transport, sleep=record)
        drive.failures.append((429, {"error": {"message": "slow"}}))
        # MockTransport cannot set headers on queued failures, so assert only that
        # a delay was taken — the header path is covered by _retry_after directly.
        await client.ensure_folder("Pocket.ai Studio")
        assert seen and seen[0] >= 0

    def test_retry_after_header_is_preferred(self):
        import httpx

        response = httpx.Response(429, headers={"Retry-After": "7"})
        assert dc._retry_after(response, attempt=0) == 7.0


class TestUploads:
    async def test_small_file_uses_multipart(self, client, drive):
        parent = drive.add_folder("parent")
        file_id, session = await client.upload(
            name="summary.md", content=b"# Summary\n", parent=parent, mime_type="text/markdown"
        )

        assert session is None
        assert drive.files[file_id].content == b"# Summary\n"

    async def test_update_replaces_content_in_place(self, client, drive):
        parent = drive.add_folder("parent")
        file_id, _ = await client.upload(name="s.md", content=b"v1", parent=parent)
        same_id, _ = await client.upload(name="s.md", content=b"v2", parent=parent, file_id=file_id)

        assert same_id == file_id
        assert drive.files[file_id].content == b"v2"
        assert len(drive.files) == 2  # parent + the one file

    async def test_large_file_uses_resumable_chunks(self, client, drive, monkeypatch):
        monkeypatch.setattr(dc, "RESUMABLE_THRESHOLD", 1024)
        monkeypatch.setattr(dc, "CHUNK_SIZE", 512)
        parent = drive.add_folder("parent")
        payload = bytes(range(256)) * 12  # 3072 bytes → 6 chunks

        file_id, session = await client.upload(
            name="audio.m4a", content=payload, parent=parent, mime_type="audio/mp4"
        )

        assert session is None
        assert drive.files[file_id].content == payload

    async def test_interrupted_upload_surfaces_its_session(self, client, drive, monkeypatch):
        """The session URI is the difference between resuming and restarting."""
        monkeypatch.setattr(dc, "RESUMABLE_THRESHOLD", 1024)
        monkeypatch.setattr(dc, "CHUNK_SIZE", 512)
        drive.fail_chunk_after = 2
        parent = drive.add_folder("parent")

        with pytest.raises(ResumableInterrupted) as caught:
            await client.upload(
                name="audio.m4a", content=bytes(3072), parent=parent, mime_type="audio/mp4"
            )

        assert caught.value.session_uri
        assert caught.value.offset > 0

    async def test_resume_continues_from_the_server_offset(self, client, drive, monkeypatch):
        monkeypatch.setattr(dc, "RESUMABLE_THRESHOLD", 1024)
        monkeypatch.setattr(dc, "CHUNK_SIZE", 512)
        parent = drive.add_folder("parent")
        payload = bytes(range(256)) * 12

        drive.fail_chunk_after = 2
        with pytest.raises(ResumableInterrupted) as caught:
            await client.upload(name="audio.m4a", content=payload, parent=parent)

        drive.fail_chunk_after = None
        file_id, session = await client.upload(
            name="audio.m4a",
            content=payload,
            parent=parent,
            resumable_session=caught.value.session_uri,
        )

        assert session is None
        assert drive.files[file_id].content == payload

    async def test_dead_session_restarts_cleanly(self, client, drive, monkeypatch):
        monkeypatch.setattr(dc, "RESUMABLE_THRESHOLD", 1024)
        monkeypatch.setattr(dc, "CHUNK_SIZE", 512)
        parent = drive.add_folder("parent")
        payload = bytes(2048)

        file_id, session = await client.upload(
            name="audio.m4a",
            content=payload,
            parent=parent,
            resumable_session="https://upload.test/resumable/gone",
        )

        assert session is None
        assert drive.files[file_id].content == payload

    def test_range_parsing(self):
        assert DriveClient._parse_range("bytes=0-511", fallback=0) == 512
        assert DriveClient._parse_range(None, fallback=42) == 42
        assert DriveClient._parse_range("garbage", fallback=7) == 7


class TestFolderContract:
    async def test_creates_root_year_and_meeting_folders(self, storage, drive, meeting):
        await storage.ensure_meeting_folder(meeting)

        names = {f.name for f in drive.files.values()}
        assert "Pocket.ai Studio" in names
        assert "2026" in names
        assert meeting.folder_name in names

    async def test_writes_the_privacy_readme(self, storage, drive, meeting):
        folder_id = await storage.ensure_meeting_folder(meeting)
        readme = next(f for f in drive.children(folder_id) if f.name == "README.md")

        assert b"without their agreement" in readme.content

    async def test_meeting_folder_is_tagged_for_recovery(self, storage, drive, meeting):
        folder_id = await storage.ensure_meeting_folder(meeting)
        assert drive.files[folder_id].app_properties["meetingId"] == meeting.id

    async def test_retitled_meeting_reuses_its_folder(self, storage, drive, meeting):
        """Lookup is by meeting id, so a new title must not start a second folder."""
        original = await storage.ensure_meeting_folder(meeting)
        storage._folder_cache.clear()

        renamed = meeting.model_copy(update={"title": "Completely Different Title"})
        assert await storage.ensure_meeting_folder(renamed) == original

    async def test_same_day_title_clash_is_disambiguated(self, storage, drive, meeting):
        await storage.ensure_meeting_folder(meeting)
        storage._folder_cache.clear()

        other = meeting.model_copy(update={"id": "a-different-meeting-entirely"})
        second = await storage.ensure_meeting_folder(other)

        assert drive.files[second].name != meeting.folder_name
        assert drive.files[second].name.startswith(meeting.folder_name)

    async def test_audio_keeps_its_extension(self, storage, drive, meeting):
        wav = meeting.model_copy(
            update={"audio": meeting.audio.model_copy(update={"original_filename": "rec.wav"})}
        )
        data = b"audio-bytes"
        await storage.export(
            wav, Artifact(kind=ArtifactKind.AUDIO, content=data, content_hash=content_hash(data))
        )

        assert any(f.name == "audio.wav" for f in drive.files.values())


class TestIdempotency:
    async def test_reexport_of_unchanged_content_uploads_nothing(self, storage, drive, meeting):
        """Literally zero writes — the cheapest regression test for idempotency."""
        artifacts = build_artifacts(meeting)
        await storage.export_all(meeting, artifacts)
        baseline = drive.uploads

        manifest = await storage.export_all(meeting, artifacts)

        assert drive.uploads == baseline
        assert all(
            e.status is ExportStatus.OK
            for e in manifest.entries
            if e.artifact_kind is not ArtifactKind.MANIFEST
        )

    async def test_a_single_changed_artifact_writes_only_itself(self, storage, drive, meeting):
        def summary(body: bytes) -> Artifact:
            return Artifact(
                kind=ArtifactKind.SUMMARY, content=body, content_hash=content_hash(body)
            )

        artifacts = [*build_artifacts(meeting), summary(b"# Summary\n\nv1\n")]
        await storage.export_all(meeting, artifacts)
        baseline = drive.uploads

        artifacts[-1] = summary(b"# Summary\n\nv2\n")
        await storage.export_all(meeting, artifacts)

        # The changed summary plus the manifest — nothing else moved.
        assert drive.uploads - baseline == 2

    async def test_no_duplicate_files_appear(self, storage, drive, meeting):
        """`transcript (2).md` in the archive is the failure this prevents."""
        artifacts = build_artifacts(meeting)
        for _ in range(3):
            await storage.export_all(meeting, artifacts)

        folder_id = await storage.ensure_meeting_folder(meeting)
        names = [f.name for f in drive.children(folder_id)]
        assert len(names) == len(set(names))

    async def test_changed_artifact_is_updated_in_place(self, storage, drive, meeting):
        v1 = b"# Summary\n\nfirst\n"
        v2 = b"# Summary\n\nsecond\n"
        first = await storage.export(
            meeting, Artifact(kind=ArtifactKind.SUMMARY, content=v1, content_hash=content_hash(v1))
        )
        second = await storage.export(
            meeting, Artifact(kind=ArtifactKind.SUMMARY, content=v2, content_hash=content_hash(v2))
        )

        assert second.drive_file_id == first.drive_file_id
        assert drive.files[second.drive_file_id].content == v2

    async def test_lost_manifest_falls_back_to_a_name_lookup(self, storage, drive, meeting):
        """Without this, a lost manifest silently duplicates every artifact."""
        artifacts = build_artifacts(meeting)
        await storage.export_all(meeting, artifacts)

        folder_id = await storage.ensure_meeting_folder(meeting)
        manifest_file = next(f for f in drive.children(folder_id) if f.name == "manifest.json")
        manifest_file.trashed = True
        storage._folder_cache.clear()

        await storage.export_all(meeting, artifacts)

        names = [f.name for f in drive.children(folder_id) if not f.trashed]
        assert len(names) == len(set(names))


class TestManifestRecovery:
    async def test_manifest_is_written_to_drive(self, storage, drive, meeting):
        await storage.export_all(meeting, build_artifacts(meeting))
        folder_id = await storage.ensure_meeting_folder(meeting)

        assert any(f.name == "manifest.json" for f in drive.children(folder_id))

    async def test_state_recovers_from_drive_alone(
        self, storage, drive_settings, authorized_flow, client, meeting
    ):
        """ADR-0002's claim: losing the database must be recoverable."""
        await storage.export_all(meeting, build_artifacts(meeting))

        fresh = DriveStorageService(drive_settings, oauth=authorized_flow, client=client)
        recovered = await fresh.read_manifest(meeting.id)

        assert recovered is not None
        assert recovered.meeting_id == meeting.id
        assert recovered.entry_for(ArtifactKind.TRANSCRIPT_MD) is not None

    async def test_unknown_meeting_has_no_manifest(self, storage):
        assert await storage.read_manifest("never-exported") is None

    async def test_corrupt_manifest_does_not_block_export(self, storage, drive, meeting):
        await storage.export_all(meeting, build_artifacts(meeting))
        folder_id = await storage.ensure_meeting_folder(meeting)
        next(f for f in drive.children(folder_id) if f.name == "manifest.json").content = b"{{{"

        recovered = await storage.read_manifest(meeting.id)
        assert recovered is not None
        assert recovered.entries == []


class TestFailureHandling:
    async def test_one_failing_artifact_does_not_abandon_the_rest(
        self, storage, drive, meeting, monkeypatch
    ):
        # Create the folder (and its README) first, so the patch below only affects
        # artifact uploads rather than folder setup.
        await storage.ensure_meeting_folder(meeting)

        artifacts = build_artifacts(meeting)
        calls = {"n": 0}
        real_upload = storage.client.upload

        async def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise DriveError("simulated failure")
            return await real_upload(**kwargs)

        monkeypatch.setattr(storage.client, "upload", flaky)
        manifest = await storage.export_all(meeting, artifacts)

        assert any(e.status is ExportStatus.FAILED for e in manifest.entries)
        assert any(e.status is ExportStatus.OK for e in manifest.entries)

    async def test_failed_entry_records_a_reason(self, storage, meeting, monkeypatch):
        await storage.ensure_meeting_folder(meeting)
        manifest = ExportManifest(meeting_id=meeting.id, folder_name=meeting.folder_name)

        async def always_fail(**kwargs):
            raise DriveError("quota exhausted")

        monkeypatch.setattr(storage.client, "upload", always_fail)
        result = await storage._export_one(
            meeting,
            Artifact(kind=ArtifactKind.SUMMARY, content=b"x", content_hash=content_hash(b"x")),
            manifest,
        )

        assert result.status is ExportStatus.FAILED
        assert "quota exhausted" in result.reason
        assert manifest.entry_for(ArtifactKind.SUMMARY).status is ExportStatus.FAILED

    async def test_interrupted_audio_persists_its_session(
        self, storage, drive, meeting, monkeypatch
    ):
        """A stalled 400 MB upload must cost seconds on retry, not the whole transfer."""
        monkeypatch.setattr(dc, "RESUMABLE_THRESHOLD", 1024)
        monkeypatch.setattr(dc, "CHUNK_SIZE", 512)
        drive.fail_chunk_after = 1

        payload = bytes(3072)
        manifest = await storage.export_all(
            meeting,
            [
                Artifact(
                    kind=ArtifactKind.AUDIO, content=payload, content_hash=content_hash(payload)
                )
            ],
        )

        entry = manifest.entry_for(ArtifactKind.AUDIO)
        assert entry.status is ExportStatus.FAILED
        assert entry.resumable_session_uri

    async def test_a_previously_failed_artifact_is_retried(self, storage, drive, meeting):
        """`is_unchanged` must not treat a failed entry as already done."""
        await storage.ensure_meeting_folder(meeting)
        artifacts = [
            Artifact(kind=ArtifactKind.SUMMARY, content=b"body", content_hash=content_hash(b"body"))
        ]
        real_upload = storage.client.upload
        calls = {"n": 0}

        async def fail_first_artifact(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise DriveError("transient")
            return await real_upload(**kwargs)

        storage.client.upload = fail_first_artifact
        first = await storage.export_all(meeting, artifacts)
        assert first.entry_for(ArtifactKind.SUMMARY).status is ExportStatus.FAILED

        storage.client.upload = real_upload
        manifest = await storage.export_all(meeting, artifacts)

        assert manifest.entry_for(ArtifactKind.SUMMARY).status is ExportStatus.OK


class TestDiagnostics:
    async def test_check_reports_the_account(self, storage):
        result = await storage.check()

        assert result["ok"] is True
        assert result["account"] == "user@example.test"

    async def test_check_without_credentials_reports_unauthorized(self, tmp_path, drive):
        # A distinct token path: the authorized fixtures write to the shared one.
        settings = Settings(
            media_root=tmp_path / "media",
            google_client_id="client-id",
            google_client_secret="client-secret",
            google_token_path=tmp_path / "empty" / "token.json",
            app_env="test",
        )
        flow = GoogleOAuthFlow(settings, transport=drive.transport)
        service = DriveStorageService(
            settings, oauth=flow, client=DriveClient(flow, transport=drive.transport)
        )

        result = await service.check()
        assert result["ok"] is False
        assert result["authorized"] is False


class TestAppTag:
    async def test_artifacts_carry_recovery_metadata(self, storage, drive, meeting):
        await storage.export_all(meeting, build_artifacts(meeting))
        folder_id = await storage.ensure_meeting_folder(meeting)

        transcript = next(f for f in drive.children(folder_id) if f.name == "transcript.md")
        assert transcript.app_properties[APP_TAG] == "artifact"
        assert transcript.app_properties["meetingId"] == meeting.id
        assert transcript.app_properties["artifactKind"] == "transcript_md"
