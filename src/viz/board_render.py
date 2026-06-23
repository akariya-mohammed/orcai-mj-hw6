"""Render a board state to PNG — a UI/UX artefact for the report.

No display required (Agg backend), so it runs in CI and headless.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402


def render_board(
    rows: int,
    cols: int,
    origin: int,
    cop: tuple[int, int],
    thief: tuple[int, int],
    barriers: list[tuple[int, int]],
    title: str,
    out_path: str | Path,
    *,
    cop_trail: list[tuple[int, int]] | None = None,
    thief_trail: list[tuple[int, int]] | None = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(5, 5))
    lo = origin - 0.5
    hi_r, hi_c = origin + rows - 0.5, origin + cols - 0.5

    # grid
    for r in range(origin, origin + rows + 1):
        ax.plot([lo, hi_c], [r - 0.5, r - 0.5], color="#cccccc", lw=1, zorder=0)
    for c in range(origin, origin + cols + 1):
        ax.plot([c - 0.5, c - 0.5], [lo, hi_r], color="#cccccc", lw=1, zorder=0)

    # barriers
    for br, bc in barriers:
        ax.add_patch(Rectangle((bc - 0.5, br - 0.5), 1, 1, color="#555555", zorder=1))

    # trails
    def _trail(trail, color):
        if trail and len(trail) > 1:
            xs = [c for (_, c) in trail]
            ys = [r for (r, _) in trail]
            ax.plot(xs, ys, color=color, lw=1.5, alpha=0.4, zorder=2)

    _trail(cop_trail, "#1f77b4")
    _trail(thief_trail, "#d62728")

    # agents
    ax.scatter([cop[1]], [cop[0]], s=600, color="#1f77b4", marker="o", zorder=3, label="Cop")
    ax.scatter([thief[1]], [thief[0]], s=600, color="#d62728", marker="*", zorder=3, label="Thief")
    ax.text(
        cop[1], cop[0], "C", color="white", ha="center", va="center", fontweight="bold", zorder=4
    )
    ax.text(
        thief[1],
        thief[0],
        "T",
        color="white",
        ha="center",
        va="center",
        fontweight="bold",
        zorder=4,
    )

    ax.set_xlim(lo, hi_c)
    ax.set_ylim(lo, hi_r)
    ax.set_xticks(range(origin, origin + cols))
    ax.set_yticks(range(origin, origin + rows))
    ax.set_aspect("equal")
    ax.invert_yaxis()  # row 1 at the top, like the lecture board
    ax.set_xlabel("column")
    ax.set_ylabel("row")
    ax.set_title(title)
    ax.legend(loc="upper right", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
