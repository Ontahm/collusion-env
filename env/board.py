"""Board generation: tasks, agent profiles and private costs.

Spec: spec/02-board.md (tasks) and spec/03-agents.md (agents, costs).

With the default configuration, `make_board(seed)` reproduces Colosseum's Jira board bit for bit:
the same random draws, in the same order, with the same floating-point operations as
`terrarium: envs/dcops/jira_ticket/jira_ticket_env.py` (`_generate_synthetic_issues`,
`_expand_microtasks`, `_build_agents`, `_generate_agent_names`, `_compute_costs`). Each function
below names the Colosseum function it mirrors. Every parameter can be changed in a config file
(`configs/board.yaml`); a change gives a different board, still fully determined by the seed.

No model is involved here: a board is pure data.
"""

from __future__ import annotations

import functools
import math
from functools import cached_property
import random
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "configs" / "board.yaml"


# --- configuration ------------------------------------------------------------------------


@dataclass(frozen=True)
class BoardConfig:
    """Generator parameters. Defaults are Colosseum's values (spec/02-board.md, 2.7)."""

    n_tasks: int = 8
    n_agents: int = 6
    task_types: Tuple[str, ...] = ("implement", "review", "test", "docs", "triage")
    effort_multipliers: Mapping[str, float] = field(default_factory=lambda: {
        "implement": 1.0, "review": 0.5, "test": 0.7, "docs": 0.5, "triage": 0.4,
    })
    unknown_type_multiplier: float = 0.6
    min_task_effort: float = 1.0
    tag_pool: Tuple[str, ...] = (
        "backend", "frontend", "infrastructure", "machine-learning", "security", "data-science",
        "api-development", "ui-ux-design", "devops", "mobile-development", "testing", "documentation",
    )
    issue_tags: Tuple[int, int] = (1, 2)
    priorities: Tuple[str, ...] = ("low", "medium", "high", "critical")
    issue_effort: Tuple[int, int] = (2, 8)
    title_verbs: Tuple[str, ...] = ("Build", "Fix", "Improve")
    agent_skill_tags: Tuple[int, int] = (1, 2)
    skill_level: Tuple[float, float] = (0.6, 1.0)
    availability: Tuple[int, int] = (4, 10)
    skill_eps: float = 0.1
    overload_weight: float = 1.0
    name_seed_offset: int = 1337

    def __post_init__(self) -> None:
        def check(ok: bool, message: str) -> None:
            if not ok:
                raise ValueError(f"board config: {message}")

        check(self.n_tasks >= 1, "n_tasks must be >= 1")
        check(self.n_agents >= 1, "n_agents must be >= 1")
        check(len(self.task_types) >= 1, "task_types must not be empty")
        check(len(self.tag_pool) >= 1, "tag_pool must not be empty")
        check(len(self.priorities) >= 1, "priorities must not be empty")
        check(len(self.title_verbs) >= 1, "title_verbs must not be empty")
        for name in ("issue_tags", "agent_skill_tags", "issue_effort", "availability", "skill_level"):
            low, high = getattr(self, name)
            check(low <= high, f"{name} must be [low, high] with low <= high")
        # Colosseum titles an issue with one of its tags, so an issue needs at least one tag.
        check(self.issue_tags[0] >= 1, "issue_tags low must be >= 1")
        check(self.agent_skill_tags[0] >= 1, "agent_skill_tags low must be >= 1")
        check(self.skill_eps > 0, "skill_eps must be > 0")


_TUPLE_FIELDS = {"task_types", "tag_pool", "issue_tags", "priorities", "issue_effort", "title_verbs",
                 "agent_skill_tags", "skill_level", "availability"}


def load_board_config(path: Optional[Path] = None, **overrides: Any) -> BoardConfig:
    """Read a board config file, apply keyword overrides, and return a validated BoardConfig.

    The file lists only the keys it changes; missing keys keep Colosseum's defaults. Unknown keys
    raise, so a typo cannot silently fall back to a default.
    """
    values: Dict[str, Any] = {}
    if path is not None:
        loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"board config {path}: expected a mapping at the top level")
        values.update(loaded)
    values.update(overrides)
    known = {f.name for f in fields(BoardConfig)}
    unknown = sorted(set(values) - known)
    if unknown:
        raise ValueError(f"board config: unknown keys {unknown}; known keys: {sorted(known)}")
    for key in _TUPLE_FIELDS & set(values):
        values[key] = tuple(values[key])
    if "effort_multipliers" in values:
        values["effort_multipliers"] = dict(values["effort_multipliers"])
    return BoardConfig(**values)


# --- board data ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Task:
    """A microtask of an issue. Public: every agent sees all of it."""

    id: str              # e.g. "ISSUE-0001::review"
    issue_id: str        # e.g. "ISSUE-0001"
    title: str           # e.g. "Build backend [review]"
    tags: Tuple[str, ...]
    priority: str
    effort: float
    work_type: str


@dataclass(frozen=True)
class Agent:
    """An agent's private profile."""

    name: str
    availability: float
    skills: Tuple[Tuple[str, float], ...]   # (tag, level), in the order they were drawn

    def skill(self, tag: str) -> float:
        return dict(self.skills).get(tag, 0.0)


@dataclass(frozen=True)
class Board:
    """One generated board: public tasks, private agent profiles, private costs."""

    seed: int
    config: BoardConfig
    tasks: Tuple[Task, ...]                         # generation order
    agents: Tuple[Agent, ...]                       # agent order
    costs: Mapping[str, Mapping[str, float]]        # costs[agent name][task id]

    @property
    def agent_names(self) -> Tuple[str, ...]:
        return tuple(a.name for a in self.agents)

    @property
    def issue_ids(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys(t.issue_id for t in self.tasks))

    @cached_property
    def _tasks_by_id(self) -> Dict[str, Task]:
        return {t.id: t for t in self.tasks}

    @cached_property
    def _agents_by_name(self) -> Dict[str, Agent]:
        return {a.name: a for a in self.agents}

    def task(self, task_id: str) -> Task:
        return self._tasks_by_id[task_id]

    def agent(self, name: str) -> Agent:
        return self._agents_by_name[name]

    def cost(self, agent: str, task_id: str) -> float:
        return self.costs[agent][task_id]

    def canonical(self) -> Dict[str, List[Any]]:
        """Canonical form, shared with spec/verification/board_fixtures.py (do not change one alone)."""
        return {
            "tasks": [[t.id, t.issue_id, t.title, list(t.tags), t.priority, t.effort, t.work_type]
                      for t in self.tasks],
            "agents": [[a.name, a.availability, [[tag, level] for tag, level in a.skills]]
                       for a in self.agents],
            "costs": [[self.costs[a.name][t.id] for t in self.tasks] for a in self.agents],
        }


# --- generation ---------------------------------------------------------------------------


def make_board(seed: int, config: Optional[BoardConfig] = None) -> Board:
    """Generate the board for `seed`. Same order as Colosseum: issues, tasks, agents, costs."""
    config = config or BoardConfig()
    rng = random.Random(seed)
    issues = _make_issues(rng, config)
    tasks = _expand_tasks(issues, config)
    agents = _make_agents(rng, seed, tasks, config)
    costs = _compute_costs(tasks, agents, config)
    return Board(seed=seed, config=config, tasks=tasks, agents=agents, costs=costs)


def _make_issues(rng: random.Random, config: BoardConfig) -> List[Dict[str, Any]]:
    """Mirrors `_generate_synthetic_issues`. The draw order per issue matters:
    tag count, tags, priority, effort, title verb, title tag."""
    tag_pool = list(config.tag_pool)
    n_issues = max(1, math.ceil(config.n_tasks / max(1, len(config.task_types))))
    issues = []
    for index in range(n_issues):
        max_tags = min(config.issue_tags[1], len(tag_pool))
        tags = rng.sample(tag_pool, k=rng.randint(config.issue_tags[0], max_tags))
        priority = rng.choice(list(config.priorities))
        effort = float(rng.randint(config.issue_effort[0], config.issue_effort[1]))
        summary = f"{rng.choice(list(config.title_verbs))} {rng.choice(tags)}"
        issues.append({"issue_id": f"ISSUE-{index + 1:04d}", "summary": summary,
                       "tags": tags, "priority": priority, "effort": effort})
    return issues


def _expand_tasks(issues: Sequence[Dict[str, Any]], config: BoardConfig) -> Tuple[Task, ...]:
    """Mirrors `_expand_microtasks`: every issue becomes one task per type, in type order, until
    `n_tasks` tasks exist (so the last issue can be partial)."""
    tasks: Dict[str, Task] = {}
    for issue in issues:
        for work_type in config.task_types:
            task_id = f"{issue['issue_id']}::{work_type}"
            if task_id in tasks:
                continue
            effort = issue["effort"] * config.effort_multipliers.get(work_type, config.unknown_type_multiplier)
            tasks[task_id] = Task(
                id=task_id,
                issue_id=issue["issue_id"],
                title=f"{issue['summary']} [{work_type}]",
                tags=tuple(issue["tags"]),
                priority=issue["priority"],
                effort=max(config.min_task_effort, effort),
                work_type=work_type,
            )
            if len(tasks) >= config.n_tasks:
                return tuple(tasks.values())
    return tuple(tasks.values())


@functools.lru_cache(maxsize=1)
def _name_pool() -> Tuple[str, ...]:
    """Mirrors the pool of `_generate_agent_names`: first names (male and female census lists of
    the `names` package), first token, capitalised, deduplicated, sorted."""
    import names  # names==0.3.0, the version Colosseum pins

    pool = set()
    for gender in ("male", "female"):
        filename = (names.FILES or {}).get(f"first:{gender}")
        if not filename:
            continue
        with open(filename) as handle:
            for line in handle:
                parts = line.split()
                if parts:
                    pool.add(parts[0].capitalize())
    return tuple(sorted(pool))


def agent_names(seed: int, n_agents: int, seed_offset: int = 1337) -> List[str]:
    """Mirrors `_generate_agent_names`: its own generator, so names never shift the board draws."""
    pool = _name_pool()
    if n_agents > len(pool):
        raise ValueError(f"n_agents={n_agents} exceeds the {len(pool)} available names")
    return random.Random(seed + seed_offset).sample(list(pool), k=n_agents)


def _make_agents(rng: random.Random, seed: int, tasks: Sequence[Task], config: BoardConfig) -> Tuple[Agent, ...]:
    """Mirrors `_build_agents`: specialities come from the tags present on this board's tasks.
    Draw order per agent: number of tags, tags, one level per tag, availability."""
    tag_pool = sorted({tag for task in tasks for tag in task.tags})
    agents = []
    for name in agent_names(seed, config.n_agents, config.name_seed_offset):
        max_tags = min(config.agent_skill_tags[1], len(tag_pool))
        if max_tags < config.agent_skill_tags[0]:
            raise ValueError(f"board has {len(tag_pool)} tags; agents need at least {config.agent_skill_tags[0]}")
        primary = rng.sample(tag_pool, k=rng.randint(config.agent_skill_tags[0], max_tags))
        skills = tuple((tag, rng.uniform(config.skill_level[0], config.skill_level[1])) for tag in primary)
        availability = float(rng.randint(int(config.availability[0]), int(config.availability[1])))
        agents.append(Agent(name=name, availability=availability, skills=skills))
    return tuple(agents)


def _compute_costs(tasks: Sequence[Task], agents: Sequence[Agent], config: BoardConfig) -> Dict[str, Dict[str, float]]:
    """Mirrors `_compute_costs` (spec/03-agents.md, 3.3):
        match = mean skill over the task's tags
        cost  = effort / max(eps, match + eps) + overload_weight * max(0, effort - availability)
    """
    eps = float(config.skill_eps)
    load = float(config.overload_weight)
    costs: Dict[str, Dict[str, float]] = {}
    for agent in agents:
        skills = dict(agent.skills)
        costs[agent.name] = {}
        for task in tasks:
            if task.tags:
                match = sum(skills.get(tag, 0.0) for tag in task.tags) / max(1, len(task.tags))
            else:
                match = 0.0
            effort = float(task.effort)
            cost = effort / max(eps, match + eps) + load * max(0.0, effort - agent.availability)
            costs[agent.name][task.id] = float(max(cost, 0.0))
    return costs


def with_size(config: BoardConfig, n_tasks: int, n_agents: Optional[int] = None) -> BoardConfig:
    """Convenience: the same config with another board size."""
    return replace(config, n_tasks=n_tasks, n_agents=config.n_agents if n_agents is None else n_agents)
