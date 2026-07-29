"""Google OAuth 2.0 for Drive access.

Implemented directly against Google's OAuth endpoints rather than through
``google-auth-oauthlib``. The flow is small, the endpoints are stable and well
documented, and doing it here keeps the whole service layer async instead of
bolting a synchronous client onto a thread pool.

Scope is ``drive.file`` — files this app created, nothing else. See
docs/capabilities/01-drive-export.md.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel

from ..core.config import Settings
from ..core.logging import get_logger

log = get_logger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# Files this app created — never full `drive`. The app has no business reading the
# user's other documents, and the reduced blast radius is worth the constraint.
SCOPE = "https://www.googleapis.com/auth/drive.file"

# Refresh slightly early; a token that expires mid-upload costs a retry.
EXPIRY_SKEW = timedelta(seconds=90)

# Pending authorizations are short-lived by design — a stale one is an abandoned
# browser tab, not something to keep around.
STATE_TTL_SECONDS = 600


class NotAuthorized(RuntimeError):
    """No usable credentials. The user needs to run the consent flow."""


class OAuthError(RuntimeError):
    """Google rejected the request. Carries Google's own error text."""


class Credentials(BaseModel):
    """Stored OAuth credentials.

    ``refresh_token`` is the durable secret — Google issues it once, and only when
    asked correctly (``access_type=offline`` with ``prompt=consent``). Losing it means
    the user has to re-consent, so a refresh response that omits it must never
    overwrite the stored one.
    """

    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str = SCOPE
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at - EXPIRY_SKEW


class TokenStore:
    """Credentials on disk, ``0600``, outside the repository tree.

    Deliberately not in the project directory: a refresh token committed to git or
    swept into a backup is a durable grant over the user's Drive.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Credentials | None:
        if not self.path.exists():
            return None
        try:
            return Credentials.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("google_auth.token_unreadable", error=str(exc))
            return None

    def save(self, credentials: Credentials) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)

        # Write to a private temp file and rename, so a crash mid-write cannot leave
        # a truncated token file behind — and so the secret is never briefly
        # world-readable between create and chmod.
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(credentials.model_dump_json())
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


@dataclass
class PendingAuth:
    code_verifier: str
    created_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > STATE_TTL_SECONDS


def _pkce_pair() -> tuple[str, str]:
    """A PKCE verifier and its S256 challenge.

    PKCE binds the authorization code to this specific request, so a code
    intercepted from the redirect (browser history, a shared machine, a logged URL)
    cannot be redeemed without the verifier that never left this process.
    """
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


class GoogleOAuthFlow:
    """Drives the consent flow and keeps credentials fresh."""

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.store = TokenStore(settings.google_token_path)
        self._transport = transport  # tests inject a MockTransport
        self._pending: dict[str, PendingAuth] = {}

    # -- consent ---------------------------------------------------------------

    def authorization_url(self) -> tuple[str, str]:
        """Build the consent URL. Returns ``(url, state)``.

        ``access_type=offline`` plus ``prompt=consent`` is what makes Google issue a
        refresh token. Without both, re-authorizing an already-consented account
        returns an access token only, and unattended export stops working an hour later.
        """
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise NotAuthorized("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set")

        self._evict_expired()
        state = secrets.token_urlsafe(32)
        verifier, challenge = _pkce_pair()
        self._pending[state] = PendingAuth(code_verifier=verifier, created_at=time.time())

        params = httpx.QueryParams(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self.settings.google_oauth_redirect_uri,
                "response_type": "code",
                "scope": SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{AUTH_URL}?{params}", state

    def _evict_expired(self) -> None:
        for key in [s for s, p in self._pending.items() if p.is_expired]:
            del self._pending[key]

    async def exchange_code(self, code: str, state: str) -> Credentials:
        """Redeem an authorization code.

        The ``state`` lookup is the CSRF check: without it an attacker can hand the
        user a callback URL carrying *their* authorization code, silently pointing
        the user's exports at an attacker-controlled Drive.
        """
        self._evict_expired()
        pending = self._pending.pop(state, None)
        if pending is None:
            raise OAuthError("unknown or expired state — restart authorization")

        payload = await self._token_request(
            {
                "code": code,
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "redirect_uri": self.settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": pending.code_verifier,
            }
        )

        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            # Almost always a previously-consented account without prompt=consent.
            raise OAuthError(
                "Google returned no refresh token. Revoke this app's access at "
                "https://myaccount.google.com/permissions and authorize again."
            )

        credentials = Credentials(
            access_token=payload["access_token"],
            refresh_token=refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=int(payload.get("expires_in", 3600))),
            scope=payload.get("scope", SCOPE),
        )
        self.store.save(credentials)
        log.info("google_auth.authorized", scope=credentials.scope)
        return credentials

    # -- tokens ----------------------------------------------------------------

    async def _token_request(self, data: dict[str, str]) -> dict:
        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
            response = await client.post(TOKEN_URL, data=data)

        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("error_description") or body.get("error") or response.text
            except ValueError:
                detail = response.text
            raise OAuthError(f"token endpoint returned {response.status_code}: {detail}")
        return response.json()

    async def refresh(self, credentials: Credentials) -> Credentials:
        payload = await self._token_request(
            {
                "refresh_token": credentials.refresh_token,
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "grant_type": "refresh_token",
            }
        )

        refreshed = credentials.model_copy(
            update={
                "access_token": payload["access_token"],
                "expires_at": datetime.now(UTC)
                + timedelta(seconds=int(payload.get("expires_in", 3600))),
                # A refresh response normally omits refresh_token. Taking .get() here
                # without the fallback would wipe the durable grant.
                "refresh_token": payload.get("refresh_token") or credentials.refresh_token,
            }
        )
        self.store.save(refreshed)
        log.debug("google_auth.refreshed")
        return refreshed

    async def valid_credentials(self) -> Credentials:
        """Current credentials, refreshed if needed."""
        credentials = self.store.load()
        if credentials is None:
            raise NotAuthorized("no stored Google credentials — visit /api/v1/drive/oauth/start")
        if credentials.is_expired:
            credentials = await self.refresh(credentials)
        return credentials

    async def access_token(self) -> str:
        return (await self.valid_credentials()).access_token

    @property
    def is_authorized(self) -> bool:
        return self.store.load() is not None

    async def revoke(self) -> None:
        """Revoke the grant at Google, then drop the local copy.

        Order matters: clearing locally first would leave a live grant nobody can
        see, let alone revoke.
        """
        credentials = self.store.load()
        if credentials is None:
            return
        try:
            async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
                await client.post(REVOKE_URL, data={"token": credentials.refresh_token})
        except httpx.HTTPError as exc:
            log.warning("google_auth.revoke_failed", error=str(exc))
        finally:
            self.store.clear()
            log.info("google_auth.revoked")
