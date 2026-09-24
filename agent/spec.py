"""
Loads a spec file. A spec is plain markdown with a title and a list of
acceptance criteria, each with an ID the generated tests must reference:

    # Checkout: required customer fields
    - AC-1: Continuing with an empty last name shows "Error: Last Name is required"
    - AC-2: ...

The IDs are what lets us check coverage without trusting the model's word.
"""
import re
from dataclasses import dataclass
from pathlib import Path

CRITERION_PATTERN = re.compile(r"^\s*[-*]\s*(AC-\d+)\s*:\s*(.+)$", re.MULTILINE)


@dataclass
class Spec:
    name: str          # file stem, used for the generated file name
    path: str
    title: str
    text: str          # the full markdown, sent to the model as-is
    criteria: dict     # {"AC-1": "Continuing with an empty ..."}


def load_spec(path: str) -> Spec:
    file = Path(path)
    text = file.read_text(encoding="utf-8")

    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else file.stem

    criteria = {cid: desc.strip() for cid, desc in CRITERION_PATTERN.findall(text)}
    if not criteria:
        raise ValueError(f"{path}: no acceptance criteria found (expected lines like '- AC-1: ...')")

    name = re.sub(r"[^a-z0-9_]", "_", file.stem.lower())
    return Spec(name=name, path=file.as_posix(), title=title, text=text, criteria=criteria)
