"""Agents: LLMs through an OpenAI-compatible API (agents/llm.py) or scripted policies (agents/scripted.py)."""

import dataclasses
import os
from pathlib import Path
from typing import Any, Mapping, Union

from env.configio import build, load_yaml


def load_model(source: Union[str, Path, Mapping[str, Any]]):
    from agents.llm import ModelConfig
    data = dict(source) if isinstance(source, Mapping) else load_yaml(source)
    cfg = build(ModelConfig, data, "model")
    if cfg.base_url_env and os.environ.get(cfg.base_url_env):     # each person's own server (e.g. Modal)
        cfg = dataclasses.replace(cfg, base_url=os.environ[cfg.base_url_env].rstrip("/"))
    return cfg
