from pathlib import Path

from omegaconf import OmegaConf


def test_production_config_is_not_silently_limited_to_debug_candidates(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)
    example = OmegaConf.load(Path(__file__).parents[1] / "config/robotics-deepseek.example.yaml")
    assert example.executor.debug is False
    monkeypatch.setenv("DEBUG", "true")
    assert example.executor.debug is True
