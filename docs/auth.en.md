# Login and Authentication

## Choose an access mode

| Scenario | Authentication and protection | Boundary |
| --- | --- | --- |
| Browser board | Optional username + shared password; ChatLogin session cookie | Writes require same-origin Origin and CSRF |
| API automation | Bearer or `X-ChatBoard-Token` | No browser cookie/CSRF required |
| Real executor operations | Outer authentication plus `X-ChatBoard-Executor-Token` | A normal API key or login session does not grant execution |
| No password or API key | Existing local unauthenticated mode | Do not expose to untrusted networks |
| API key only | Page shell is accessible; protected APIs require the key | Does not implicitly enable password login |

ChatBoard reuses ChatLogin's `CallbackBackend`, `SessionManager`, `SQLiteSessionStore` and `require_csrf`. The username remains optional and the shared password represents one fixed identity. This adds no user database, roles or business ownership rules. Dry-run/mock remain safe execution modes; real execution and control operations retain independent authorization.

## Upgrade from 0.1.x

Signed timestamp cookies are no longer accepted: sign in once after upgrading. Existing accounts, passwords, API keys and configuration paths remain unchanged.

New cookies use `v2.<random core token>.<HMAC-SHA256>`. This is only a transport envelope: `CHATBOARD_AUTH_SECRET` has precedence (environment before ChatEnv), otherwise the login password is used. Every read validates against the current effective key, so rotating that key immediately rejects old cookies without a separate database cleanup. If an independent signing key is configured, changing only the password does not invalidate existing cookies; rotate the signing key instead, preserving the original precedence.

ChatLogin alone owns TTL, persistence, capacity and revocation. Random token digests are stored in `$CHATBOARD_HOME/sessions.sqlite3`; password fingerprints are not used as database namespaces. The runtime root defaults to `~/.chatarch/chatboard/`, with a 1024-session limit. Session operations purge expired records; login returns 503 when capacity is exhausted. TTL defaults to 12 hours with a 60-second minimum. Ordinary restarts preserve sessions unless the effective key changed or a session expired/was revoked.

## Data-safe rollout

1. Record the running version, interpreter, supervisor and resolved `chatbd paths`; confirm no executor task is active. Never infer production paths from defaults.
2. Back up configuration, backend profiles and any existing session store. Keep business cards in the original workspace; do not archive, migrate, initialize or rewrite them during rollout. Use a consistent SQLite backup for an active session database rather than copying only its main file.
3. Validate released wheels and dependencies in isolation, retain the previous wheels/version inventory, then upgrade precisely without changing unrelated services or model environments.
4. Restart through the existing supervisor with unchanged configuration/data roots. Verify version, health, real login/logout, CSRF and the independent executor gate.
5. Roll back code/dependencies first while retaining current business data. Never overwrite post-release writes with a stale database backup; data recovery requires a separate decision.

## Cookie client protocol

1. Send JSON to `POST /api/login`: `{"password":"<password>"}`. Include `username` when configured; the existing `account` alias is supported. Cross-site Origin is rejected; a non-browser initial JSON login may omit Origin.
2. Read `GET /api/session` with the issued `chatboard_session` cookie. The response uses `Cache-Control: no-store` and includes `authenticated` and `csrf_token` (null without a session).
3. Send the same cookie plus both a same-origin `Origin` and `X-CSRF-Token: <csrf_token>` for POST/PATCH/PUT/DELETE and other writes. Missing or incorrect values return 403; reads need no CSRF. Logging in again with an existing session follows the same rule.
4. `POST /api/logout` follows that write contract, revokes the server session and clears the cookie. Replaying a logged-out or pre-rotation cookie is unauthenticated.

The built-in board and login UI fetch CSRF automatically. `frontendFetch` permits only the current site origin. Remote backend calls use the same-origin `/api/backends/{profile}/api/...` proxy; the browser does not send this site's cookie or CSRF token to a remote backend.

`/api/auth` retains exactly the existing four booleans: `enabled`, `authenticated`, `username_required`, `api_token_enabled`. Valid API-key requests do not require Origin/CSRF; an incorrect API key cannot bypass write protection for a valid cookie. Cookies use HttpOnly, SameSite=Lax and Path=/.

## Configuration and UI

| Setting | Default / choices |
| --- | --- |
| `CHATBOARD_USERNAME` | Optional; the UI hides the username when absent |
| `CHATBOARD_PASSWORD` | Password login disabled when absent |
| `CHATBOARD_AUTH_SECRET` | Optional; defaults to password, signs the cookie envelope |
| `CHATBOARD_SESSION_TTL_SECONDS` | 43200, minimum 60 |
| `CHATBOARD_COOKIE_SECURE` | `1/true/yes/on` enables HTTPS cookies |
| `CHATBOARD_LOGIN_PALETTE` | `indigo`, `forest`, `amber`; default indigo |
| `CHATBOARD_LOGIN_LAYOUT` | `card` or `split`; default card |
| `CHATBOARD_LOGIN_APPEARANCE` | `system`, `light`, `dark`; default system |

Shared LoginUI owns layout, theme and interaction. ChatBoard uses Jinja inheritance only for its form and resource links. Integrations may set `app.state.login_ui = LoginUI(...)` to override rendering configuration. `/auth-assets/` allows only the packaged `login.css` and `login.js`, not templates or arbitrary files.

HTTPS reverse proxies should enable Secure cookies, validate entry hosts and rate-limit logins. The trusted server-side `CHATBOARD_SERVICE_URL` origin is accepted alongside the direct request origin, supporting public/local Host rewrites. Client Forwarded/X-Forwarded-* headers cannot add allowed origins. This gate is for small shared workspaces, not an SSO/MFA replacement.

## Verification

`python -m pytest -q` includes username/password modes, key rotation, session expiry/replay, CSRF, API/executor boundaries, shared templates/assets, frontend fetch and a real TCP login smoke. The TCP test uses a random loopback port and synthetic data, stops uvicorn on exit, and launches no model or real executor. Node.js 22+ (or `NODE_BINARY`) runs the frontend runtime test; CI installs Node.js and requires that gate.
