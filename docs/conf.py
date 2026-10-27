"""Build from a checkout without importing setup.py or the application."""

import ast
from pathlib import Path

project = "pyramid_session_redis"
author = "Jonathan Vanasco and contributors"

package_root = Path(__file__).resolve().parents[1] / "src"
source = package_root / "pyramid_session_redis" / "__init__.py"
for statement in ast.parse(source.read_text(encoding="utf-8")).body:
    if isinstance(statement, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "__VERSION__"
        for target in statement.targets
    ):
        release = ast.literal_eval(statement.value)
        break
else:
    raise RuntimeError("Cannot find the package version")

version = release
extensions = []
root_doc = "index"
exclude_patterns = ["_build"]
html_theme = "alabaster"
nitpicky = True
