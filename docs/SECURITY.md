# Security

The cloud level exposes MCP server URLs to the internet, so security is a graded
part of the task. This is how we keep it safe.

## Attack surface & mitigations

| Surface | Risk | Mitigation |
| --- | --- | --- |
| Public MCP URL (cop / thief) | A stranger drives your agent / cheats | **Bearer token** per server — every tool call checks the token from `servers.<role>.token_env`; a wrong/missing token raises `AuthError`. ([src/servers/app.py](../src/servers/app.py)) |
| LLM endpoint | Exposing a local model / firewall hole | LLM calls are **outbound only**; Ollama stays bound to `127.0.0.1:11434` and is **never** exposed. Only the MCP servers (which hold no secrets) are reachable. |
| API keys / OAuth | Secrets leaking into git | Keys live in `.env`; Gmail `credentials.json` / `token.json` live in `secrets/`. **Both are gitignored**; `detect-private-key` pre-commit hook is a second net. |
| Untrusted opponent messages | Malformed / adversarial NL desyncs the game | `Persona.interpret` validates every parsed move against the rules; un-parseable input is logged and the game resyncs via the heuristic (no crash, no illegal move). |
| Runaway autonomous run | Hung loop / token blow-up | `Watchdog` kills a stalled run; `TokenGatekeeper` caps total LLM tokens. |
| Result disputes between groups | One group claims a different result | Symmetric bonus JSON with `mutual_agreement`, plus the full JSONL log as evidence. |

## Token setup (cloud level)

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # generate
# put the values in .env:
#   COP_MCP_TOKEN=...
#   THIEF_MCP_TOKEN=...
```

The client passes the matching token on every tool call; rotate by changing the
env value and restarting the server (a `Revoke` is just "change the token").

> Hardening note: the token is checked at the tool-argument layer for portability
> across FastMCP versions. For production, also enable FastMCP's transport-level
> bearer auth and put the servers behind TLS (the URL should be `https://`).

## Gmail OAuth

Desktop OAuth client, scope `gmail.modify`. The first send opens a browser once,
then caches `secrets/token.json` and refreshes silently. The e-mail body is the
report **JSON only** — no free text, nothing sensitive beyond the agreed result.

## Secret hygiene checklist

- [x] `.env`, `secrets/` gitignored
- [x] `detect-private-key` + `check-added-large-files` pre-commit hooks
- [x] no key printed in logs (gatekeeper logs counts, not content)
- [x] tests force the `mock` LLM — CI never needs a key or network
