import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

const TRACK_LABELS: Record<string, string> = {
  written: "Written English",
  spoken: "Spoken English",
  thought_leadership: "Thought leadership",
  thought_development: "Thought development",
};

export default async function CoachPage() {
  let rubrics: Record<string, string[]> = {};
  let error: string | null = null;

  try {
    rubrics = await api.rubrics();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main>
      <h2>Executive coach</h2>
      <p className="meta">
        Every observation is drawn from your own recordings and cites the moment it came
        from. Dimensions with no supporting evidence are reported unscored rather than
        given an invented number.
      </p>

      {error && <p className="empty">Could not load rubrics: {error}</p>}

      {Object.entries(rubrics).map(([track, dimensions]) => (
        <section key={track} className="card">
          <h3>{TRACK_LABELS[track] ?? track}</h3>
          <div className="stages">
            {dimensions.map((dimension) => (
              <span key={dimension} className="pill">
                {dimension.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </section>
      ))}

      <p className="meta">
        Scoring lands in Phase 4 — see <code>docs/capabilities/08-executive-coach.md</code>.
      </p>
    </main>
  );
}
