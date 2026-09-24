"""
Where everything the agent needs for one site lives, following the repo layout:

    sites/<site>/
        config.py            site settings (URL, users) - sent to the model
        pages/*.py           page objects - sent to the model, and the API it may use
        specs/*.md           agent input
        tests/*.py           hand-written tests - one is the style example
        tests/generated/     agent output
"""
from dataclasses import dataclass
from glob import glob
from pathlib import Path

from agent.config import AgentConfig


class SiteError(Exception):
    """The site does not exist or is missing what the agent needs."""


@dataclass(frozen=True)
class Site:
    name: str
    root: Path
    config_file: Path
    page_files: tuple
    specs_dir: Path
    generated_dir: Path
    style_example: Path

    @property
    def package(self) -> str:
        """Import path of the site, e.g. 'sites.saucedemo'."""
        return ".".join(self.root.parts)

    @property
    def allowed_imports(self) -> tuple:
        """What a generated test may import: test tools plus this site's config and pages only."""
        return ("pytest", "re", "playwright.sync_api", f"{self.package}.config", f"{self.package}.pages")

    def context_files(self) -> list:
        return [self.config_file, *self.page_files]

    def find_specs(self, patterns: list = None) -> list:
        """
        Spec files to process. With no patterns: every spec in the site's specs folder.
        Patterns are expanded here, not by the shell, because PowerShell does not expand *.md.
        """
        if not patterns:
            found = sorted(self.specs_dir.glob("*.md"))
        else:
            found = []
            for pattern in patterns:
                matches = sorted(Path(p) for p in glob(pattern))
                if not matches and not Path(pattern).parent.parts:
                    # A bare name like "cart_remove_items" or "cart_*.md" means the site's specs folder
                    name = pattern if pattern.endswith(".md") else f"{pattern}.md"
                    matches = sorted(self.specs_dir.glob(name))
                if not matches:
                    raise SiteError(f"No spec matches '{pattern}'")
                found.extend(matches)
        if not found:
            raise SiteError(f"No specs found in {self.specs_dir}")
        return [p.as_posix() for p in dict.fromkeys(found)]  # keep order, drop duplicates


def load_site(name: str, sites_dir: str = None, config=AgentConfig) -> Site:
    sites_dir = Path(sites_dir or config.SITES_DIR)
    root = sites_dir / name
    if not (root / "pages").is_dir() or not (root / "config.py").is_file():
        raise SiteError(
            f"'{name}' is not a site the agent can work on (needs {root}/config.py and {root}/pages/). "
            f"Sites that can: {', '.join(available_sites(sites_dir)) or 'none'}"
        )

    page_files = tuple(sorted(p for p in (root / "pages").glob("*.py") if p.name != "__init__.py"))
    if not page_files:
        raise SiteError(f"{root}/pages/ has no page objects")

    return Site(
        name=name,
        root=root,
        config_file=root / "config.py",
        page_files=page_files,
        specs_dir=root / "specs",
        generated_dir=root / "tests" / "generated",
        style_example=_style_example(name, root, config),
    )


def available_sites(sites_dir: Path) -> list:
    return sorted(
        p.name for p in Path(sites_dir).iterdir()
        if (p / "pages").is_dir() and (p / "config.py").is_file()
    ) if Path(sites_dir).is_dir() else []


def _style_example(name: str, root: Path, config) -> Path:
    configured = config.STYLE_EXAMPLES.get(name)
    if configured:
        return Path(configured)
    hand_written = [p for p in (root / "tests").glob("test_*.py")]
    if not hand_written:
        raise SiteError(f"{root}/tests/ has no hand-written test to use as a style example")
    return max(hand_written, key=lambda p: p.stat().st_size)
