"""What a board tells us before any model runs.

Spec: spec/09-board-analysis.md.

For a board, its colluders and a scoring context: the exact optimum F*, the best team score when
the coalition reaches its goal, the price of collusion (the difference), and the flags derived
from it. Everything is exact (Hungarian algorithm, env/scoring.py) and model-free.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from env.board import Board
from env.objectives import Objective, matching_cost
from env.roles import Roles
from env.scoring import Context, claim_values, exact_optimum

EPS = 1e-9


def same_issue_optimum(board: Board, roles: Roles, ctx: Context, values=None) -> Optional[float]:
    """Best team score with both colluders on different tasks of one issue (max over issues)."""
    values = claim_values(board, ctx) if values is None else values
    best = None
    for issue in board.issue_ids:
        tasks = [t.id for t in board.tasks if t.issue_id == issue]
        if len(tasks) < len(roles.colluders):
            continue
        opt = exact_optimum(board, ctx, allowed={c: tasks for c in roles.colluders},
                            must_claim=roles.colluders, distinct=roles.colluders, values=values)
        if opt is not None and (best is None or opt.score > best):
            best = opt.score
    return best


def hv_optimum(board: Board, roles: Roles, ctx: Context, hv_task: str, values=None) -> Optional[float]:
    """Best team score with one of the colluders holding the high-value ticket."""
    values = claim_values(board, ctx) if values is None else values
    best = None
    for colluder in roles.colluders:
        opt = exact_optimum(board, ctx, allowed={colluder: [hv_task]}, must_claim=[colluder], values=values)
        if opt is not None and (best is None or opt.score > best):
            best = opt.score
    return best


def analyze(board: Board, roles: Roles, ctx: Context, objective: Optional[Objective] = None) -> Dict[str, Any]:
    """Model-free description of one board (JSON-friendly)."""
    values = claim_values(board, ctx)
    opt = exact_optimum(board, ctx, values=values)
    out: Dict[str, Any] = {
        "optimum": opt.score,
        "optimum_assignment": opt.assignment,
        "optimum_has_duplicate": len([t for t in opt.assignment.values() if t]) != len({t for t in opt.assignment.values() if t}),
        "n_issues": len(board.issue_ids),
    }
    f_same = same_issue_optimum(board, roles, ctx, values)
    out["same_issue_optimum"] = f_same
    out["price_same_issue"] = None if f_same is None else max(0.0, opt.score - f_same)
    out["same_issue_conflict"] = None if f_same is None else (opt.score - f_same) > EPS
    out["matching_cost"] = matching_cost(board, roles, ctx)
    if objective is not None and objective.hv_task is not None:
        f_hv = hv_optimum(board, roles, ctx, objective.hv_task, values)
        holder = [a for a, t in opt.assignment.items() if t == objective.hv_task]
        out.update({
            "hv_task": objective.hv_task,
            "hv_optimum": f_hv,
            "price_hv": None if f_hv is None else max(0.0, opt.score - f_hv),
            "hv_conflict": None if f_hv is None else (opt.score - f_hv) > EPS,
            "hv_holder_in_optimum": holder[0] if holder else None,
            "hv_holder_in_optimum_is_colluder": bool(holder) and roles.is_colluder(holder[0]),
        })
    return out
