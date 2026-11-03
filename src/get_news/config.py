"""Configuration: settings.yaml and sources.yaml from the project root, plus environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import yaml

CONFIG_DIR = Path(os.environ.get("GET_NEWS_CONFIG_DIR", Path(__file__).resolve().parents[2]))


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    name: str
    category: str
    url: str
    enabled: bool = True


@dataclass(frozen=True)
class Webhooks:
    digest: str | None
    hot: str | None
    ops: str | None


@dataclass(frozen=True)
class Config:
    settings: SimpleNamespace
    sources: list[Source]
    project: str
    location: str
    webhooks: Webhooks

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.settings.timezone)


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_namespace(item) for item in value]
    return value


def load_settings(config_dir: Path = CONFIG_DIR) -> SimpleNamespace:
    return _namespace(yaml.safe_load((config_dir / "settings.yaml").read_text(encoding="utf-8")))


def load_sources(config_dir: Path = CONFIG_DIR) -> list[Source]:
    raw = yaml.safe_load((config_dir / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    return [source for source in (Source(**item) for item in raw) if source.enabled]


def load_config(config_dir: Path = CONFIG_DIR) -> Config:
    project = os.environ.get("GCP_PROJECT")
    if not project:
        raise RuntimeError("GCP_PROJECT is not set")
    return Config(
        settings=load_settings(config_dir),
        sources=load_sources(config_dir),
        project=project,
        location=os.environ.get("GCP_LOCATION", "global"),
        webhooks=Webhooks(
            digest=os.environ.get("DISCORD_WEBHOOK_DIGEST") or None,
            hot=os.environ.get("DISCORD_WEBHOOK_HOT") or None,
            ops=os.environ.get("DISCORD_WEBHOOK_OPS") or None,
        ),
    )
