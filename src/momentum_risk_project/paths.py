"""Resolve every operational path relative to an explicit project root."""
from pathlib import Path
import os


def project_root(root=None):
    if root is not None:
        return Path(root).expanduser().resolve()
    if os.environ.get("MOMENTUM_PROJECT_ROOT"):
        return Path(os.environ["MOMENTUM_PROJECT_ROOT"]).expanduser().resolve()
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        for candidate in (base, *base.parents):
            if (candidate / "pyproject.toml").is_file() and (candidate / "configs/config.yaml").is_file():
                return candidate
    raise FileNotFoundError("Run inside the repository or set MOMENTUM_PROJECT_ROOT")


def project_path(value, root=None):
    value=Path(value)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("Configured paths must stay relative to the project root")
    base=project_root(root)
    path=base/value
    if not path.resolve().is_relative_to(base):
        raise ValueError("Configured path escapes project root")
    return path
