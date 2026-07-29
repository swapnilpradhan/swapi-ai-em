"""Export idempotency and manifest recovery.

These are the properties ADR-0002 depends on. The stub writes the same folder contract
as Drive, so getting these right here is what makes the Drive adapter thin.
"""

from __future__ import annotations

from backend.app.models import ArtifactKind, ExportStatus
from backend.app.services.artifacts import build_artifacts
from backend.app.services.storage import StubStorageService


class TestFolderContract:
    async def test_creates_the_year_and_meeting_folders(self, settings, meeting):
        service = StubStorageService(settings)
        folder = await service.ensure_meeting_folder(meeting)

        assert "2026" in folder
        assert meeting.folder_name in folder

    async def test_writes_the_privacy_readme(self, settings, meeting):
        """The warning goes where someone is about to make the mistake."""
        service = StubStorageService(settings)
        folder = await service.ensure_meeting_folder(meeting)

        readme = settings.drive_stub_root / "2026" / meeting.folder_name / "README.md"
        assert readme.exists()
        assert "without their agreement" in readme.read_text()
        assert folder

    async def test_audio_keeps_its_original_extension(self, settings, meeting):
        from backend.app.models import Artifact
        from backend.app.services.ingest import content_hash

        service = StubStorageService(settings)
        wav = meeting.model_copy(
            update={"audio": meeting.audio.model_copy(update={"original_filename": "rec.wav"})}
        )
        data = b"audio"
        await service.export(
            wav, Artifact(kind=ArtifactKind.AUDIO, content=data, content_hash=content_hash(data))
        )

        folder = settings.drive_stub_root / "2026" / wav.folder_name
        assert (folder / "audio.wav").exists()


class TestIdempotency:
    async def test_reexport_of_unchanged_content_writes_nothing(self, settings, meeting):
        """The cheapest regression test for the whole idempotency design."""
        service = StubStorageService(settings)
        artifacts = build_artifacts(meeting)

        first = await service.export_all(meeting, artifacts)
        assert all(e.status is ExportStatus.OK for e in first.entries)

        results = [await service.export(meeting, a) for a in artifacts]
        assert all(r.status is ExportStatus.SKIPPED_UNCHANGED for r in results)

    async def test_changed_content_is_rewritten(self, settings, meeting):
        from backend.app.models import Artifact
        from backend.app.services.ingest import content_hash

        service = StubStorageService(settings)

        v1 = b"# Summary\n\nfirst version\n"
        v2 = b"# Summary\n\nsecond version\n"
        await service.export(
            meeting,
            Artifact(kind=ArtifactKind.SUMMARY, content=v1, content_hash=content_hash(v1)),
        )
        result = await service.export(
            meeting,
            Artifact(kind=ArtifactKind.SUMMARY, content=v2, content_hash=content_hash(v2)),
        )

        assert result.status is ExportStatus.OK
        folder = settings.drive_stub_root / "2026" / meeting.folder_name
        assert (folder / "summary.md").read_bytes() == v2

    async def test_no_duplicate_files_are_created(self, settings, meeting):
        """`transcript (2).md` appearing in the archive is the failure this prevents."""
        service = StubStorageService(settings)
        artifacts = build_artifacts(meeting)

        for _ in range(3):
            await service.export_all(meeting, artifacts)

        folder = settings.drive_stub_root / "2026" / meeting.folder_name
        names = sorted(p.name for p in folder.iterdir())
        assert names == sorted(set(names))
        assert not any("(" in n for n in names)


class TestManifestRecovery:
    async def test_manifest_is_written_to_the_archive(self, settings, meeting):
        service = StubStorageService(settings)
        await service.export_all(meeting, build_artifacts(meeting))

        path = settings.drive_stub_root / "2026" / meeting.folder_name / "manifest.json"
        assert path.exists()

    async def test_export_state_recovers_from_the_archive_alone(self, settings, meeting):
        """ADR-0002's claim: losing the database must be recoverable."""
        service = StubStorageService(settings)
        await service.export_all(meeting, build_artifacts(meeting))

        # A completely fresh service instance holds no state of its own.
        recovered = await StubStorageService(settings).read_manifest(meeting.id)

        assert recovered is not None
        assert recovered.meeting_id == meeting.id
        assert recovered.entry_for(ArtifactKind.TRANSCRIPT_MD) is not None

    async def test_unknown_meeting_has_no_manifest(self, settings):
        assert await StubStorageService(settings).read_manifest("nope") is None
