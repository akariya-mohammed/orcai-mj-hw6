# Message to send the partner group (WhatsApp / email)

---

Hey! We're group **orcai-mj** — let's set up the HW6 cops-and-robbers bonus match.
Proposing this so our agents actually interoperate (sharing architecture is
allowed; our strategies stay our own):

**Game params:** 10×10 board, origin 1, 8-direction moves, 25-move cap, cop ≤5
barriers, scoring 20/5 (cop win) and 5/10 (thief win), 6 sub-games (we're cop for
3, you're cop for 3).

**Protocol:** each side runs a cop MCP server + a thief MCP server exposing 4
tools — `setup(cop, thief, token)`, `my_move(token)`, `observe(message, mover,
token)`, `state(token)`. Turns alternate (thief first): the mover's `my_move`
returns a natural-language message ("Thief from (3,3) MOVE to (4,4)"), the
opponent's `observe` reads it. One of us runs a referee that connects to all four
URLs and drives the loop.

We've got a working reference implementation we can share (you'd only swap in your
own strategy). We'll expose our two servers via ngrok and send you the HTTPS URLs
+ tokens; send us yours.

After the 6 sub-games, we compare the result JSON and **both email the same
result** to the lecturer (conflicting results disqualify both, so we confirm
first).

Full spec here: [link to our repo `docs/INTEROP.md`]. What board size works for
you — 10×10 ok? When do you want to run it?

---
