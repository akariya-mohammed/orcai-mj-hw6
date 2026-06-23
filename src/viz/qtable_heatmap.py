"""Render a Q-table value heatmap — the bonus RL visualization.

For a fixed opponent cell, colour each board cell by V(s) = max_a Q(s, a): where
the learner "wants" to be. This makes the learned pursuit/evasion policy visible.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def render_qtable_heatmap(
    value_grid: np.ndarray,
    opp_cell: tuple[int, int],
    origin: int,
    title: str,
    out_path: str | Path,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows, cols = value_grid.shape

    fig, ax = plt.subplots(figsize=(5.5, 5))
    im = ax.imshow(value_grid, cmap="viridis", origin="upper")
    fig.colorbar(im, ax=ax, label="V(state) = max_a Q(s, a)")

    # annotate cells
    for r in range(rows):
        for c in range(cols):
            v = value_grid[r, c]
            txt = "opp" if np.isnan(v) else f"{v:.1f}"
            ax.text(c, r, txt, ha="center", va="center", color="white", fontsize=8)

    ax.set_xticks(range(cols))
    ax.set_yticks(range(rows))
    ax.set_xticklabels(range(origin, origin + cols))
    ax.set_yticklabels(range(origin, origin + rows))
    ax.set_xlabel("column")
    ax.set_ylabel("row")
    ax.set_title(f"{title}\n(opponent fixed at {opp_cell})")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
