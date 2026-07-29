"use client";

import { useState } from "react";
import { api, type CitedAnswer } from "@/lib/api";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<CitedAnswer | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;

    setPending(true);
    setError(null);
    try {
      setAnswer(await api.ask(question, "corpus"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(false);
    }
  }

  return (
    <main>
      <h2>Ask your meetings</h2>
      <p className="meta">
        Answers come only from your transcripts. If the corpus does not support an
        answer, you get a refusal rather than a guess.
      </p>

      <form onSubmit={ask} style={{ display: "flex", gap: "0.5rem", margin: "1rem 0" }}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What did we decide about the migration?"
          style={{ flex: 1, padding: "0.6rem", borderRadius: 8, border: "1px solid var(--line)" }}
        />
        <button type="submit" disabled={pending} style={{ padding: "0.6rem 1rem" }}>
          {pending ? "Searching…" : "Ask"}
        </button>
      </form>

      {error && <p className="empty">{error}</p>}

      {answer && (
        <section className="card">
          {/* A refusal is a legitimate, useful result — present it as such. */}
          {answer.status !== "answered" && (
            <p className="meta">
              <strong>
                {answer.status === "not_in_corpus"
                  ? "Not found in your meetings"
                  : "Filters too narrow"}
              </strong>
            </p>
          )}
          <p>{answer.answer}</p>

          {answer.citations.length > 0 && (
            <>
              <h3>Sources</h3>
              {answer.citations.map((citation, i) => (
                <blockquote key={i} className="meta">
                  <strong>{citation.meeting_title}</strong> (
                  {new Date(citation.occurred_at).toLocaleDateString()}) — “
                  {citation.span.quote}”
                </blockquote>
              ))}
            </>
          )}
        </section>
      )}
    </main>
  );
}
