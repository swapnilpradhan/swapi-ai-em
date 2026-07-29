"""Google Drive implementation of ``StorageService``.

Behaviourally identical to ``StubStorageService`` — same folder contract, same
idempotency, same manifest. The stub exists so that logic could be settled offline;
this is the adapter that runs it against Drive.

See docs/capabilities/01-drive-export.md and ADR-0002.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..core.config import Settings
from ..core.logging import get_logger
from ..models import (
    Artifact,
    ArtifactKind,
    ExportManifest,
    ExportResult,
    ExportStatus,
    ManifestEntry,
    Meeting,
)
from .drive_client import DriveClient, DriveError, ResumableInterrupted
from .google_auth import GoogleOAuthFlow, NotAuthorized
from .storage import PRIVACY_README

log = get_logger(__name__)

MIME_TYPES: dict[ArtifactKind, str] = {
    ArtifactKind.AUDIO: "audio/mp4",
    ArtifactKind.TRANSCRIPT_MD: "text/markdown",
    ArtifactKind.TRANSCRIPT_JSON: "application/json",
    ArtifactKind.SUMMARY: "text/markdown",
    ArtifactKind.ACTION_ITEMS: "text/markdown",
    ArtifactKind.MIND_MAP: "text/markdown",
    ArtifactKind.DECK: (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
    ArtifactKind.MANIFEST: "application/json",
    ArtifactKind.README: "text/markdown",
}

# Stamped on every file and folder we create. This is what makes the archive
# self-describing: export state can be rebuilt from Drive alone, without the
# database, which is the property ADR-0002 rests on.
APP_TAG = "pocketAiStudio"


class DriveStorageService:
    def __init__(
        self,
        settings: Settings,
        *,
        oauth: GoogleOAuthFlow | None = None,
        client: DriveClient | None = None,
    ) -> None:
        self.settings = settings
        self.oauth = oauth or GoogleOAuthFlow(settings)
        self.client = client or DriveClient(self.oauth)
        # Folder ids are stable for the process lifetime; re-looking them up on every
        # artifact would triple the request count of a full export.
        self._folder_cache: dict[str, str] = {}

    # -- folders ---------------------------------------------------------------

    async def _root_folder(self) -> str:
        key = "__root__"
        if key not in self._folder_cache:
            self._folder_cache[key] = await self.client.ensure_folder(
                self.settings.drive_root_folder_name,
                app_properties={APP_TAG: "root"},
            )
        return self._folder_cache[key]

    async def _year_folder(self, year: int) -> str:
        key = f"year:{year}"
        if key not in self._folder_cache:
            self._folder_cache[key] = await self.client.ensure_folder(
                str(year), parent=await self._root_folder(), app_properties={APP_TAG: "year"}
            )
        return self._folder_cache[key]

    async def ensure_meeting_folder(self, meeting: Meeting) -> str:
        key = f"meeting:{meeting.id}"
        if key in self._folder_cache:
            return self._folder_cache[key]

        # Look up by meeting id first: a retitled meeting must land in its existing
        # folder rather than starting a second one alongside it.
        existing = await self.client.find(
            app_properties={APP_TAG: "meeting", "meetingId": meeting.id}
        )
        if existing:
            self._folder_cache[key] = existing.id
            return existing.id

        year_folder = await self._year_folder(meeting.occurred_at.year)
        name = await self._unique_folder_name(meeting, year_folder)

        folder_id = await self.client.ensure_folder(
            name,
            parent=year_folder,
            app_properties={APP_TAG: "meeting", "meetingId": meeting.id},
        )
        self._folder_cache[key] = folder_id

        await self._ensure_privacy_readme(meeting, folder_id)
        return folder_id

    async def _unique_folder_name(self, meeting: Meeting, year_folder: str) -> str:
        """Disambiguate two meetings sharing a date and title.

        Same-day recurring meetings with identical titles are common, and merging
        them into one folder would overwrite one meeting's artifacts with another's.
        """
        name = meeting.folder_name
        clash = await self.client.find(name=name, parent=year_folder)
        if clash is None:
            return name
        return f"{name} ({meeting.id[:8]})"

    async def _ensure_privacy_readme(self, meeting: Meeting, folder_id: str) -> None:
        """The warning belongs where someone is about to share the folder."""
        if await self.client.find(name="README.md", parent=folder_id):
            return
        await self.client.upload(
            name="README.md",
            content=PRIVACY_README.encode("utf-8"),
            parent=folder_id,
            mime_type="text/markdown",
            app_properties={APP_TAG: "readme", "meetingId": meeting.id},
        )

    # -- manifest --------------------------------------------------------------

    async def read_manifest(self, meeting_id: str) -> ExportManifest | None:
        """Read export state from Drive, not from the database.

        This is what makes "losing the database is recoverable" true rather than
        aspirational — see ADR-0002.
        """
        folder = await self.client.find(
            app_properties={APP_TAG: "meeting", "meetingId": meeting_id}
        )
        if folder is None:
            return None

        manifest_file = await self.client.find(name="manifest.json", parent=folder.id)
        if manifest_file is None:
            return ExportManifest(
                meeting_id=meeting_id, folder_name=folder.name, drive_folder_id=folder.id
            )

        try:
            manifest = ExportManifest.model_validate_json(
                await self.client.download(manifest_file.id)
            )
        except (DriveError, ValueError) as exc:
            # A corrupt manifest must not block export. Rebuilding an empty one means
            # the next run re-uploads everything, which is wasteful but never lossy.
            log.warning("drive.manifest_unreadable", meeting_id=meeting_id, error=str(exc))
            return ExportManifest(
                meeting_id=meeting_id, folder_name=folder.name, drive_folder_id=folder.id
            )

        manifest.drive_folder_id = folder.id
        return manifest

    async def _write_manifest(self, meeting: Meeting, manifest: ExportManifest) -> None:
        folder_id = await self.ensure_meeting_folder(meeting)
        content = manifest.model_dump_json(indent=2).encode("utf-8")

        entry = manifest.entry_for(ArtifactKind.MANIFEST)
        file_id = entry.drive_file_id if entry else None
        if file_id is None:
            found = await self.client.find(name="manifest.json", parent=folder_id)
            file_id = found.id if found else None

        new_id, _ = await self.client.upload(
            name="manifest.json",
            content=content,
            parent=folder_id,
            mime_type="application/json",
            app_properties={APP_TAG: "manifest", "meetingId": meeting.id},
            file_id=file_id,
        )
        manifest.upsert(
            ManifestEntry(
                artifact_kind=ArtifactKind.MANIFEST,
                filename="manifest.json",
                drive_file_id=new_id,
                content_hash=None,  # self-referential; hashing it would never match
                size_bytes=len(content),
                exported_at=datetime.now(UTC),
                status=ExportStatus.OK,
            )
        )

    # -- export ----------------------------------------------------------------

    async def export(self, meeting: Meeting, artifact: Artifact) -> ExportResult:
        manifest = await self.read_manifest(meeting.id) or ExportManifest(
            meeting_id=meeting.id, folder_name=meeting.folder_name
        )
        result = await self._export_one(meeting, artifact, manifest)
        await self._write_manifest(meeting, manifest)
        return result

    async def _export_one(
        self, meeting: Meeting, artifact: Artifact, manifest: ExportManifest
    ) -> ExportResult:
        if manifest.is_unchanged(artifact.kind, artifact.content_hash):
            entry = manifest.entry_for(artifact.kind)
            log.debug("drive.skip_unchanged", meeting_id=meeting.id, kind=artifact.kind.value)
            return ExportResult(
                artifact_kind=artifact.kind,
                status=ExportStatus.SKIPPED_UNCHANGED,
                drive_file_id=entry.drive_file_id if entry else None,
            )

        folder_id = await self.ensure_meeting_folder(meeting)
        filename = self._filename_for(meeting, artifact)
        entry = manifest.entry_for(artifact.kind)

        # Prefer the recorded id; fall back to a name lookup before creating, so a
        # lost manifest updates the existing file instead of duplicating it.
        file_id = entry.drive_file_id if entry else None
        if file_id is None:
            found = await self.client.find(name=filename, parent=folder_id)
            file_id = found.id if found else None

        try:
            new_id, live_session = await self.client.upload(
                name=filename,
                content=artifact.content,
                parent=folder_id,
                mime_type=MIME_TYPES.get(artifact.kind, "application/octet-stream"),
                app_properties={
                    APP_TAG: "artifact",
                    "meetingId": meeting.id,
                    "artifactKind": artifact.kind.value,
                },
                file_id=file_id,
                resumable_session=entry.resumable_session_uri if entry else None,
            )
        except ResumableInterrupted as exc:
            # Persist the session so the next run resumes rather than restarts. This
            # is the difference between a stalled 400 MB upload costing seconds and
            # costing the whole transfer again.
            manifest.upsert(
                ManifestEntry(
                    artifact_kind=artifact.kind,
                    filename=filename,
                    drive_file_id=file_id,
                    content_hash=None,
                    exported_at=datetime.now(UTC),
                    status=ExportStatus.FAILED,
                    reason=str(exc),
                    resumable_session_uri=exc.session_uri,
                )
            )
            log.warning("drive.upload_interrupted", kind=artifact.kind.value, offset=exc.offset)
            return ExportResult(
                artifact_kind=artifact.kind, status=ExportStatus.FAILED, reason=str(exc)
            )
        except DriveError as exc:
            manifest.upsert(
                ManifestEntry(
                    artifact_kind=artifact.kind,
                    filename=filename,
                    drive_file_id=file_id,
                    content_hash=None,
                    exported_at=datetime.now(UTC),
                    status=ExportStatus.FAILED,
                    reason=str(exc),
                )
            )
            log.warning("drive.upload_failed", kind=artifact.kind.value, error=str(exc))
            return ExportResult(
                artifact_kind=artifact.kind, status=ExportStatus.FAILED, reason=str(exc)
            )

        manifest.upsert(
            ManifestEntry(
                artifact_kind=artifact.kind,
                filename=filename,
                drive_file_id=new_id,
                content_hash=artifact.content_hash,
                size_bytes=len(artifact.content),
                exported_at=datetime.now(UTC),
                status=ExportStatus.OK,
                resumable_session_uri=None,  # cleared: the upload finished
            )
        )
        log.info("drive.uploaded", meeting_id=meeting.id, kind=artifact.kind.value)
        return ExportResult(
            artifact_kind=artifact.kind, status=ExportStatus.OK, drive_file_id=new_id
        )

    async def export_all(self, meeting: Meeting, artifacts: list[Artifact]) -> ExportManifest:
        manifest = await self.read_manifest(meeting.id) or ExportManifest(
            meeting_id=meeting.id, folder_name=meeting.folder_name
        )

        results = []
        for artifact in artifacts:
            # One artifact failing must not abandon the rest — a failed deck upload
            # should never cost the transcript.
            results.append(await self._export_one(meeting, artifact, manifest))

        changed = any(r.status is not ExportStatus.SKIPPED_UNCHANGED for r in results)
        renamed = manifest.folder_name != meeting.folder_name

        # Re-exporting an unchanged meeting performs *zero* writes, manifest included.
        # That exact property is the cheapest regression test for the whole
        # idempotency design, so it is worth not spending a write on a timestamp.
        if changed or renamed or not manifest.entries:
            manifest.last_full_sync = datetime.now(UTC)
            manifest.folder_name = meeting.folder_name
            await self._write_manifest(meeting, manifest)

        return manifest

    @staticmethod
    def _filename_for(meeting: Meeting, artifact: Artifact) -> str:
        if artifact.kind is ArtifactKind.AUDIO:
            suffix = Path(meeting.audio.original_filename).suffix or ".m4a"
            return f"audio{suffix}"
        return artifact.filename

    # -- diagnostics -----------------------------------------------------------

    async def check(self) -> dict:
        """Verify credentials and folder access without exporting anything."""
        try:
            about = await self.client.about()
        except NotAuthorized as exc:
            return {"ok": False, "reason": str(exc), "authorized": False}
        except DriveError as exc:
            return {"ok": False, "reason": str(exc), "authorized": True}

        quota = about.get("storageQuota", {})
        return {
            "ok": True,
            "authorized": True,
            "account": about.get("user", {}).get("emailAddress"),
            "root_folder": self.settings.drive_root_folder_name,
            "quota_used": quota.get("usage"),
            "quota_limit": quota.get("limit"),
        }
