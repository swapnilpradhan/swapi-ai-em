import Link from "next/link";
import StubBanner from "@/components/StubBanner";
import { api, type Meeting, type ProcessingStatus } from "@/lib/api";

export const dynamic = "force-dynamic";

const STAGES: (keyof ProcessingStatus)[] = [
  "ingest",
  "export",
  "diarization",
  "identification",
  "enrichment",
  "indexing",
];

function Stages({ status }: { status: ProcessingStatus }) {
  return (
    <div className="stages">
      {STAGES.map((stage) => (
        <span key={stage} className="pill" data-status={status[stage].status}>
          {stage}
        </span>
      ))}
    </div>
  );
}

export default async function MeetingsPage() {
  let meetings: Meeting[] = [];
  let error: string | null = null;

  try {
    meetings = await api.listMeetings();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main>
      <StubBanner />

      {error && <p className="empty">Could not load meetings: {error}</p>}

      {!error && meetings.length === 0 && (
        <div className="empty">
          <p>No meetings yet.</p>
          <p className="meta">
            POST a recording to <code>/api/v1/meetings</code> to get started.
          </p>
        </div>
      )}

      {meetings.map((meeting) => (
        <article key={meeting.id} className="card">
          <h3>
            <Link href={`/meetings/${meeting.id}`}>{meeting.title}</Link>
          </h3>
          <p className="meta">
            {new Date(meeting.occurred_at).toLocaleDateString()} ·{" "}
            {Math.round(meeting.duration_seconds / 60)} min ·{" "}
            {meeting.transcript.segments.length} segments
          </p>
          <Stages status={meeting.status} />
        </article>
      ))}
    </main>
  );
}
