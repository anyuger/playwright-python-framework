"""
Test tags for saucedemo.

Every test in this folder is tagged `regression` automatically, including the ones the
spec-to-test agent generates, so nobody has to remember the tag. `smoke` is chosen by a
person, test by test, with @pytest.mark.smoke.

    pytest -m smoke                       critical path only
    pytest -m regression                  everything tagged regression (smoke included)
    pytest sites/saucedemo -m "not smoke" regression without the smoke tests
"""
from pathlib import Path

import pytest

SITE_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    # This hook sees every collected test in the run, so only tag the ones in this folder
    for item in items:
        if SITE_DIR in item.path.parents:
            item.add_marker(pytest.mark.regression)
