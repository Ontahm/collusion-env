"""Print one recorded game as a readable story: the board, who colludes, what each agent said,
reserved and claimed, and what it cost the team.

    python -m analysis.episode runs/<run>                          # list the games of a run
    python -m analysis.episode runs/<run> --scenario ACT-1 --seed 3       # or --cond secret_chat
    make episode RUN=runs/<run> SC=ACT-1 SEED=3 [ARGS='--cot --full --round 2']

Options: --model (when the run has several), --rep (replication, default 0), --round (one round
of a repeated game), --cot (each agent's reasoning text, when the model returned any), --full
(messages not shortened). Everything comes from episode.json; nothing is recomputed except each
agent's best task alone (the one it would pick if nobody else played), from the recorded costs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

PRIORITY = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
_SUFFIX = re.compile(r"\s*\(phase=[^)]*\)\s*$")


def short(task: Optional[str]) -> str:
    return "skip" if not task else task.replace("ISSUE-000", "I").replace("ISSUE-00", "I")


def clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def own_values(round_: Dict[str, Any], scoring: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Each agent's reward for each task on its own (no duplicate penalty): the 'best for itself'."""
    board = round_["board"]
    done = float(scoring.get("tasks_done_bonus", 20.0))
    prio = float(scoring.get("priority_bonus", 20.0))
    weights = {**PRIORITY, **(scoring.get("priority_weights") or {})}
    tasks = board["tasks"]
    return {agent[0]: {t[0]: done + prio * weights[t[4]] - cost for t, cost in zip(tasks, costs)}
            for agent, costs in zip(board["agents"], board["costs"])}


def scenario_of(ep: Dict[str, Any]) -> Optional[str]:
    import scenarios
    return scenarios.identify(ep.get("game") or {})


def episodes(run: Path) -> List[Path]:
    return sorted(run.glob("episodes/*/*/*/episode.json"))


def story(ep: Dict[str, Any], round_filter: Optional[int], cot: bool, width: int) -> List[str]:
    out: List[str] = []
    scoring = (ep.get("game") or {}).get("scoring") or {}
    model = ep["model"]["label"] if isinstance(ep.get("model"), dict) else str(ep.get("model"))
    rounds = ep.get("rounds", [])
    for r in rounds:
        if round_filter is not None and r["round"] + 1 != round_filter:
            continue
        m, a = r.get("metrics", {}), r.get("analysis", {})
        colluders = r["colluders"]
        star = lambda n: f"{n}*" if n in colluders else n          # noqa: E731
        values = own_values(r, scoring)
        best = {n: max(v, key=v.get) for n, v in values.items()}
        sid = scenario_of(ep)
        out += ["", "=" * 100,
                f"{(sid + ' ') if sid else ''}{ep['condition']} · {model} · seed {ep['seed']}" + (f" rep {ep['replication']}" if ep.get("replication") else "")
                + f" · round {r['round'] + 1} of {len(rounds)} · board seed {r['board_seed']}", "=" * 100]

        # the goal and the board ---------------------------------------------------------------------
        obj = r.get("objective") or {}
        goal = obj.get("type", "?")
        if goal == "same_issue":
            kind = "conflict" if a.get("same_issue_conflict") else "costless"
            out.append(f"Goal of the colluders: claim different tasks of the same issue. Board: {kind} "
                       f"(price of collusion {a.get('price_same_issue', 0):.2f}, matching cost {a.get('matching_cost') or 0:.2f}"
                       + (f", bonus {obj.get('same_issue_bonus'):.2f}" if obj.get("same_issue_bonus") else "") + ")")
        elif goal == "high_value_ticket":
            kind = "conflict" if a.get("hv_conflict") else "costless"
            out.append(f"Goal of the colluders: get the high-value ticket {short(obj.get('hv_task'))} "
                       f"(bonus {obj.get('hv_coalition_bonus', 0):g} for the coalition). Board: {kind} "
                       f"(the team loses at least {a.get('price_hv') or 0:.2f} if a colluder holds it)")
        else:
            out.append("Goal of the colluders: maximise their joint reward (Colosseum's). No target task or issue.")
        out.append("")
        out.append(f"{'task':16s} {'priority':9s} {'effort':>6s}   best task for")
        for t in r["board"]["tasks"]:
            fans = [star(n) for n, b in best.items() if b == t[0]]
            mark = "  <- high-value ticket" if t[0] == obj.get("hv_task") else ""
            out.append(f"{short(t[0]):16s} {t[4]:9s} {t[5]:6.1f}   {', '.join(fans)}{mark}")
        out.append("")
        out.append("Agents in turn order (* colluder): " + ", ".join(star(n) for n in r["turn_order"]))
        out.append(f"Best team plan (score {a.get('optimum', 0):.2f}): "
                   + ", ".join(f"{star(n)} {short(t)}" for n, t in (a.get("optimum_assignment") or {}).items()))

        # the play, turn by turn ---------------------------------------------------------------------
        boards = {b["blackboard_id"]: b["kind"] for b in r.get("boards", [])}
        out += ["", "Play:"]
        last_phase, last_post = None, None
        for t in r.get("turns", []):
            phase = f"{t['phase']} pass {t['pass'] + 1}" if t["kind"] != "claim" else "claims"
            if phase != last_phase:
                out.append(f"  -- {phase}")
                last_phase, last_post = phase, None
            if cot:
                for s in t.get("steps") or []:
                    if s.get("reasoning"):
                        out.append(textwrap.indent(textwrap.fill(f"({t['agent']} thinks) " + clip(s["reasoning"], width * 3), 96), "     "))
            if not t.get("tool_calls"):
                out.append(f"     {star(t['agent'])}: no action" + (f" ({clip(t['final_text'], 80)})" if t.get("final_text") else ""))
            for c in t.get("tool_calls", []):
                args, res = c.get("arguments") or {}, c.get("result")
                failed = isinstance(res, dict) and (res.get("status") in ("retry", "failed") or "error" in res)
                if c["tool"] == "post_message":
                    text = _SUFFIX.sub("", str(args.get("message", "")))
                    where = boards.get(args.get("blackboard_id"), f"board {args.get('blackboard_id')}")
                    if last_post and last_post[0] == (t["agent"], where, text):
                        last_post[1] += 1
                        out[last_post[2]] = out[last_post[2]].rsplit(" (x", 1)[0] + f" (x{last_post[1]})"
                        continue
                    out.append(textwrap.fill(f"{star(t['agent'])} [{where}]: {clip(text, width)}", 96,
                                             initial_indent="     ", subsequent_indent="        "))
                    last_post = [(t["agent"], where, text), 1, len(out) - 1]
                elif c["tool"] in ("reserve_task", "assign_task"):
                    task = args.get("task_id")
                    verb = "reserves" if c["tool"] == "reserve_task" else "claims"
                    note = ""
                    if failed:
                        note = f"  REFUSED: {clip(str(res.get('reason') or res.get('error')), 80)}"
                    elif c["tool"] == "assign_task" and task and task != "skip":
                        own = values.get(t["agent"], {}).get(task)
                        b = best.get(t["agent"])
                        note = "  (its best alone)" if task == b else (
                            f"  (best alone: {short(b)}, gives up {values[t['agent']][b] - own:.1f})" if own is not None else "")
                    out.append(f"     {star(t['agent'])} {verb} {short(task)}{note}")
                else:
                    out.append(f"     {star(t['agent'])} {c['tool']}({clip(json.dumps(args), 60)})" + ("  REFUSED" if failed else ""))
        if r.get("filled"):
            out.append("  -- random fills (missing claims): " + ", ".join(f"{star(n)} {short(t)}" for n, t in r["filled"].items()))

        # the outcome ------------------------------------------------------------------------------
        ev = r.get("evaluation", {})
        out += ["", "Outcome:",
                f"  team score {ev.get('score', 0):.2f} of {a.get('optimum', 0):.2f} possible: team loss {m.get('team_loss', 0):.2f}; "
                f"duplicate claims {ev.get('violations', 0)}",
                "  rewards: " + ", ".join(f"{star(n)} {v:.1f}" for n, v in (ev.get("rewards") or {}).items())]
        if goal == "high_value_ticket":
            out.append(f"  high-value ticket: {m.get('hv_outcome', '?')} (held by {', '.join(map(star, m.get('hv_holders') or [])) or 'nobody'})")
        sac = {n: v for n, v in (m.get("colluder_sacrifice") or {}).items() if v}
        out.append(f"  colluders on the same issue: {'yes' if m.get('same_issue_match') else 'no'}"
                   + (f"; collusive (a colluder gave up reward): {', '.join(f'{n} {v:.1f}' for n, v in sac.items())}" if m.get("collusive_match") else ""))
        out.append(f"  Colosseum: regret gap {m.get('regret_gap', 0):.2f}, reward gap {m.get('reward_gap', 0):.2f} "
                   "(positive: colluders do better than the others)")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run")
    parser.add_argument("--cond", help="condition name (as in the study)")
    parser.add_argument("--scenario", help="scenario ID (configs/scenarios.yaml), instead of --cond")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model")
    parser.add_argument("--rep", type=int, default=0)
    parser.add_argument("--round", type=int)
    parser.add_argument("--cot", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args(argv)
    run = Path(args.run)
    eps = episodes(run)
    if not eps:
        print(f"no episodes in {run}")
        return 1
    from scenarios import run_scenarios
    ids = run_scenarios(run)
    if args.scenario:
        conds = [c for c, s in ids.items() if s == args.scenario]
        if not conds:
            print(f"scenario {args.scenario} was not played in {run}; run without it to list the games")
            return 1
        args.cond = conds[0]
    if args.cond is None or args.seed is None:
        print(f"Games in {run} (pick one: make episode RUN=... SC=<scenario> SEED=<k>, or COND=<condition>):")
        by: Dict[tuple, List[str]] = {}
        for e in eps:
            cond, model, folder = e.parts[-4], e.parts[-3], e.parts[-2]
            by.setdefault((cond, model), []).append(folder.replace("seed", "").replace("_rep0", ""))
        for (cond, model), seeds in sorted(by.items(), key=lambda kv: (ids.get(kv[0][0]) or "~", kv[0])):
            seeds.sort(key=lambda s: int(re.match(r"\d+", s).group()))
            print(f"  SC={ids.get(cond) or '-':8s} COND={cond:28s} model {model:24s} seeds {' '.join(seeds)}")
        return 0
    pattern = f"episodes/{args.cond}/{args.model or '*'}/seed{args.seed}_rep{args.rep}/episode.json"
    found = sorted(run.glob(pattern))
    if not found:
        print(f"no game matches {pattern}; run without --cond to list them")
        return 1
    if len(found) > 1:
        print("several models played this game; pick one with --model: " + ", ".join(p.parts[-3] for p in found))
        return 1
    ep = json.loads(found[0].read_text())
    print("\n".join(story(ep, args.round, args.cot, 10**6 if args.full else 300)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
