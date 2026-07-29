import { api } from "@/lib/api";

/**
 * Says plainly when output on screen is synthetic.
 *
 * Stub output that looks real is a trap — the whole stub-first architecture depends
 * on the user never mistaking it for the real thing.
 */
export default async function StubBanner() {
  let stubs: string[] = [];
  try {
    stubs = (await api.health()).stub_backends;
  } catch {
    return (
      <p className="stub-banner">
        Backend unreachable. Start it with <code>make dev</code>.
      </p>
    );
  }

  if (stubs.length === 0) return null;

  return (
    <p className="stub-banner">
      <strong>Synthetic output.</strong> These backends are running on stubs:{" "}
      {stubs.join(", ")}. Configure credentials in <code>.env</code> for real results.
    </p>
  );
}
