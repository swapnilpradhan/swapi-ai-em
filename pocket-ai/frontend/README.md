# Pocket.ai Studio — web

Next.js 15 App Router frontend. Deliberately thin: it renders what the API returns and
adds no business logic of its own.

```bash
npm install
npm run dev     # http://localhost:3000
```

`/api/*` is proxied to the FastAPI backend (`http://localhost:8000` by default, override
with `API_ORIGIN`), so the browser sees a single origin.

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Meeting list with per-stage processing status |
| `/meetings/[id]` | Summary, action items, mind map, transcript — all with citations |
| `/chat` | Ask questions across the corpus |
| `/coach` | Published coaching rubrics |

## Two things this UI must keep doing

**Show the stub banner.** `StubBanner` reads `/health` and says plainly when output is
synthetic. Stub output that looks real is a trap, and the whole stub-first architecture
depends on the user never mistaking one for the other.

**Show citations.** Every generated claim carries `TranscriptSpan`s, and the `Evidence`
component makes them inspectable in two seconds. That is what converts "trust the
system" into "verify cheaply" — a much sturdier foundation. Do not render a `Cited<T>`
value without its spans.
