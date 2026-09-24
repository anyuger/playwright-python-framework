"""
Settings for the spec-to-test agent.

Site-specific paths (page objects, specs, where generated tests go) are not
set here: they follow the sites/<site>/ layout and are worked out in site.py.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # ANTHROPIC_API_KEY and the overrides below can live in .env


class AgentConfig:

    # Models: primary does the work, fallback is used when the primary is
    # unavailable (overloaded, rate limited, retired) after all retries.
    PRIMARY_MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-5")
    FALLBACK_MODEL = os.getenv("AGENT_FALLBACK_MODEL", "claude-haiku-4-5-20251001")
    MAX_TOKENS = 8000

    # Reliability
    MAX_RETRIES = 3               # attempts per model on transient errors
    BACKOFF_BASE_SECONDS = 2      # waits 2s, 4s, 8s ... plus a little jitter
    REQUEST_TIMEOUT_SECONDS = 120

    # Self-healing: how many times the agent may repair its own tests
    MAX_REPAIR_ATTEMPTS = int(os.getenv("AGENT_MAX_REPAIRS", "2"))

    # Generated files may already have been reviewed and edited by a human, so an
    # existing file is kept and the new version goes to the run folder instead.
    # --overwrite on the command line turns this on for one run.
    OVERWRITE_GENERATED = False

    # Cost control: the run stops before any call once this is spent
    MAX_RUN_COST_USD = float(os.getenv("AGENT_MAX_COST_USD", "1.00"))

    # USD per million tokens, from the Claude pricing page (Sep 2026).
    # Keys: input, output, cache_write (5 min), cache_read
    PRICING = {
        "claude-sonnet-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.20},
        "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
        "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.10},
    }

    # Where the sites live, and where run reports go (not committed)
    SITES_DIR = "sites"
    RUNS_DIR = "agent_runs"

    # The hand-written test the model copies the style of, per site.
    # A site not listed here uses its largest hand-written test file.
    STYLE_EXAMPLES = {
        "saucedemo": "sites/saucedemo/tests/test_checkout.py",
    }
