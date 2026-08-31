import re
from importlib.metadata import distributions, metadata, version
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOTS = ["PySide6", "SQLAlchemy", "alembic"]
DEV_ROOTS = ["pytest", "ruff"]

HEADER = """# Exact versions the application was built and tested against.
#
# pyproject.toml says which libraries the application needs; this file says which
# builds of them. Without it a fresh install takes whatever PyPI happens to be serving
# that day, which is how a machine ends up running code nobody here ever tested.
#
#     pip install -r requirements.txt -e .
#
# Regenerate after changing a dependency, from an environment that has them installed:
#
#     python tools/lock.py
#
# Hashes are the step up from this: pip-compile --generate-hashes, or uv lock. Both pin
# every platform's wheel, rather than only the one that happens to be installed here.
"""

DEV_HEADER = """# Everything in requirements.txt, plus what the tests and the linter need.
-r requirements.txt
"""


def key(name: str) -> str:
    """PEP 503 normalisation: 'typing_extensions' and 'typing-extensions' are one name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_names() -> dict[str, str]:
    return {key(dist.metadata["Name"]): dist.metadata["Name"] for dist in distributions()}


def closure(roots: list[str], installed: dict[str, str]) -> set[str]:
    """Every package those roots drag in, as actually installed."""
    seen: set[str] = set()
    queue = list(roots)
    while queue:
        name = key(queue.pop())
        if name in seen or name not in installed:
            continue
        seen.add(name)
        for raw in metadata(installed[name]).get_all("Requires-Dist") or []:
            requirement = Requirement(raw)
            # Extras are not installed, so they are not part of the closure.
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue
            queue.append(requirement.name)
    return seen


def render(names: set[str], installed: dict[str, str]) -> str:
    return "\n".join(f"{installed[name]}=={version(installed[name])}" for name in sorted(names))


def main() -> None:
    installed = installed_names()
    runtime = closure(RUNTIME_ROOTS, installed)
    dev = closure(DEV_ROOTS, installed) - runtime

    (ROOT / "requirements.txt").write_text(
        f"{HEADER}\n{render(runtime, installed)}\n", encoding="utf-8"
    )
    (ROOT / "requirements-dev.txt").write_text(
        f"{DEV_HEADER}\n{render(dev, installed)}\n", encoding="utf-8"
    )
    print(f"Zapisano {len(runtime)} zależności aplikacji i {len(dev)} narzędzi.")


if __name__ == "__main__":
    main()
