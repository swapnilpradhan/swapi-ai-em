"""Export artifacts and the manifest.

The manifest is written to Drive alongside the artifacts, not only to the database.
That is what makes "database loss is recoverable" a real property rather than an
aspiration — see docs/adr/0002-drive-as-system-of-record.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ArtifactKind(str, Enum):
    """Every artifact needs a defined place in the folder contract.

    An artifact with no entry here ends up at the folder root with an invented name,
    and the contract erodes.
    """

    AUDIO = "audio"
    TRANSCRIPT_MD = "transcript_md"
    TRANSCRIPT_JSON = "transcript_json"
    SUMMARY = "summary"
    ACTION_ITEMS = "action_items"
    MIND_MAP = "mind_map"
    DECK = "deck"
    MANIFEST = "manifest"
    README = "readme"


FILENAMES: dict[ArtifactKind, str] = {
    ArtifactKind.AUDIO: "audio",  # extension comes from the source file
    ArtifactKind.TRANSCRIPT_MD: "transcript.md",
    ArtifactKind.TRANSCRIPT_JSON: "transcript.json",
    ArtifactKind.SUMMARY: "summary.md",
    ArtifactKind.ACTION_ITEMS: "action-items.md",
    ArtifactKind.MIND_MAP: "mind-map.md",
    ArtifactKind.DECK: "deck.pptx",
    ArtifactKind.MANIFEST: "manifest.json",
    ArtifactKind.README: "README.md",
}


class ExportStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED_UNCHANGED = "skipped_unchanged"


class Artifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ArtifactKind
    content: bytes
    content_hash: str

    @property
    def filename(self) -> str:
        return FILENAMES[self.kind]


class ManifestEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_kind: ArtifactKind
    filename: str
    drive_file_id: str | None = None
    content_hash: str | None = None
    size_bytes: int = 0
    exported_at: datetime | None = None
    status: ExportStatus = ExportStatus.OK
    reason: str | None = None
    # Persisted before an upload starts, so a killed process resumes rather than restarts.
    resumable_session_uri: str | None = None


class ExportManifest(BaseModel):
    meeting_id: str
    folder_name: str
    drive_folder_id: str | None = None
    entries: list[ManifestEntry] = Field(default_factory=list)
    last_full_sync: datetime | None = None

    def entry_for(self, kind: ArtifactKind) -> ManifestEntry | None:
        return next((e for e in self.entries if e.artifact_kind == kind), None)

    def is_unchanged(self, kind: ArtifactKind, content_hash: str) -> bool:
        """Whether an upload can be skipped entirely.

        A full re-export of an unchanged meeting should perform zero writes; this is
        the cheapest available regression test for the idempotency logic.
        """
        entry = self.entry_for(kind)
        return (
            entry is not None
            and entry.status is not ExportStatus.FAILED
            and entry.content_hash == content_hash
        )

    def upsert(self, entry: ManifestEntry) -> None:
        others = [e for e in self.entries if e.artifact_kind != entry.artifact_kind]
        self.entries = [*others, entry]


class ExportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_kind: ArtifactKind
    status: ExportStatus
    drive_file_id: str | None = None
    reason: str | None = None
