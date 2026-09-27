"""Guards against configuration drift between files that must agree.

Both checks encode a real incident or near miss: the ClickHouse patch on the
user's machine differed from the one tests ran on (ADR 0005, Day 5 review), and
settings added in code were easy to forget in ``.env.example``.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic_settings import BaseSettings

from tsetmc_viewer.config import Settings

ROOT = Path(__file__).resolve().parent.parent
IMAGE = re.compile(
    r"\b((?:clickhouse/clickhouse-server|prom/prometheus|prom/alertmanager):[\w.\-]+)"
)


def test_ci_tests_on_the_images_compose_runs() -> None:
    """CI checks configs and runs tests with exactly the versions the stack ships."""
    shipped = set(IMAGE.findall((ROOT / "docker/config.Dockerfile").read_text()))
    ci = set(IMAGE.findall((ROOT / ".github/workflows/ci.yml").read_text()))
    assert len(shipped) == 3
    assert ci == shipped


def _env_names(model: type[BaseSettings], prefix: str = "") -> set[str]:
    names: set[str] = set()
    prefix = prefix or str(model.model_config.get("env_prefix", ""))
    for name, field in model.model_fields.items():
        nested = field.annotation
        if isinstance(nested, type) and issubclass(nested, BaseSettings):
            names |= _env_names(nested)  # nested settings read their own prefix
        else:
            names.add(f"{prefix}{name}".upper())
    return names


def test_every_setting_is_documented_in_env_example() -> None:
    text = (ROOT / ".env.example").read_text()
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, flags=re.MULTILINE))
    missing = _env_names(Settings) - documented
    assert not missing, f"add to .env.example (commented out if advanced): {sorted(missing)}"
