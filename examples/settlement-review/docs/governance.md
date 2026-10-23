# Governance — who can do what (Settlement Review follow-up demo)

There are four separate parties here, with separate controls. Having one kind of access gives no access of another kind.

| Party | What it is | How it is controlled | Status |
|---|---|---|---|
| **App users** | `viewer.a`, `operator.a`, `operator.b`: public synthetic demo logins | Server-side account table (`app/users.py`), PBKDF2 password check, random server-side sessions (SQLite, token stored hashed), 30-min expiry, HttpOnly + SameSite=Strict cookie, CSRF header on writes, logout deletes the session. Role and tenant are never read from headers or the request body. | **Tested** (pytest, two-process smoke, browser e2e) |
| **Trigger requester** | The GitHub user whose issue comment is meant to start the automation | Configured automation filters (as described by the automation owner): `github:issue_comment`, `action=created`, `comment.user.login=Soham4001A`, comment body starts with `/devin-approved `, issue title starts with `[integration-demo]`, exact repository match. This filter is on the authenticated comment author; it is not a label-based permission. | **UNTESTED.** This run was a **manual invocation** (`_manual: true`, `_event_data: null`), so trigger matching was skipped. Nothing here shows that the filters accept or reject a real comment. The owner says the automation was disabled after this launch to prevent duplicate runs. |
| **Devin runtime** | This automation session (`devin-ac4adcaad5214f4faf89ce3cd08f53aa`) | Configured: mandatory read-only Git security profile, no external MCP, no GitHub CLI credential, restricted network allowlist, no production credentials. Session tags are metadata only; they grant no app or Git permission. | See the observed-vs-configured section below |
| **Human publisher** | Soham, reviewing the downloaded diff/zip | Publishes externally after review. Devin did not push, open a PR or merge. | Outside this session |

## Devin runtime: observed vs configured (2026-10-23 UTC)

What I directly observed (no credentials printed):

1. **Network.** `get_network_allowlist` reported 12 allowed destinations (GitHub hosts, PyPI, npm, Playwright CDN, GCS, the session git proxy). One plain `curl -m 10 https://example.com` (GET, no payload) failed with `curl: (6) Could not resolve host`. **This does not prove the policy blocked it**: a DNS failure is consistent with allowlist enforcement but could also be an ordinary resolver problem. Allowlisted `https://api.github.com/zen` returned HTTP 200 on the same run, so general DNS and egress were working. PyPI installs (allowlisted) worked, though one attempt failed transiently with `Network is unreachable` and worked on retry.
2. **Git.** `git ls-remote` / clone through the session git proxy returned **HTTP 403** for this public repository. `git push --dry-run` to the same proxy remote also returned 403, before any write negotiation. **This shows repo access was refused through the proxy. It does not show a write-specific denial**, because reads were refused as well. No real push was attempted, and no other credentials or transports were tried.
3. **Source.** Following the playbook, the code came from the public GitHub API tarball for commit `1a2046b7efa6a67fe1c689877ef188e19df502fd` (`main`, "Redesign key decisions as a visual one-page brief (#7)").
4. **GitHub CLI.** `gh auth status` returned "You are not logged into any GitHub hosts".
5. **Harness.** A `git config --global --list` call was rejected by the tool harness ("Do NOT run git config"). This was an extra runtime guard I ran into by accident.
6. **Devin MCP.** No Devin MCP write tools were used. No child sessions were created.

Configured but not independently tested here: the read-only Git security profile as a *write-specific* policy, absence of external MCP servers, absence of production credentials (none were found, and none were looked for beyond env-var *names*), and trigger filters.

## App-level non-goals
Not SSO, not production identity, no MFA, no rate limiting or lockout, cookie `Secure` flag off (local HTTP only), and SQLite history is not tamper-proof auditing. No real payment action exists. The Risk Vendor is simulated.
