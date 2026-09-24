"""
Command line entry point. Run from the repo root.

    python -m agent --site saucedemo                                  every spec in sites/saucedemo/specs/
    python -m agent --site saucedemo checkout_required_fields         one spec, by name
    python -m agent --site saucedemo "cart_*" --max-cost 0.50 --max-repairs 1
"""
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from agent.config import AgentConfig
from agent.site import SiteError, load_site


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent", description="Generate tests from specs")
    parser.add_argument("--site", required=True, help="Folder name under sites/, e.g. saucedemo")
    parser.add_argument("specs", nargs="*",
                        help="Spec files, names or patterns (default: every spec in sites/<site>/specs/)")
    parser.add_argument("--max-cost", type=float, help="Budget for this run in USD")
    parser.add_argument("--max-repairs", type=int, help="Self-healing attempts per spec")
    args = parser.parse_args(argv)

    # The report has emoji; a Windows console or pipe may not be UTF-8 by default
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        site = load_site(args.site)
        spec_paths = site.find_specs(args.specs)
    except SiteError as error:
        print(error, file=sys.stderr)
        return 2

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set (add it to .env or the environment).", file=sys.stderr)
        return 2
    if args.max_cost is not None:
        AgentConfig.MAX_RUN_COST_USD = args.max_cost
    if args.max_repairs is not None:
        AgentConfig.MAX_REPAIR_ATTEMPTS = args.max_repairs

    # Imported here so --help works without the SDK installed
    from agent.context import build_context, page_object_api
    from agent.generator import SpecToTestGenerator
    from agent.llm_client import LLMClient
    from agent.pipeline import SpecPipeline
    from agent.report import write_reports
    from agent.spec import load_spec

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(AgentConfig.RUNS_DIR) / f"{run_id}_{site.name}"

    llm = LLMClient()
    generator = SpecToTestGenerator(llm, build_context(site), site.allowed_imports)
    pipeline = SpecPipeline(generator, site, page_object_api(site), run_dir)

    results = [pipeline.process(load_spec(path)) for path in spec_paths]
    report_path = write_reports(results, llm, run_dir, run_id, site.name)

    markdown = report_path.read_text(encoding="utf-8")
    print(markdown)
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")  # shows the report on the Actions run page
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(markdown)

    # Non-zero only when the agent itself could not do its job
    return 1 if any(r.status == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
