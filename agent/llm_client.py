"""
Thin wrapper around the Anthropic API that adds the production concerns
the agent needs:

- retries with exponential backoff on transient errors (429, 5xx, 529, network)
- fallback to a second model when the primary stays unavailable
- a hard cost budget per run
- a record of every call: model, tokens, cache hits, latency, cost

Retries are done here instead of inside the SDK (max_retries=0) so that every
attempt is logged and counted.
"""
import logging
import random
import time
from dataclasses import dataclass, asdict

import anthropic

from agent.config import AgentConfig

logger = logging.getLogger(__name__)

# HTTP status codes worth retrying: rate limit, server errors, overloaded
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 529}


class BudgetExceededError(Exception):
    """Raised before a call when the run has already spent its budget."""


class LLMUnavailableError(Exception):
    """Raised when both the primary and the fallback model failed."""


@dataclass
class CallRecord:
    purpose: str
    model: str
    attempt: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    latency_seconds: float
    cost_usd: float

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_cost(model: str, usage, pricing: dict = None) -> float:
    """Cost of one call in USD. Unknown models are priced as 0 with a warning."""
    pricing = pricing or AgentConfig.PRICING
    prices = pricing.get(model)
    if prices is None:
        logger.warning(f"No pricing for model '{model}', cost recorded as 0")
        return 0.0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cost = (
        usage.input_tokens * prices["input"]
        + usage.output_tokens * prices["output"]
        + cache_write * prices["cache_write"]
        + cache_read * prices["cache_read"]
    ) / 1_000_000
    return round(cost, 6)


class LLMClient:

    def __init__(self, client=None, config=AgentConfig, sleep=time.sleep):
        # client and sleep can be swapped for fakes in unit tests
        self.client = client or anthropic.Anthropic(
            max_retries=0, timeout=config.REQUEST_TIMEOUT_SECONDS
        )
        self.config = config
        self.sleep = sleep
        self.calls: list[CallRecord] = []

    @property
    def total_cost(self) -> float:
        return round(sum(c.cost_usd for c in self.calls), 6)

    def create_message(self, purpose: str, **request):
        """
        Send one Messages API request (system, messages, tools, ...).
        Tries the primary model, then the fallback. Returns the response.
        """
        if self.total_cost >= self.config.MAX_RUN_COST_USD:
            raise BudgetExceededError(
                f"Run budget ${self.config.MAX_RUN_COST_USD:.2f} reached "
                f"(spent ${self.total_cost:.4f}); stopping before '{purpose}'"
            )

        models = [self.config.PRIMARY_MODEL, self.config.FALLBACK_MODEL]
        last_error = None

        for model in models:
            for attempt in range(1, self.config.MAX_RETRIES + 1):
                start = time.perf_counter()
                try:
                    response = self.client.messages.create(
                        model=model, max_tokens=self.config.MAX_TOKENS, **request
                    )
                except anthropic.APIConnectionError as error:  # includes timeouts
                    last_error = error
                    self._wait_before_retry(model, attempt, error)
                    continue
                except anthropic.NotFoundError as error:
                    # Model name unknown or retired - no point retrying it
                    last_error = error
                    logger.error(f"Model '{model}' not found, skipping to fallback")
                    break
                except anthropic.APIStatusError as error:
                    if error.status_code not in RETRYABLE_STATUS_CODES:
                        raise  # 400, 401, 403 ... are our bugs, not transient
                    last_error = error
                    self._wait_before_retry(model, attempt, error)
                    continue

                latency = round(time.perf_counter() - start, 2)
                self._record(purpose, model, attempt, response.usage, latency)
                return response

            if model != models[-1]:
                logger.warning(f"'{model}' unavailable after retries, falling back")

        raise LLMUnavailableError(f"All models failed for '{purpose}': {last_error}")

    def _wait_before_retry(self, model: str, attempt: int, error: Exception):
        if attempt >= self.config.MAX_RETRIES:
            logger.warning(f"{model} attempt {attempt} failed: {error}")
            return
        delay = self.config.BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
        delay += random.uniform(0, 1)  # jitter so parallel jobs don't retry in lockstep
        # Honour the server's retry-after header when it sends one
        response = getattr(error, "response", None)
        retry_after = response.headers.get("retry-after") if response is not None else None
        if retry_after and retry_after.replace(".", "", 1).isdigit():
            delay = max(delay, float(retry_after))
        logger.warning(
            f"{model} attempt {attempt} failed ({type(error).__name__}), retrying in {delay:.1f}s"
        )
        self.sleep(delay)

    def _record(self, purpose, model, attempt, usage, latency):
        record = CallRecord(
            purpose=purpose,
            model=model,
            attempt=attempt,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            latency_seconds=latency,
            cost_usd=calculate_cost(model, usage, self.config.PRICING),
        )
        self.calls.append(record)
        logger.info(
            f"LLM call '{purpose}' on {model}: {record.input_tokens} in / "
            f"{record.output_tokens} out / {record.cache_read_tokens} cached, "
            f"{latency}s, ${record.cost_usd:.4f}"
        )
