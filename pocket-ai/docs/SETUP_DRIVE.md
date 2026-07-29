# Connecting Google Drive

Fifteen minutes, once. After this, exports run unattended.

## 1. Create an OAuth client

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a
   project (or pick an existing one).
2. **APIs & Services → Library →** enable the **Google Drive API**.
3. **APIs & Services → OAuth consent screen:**
   - User type **External** is fine for a personal Google account; **Internal** if you
     are on Workspace and only you will use it.
   - Add the scope `https://www.googleapis.com/auth/drive.file`. Do **not** add
     `.../auth/drive` — this app never needs to read your other files, and the narrower
     scope is the difference between "can touch its own folder" and "can read everything
     in your Drive".
   - Add your own address under **Test users**. While the app is in Testing you do not
     need Google verification, but refresh tokens expire after 7 days — see
     [Troubleshooting](#troubleshooting).
4. **APIs & Services → Credentials → Create credentials → OAuth client ID:**
   - Application type: **Web application**
   - Authorized redirect URI: `http://localhost:8000/api/v1/drive/oauth/callback`

   This must match `GOOGLE_OAUTH_REDIRECT_URI` **byte for byte**, trailing slash
   included. A mismatch here is the single most common failure.

## 2. Configure

```bash
# .env
GOOGLE_CLIENT_ID=<from Cloud Console>
GOOGLE_CLIENT_SECRET=<from Cloud Console>
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/drive/oauth/callback
DRIVE_ROOT_FOLDER_NAME=Pocket.ai Studio
GOOGLE_TOKEN_PATH=~/.pocket-ai/google_token.json
```

Setting a client id and secret is what flips storage from the stub to real Drive —
`GET /api/v1/drive/status` will show `"backend": "real"`.

## 3. Authorize

```bash
make dev
open http://localhost:8000/api/v1/drive/oauth/start
```

Grant access, and you should land on a "Connected to Google Drive" page. Confirm:

```bash
curl -s localhost:8000/api/v1/drive/status | jq
```

```json
{
  "backend": "real",
  "scope": "https://www.googleapis.com/auth/drive.file",
  "authorized": true,
  "check": { "ok": true, "account": "you@example.com" }
}
```

## 4. Export

```bash
curl -X POST localhost:8000/api/v1/drive/export \
  -H 'Content-Type: application/json' \
  -d '{"meeting_id":"<id>"}'
```

Run it twice. The second run should upload nothing — that is the idempotency guarantee
working, and it is worth confirming once with your own eyes.

## What lands in Drive

```
Pocket.ai Studio/
└── 2026/
    └── 2026-07-29 — Platform Architecture Review/
        ├── audio.m4a
        ├── transcript.md
        ├── transcript.json
        ├── summary.md
        ├── action-items.md
        ├── mind-map.md
        ├── manifest.json
        └── README.md      ← privacy notice
```

Every file opens without this app. That is deliberate — see
[ADR-0002](adr/0002-drive-as-system-of-record.md).

## Security notes

- **Scope is `drive.file`.** The app can only see files it created. Your other documents
  are invisible to it, by construction rather than by policy.
- **The refresh token is a durable grant.** It lives at `GOOGLE_TOKEN_PATH` with mode
  `0600` in a `0700` directory, outside the repository tree so it cannot be committed or
  swept into a project backup.
- **Files are created private.** The app never sets link-sharing. If you want to share a
  summary, share it yourself through Drive's UI, where the consequences are visible.
- **Revoke any time:** `POST /api/v1/drive/oauth/revoke`, or from
  [Google Account permissions](https://myaccount.google.com/permissions).

## Troubleshooting

**`redirect_uri_mismatch`** — the Cloud Console URI and `GOOGLE_OAUTH_REDIRECT_URI`
differ. Check for a trailing slash, `http` vs `https`, and `localhost` vs `127.0.0.1`.

**"Google returned no refresh token"** — the account previously consented, so Google
skipped the consent screen and issued only an access token. Remove the app at
[myaccount.google.com/permissions](https://myaccount.google.com/permissions) and
authorize again. (The app already sends `prompt=consent`, which normally prevents this.)

**Authorization works, then breaks after a week** — an OAuth consent screen in **Testing**
issues refresh tokens that expire after 7 days. Publish the app (**OAuth consent screen →
Publish**). For a `drive.file`-only scope, Google does not require verification for
personal use.

**`invalid_grant` on refresh** — the token was revoked, expired, or the client secret
changed. Re-authorize.

**403 with `insufficientFilePermissions`** — you are trying to touch a file this app did
not create. Under `drive.file` that is expected and correct; it fails fast rather than
retrying.

**Uploads stall on large audio** — resumable sessions persist in `manifest.json`. Re-run
the export; it resumes from the last confirmed byte rather than restarting.

## Verification status

The implementation is complete and covered by 243 offline tests, including the full
client path against an in-memory Drive. It has **not yet been run against a real Google
account** — that needs a Cloud Console client, which only you can create. The checklist
in [`capabilities/01-drive-export.md`](capabilities/01-drive-export.md) tracks it.
