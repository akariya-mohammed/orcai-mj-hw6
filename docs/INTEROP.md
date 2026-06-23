# Cross-Group Interop Contract (Bonus Game)

So two groups' agents can actually play, both sides must agree on (1) the game
parameters, (2) the MCP tool contract, and (3) the turn protocol. Sharing this is
explicitly allowed by the assignment ("groups may share code and architecture");
**only the strategy/eval inside each agent must stay original.**

## 1. Agreed game parameters

| parameter | value |
| --- | --- |
| board (`grid_size`) | **10 × 10** (recommended — see note) |
| origin | 1 (cells span (1,1)…(10,10)) |
| moves per direction | 1 step, **8 directions** (incl. diagonal) |
| move cap | **25** (thief wins if uncaught) |
| barriers | cop ≤ **5**; placing one = cop stays put; nobody may enter a barrier |
| scoring | cop-win 20/5 · thief-win 5/10 |
| sub-games | **6** total — 3 with group A as cop, 3 with group B as cop |

> **Board size note.** On 5×5 an optimal cop always catches → the match ties.
> A larger board (≈10×10) makes skill decide. Pick the size you both accept.

## 2. MCP tool contract

Each group runs **two** MCP servers (cop, thief), each exposing these tools.
Every call carries a bearer `token` (the value the server owner shares with you).

| tool | input | returns |
| --- | --- | --- |
| `setup` | `cop:[r,c]`, `thief:[r,c]`, `token` | `{role, snapshot}` |
| `my_move` | `token` | `{message, snapshot, status}` |
| `observe` | `message:str`, `mover:"cop"\|"thief"`, `token` | `{snapshot, status}` |
| `state` | `token` | `snapshot` |

`snapshot` shape:

```json
{ "cop": [r,c], "thief": [r,c], "barriers": [[r,c],...],
  "barriers_left": int, "move_count": int, "max_moves": 25,
  "turn": "cop"|"thief", "status": "playing"|"cop_win"|"thief_win",
  "distance": int }
```

Reference implementation: [`src/servers/`](../src/servers/) (`app.py`,
`common.py`). You can adopt it verbatim and only swap the strategy.

## 3. Turn protocol

1. Both servers `setup(cop, thief)` with the **same agreed start cells**.
2. **Thief moves first.** Each turn:
   - the mover's server `my_move()` → returns a **natural-language** `message`
     (e.g. *"Thief here. From (3,3) I slip south-east. MOVE to (4,4)."*) and
     applies the move to its own world;
   - that `message` is passed to the opponent's `observe(message, mover)`, which
     interprets it and applies the move to its world.
3. Repeat until `status != "playing"`. Score the sub-game; rotate roles.

**Natural-language messages are free-form**, but to keep the round-trip robust
each message should contain the destination as `(row, col)` and the word `MOVE`
or `BARRIER`. Our interpreter also accepts `row R col C`, bare directions
("I move north"), and `wall`/`block` synonyms — see
[`src/client/personas.py`](../src/client/personas.py).

## 4. Who runs the match + connectivity

- **One group runs the referee** ([`src/client/networked.py`](../src/client/networked.py)),
  which connects to all four MCP URLs and drives the turn loop. (Either group can;
  results are deterministic given the same start cells.)
- Expose each local server with a tunnel, e.g. `ngrok http 8765` (cop) and
  `ngrok http 8766` (thief); share the two HTTPS URLs **and** the tokens.
- Run: `python -m src.client.networked --our-cop-url … --our-thief-url …
  --opp-cop-url … --opp-thief-url …` (set `OPPONENT_MCP_TOKEN` in `.env`).

## 5. Result + email

Both groups must email **agreeing** results (conflicting emails disqualify both).
The referee writes `artefacts/bonus_report.json` with `totals_by_group`,
`bonus_claim`, and `mutual_agreement: true`. Compare it with the other group,
then each group emails the **same** result to the lecturer.

## 6. Disputes

Each side keeps the full JSONL log ([`src/report/logbook.py`](../src/report/logbook.py)).
On a disagreement, compare logs move-by-move before escalating.
