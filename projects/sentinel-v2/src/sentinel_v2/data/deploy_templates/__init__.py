"""Deploy templates for fly.io — Dockerfile + fly.toml per stack."""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).parent


def load_templates() -> str:
    """Return a formatted string with all deploy templates for prompt injection."""
    sections: list[str] = []
    for stack_dir in sorted(_DIR.iterdir()):
        if not stack_dir.is_dir() or stack_dir.name.startswith("_"):
            continue
        dockerfile = stack_dir / "Dockerfile"
        flytoml = stack_dir / "fly.toml"
        if not dockerfile.exists() or not flytoml.exists():
            continue
        label = stack_dir.name.replace("_", " ").title()
        sections.append(
            f"### {label}\n\n"
            f"**Dockerfile:**\n```dockerfile\n{dockerfile.read_text()}\n```\n\n"
            f"**fly.toml:**\n```toml\n{flytoml.read_text()}\n```"
        )
    return "\n\n".join(sections)
