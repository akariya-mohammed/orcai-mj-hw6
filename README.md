# HW6 — Cops & Robbers: Dual-AI Race via MCP Servers

Two autonomous AI agents — a **Cop** and a **Thief** — each behind its **own
FastMCP server**, play a grid pursuit/evasion game by talking to each other in
**free natural language**. An LLM-driven MCP **client** interprets the
conversation and fires each server's tools to move and place barriers. A full
**game = 6 sub-games** (3 as cop, 3 as thief) runs autonomously end-to-end; the
result is scored and emailed as JSON to the lecturer.

> Course: Dr. Yoram Segal, AI Orchestration · Assignment **ex06** (Lecture 09).

---

## What it does (assignment → where)

| Requirement | Where |
| --- | --- |
| Two separate MCP servers (cop, thief) | [src/servers/](src/servers/) — `cop_server.py`, `thief_server.py`, `app.py` |
| Agents converse in **free natural language**; tools fire from interpretation | [src/client/personas.py](src/client/personas.py) (announce/interpret) + [src/servers/common.py](src/servers/common.py) |
| LLM needed to interpret the protocol | [src/client/llm.py](src/client/llm.py) — Ollama / Anthropic / Gemini / mock |
| Grid game, capture & barrier rules, 25-move cap | [src/engine/](src/engine/) |
| 6 sub-games (3 cop / 3 thief), scoring table | [src/engine/scoring.py](src/engine/scoring.py) |
| Reinforcement Learning (Q-Table) strategy | [src/strategy/qlearning.py](src/strategy/qlearning.py) |
| Autonomous run, full logging | [src/client/orchestrator.py](src/client/orchestrator.py) + [src/report/logbook.py](src/report/logbook.py) |
| Result email (Gmail API), **JSON body** | [src/mailer/gmail.py](src/mailer/gmail.py) + [src/report/](src/report/) |
| Token-secured MCP URLs (cloud level) | [src/servers/app.py](src/servers/app.py) |
| Cross-group bonus report | [src/report/bonus.py](src/report/bonus.py) |
| No hard-coding — central config | [config.yaml](config.yaml) |

---

## Architecture

```
 Cop-LLM persona  <----- natural language ----->  Thief-LLM persona
   (voice + ears)        the "conversation"          (voice + ears)
        |                                                  |
        |            MCP client / orchestrator             |
        |        (holds the loop, logging, scoring)        |
        v  tool calls                          tool calls  v
  Cop MCP server (FastMCP)                Thief MCP server (FastMCP)
   AgentBody: own world view,              AgentBody: own world view,
   strategy (heuristic / Q),              strategy (heuristic / Q),
   rule validation                        rule validation
```

* **The LLM lives in the client**, never inside a server (per spec). The
  *strategy* (deterministic heuristic, or a trained Q-table) decides each move;
  the *persona* turns it into a free-language sentence and reads the opponent's
  sentence back into a structured move.
* **Each MCP server is one agent's "body"** ([AgentBody](src/servers/common.py)):
  it owns that agent's position, barrier budget, and rule validation, and exposes
  `setup` / `my_move` / `observe` / `state` as MCP tools. The two bodies stay in
  sync purely through the natural-language messages.

---

## Quick start

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt

# Fastest: a full 6-sub-game match with the offline mock backend (no LLM needed)
python -m src.client.orchestrator --provider mock

# With a local LLM (free, unlimited): install Ollama, then `ollama pull llama3.1:8b`
python -m src.client.orchestrator                    # provider from config.yaml (ollama)

# Generate the report artefacts (board image, Q-table heatmaps, sample log, JSON)
python -m src.viz.make_artefacts
```

### Run it as two real MCP servers (cloud / cross-group level)

```bash
# set tokens first (see .env.example):  COP_MCP_TOKEN=...  THIEF_MCP_TOKEN=...
python -m src.servers.cop_server      # serves http://127.0.0.1:8765/mcp
python -m src.servers.thief_server    # serves http://127.0.0.1:8766/mcp
```

Each tool requires the matching bearer **token**, so a public URL can't be driven
by a stranger.

### Cross-group bonus match (the 10-pt path)

The networked orchestrator plays a full 6-microgame match across MCP **URLs** —
3 sub-games as cop (our cop vs the partner's thief), 3 as thief — and emits the
**bonus** JSON (`artefacts/bonus_report.json`).

```bash
# Offline proof (no partner, no network): play against our own in-process servers
python -m src.client.networked --selftest --provider mock

# Real match vs a partner group (they give you their two MCP URLs + a token):
#   set OPPONENT_MCP_TOKEN in .env, then:
python -m src.client.networked \
  --our-cop-url   http://127.0.0.1:8765/mcp \
  --our-thief-url http://127.0.0.1:8766/mcp \
  --opp-cop-url   https://PARTNER/cop/mcp \
  --opp-thief-url https://PARTNER/thief/mcp
```

To expose your local servers to a partner, tunnel each port (e.g.
`ngrok http 8765`) and share the two HTTPS URLs + your tokens. Both groups must
email **agreeing** results — the bonus report carries `mutual_agreement: true`.

---

## What using it looks like (UI/UX)

A run prints a per-sub-game summary and writes a JSONL log + JSON report:

```
sub-game 1/6 (cop):   cop_win   cop=20 thief= 5 rounds=9
...
TOTALS  cop=120  thief=30  our_total=75
log:    logs/match-*.jsonl
report: artefacts/internal_report.json
```

Committed artefacts (under [artefacts/](artefacts/)):

| File | What |
| --- | --- |
| `sample_board.png` | a played-out sub-game with cop/thief trails and barriers |
| `qtable_thief_heatmap.png` / `qtable_cop_heatmap.png` | learned RL value maps |
| `internal_report.json` | the JSON email body (self-play) |
| `email_dry_run.json` | the rendered outgoing email |
| `logs/sample-match.jsonl` | a full autonomous 6-sub-game log |

---

## Strategy: heuristic + Reinforcement Learning

* **Heuristic** ([heuristic.py](src/strategy/heuristic.py)) — cop greedily closes
  Chebyshev distance and drops barriers on the thief's best escape; thief
  maximises distance and mobility. Always legal; the RL fallback.
* **Q-Learning** ([qlearning.py](src/strategy/qlearning.py)) — tabular Q over
  state `(own cell, opponent cell)`, 8 movement actions, ε-greedy training by
  self-play against the heuristic, Bellman update. Visualised as a Q-value
  heatmap. Switch per role in `config.yaml` (`strategy.cop`, `strategy.thief`).

---

## Configuration & security

* **Everything tunable is in [config.yaml](config.yaml)** — grid size, 25-move
  cap, 5-barrier limit, scoring, LLM provider, server ports/tokens, email.
* **Secrets never reach git**: API keys and OAuth files live in `.env` /
  `secrets/` (both gitignored). See [.env.example](.env.example).
* **MCP URLs are token-gated**; the LLM is **outbound-only** (Ollama stays on
  localhost). Full threat model in [docs/SECURITY.md](docs/SECURITY.md).
* A **token-budget gatekeeper** caps LLM spend and a **watchdog** kills a hung
  run — see [src/reliability/](src/reliability/).

---

## Extensibility

* **Swap the LLM** — one line: `llm.provider` in `config.yaml`.
* **Swap a strategy** — `strategy.cop` / `strategy.thief` = `heuristic` |
  `qlearning`.
* **Change the rules** — grid size, move cap, barriers, scoring are all config.
* **Add an agent action** — extend `SubGame.legal_moves` + `Persona` keywords.
* **Plug in a partner group** — set `bonus.opponent.*` URLs/token and use the
  bonus report builder ([src/report/bonus.py](src/report/bonus.py)).

---

## Quality

`ruff` + `black` + `pytest` (22 tests, mock backend — no network), enforced by
[.pre-commit-config.yaml](.pre-commit-config.yaml) and GitHub Actions
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

```bash
ruff check src tests && black --check src tests && pytest
```

## Repository layout

```
config.yaml            central config (no magic numbers in code)
src/engine/            board, rules, state machine, scoring
src/strategy/          heuristic + tabular Q-learning
src/servers/           AgentBody + FastMCP cop/thief servers
src/client/            LLM factory, personas, orchestrator
src/reliability/       token gatekeeper + watchdog
src/report/            internal/bonus JSON + JSONL logbook
src/mailer/            Gmail API sender
src/viz/               board renderer + Q-table heatmap + artefact generator
tests/                 pytest suite
docs/                  PROJECT_PLAN, COSTS, SECURITY
```

## Known limitations

* On a 5×5 board the heuristic cop is strong, so the thief rarely wins self-play;
  larger boards or the trained Q-thief make it competitive.
* The local orchestrator keeps one authoritative world; the networked path keeps
  two worlds synced by NL (`run_loopback_match` proves the sync without a daemon).
* See [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for design rationale and the
  Dec-POMDP formal model.
