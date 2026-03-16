"""
Synthetic eval runner.

Runs the documentation agent on all questions from questions_generated.csv
in parallel (default concurrency=5), and saves the results to a dated JSON
file with a '_synthetic' suffix, e.g.:

    evals/evals_run_2026_03_16_synthetic.json

Usage:
    python evals/run_evals_synthetic.py
    python evals/run_evals_synthetic.py --limit 10
    python evals/run_evals_synthetic.py --concurrency 3
    python evals/run_evals_synthetic.py --output my_results.json
"""

import os
import sys
import json
import time
import random
import asyncio
import argparse
from datetime import date
from dataclasses import dataclass

import pandas as pd
from tqdm.auto import tqdm
from dotenv import load_dotenv

# Allow imports from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from doc_agent import DocumentationAgentConfig, create_agent, run_agent
from tools import create_documentation_tools_cached

load_dotenv()


# ---------------------------------------------------------------------------
# Cost tracking  (same as run_evals.py)
# ---------------------------------------------------------------------------

MODEL_PRICES = {
    "openai:gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai:gpt-4o":      {"input": 2.50, "output": 10.00},
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = MODEL_PRICES.get(model.lower(), {"input": 0.0, "output": 0.0})
    return (
        (input_tokens  / 1_000_000) * prices["input"]
        + (output_tokens / 1_000_000) * prices["output"]
    )


@dataclass
class CostAccumulator:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage) -> None:
        self.input_tokens  += usage.input_tokens  or 0
        self.output_tokens += usage.output_tokens or 0

    @property
    def total_cost(self) -> float:
        return cost_usd(self.model, self.input_tokens, self.output_tokens)


# ---------------------------------------------------------------------------
# async map with tqdm progress bar
# (from https://alexeygrigorev.com/snippets/snippets/python/async_map_tqdm.html)
# ---------------------------------------------------------------------------

async def map_progress(seq, func, max_concurrency=5):
    """Asynchronously map an async function over a sequence with progress bar.

    Limits concurrency to `max_concurrency` using asyncio.Semaphore.
    Note: results may not be in the same order as the input because
    asyncio.as_completed yields in completion order.
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_with_semaphore(item):
        async with semaphore:
            return await func(item)

    coros = [run_with_semaphore(el) for el in seq]
    results = []
    for coro in tqdm(asyncio.as_completed(coros), total=len(coros)):
        result = await coro
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

def make_agent():
    """Create a fresh agent (search tools + config)."""
    search_tools = create_documentation_tools_cached()
    config = DocumentationAgentConfig()
    return create_agent(config, search_tools)


async def run_agent_on_row(agent, row: dict, cost: CostAccumulator) -> dict:
    """Run the agent on a single row from questions_generated.csv."""
    question = row["question"]
    try:
        result = await run_agent(agent, question)
        rag_response = result.output.model_dump()

        tools = []
        for message in result.new_messages():
            for part in message.parts:
                if part.part_kind == "tool-call" and part.tool_name != "final_result":
                    tools.append({"name": part.tool_name, "args": part.args})

        usage = result.usage()
        cost.add(usage)
        q_cost = cost_usd(
            cost.model,
            usage.input_tokens or 0,
            usage.output_tokens or 0,
        )

        return {
            "input": row,
            "rag_response": rag_response,
            "tools": tools,
            "cost": q_cost,
        }
    except Exception as exc:
        return {
            "input": row,
            "rag_response": {"answer": f"Agent error: {exc}"},
            "tools": [],
            "cost": 0.0,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(results: list[dict], cost: CostAccumulator, elapsed: float) -> None:
    total = len(results)
    errors = sum(1 for r in results if "error" in r)

    def fmt_time(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s:02d}s" if m else f"{s}s"

    print("\n" + "=" * 55)
    print("  SYNTHETIC EVAL RESULTS")
    print("=" * 55)
    print(f"  Total questions : {total}")
    print(f"  Errors          : {errors}")
    print("=" * 55)
    print("  COST & TIME")
    print("=" * 55)
    print(f"  Model           : {cost.model}")
    print(f"  Tokens in/out   : {cost.input_tokens:,} / {cost.output_tokens:,}")
    print(f"  Total cost      : ${cost.total_cost:.4f}")
    print(f"  Total time      : {fmt_time(elapsed)}")
    print("=" * 55)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the documentation agent on synthetic questions in parallel."
    )
    parser.add_argument(
        "--questions",
        default="evals/questions_generated.csv",
        help="Path to questions_generated.csv (default: evals/questions_generated.csv)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path. Defaults to evals/evals_run_<YYYY_MM_DD>_synthetic.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run on a random subset of N questions instead of the full list.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Number of parallel agent calls (default: 5).",
    )
    args = parser.parse_args()

    # Resolve paths relative to project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    questions_path = args.questions
    if not os.path.isabs(questions_path):
        questions_path = os.path.join(project_root, questions_path)

    if args.output:
        output_path = args.output
        if not os.path.isabs(output_path):
            output_path = os.path.join(project_root, output_path)
    else:
        today = date.today().strftime("%Y_%m_%d")
        output_path = os.path.join(
            project_root, "evals", f"evals_run_{today}_synthetic.json"
        )

    # Load questions
    print(f"Loading questions from {questions_path}...")
    df = pd.read_csv(questions_path)
    # Fill NaN so JSON serialisation works cleanly
    df = df.where(pd.notna(df), None)
    rows = df.to_dict(orient="records")
    print(f"  → {len(rows)} questions loaded.")

    if args.limit is not None:
        k = min(args.limit, len(rows))
        rows = random.sample(rows, k)
        print(f"  → Sampling {k} random questions (--limit {args.limit}).")

    # Create shared agent tools and cost accumulator
    search_tools = create_documentation_tools_cached()
    cost = CostAccumulator(model="openai:gpt-4o-mini")

    print(f"\nRunning {len(rows)} questions with concurrency={args.concurrency}...")
    print("━" * 55)

    t0 = time.perf_counter()

    async def process(row):
        agent = create_agent(DocumentationAgentConfig(), search_tools)
        return await run_agent_on_row(agent, row, cost)

    results = await map_progress(rows, process, max_concurrency=args.concurrency)
    elapsed = time.perf_counter() - t0

    # Save results
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    report(results, cost, elapsed)


if __name__ == "__main__":
    asyncio.run(main())
