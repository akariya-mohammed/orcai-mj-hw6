# Costs & Token Economics

The **strategy is deterministic**, so the LLM is used only to phrase a move and
to read the opponent's phrasing. That keeps usage low and lets a free local model
do the job.

## What one full game costs

A full game ≈ **6 sub-games × ~15 rounds × ~3 LLM calls** ≈ **270 calls**, each
with a short output (~250 tokens). Pricing per 1M tokens (current): Opus 4.8
$5/$25, Sonnet 4.6 $3/$15, Haiku 4.5 $1/$5; prompt-cache reads ≈ 0.1× input.

| Backend | One full match (no cache) | One match (cached) | Whole project (~20–40 dev runs) |
| --- | --- | --- | --- |
| **Ollama (local)** | **$0** | **$0** | **$0** (rate-limit-free, default) |
| Haiku 4.5 | ~$1 | ~$0.5 | ~$10–30 |
| Sonnet 4.6 | ~$3 | ~$1.5 | ~$25–75 |
| Opus 4.8 | ~$5–8 | ~$2.5–3 | ~$50–150 |
| Gemini free tier | $0 but **rate-limited** | — | runs out mid-match (~270 calls) — not viable |

**Default: Ollama** (free, unlimited). **Cheap paid fallback: Haiku 4.5.** Switch
in one line: `llm.provider` in [config.yaml](../config.yaml).

## How cost scales

- Per **move**: ~2 calls (announce + interpret). Independent of board size.
- Per **sub-game**: O(rounds) calls; rounds ≤ 25 (the move cap bounds it).
- Per **game**: 6 × per-sub-game. Linear in sub-games.
- Across **groups/users**: linear; no shared state. 100 matches on Haiku ≈ $50–100.

## How the gatekeeper bounds risk

`TokenGatekeeper` ([src/reliability/gatekeeper.py](../src/reliability/gatekeeper.py))
enforces `llm.max_tokens_budget` (default 400k) and refuses to start a call once
the cap is hit — so even a pathological loop can't exceed it. On Haiku that cap is
an absolute worst case of roughly **$1.2 input + $2.0 output ≈ $3.2**; on Ollama
it is **$0** regardless. Every call logs a running total:

```
GATEKEEPER[hw6] call#42 by cop.persona: in=210 out=180 total=16110/400000 (4.0%)
```
