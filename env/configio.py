"""Reading configs: YAML files, inheritance, dotted overrides, strict conversion to dataclasses.

A config file may start with `extends: <path>` (relative to the file): its keys are merged over
the parent's. A study can change single keys with dotted paths, e.g. `{"views.colluders": "hidden"}`.
Conversion into the dataclasses is strict: an unknown key is an error, so a typo never silently
falls back to a default.
"""

from __future__ import annotations

import copy
import dataclasses
import typing
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

import yaml

ROOT = Path(__file__).resolve().parent.parent


def resolve_path(path: Union[str, Path], base: Optional[Path] = None) -> Path:
    """Paths in configs are relative to the repository root unless they start with ./ or ../
    (then relative to the file that contains them)."""
    p = Path(path)
    if p.is_absolute():
        return p
    if base is not None and str(path).startswith(("./", "../")):
        return (base / p).resolve()
    return (ROOT / p).resolve()


def deep_merge(base: Dict[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    """Load a YAML mapping, following `extends:` chains."""
    path = resolve_path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    parent = data.pop("extends", None)
    if parent:
        data = deep_merge(load_yaml(resolve_path(parent, path.parent)), data)
    return data


def apply_set(data: Dict[str, Any], overrides: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Apply dotted-key overrides: {"views.colluders": "hidden"}."""
    out = copy.deepcopy(data)
    for dotted, value in (overrides or {}).items():
        node = out
        parts = str(dotted).split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise ValueError(f"override {dotted!r}: {part!r} is not a mapping")
        node[parts[-1]] = copy.deepcopy(value)
    return out


def build(cls: Any, data: Any, where: str = "") -> Any:
    """Strictly convert plain data into dataclass `cls` (nested dataclasses, tuples, mappings)."""
    if data is None:
        return cls()
    if dataclasses.is_dataclass(cls):
        if not isinstance(data, Mapping):
            raise ValueError(f"{where or cls.__name__}: expected a mapping, got {type(data).__name__}")
        hints = typing.get_type_hints(cls)
        known = {f.name for f in dataclasses.fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"{where or cls.__name__}: unknown keys {unknown}; known keys: {sorted(known)}")
        values = {k: _convert(hints[k], v, f"{where}.{k}".strip(".")) for k, v in data.items()}
        return cls(**values)
    return data


def _convert(tp: Any, value: Any, where: str) -> Any:
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is Union:                                   # Optional[X]
        non_none = [a for a in args if a is not type(None)]
        if value is None:
            return None
        return _convert(non_none[0], value, where) if len(non_none) == 1 else value
    if dataclasses.is_dataclass(tp):
        return build(tp, value, where)
    if origin in (tuple, typing.Tuple):
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"{where}: expected a list")
        item = args[0] if args and (len(args) == 2 and args[1] is Ellipsis) else None
        if item is not None:
            return tuple(_convert(item, v, f"{where}[{i}]") for i, v in enumerate(value))
        if args and len(args) == len(value):
            return tuple(_convert(a, v, f"{where}[{i}]") for i, (a, v) in enumerate(zip(args, value)))
        return tuple(value)
    if origin in (dict, Mapping, typing.Mapping) or tp in (dict, Mapping):
        if not isinstance(value, Mapping):
            raise ValueError(f"{where}: expected a mapping")
        return dict(value)
    if tp is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    return value


def to_plain(obj: Any) -> Any:
    """Dataclasses -> plain JSON-friendly data (for logging the exact config used)."""
    if dataclasses.is_dataclass(obj):
        return {f.name: to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Mapping):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    return obj
