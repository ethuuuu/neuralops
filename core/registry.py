"""Loads config.yaml. The only place that knows what models exist."""
import yaml
from pathlib import Path

_cfg = None


ROOT = Path(__file__).resolve().parent.parent


def load(path=None):
    """Config is resolved relative to the project root, not the caller's cwd."""
    global _cfg
    if _cfg is None:
        _cfg = yaml.safe_load(Path(path or ROOT / "config.yaml").read_text())
    return _cfg


def models():
    return {m["id"]: m for m in load()["models"]}


def model(model_id):
    return models()[model_id]


def embeddings_cfg():
    return load()["embeddings"]


def routing_cfg():
    return load()["routing"]


def get(section, default=None):
    return load().get(section, default)
