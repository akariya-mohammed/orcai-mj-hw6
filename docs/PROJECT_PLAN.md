# Project Plan — HW6 Cops & Robbers (Dual-AI MCP Race)

## Problem

Build two autonomous AI agents (a Cop and a Thief), each behind its **own MCP
server**, that play a grid pursuit/evasion game by conversing in **free natural
language** — no fixed wire protocol. An LLM-driven client interprets the
conversation and invokes each server's tools. A full game (6 sub-games, roles
alternating) must run autonomously, be scored, logged, and emailed as JSON.

## Goals

- **G1** Two independent MCP servers (cop, thief), each owning its agent's world.
- **G2** Agents coordinate in natural language; tools fire from *interpretation*.
- **G3** Correct, configurable rules (capture, barriers, 25-move cap, scoring).
- **G4** A reinforcement-learning strategy (tabular Q-learning) plus a heuristic
  baseline, with a visual Q-table artefact.
- **G5** Autonomous 6-sub-game run with full JSONL logging and a JSON report.
- **G6** Result email via the Gmail API (pure-JSON body).
- **G7** Cloud-ready: token-secured MCP URLs; cross-group bonus report.
- **G8** Engineering professionalism: config-driven, tested, linted, documented.

## Non-goals

- Not a general game platform or UI product.
- Not a deep-RL project — tabular Q-learning is sufficient and interpretable.
- The client does not host the LLM inside a server (spec forbids it).

## Formal model — Dec-POMDP

The game is a two-agent decentralized partially-observable Markov decision
process `⟨n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ⟩`:

- **n = 2** agents: cop and thief.
- **S** — state = `(cop_cell, thief_cell, barrier_set, move_count)` on the
  `rows × cols` grid.
- **Aᵢ** — actions:
  - `A_cop` = {one step in 8 directions} ∪ {place a barrier on an adjacent free
    cell (stay put)}, barriers capped at 5.
  - `A_thief` = {one step in 8 directions} (must move; cannot enter a barrier).
- **P** — transition: deterministic application of the chosen one-step action /
  barrier placement.
- **R** — reward (per sub-game): cop +20 / thief +5 on capture; cop +5 /
  thief +10 on thief survival. RL adds per-step shaping (cop −0.1/step,
  thief +0.1/step, ±10 terminal).
- **Ωᵢ, O** — observations are **partial**: an agent learns the opponent's
  position only through the opponent's **natural-language message**; `O` is the
  persona's *interpretation* of that message (which may be noisy or, adversari‑
  ally, wrong). This is exactly what makes the architecture a Dec-**PO**MDP and
  why robustness (parse fallback, dispute logging) matters.
- **γ** — discount factor (0.9 in the Q-learner).

## Architecture

A "voice + body" split (see [README](../README.md) diagram):

- **Body** (`AgentBody`, one per MCP server): authoritative world view, rule
  validation, strategy. Tools: `setup`, `my_move`, `observe`, `state`.
- **Voice/ears** (`Persona`): `announce` a move as free language; `interpret`
  the opponent's language into a structured move (LLM extraction + regex net).
- **Orchestrator** (MCP client): owns the turn loop, logging, scoring, report,
  and the watchdog/gatekeeper.

## Key design decisions

1. **Deterministic strategy, LLM only for language.** Keeps the 6-game run
   reliable on a small/free local model while still satisfying "agents talk in
   natural language; tools fire from interpretation."
2. **Coordinates embedded in every announcement.** Guarantees the NL round-trip
   stays in sync even if an 8B model rephrases loosely; the regex net recovers
   structure, and mismatches are logged (the basis for dispute handling).
3. **Two-world sync proven in-process** (`run_loopback_match`) so the distributed
   logic is unit-testable without a daemon.
4. **Config-first.** No rule constant is hard-coded; the same code runs 2×2 for
   debugging and 5×5 for the real game.
5. **Heuristic as RL fallback.** An unseen Q-state defers to the heuristic, so
   the learner is never worse than the baseline.

## Alternatives considered

- *LLM picks the move directly* — rejected: unreliable/expensive over hundreds of
  turns, and conflates strategy with language.
- *Rigid JSON protocol between agents* — rejected: the spec wants free language.
- *Gemini free tier as default LLM* — rejected: rate limits exhaust mid-match
  (~270 calls); Ollama (local) is free and unlimited, Haiku is the cheap paid
  fallback. See [COSTS](COSTS.md).
- *Deep-RL (DQN)* — rejected: tabular Q-learning is enough on a 5×5 grid and is
  far easier to visualise and defend.

## Build phases

1. Engine (board, rules, scoring) — tested. ✅
2. Strategy (heuristic + Q-learning + heatmap). ✅
3. Reliability (gatekeeper + watchdog). ✅
4. Reports (internal + bonus JSON, JSONL log) + Gmail mailer. ✅
5. LLM factory + personas + orchestrator (local self-play). ✅
6. AgentBody + FastMCP servers + loopback sync. ✅
7. Visualization + committed artefacts. ✅
8. Cloud token auth (done) + Gmail OAuth (scaffolded; needs `credentials.json`).
9. Cross-group: point at a partner's URLs (tested against a second local body).

## Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Small LLM mangles a message | coordinates always embedded + regex parse + heuristic resync |
| Hung autonomous run | `Watchdog` kill-switch |
| Runaway token spend | `TokenGatekeeper` hard cap |
| Two groups report conflicting results | symmetric bonus JSON with `mutual_agreement` + full logs |
| Public MCP URL abused | per-server bearer token |

## Self-assessment

Honest target ≈ **88–92**. Core + cloud-token + RL + visualization + email
(dry-run) + full docs/tests are done; the only user-side steps left are Google
OAuth `credentials.json` and a live cross-group match with a real partner group.
