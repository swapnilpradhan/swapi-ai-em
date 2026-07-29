"""OAuth flow: PKCE, CSRF state, token persistence, refresh semantics.

The negative cases are the point. A missing state check or a clobbered refresh token
are both silent failures that only surface much later.
"""

from __future__ import annotations

import os
import stat
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.services.google_auth import (
    SCOPE,
    Credentials,
    GoogleOAuthFlow,
    NotAuthorized,
    OAuthError,
    TokenStore,
)
from tests.fake_drive import FakeDrive


@pytest.fixture
def oauth_settings(tmp_path) -> Settings:
    return Settings(
        media_root=tmp_path / "media",
        google_client_id="client-id.apps.googleusercontent.com",
        google_client_secret="client-secret",
        google_oauth_redirect_uri="http://localhost:8000/api/v1/drive/oauth/callback",
        google_token_path=tmp_path / "creds" / "google_token.json",
        app_env="test",
    )


@pytest.fixture
def drive() -> FakeDrive:
    return FakeDrive()


@pytest.fixture
def flow(oauth_settings, drive) -> GoogleOAuthFlow:
    return GoogleOAuthFlow(oauth_settings, transport=drive.transport)


class TestAuthorizationUrl:
    def test_includes_everything_google_needs(self, flow):
        url, state = flow.authorization_url()
        params = httpx.URL(url).params

        assert params["scope"] == SCOPE
        assert params["response_type"] == "code"
        assert params["state"] == state
        assert params["code_challenge_method"] == "S256"
        assert params["code_challenge"]

    def test_requests_offline_access_with_consent(self, flow):
        """Both are required, or Google returns no refresh token for a known account."""
        params = httpx.URL(flow.authorization_url()[0]).params

        assert params["access_type"] == "offline"
        assert params["prompt"] == "consent"

    def test_scope_is_drive_file_not_full_drive(self, flow):
        assert httpx.URL(flow.authorization_url()[0]).params["scope"].endswith("/drive.file")

    def test_each_call_gets_a_fresh_state_and_verifier(self, flow):
        first_url, first_state = flow.authorization_url()
        second_url, second_state = flow.authorization_url()

        assert first_state != second_state
        assert (
            httpx.URL(first_url).params["code_challenge"]
            != httpx.URL(second_url).params["code_challenge"]
        )

    def test_missing_client_config_is_rejected(self, tmp_path, drive):
        bare = Settings(media_root=tmp_path, google_token_path=tmp_path / "t.json")
        with pytest.raises(NotAuthorized, match="GOOGLE_CLIENT_ID"):
            GoogleOAuthFlow(bare, transport=drive.transport).authorization_url()


class TestCodeExchange:
    async def test_valid_exchange_stores_credentials(self, flow):
        _, state = flow.authorization_url()
        credentials = await flow.exchange_code("auth-code", state)

        assert credentials.refresh_token == "refresh-1"
        assert flow.is_authorized

    async def test_unknown_state_is_rejected(self, flow):
        """The CSRF check: an attacker-supplied callback must not be redeemable."""
        flow.authorization_url()
        with pytest.raises(OAuthError, match="unknown or expired state"):
            await flow.exchange_code("auth-code", "state-we-never-issued")

    async def test_state_cannot_be_replayed(self, flow):
        _, state = flow.authorization_url()
        await flow.exchange_code("auth-code", state)

        with pytest.raises(OAuthError, match="unknown or expired state"):
            await flow.exchange_code("auth-code", state)

    async def test_response_without_refresh_token_is_an_error(self, flow, drive):
        """Silently accepting this yields exports that die an hour later."""
        _, state = flow.authorization_url()
        drive.failures.append((200, {"access_token": "a", "expires_in": 3600}))

        with pytest.raises(OAuthError, match="no refresh token"):
            await flow.exchange_code("auth-code", state)

    async def test_google_error_is_surfaced(self, flow, drive):
        _, state = flow.authorization_url()
        drive.failures.append((400, {"error_description": "invalid_grant: code expired"}))

        with pytest.raises(OAuthError, match="code expired"):
            await flow.exchange_code("auth-code", state)


class TestTokenStore:
    def test_token_file_is_owner_only(self, oauth_settings):
        """A world-readable refresh token is a durable grant over the user's Drive."""
        store = TokenStore(oauth_settings.google_token_path)
        store.save(
            Credentials(
                access_token="a",
                refresh_token="r",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )

        mode = stat.S_IMODE(os.stat(store.path).st_mode)
        assert mode == 0o600
        assert stat.S_IMODE(os.stat(store.path.parent).st_mode) == 0o700

    def test_round_trip(self, oauth_settings):
        store = TokenStore(oauth_settings.google_token_path)
        expiry = datetime.now(UTC) + timedelta(hours=1)
        store.save(Credentials(access_token="a", refresh_token="r", expires_at=expiry))

        loaded = store.load()
        assert loaded.refresh_token == "r"

    def test_no_temp_file_is_left_behind(self, oauth_settings):
        store = TokenStore(oauth_settings.google_token_path)
        store.save(
            Credentials(
                access_token="a",
                refresh_token="r",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        assert not store.path.with_suffix(".tmp").exists()

    def test_corrupt_file_reads_as_absent(self, oauth_settings):
        store = TokenStore(oauth_settings.google_token_path)
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text("not json")

        assert store.load() is None

    def test_clear_removes_the_file(self, oauth_settings):
        store = TokenStore(oauth_settings.google_token_path)
        store.save(
            Credentials(
                access_token="a",
                refresh_token="r",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        store.clear()
        assert store.load() is None


class TestRefresh:
    async def test_refresh_preserves_the_refresh_token(self, flow, drive):
        """Google omits refresh_token on refresh; taking it blindly wipes the grant."""
        _, state = flow.authorization_url()
        original = await flow.exchange_code("auth-code", state)

        refreshed = await flow.refresh(original)

        assert refreshed.refresh_token == original.refresh_token
        assert refreshed.access_token != original.access_token
        assert flow.store.load().refresh_token == "refresh-1"

    async def test_expired_credentials_refresh_automatically(self, flow, drive):
        _, state = flow.authorization_url()
        credentials = await flow.exchange_code("auth-code", state)
        flow.store.save(
            credentials.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(minutes=5)})
        )

        await flow.valid_credentials()
        assert drive.token_refreshes == 1

    async def test_fresh_credentials_are_not_refreshed(self, flow, drive):
        _, state = flow.authorization_url()
        await flow.exchange_code("auth-code", state)

        await flow.valid_credentials()
        assert drive.token_refreshes == 0

    async def test_near_expiry_refreshes_early(self, flow, drive):
        """A token expiring mid-upload costs a retry; refresh before it lapses."""
        _, state = flow.authorization_url()
        credentials = await flow.exchange_code("auth-code", state)
        flow.store.save(
            credentials.model_copy(update={"expires_at": datetime.now(UTC) + timedelta(seconds=30)})
        )

        await flow.valid_credentials()
        assert drive.token_refreshes == 1

    async def test_no_credentials_raises_not_authorized(self, flow):
        with pytest.raises(NotAuthorized, match="oauth/start"):
            await flow.valid_credentials()


class TestRevoke:
    async def test_revoke_clears_local_credentials(self, flow):
        _, state = flow.authorization_url()
        await flow.exchange_code("auth-code", state)

        await flow.revoke()
        assert not flow.is_authorized

    async def test_revoke_without_credentials_is_a_no_op(self, flow):
        await flow.revoke()
        assert not flow.is_authorized
