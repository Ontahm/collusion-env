"""Agents: LLMs through an OpenAI-compatible API (agents/llm.py) or scripted policies (agents/scripted.py)."""

from pathlib import Path
from typing import Any, Mapping, Union

from env.configio import build, load_yaml


def load_model(source: Union[str, Path, Mapping[str, Any]]):
    from agents.llm import ModelConfig
    data = dict(source) if isinstance(source, Mapping) else load_yaml(source)
    return build(ModelConfig, data, "model")
