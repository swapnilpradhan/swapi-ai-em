import { notFound } from "next/navigation";
import {
  api,
  formatTimestamp,
  type MeetingInsights,
  type TranscriptSpan,
} from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * Renders the evidence behind a claim.
 *
 * Every generated claim carries spans, and the user must be able to check any of them
 * in two seconds. That is what converts "trust the system" into "verify cheaply".
 */
function Evidence({ spans }: { spans: TranscriptSpan[] }) {
  if (spans.length === 0) return null;
  return (
    <details>
      <summary className="meta">
        {spans.length} citation{spans.length === 1 ? "" : "s"}
      </summary>
      {spans.map((span, i) => (
        <blockquote key={i} className="meta">
          “{span.quote}” <span>(segments {span.segment_start}–{span.segment_end})</span>
        </blockquote>
      ))}
    </details>
  );
}

function Insights({ insights }: { insights: MeetingInsights }) {
  const actions = insights.action_items.filter(
    (a) => a.commitment_type !== "hypothetical",
  );

  return (
    <>
      {insights.executive_summary && (
        <section className="card">
          <h3>Summary</h3>
          <p>{insights.executive_summary.value}</p>
          <Evidence spans={insights.executive_summary.spans} />
        </section>
      )}

      <section className="card">
        <h3>Action items</h3>
        {actions.length === 0 ? (
          <p className="meta">No commitments were made in this meeting.</p>
        ) : (
          <ul>
            {actions.map((item) => (
              <li key={item.id}>
                {item.description}{" "}
                <span className="meta">
                  ({item.owner_raw || "unassigned"} · {item.commitment_type} ·{" "}
                  {item.confidence.toFixed(2)})
                </span>
                <Evidence spans={item.spans} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {insights.mind_map && (
        <section className="card">
          <h3>Mind map</h3>
          <pre>{insights.mind_map.rendered_mermaid}</pre>
        </section>
      )}
    </>
  );
}

export default async function MeetingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let meeting;
  try {
    meeting = await api.getMeeting(id);
  } catch {
    notFound();
  }

  // Insights are partial by design — a missing section is a normal state, not an error.
  let insights: MeetingInsights | null = null;
  try {
    insights = await api.getInsights(id);
  } catch {
    insights = null;
  }

  return (
    <main>
      <h2>{meeting.title}</h2>
      <p className="meta">
        {new Date(meeting.occurred_at).toLocaleString()} ·{" "}
        {Math.round(meeting.duration_seconds / 60)} min
      </p>

      {meeting.status.diarization.status === "failed" && (
        <p className="stub-banner">
          Speaker attribution unavailable: {meeting.status.diarization.reason}. The
          transcript and summary below are still complete.
        </p>
      )}

      {insights && <Insights insights={insights} />}

      <section className="card">
        <h3>Transcript</h3>
        {meeting.transcript.segments.map((segment) => (
          <p key={segment.index}>
            <code className="meta">{formatTimestamp(segment.start_ms)}</code>{" "}
            {segment.speaker_label && <strong>{segment.speaker_label}: </strong>}
            {segment.text}
          </p>
        ))}
      </section>
    </main>
  );
}
