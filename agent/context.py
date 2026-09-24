"""
Builds what the agent knows about the framework:

- the source of one site's page objects and config (sent to the model as context)
- those page objects' public API (used to catch hallucinated methods)
"""
import ast
from pathlib import Path

from agent.site import Site


def build_context(site: Site) -> str:
    """Source of the site's config and page objects, formatted for the prompt."""
    parts = [
        f"# Site under test: {site.name}\n",
        f"Import these files as modules under `{site.package}`, "
        f"e.g. `from {site.package}.pages.<module> import <Class>` and `from {site.package}.config import Config`.\n",
        "# Framework files you can import and use\n",
    ]
    for path in site.context_files():
        parts.append(_file_block(path))
    parts.append("# Style reference - an existing hand-written test file\n")
    parts.append(_file_block(site.style_example))
    return "\n".join(parts)


def _file_block(path: Path) -> str:
    return f"## {Path(path).as_posix()}\n```python\n{Path(path).read_text(encoding='utf-8')}\n```\n"


def page_object_api(site: Site) -> dict:
    """
    Map each page object class to the names a test may use on it:
    its methods plus the attributes set in __init__ (locators).

        {"LoginPage": {"navigate", "login", "error_message", ...}, ...}
    """
    api = {}
    for path in site.page_files:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                api[node.name] = _public_members(node)
    return api


def _public_members(class_node: ast.ClassDef) -> set:
    members = set()
    for item in class_node.body:
        if isinstance(item, ast.Assign):  # class attributes like URL
            members.update(t.id for t in item.targets if isinstance(t, ast.Name))
        if not isinstance(item, ast.FunctionDef):
            continue
        if not item.name.startswith("_"):
            members.add(item.name)
        if item.name == "__init__":
            for sub in ast.walk(item):  # self.xxx = ... inside __init__
                if isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Store):
                    if isinstance(sub.value, ast.Name) and sub.value.id == "self":
                        members.add(sub.attr)
    return members
