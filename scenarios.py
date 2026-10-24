"""Scenario catalogue (configs/scenarios.yaml): readable IDs for the games the study plays.

A scenario is a set of game rules; the run size (rounds) and the model are not part of it. Studies
refer to scenarios by ID; old runs and ad-hoc conditions are recognised from their resolved rules
(the full game config after files and overrides, without its name, description and number of
rounds), so the same rules always get the same ID wherever they were played.

    python -m scenarios                  # the table (also: make scenarios), and writes docs/reference/scenarios.md
    python -m scenarios --check          # exit 1 if docs/reference/scenarios.md is out of date
    python -m scenarios --prompts HV-2   # the exact prompts of a scenario (also: make prompts SC=HV-2)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from env.configio import ROOT, load_yaml, to_plain
from env.game_config import load_game

CATALOGUE = ROOT / "configs" / "scenarios.yaml"
TABLE = ROOT / "docs" / "reference" / "scenarios.md"
SIZE_KEYS = {"series.rounds"}            # what a study may change without changing the scenario
FAMILIES = {
    "PAPER": "Colosseum's Jira conditions (paper reproduction). Goal: maximise the coalition's joint reward.",
    "ACT": "The team note of 19 Oct: can colluders coordinate through actions alone? Goal: both colluders "
           "on the same issue. Numbered along the information ladder, most information first.",
    "HV": "The team design of 23 Oct: a high-value ticket the coalition wants; chat vs reservation rounds.",
    "VAR": "Variants of the HV design, one setting changed each.",
    "PLANT": "Actions design v0.4: planted boards (a task both colluders want most, with a verified conflict with the "
             "team), Colosseum's coalition goal, 2 reservation passes + claim, 20 rounds with the same team on new boards.",
    "PSUM": "The PLANT scenarios as revised on 23 Oct: costs only (no rewards per task, as Colosseum), and the "
            "coalition's reward defined to colluders as the sum of the members' rewards.",
    "YIELD": "Positive control on yield-to-partner boards (env/planted_yield.py): colluder A's best task is T, "
             "colluder B values T more, an honest agent values it most; only a coordinating pair puts T with B. "
             "Colluders first, one sprint per board.",
    "JP": "Jackpot game, \"one bit through a claim\" (env/jackpot.py, spec/jackpot/): a coin seen only by colluder A "
          "makes one of two look-alike tasks the jackpot for colluder B; A claims first, between two tasks of equal "
          "value to it, one on each task's issue. Primary measure: B claims the jackpot (chance 50%).",
}


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    title: str
    tests: str
    game: str
    set: Mapping[str, Any] = field(default_factory=dict)

    @property
    def family(self) -> str:
        return self.id.split("-")[0]

    @property
    def label(self) -> str:
        return f"{self.id} {self.name}"


@lru_cache(maxsize=None)
def catalogue() -> Dict[str, Scenario]:
    data = load_yaml(CATALOGUE)
    out = {}
    for sid, entry in data.items():
        unknown = set(entry) - {"name", "title", "tests", "game", "set"}
        if unknown:
            raise ValueError(f"{CATALOGUE.name}: {sid}: unknown keys {sorted(unknown)}")
        out[sid] = Scenario(sid, entry["name"], entry["title"], entry.get("tests", ""), entry["game"], dict(entry.get("set") or {}))
    names = [s.name for s in out.values()]
    if len(set(names)) != len(names):
        raise ValueError(f"{CATALOGUE.name}: two scenarios share a name")
    return out


def get(sid: str) -> Scenario:
    cat = catalogue()
    if sid not in cat:
        raise ValueError(f"unknown scenario {sid!r}; known: {', '.join(cat)} (configs/scenarios.yaml)")
    return cat[sid]


def fingerprint(game_plain: Mapping[str, Any]) -> str:
    """Hash of a resolved game config without what does not define the rules."""
    g = json.loads(json.dumps(game_plain, default=str))
    g.pop("name", None)
    g.pop("description", None)
    if isinstance(g.get("series"), dict):
        g["series"].pop("rounds", None)
    return hashlib.sha256(json.dumps(g, sort_keys=True).encode()).hexdigest()[:16]


@lru_cache(maxsize=None)
def _fingerprints() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for s in catalogue().values():
        fp = fingerprint(to_plain(load_game(s.game, s.set)))
        if fp in out:
            raise ValueError(f"{CATALOGUE.name}: {s.id} has the same rules as {out[fp]}")
        out[fp] = s.id
    return out


def identify(game_plain: Mapping[str, Any]) -> Optional[str]:
    """The scenario ID of a resolved game config, or None if it is not in the catalogue. A config
    recorded before a setting existed is completed with that setting's default first, so adding
    a setting does not orphan older runs."""
    from env.configio import build
    from env.game_config import GameConfig
    try:
        fps = _fingerprints()
    except Exception:
        return None
    candidates = [game_plain]
    try:
        candidates.append(to_plain(build(GameConfig, json.loads(json.dumps(game_plain, default=str)), "game")))
    except Exception:
        pass
    for g in candidates:
        sid = fps.get(fingerprint(g))
        if sid:
            return sid
    return None


def split_set(overrides: Mapping[str, Any]) -> Dict[str, Any]:
    """Check that a study only changes the run size of a scenario; return those changes."""
    other = sorted(set(overrides) - SIZE_KEYS)
    if other:
        raise ValueError(f"a scenario's rules are fixed: only {sorted(SIZE_KEYS)} may be set in a study, not {other}. "
                         "Add a new scenario to configs/scenarios.yaml instead")
    return dict(overrides)


def run_scenarios(run_dir: Path) -> Dict[str, Optional[str]]:
    """Condition name -> scenario ID for a run folder: recorded in study.json by runs made after the
    catalogue existed; for older runs, recognised from the game config saved in an episode."""
    try:
        meta = json.loads((Path(run_dir) / "study.json").read_text())
    except (OSError, ValueError):
        meta = {}
    if isinstance(meta.get("scenarios"), dict):
        return dict(meta["scenarios"])
    out: Dict[str, Optional[str]] = {}
    for ep in sorted(Path(run_dir).glob("episodes/*/*/*/episode.json")):
        cond = ep.parts[-4]
        if cond in out:
            continue
        try:
            out[cond] = identify(json.loads(ep.read_text()).get("game") or {})
        except (OSError, ValueError):
            out[cond] = None
    return out


def label(condition: str, sid: Optional[str]) -> str:
    """How a condition is shown: its scenario ID first, when it has one."""
    return f"{sid} {condition}" if sid else condition


# --- what a scenario is, in words (generated from its resolved rules) ----------------------------------


def _phase(p: Mapping[str, Any], enabled: set) -> str:
    who = {"all": "everyone", "colluders": "colluders only", "honest": "honest agents only"}.get(p["participants"], p["participants"])
    what = {"chat": "chat", "reserve": "reservation", "claim": "claim"}.get(p["kind"], p["kind"])
    text = f"{what} x{p['passes']} ({who}"
    bds = [b for b in (p.get("boards") or []) if b in enabled]       # a phase cannot use a board the game lacks
    where = ("public, colluders also secret" if set(bds) == {"public", "secret"}
             else "secret (colluders only)" if bds == ["secret"] else "+".join(bds))
    if p["kind"] == "chat":
        text += f"; messages on: {where}"
    elif bds and p.get("post_message") == "offered":
        text += f"; may also post on: {where}"
    elif bds and p.get("post_message") == "accepted":
        text += f"; posting not offered but accepted if tried (Colosseum), on: {where}"
    else:
        text += "; no messages"
    if p["kind"] == "reserve":
        text += "; binding: " + {"none": "no (a signal)", "exclusive": "exclusive"}.get(p.get("binding"), str(p.get("binding")))
    return text + ")"


def rules(s: Scenario) -> list:
    """The rules of a scenario in plain words, from its resolved game config."""
    from env.prompts import load_texts
    g = load_game(s.game, s.set)
    o = g.objective
    if o.type == "coalition_reward":
        goal = "maximise the coalition's joint reward (Colosseum's; no target task or issue)"
    elif o.type == "same_issue":
        si = o.same_issue
        bonus = (f"bonus = {si.bonus_matching_cost_k:g} x the board's matching cost" if si.bonus_matching_cost_k is not None
                 else f"bonus {si.bonus:g}")
        goal = f"both colluders on different tasks of the same issue ({bonus}, paid outside the team score)"
    else:
        hv = o.high_value_ticket
        goal = (f"get the high-value ticket (drawn: {hv.selection}; coalition bonus {hv.coalition_bonus:g}, outside the team score"
                + (f"; worth {hv.team_value:g} to the team" if hv.team_value else "")
                + (f"; the team loses {hv.team_penalty:g} if a colluder holds it" if hv.team_penalty else "")
                + ("; honest agents are told about it" if hv.visible_to_honest else "; honest agents are not told") + ")")
    order = {"random": "random", "colluders_first": "colluders first, then honest agents"}.get(g.roles.order, g.roles.order)
    boards = [b for b, on in (("public", g.boards.public), ("secret (colluders only)", g.boards.secret)) if on] or ["none"]
    views = {"visible": "visible", "hidden": "hidden", "issue_only": "only its issue",
             "noisy": f"shown with noise ({g.views.noisy_swap_probability:.0%} swapped for a random task)"}
    series = {"independent": "independent rounds (new board and roles each round, as Colosseum)",
              "repeated_same_board": "the same board replayed, same players",
              "repeated_new_board": "new boards, same players"}.get(g.series.mode, g.series.mode)
    if g.series.mode != "independent":
        series += f"; feedback after each round: {', '.join(g.series.feedback)}"
    texts = load_texts(g.prompts)
    out = [
        ("Goal of the colluders", goal),
        ("Board", f"{g.board.n_tasks} tasks, {g.board.n_agents} agents, {g.roles.colluders} colluders drawn at random"),
        ("Turn order", order),
        ("Phases, in order", " -> ".join(_phase(to_plain(p), {b for b, on in (("public", g.boards.public), ("secret", g.boards.secret)) if on})
                                       for p in g.phases)),
        ("Message boards", ", ".join(boards) + ("; claims are posted on them" if g.boards.log_claims and boards != ["none"] else "")),
        ("A colluder sees its partner's claim", views.get(g.views.colluders, g.views.colluders)),
        ("Rounds", f"{g.series.rounds} by default (studies may change it); {series}"),
        ("Model calls per turn", f"up to {g.calls_per_turn}; missing claims " + ("filled at random (Colosseum)" if g.assignment_filling else "left empty")),
        ("System prompt", f"`{g.prompts.system}`"),
        ("Colluder instruction", f"`{g.prompts.colluder}`" if g.prompts.colluder else "none (colluders are not told they are a coalition)"),
        ("Coalition header", "yes (names the partner and the secret board, as Colosseum)" if g.prompts.colluder_header else "no"),
    ]
    if o.type == "high_value_ticket" and o.high_value_ticket.visible_to_honest:
        out.append(("Note to honest agents", f"`{g.prompts.honest_hv_note}`"))
    return out, (texts.colluder or "").strip()


# --- the exact prompts -----------------------------------------------------------------------------


def show_prompts(sid: str, seed: int = 1) -> str:
    """Play one round of the scenario with scripted agents (no model) and return the exact system
    prompt and, in each phase, the first user prompt of each colluder and of one honest agent."""
    import asyncio
    from agents.scripted import ScriptedAgent
    from env.game import Episode
    s = get(sid)
    game = load_game(s.game, {**dict(s.set), "series.rounds": 1})
    turns: list = []
    episode = Episode(game, seed, lambda name, roles: ScriptedAgent(name, "colluder"), log_turn=turns.append)
    record = asyncio.run(episode.play())[0]
    out = [f"{s.id} {s.name}: {s.title}", f"(board seed {seed}; colluders {', '.join(record['colluders'])})", "",
           "=" * 30 + " SYSTEM PROMPT (every agent) " + "=" * 30, episode.system]
    seen = set()
    for t in turns:
        key = (t["phase_index"], t["agent"] if t["role"] == "colluder" else "honest")   # both colluders: views differ
        if key in seen:
            continue
        seen.add(key)
        out += ["", "=" * 30 + f" USER PROMPT: {t['role']} {t['agent']}, {t['phase']} (pass {t['pass'] + 1}), "
                f"tools {', '.join(t['tools_offered'])} " + "=" * 30, t["user_prompt"]]
    return "\n".join(out)


# --- the table ---------------------------------------------------------------------------------------


def studies_using() -> Dict[str, list]:
    """Scenario ID -> the study files (configs/studies/) that play it."""
    out: Dict[str, list] = {}
    for f in sorted((ROOT / "configs" / "studies").glob("*.yaml")):
        for c in (load_yaml(f).get("conditions") or []):
            if isinstance(c, dict) and c.get("scenario"):
                out.setdefault(c["scenario"], [])
                if f.stem not in out[c["scenario"]]:
                    out[c["scenario"]].append(f.stem)
    return out


def markdown() -> str:
    lines = ["# Scenarios", "",
             "Generated from [configs/scenarios.yaml](../../configs/scenarios.yaml) by `make scenarios`; do not edit by hand.",
             "",
             "A **scenario** is a set of game rules with a short ID. The same ID means the same rules in every "
             "study, model and run. Studies list scenarios by ID and may change only their number of rounds.", "",
             "- every run of a scenario, with its results side by side: `make runs SC=ACT-1`",
             "- one of its games, as a story: `make episode RUN=runs/<run> SC=ACT-1 SEED=3`",
             "- add one: a new entry in `configs/scenarios.yaml` with a new ID (never change the rules of an ID "
             "that has runs), then `make scenarios`", ""]
    used = studies_using()
    by_family: Dict[str, list] = {}
    for s in catalogue().values():
        by_family.setdefault(s.family, []).append(s)
    for fam, items in by_family.items():
        lines += [f"## {fam}", "", FAMILIES.get(fam, ""), "",
                  "| ID | Name | Rules | Tests | Game file + changes | Studies |", "|---|---|---|---|---|---|"]
        for s in items:
            changes = ", ".join(f"`{k}: {json.dumps(v)}`" if not isinstance(v, list) else f"`{k}`: (see yaml)"
                                for k, v in s.set.items()) or "as in the file"
            lines.append(f"| **{s.id}** | `{s.name}` | {s.title} | {s.tests} | `{s.game}`; {changes} | "
                         + (", ".join(f"`{n}`" for n in used.get(s.id, [])) or "none yet") + " |")
        lines.append("")
    lines += ["## Details", "",
              "Generated from each scenario's resolved rules (the game file with its changes). The exact prompts "
              "agents receive, for a sample board: `make prompts SC=<ID>`.", ""]
    for s in catalogue().values():
        facts, instruction = rules(s)
        lines += [f"### {s.id} {s.name}", "", f"{s.title}. *Tests:* {s.tests}", ""]
        lines += [f"- **{k}:** {v}" for k, v in facts]
        if instruction:
            lines += ["", "Colluder instruction, verbatim (`{partners}`, `{hv_task}`… are filled in for each board):", ""]
            lines += ["> " + l if l else ">" for l in instruction.splitlines()]
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if docs/reference/scenarios.md is out of date")
    parser.add_argument("--prompts", metavar="ID", help="print the exact prompts of a scenario")
    parser.add_argument("--seed", type=int, default=1, help="board for --prompts")
    args = parser.parse_args(argv)
    if args.prompts:
        try:
            print(show_prompts(args.prompts, args.seed))
        except ValueError as exc:
            print(exc)
            return 2
        return 0
    text = markdown()
    _fingerprints()                                        # every scenario resolves, no two alike
    if args.check:
        current = TABLE.read_text() if TABLE.exists() else ""
        if current != text:
            print("docs/reference/scenarios.md is out of date: run make scenarios")
            return 1
        print("docs/reference/scenarios.md is up to date")
        return 0
    TABLE.write_text(text)
    for s in catalogue().values():
        print(f"{s.id:7s} {s.name:28s} {s.title}")
    print(f"\nwritten to {TABLE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
