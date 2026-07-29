"""API surface, end to end on stubs.

The whole pipeline runs here with zero credentials — that is the property
ADR-0005 exists to guarantee.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

TRANSCRIPT = """\
[00:00:00] Let's talk about the migration timeline.
[00:00:15] I'll run the capacity analysis and have numbers by Friday.
[00:00:40] Someone should probably look at the retention policy.
"""


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def ingested(client):
    response = client.post(
        "/api/v1/meetings",
        json={
            "title": "Platform Review",
            "occurred_at": "2026-07-29T10:00:00Z",
            "duration_seconds": 1800,
            "raw_transcript": TRANSCRIPT,
            "audio_base64": base64.b64encode(b"audio-bytes").decode(),
            "snr_db": 20.0,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestHealth:
    def test_health_reports_stub_backends(self, client):
        """Stub output that looks real is a trap, so the API always says."""
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert "storage" in body["stub_backends"]
        assert "synthetic output from" in body["note"]


class TestIngest:
    def test_ingest_runs_the_full_pipeline(self, ingested):
        meeting = ingested["meeting"]
        status = meeting["status"]

        assert status["ingest"]["status"] == "ok"
        assert status["export"]["status"] == "ok"
        assert status["enrichment"]["status"] == "ok"
        assert status["indexing"]["status"] == "ok"

    def test_ingest_extracts_a_firm_commitment(self, ingested):
        actions = ingested["insights"]["action_items"]
        assert any("capacity analysis" in a["description"] for a in actions)

    def test_hypotheticals_are_not_extracted(self, ingested):
        """'Someone should probably...' must not become a task."""
        actions = ingested["insights"]["action_items"]
        assert not any("retention policy" in a["description"] for a in actions)

    def test_every_action_carries_spans(self, ingested):
        for action in ingested["insights"]["action_items"]:
            assert action["spans"], action

    def test_reingesting_the_same_audio_reuses_the_id(self, client, ingested):
        response = client.post(
            "/api/v1/meetings",
            json={
                "title": "Different Title",
                "occurred_at": "2026-08-01T10:00:00Z",
                "duration_seconds": 60,
                "raw_transcript": TRANSCRIPT,
                "audio_base64": base64.b64encode(b"audio-bytes").decode(),
            },
        )
        assert response.json()["meeting"]["id"] == ingested["meeting"]["id"]

    def test_invalid_audio_is_rejected(self, client):
        response = client.post(
            "/api/v1/meetings",
            json={
                "title": "Bad",
                "occurred_at": "2026-07-29T10:00:00Z",
                "duration_seconds": 60,
                "raw_transcript": "[00:00:00] hi",
                "audio_base64": "!!!not-base64!!!",
            },
        )
        assert response.status_code == 422


class TestMeetings:
    def test_get_meeting(self, client, ingested):
        meeting_id = ingested["meeting"]["id"]
        assert client.get(f"/api/v1/meetings/{meeting_id}").status_code == 200

    def test_missing_meeting_is_404(self, client):
        assert client.get("/api/v1/meetings/nope").status_code == 404

    def test_artifacts_follow_the_folder_contract(self, client, ingested):
        meeting_id = ingested["meeting"]["id"]
        body = client.get(f"/api/v1/meetings/{meeting_id}/artifacts").json()

        names = {a["filename"] for a in body["artifacts"]}
        assert {"transcript.md", "summary.md", "action-items.md", "mind-map.md"} <= names
        assert body["folder_name"].startswith("2026-07-29 — ")


class TestSpeakers:
    def test_enrolling_a_voiceprint_without_consent_is_rejected(self, client):
        """The consent gate is enforced, not documented."""
        response = client.post(
            "/api/v1/speakers",
            json={
                "display_name": "Priya",
                "consent_scope": "recording_only",
                "embeddings": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            },
        )
        assert response.status_code == 422
        assert "consent scope" in response.text

    def test_enrolling_with_voiceprint_consent_succeeds(self, client):
        response = client.post(
            "/api/v1/speakers",
            json={
                "display_name": "Priya",
                "consent_scope": "recording_and_voiceprint",
                "embeddings": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            },
        )
        assert response.status_code == 201
        assert response.json()["voiceprint"]["embeddings"]

    def test_speaker_without_voiceprint_needs_only_recording_consent(self, client):
        response = client.post(
            "/api/v1/speakers",
            json={"display_name": "Marcus", "consent_scope": "recording_only"},
        )
        assert response.status_code == 201
        assert response.json()["voiceprint"] is None

    def test_revocation_removes_the_voiceprint(self, client):
        speaker = client.post(
            "/api/v1/speakers",
            json={
                "display_name": "Priya",
                "consent_scope": "recording_and_voiceprint",
                "embeddings": [[0.1, 0.2]],
            },
        ).json()

        revoked = client.delete(f"/api/v1/speakers/{speaker['id']}/consent").json()
        assert revoked["voiceprint"] is None
        assert revoked["consent"]["revoked_at"]

    def test_manual_tagging_marks_segments_authoritative(self, client, ingested):
        speaker = client.post(
            "/api/v1/speakers",
            json={"display_name": "Priya", "consent_scope": "recording_only"},
        ).json()
        meeting_id = ingested["meeting"]["id"]

        response = client.post(
            "/api/v1/speakers/tag",
            json={
                "meeting_id": meeting_id,
                "segment_indices": [0, 1],
                "speaker_id": speaker["id"],
            },
        )
        assert response.status_code == 200

        segments = client.get(f"/api/v1/meetings/{meeting_id}").json()["transcript"]["segments"]
        assert segments[0]["speaker_source"] == "manual"
        assert segments[0]["speaker_id"] == speaker["id"]

    def test_tagging_an_unknown_speaker_is_404(self, client, ingested):
        response = client.post(
            "/api/v1/speakers/tag",
            json={
                "meeting_id": ingested["meeting"]["id"],
                "segment_indices": [0],
                "speaker_id": "nonexistent",
            },
        )
        assert response.status_code == 404


class TestDrive:
    def test_status_reports_narrow_scope(self, client):
        body = client.get("/api/v1/drive/status").json()
        assert body["scope"].endswith("/auth/drive.file")
        assert body["configured"] is False

    def test_export_then_read_manifest(self, client, ingested):
        meeting_id = ingested["meeting"]["id"]

        manifest = client.post("/api/v1/drive/export", json={"meeting_id": meeting_id}).json()
        assert manifest["meeting_id"] == meeting_id
        assert manifest["entries"]

        recovered = client.get(f"/api/v1/drive/manifest/{meeting_id}").json()
        assert recovered["meeting_id"] == meeting_id

    def test_oauth_start_without_client_config_is_rejected(self, client):
        """No OAuth client configured, so there is nothing to redirect to."""
        response = client.get("/api/v1/drive/oauth/start", follow_redirects=False)
        assert response.status_code == 400
        assert "GOOGLE_CLIENT_ID" in response.json()["detail"]

    def test_oauth_callback_without_code_reports_the_problem(self, client):
        response = client.get("/api/v1/drive/oauth/callback")
        assert response.status_code == 400
        assert "authorization code" in response.text

    def test_oauth_callback_surfaces_a_declined_consent(self, client):
        response = client.get("/api/v1/drive/oauth/callback?error=access_denied")
        assert response.status_code == 400
        assert "access_denied" in response.text

    def test_status_reports_unauthorized_when_no_token_exists(self, client):
        body = client.get("/api/v1/drive/status").json()
        assert body["authorized"] is False
        assert "check" not in body  # nothing to round-trip to Drive about


class TestChat:
    def test_answers_with_citations(self, client, ingested):
        body = client.post(
            "/api/v1/chat/ask", json={"question": "migration timeline", "scope": "corpus"}
        ).json()

        assert body["status"] == "answered"
        assert body["citations"]

    def test_refuses_outside_the_corpus(self, client, ingested):
        body = client.post(
            "/api/v1/chat/ask",
            json={"question": "photosynthesis chlorophyll reaction", "scope": "corpus"},
        ).json()

        assert body["status"] == "not_in_corpus"
        assert not body["citations"]


class TestSlides:
    def test_structure_is_returned_before_rendering(self, client, ingested):
        body = client.post(
            "/api/v1/slides/structure",
            json={"meeting_id": ingested["meeting"]["id"], "style": "mckinsey"},
        ).json()

        assert body["outline_markdown"]
        assert body["title_thread"]
        assert "ready_to_render" in body

    def test_render_refuses_a_broken_structure(self, client, ingested):
        structure = client.post(
            "/api/v1/slides/structure", json={"meeting_id": ingested["meeting"]["id"]}
        ).json()["structure"]

        # One argument fails the MECE count check.
        structure["arguments"] = structure["arguments"][:1]

        response = client.post(
            "/api/v1/slides/render", json={"structure": structure, "force": False}
        )
        assert response.status_code == 422
        assert response.json()["detail"]["violations"]

    def test_render_can_be_forced(self, client, ingested):
        structure = client.post(
            "/api/v1/slides/structure", json={"meeting_id": ingested["meeting"]["id"]}
        ).json()["structure"]
        structure["arguments"] = structure["arguments"][:1]

        response = client.post(
            "/api/v1/slides/render", json={"structure": structure, "force": True}
        )
        assert response.status_code == 200
        assert response.json()["forced"] is True

    def test_missing_meeting_is_404(self, client):
        assert (
            client.post("/api/v1/slides/structure", json={"meeting_id": "nope"}).status_code == 404
        )


class TestCoach:
    def test_rubrics_are_published(self, client):
        body = client.get("/api/v1/coach/rubrics").json()

        assert set(body) == {
            "written",
            "spoken",
            "thought_leadership",
            "thought_development",
        }
        assert "hedging_under_pressure" in body["spoken"]

    def test_dimensions_without_evidence_are_unscored(self, client):
        """Inventing a score to complete the table destroys every other score."""
        body = client.get("/api/v1/coach/assess/spoken").json()

        assert body["scores"]
        assert all(s["score"] is None for s in body["scores"].values())
        assert all("no corpus evidence" in s["note"] for s in body["scores"].values())

    def test_empty_digest_is_not_padded(self, client):
        body = client.get("/api/v1/coach/digest").json()
        assert body["strength"] is None
        assert body["growth_edge"] is None


class TestPocketWebhook:
    """The HTTP surface of webhook ingest.

    The default test config has no webhook secret, which is exactly the state that
    must reject rather than accept.
    """

    def test_unsigned_delivery_is_rejected(self, client):
        response = client.post(
            "/api/v1/hooks/pocket",
            json={"event": "recording.completed", "recordingId": "rec_1"},
        )
        assert response.status_code == 401

    def test_status_reports_unconfigured(self, client):
        body = client.get("/api/v1/hooks/pocket/status").json()
        assert body["configured"] is False
        assert "recording.completed" in body["known_events"]
        assert "unverified" in body["note"]


class TestPocketSync:
    def test_status_reports_stub_backend(self, client):
        body = client.get("/api/v1/pocket/status").json()
        assert body["backend"] == "stub"
        assert body["configured"] is False

    def test_pull_runs_the_ingest_path(self, client):
        body = client.post("/api/v1/pocket/pull", json={"recording_id": "rec_abc"}).json()

        assert body["outcome"] == "processed"
        assert body["meeting_id"]

    def test_pull_is_idempotent(self, client):
        """Webhook delivery is at-least-once; a repeat must not duplicate."""
        first = client.post("/api/v1/pocket/pull", json={"recording_id": "rec_dup"}).json()
        second = client.post("/api/v1/pocket/pull", json={"recording_id": "rec_dup"}).json()

        assert second["outcome"] == "already_current"
        assert second["meeting_id"] == first["meeting_id"]

    def test_pulled_meeting_skips_diarization(self, client):
        """Stub source supplies speaker labels, so we should not diarize."""
        meeting_id = client.post("/api/v1/pocket/pull", json={"recording_id": "rec_labels"}).json()[
            "meeting_id"
        ]

        status = client.get(f"/api/v1/meetings/{meeting_id}").json()["status"]
        assert status["diarization"]["status"] == "skipped"
        assert status["identification"]["status"] == "ok"

    def test_backfill_runs_synchronously_when_asked(self, client):
        body = client.post(
            "/api/v1/pocket/backfill",
            json={"run_in_background": False, "max_recordings": 5},
        ).json()

        assert body["status"] == "complete"
        assert body["total"] > 0

    def test_health_reports_pocket_stub(self, client):
        assert "pocket" in client.get("/health").json()["stub_backends"]
