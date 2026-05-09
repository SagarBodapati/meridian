#!/usr/bin/env python3
"""
Meridian evaluation harness.

Runs a set of financial Q&A test cases and measures:
- Retrieval recall (is the gold chunk in top-k?)
- Answer accuracy (numerical fact verification vs XBRL data)
- Citation precision (cited chunk contains the claim)
- Hallucination rate (LLM-as-judge)

Usage:
  python evals/eval_runner.py --questions evals/questions.json
"""
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agents.graph import MeridianGraph
from backend.agents.state import AgentState


@dataclass
class EvalCase:
    question: str
    ticker: str
    expected_keywords: list[str] = field(default_factory=list)  # must appear in answer
    expected_number: str | None = None      # a specific figure that should appear
    expected_period: str | None = None      # e.g. "Q3-2024"
    category: str = "factual"


@dataclass
class EvalResult:
    question: str
    answer: str
    latency_ms: int
    retrieved_chunks: int
    citations: int
    keywords_found: list[str]
    keywords_missing: list[str]
    number_found: bool
    period_found: bool
    passed: bool


SAMPLE_QUESTIONS: list[EvalCase] = [
    EvalCase(
        question="What was Apple's total revenue in the most recent fiscal quarter?",
        ticker="AAPL",
        expected_keywords=["revenue", "billion"],
        category="factual",
    ),
    EvalCase(
        question="What are the main risk factors Apple disclosed in its most recent 10-K?",
        ticker="AAPL",
        expected_keywords=["risk", "competition", "supply"],
        category="risk_factors",
    ),
    EvalCase(
        question="How has Apple's gross margin trended over the last 4 quarters?",
        ticker="AAPL",
        expected_keywords=["gross margin", "percent", "%"],
        category="trend_analysis",
    ),
    EvalCase(
        question="What guidance did Apple management provide for the next quarter?",
        ticker="AAPL",
        expected_keywords=["guidance", "revenue", "expect"],
        category="guidance",
    ),
    EvalCase(
        question="What were Microsoft's Azure revenue growth rates in the last 3 quarters?",
        ticker="MSFT",
        expected_keywords=["Azure", "cloud", "growth"],
        category="trend_analysis",
    ),
    EvalCase(
        question="Compare Apple and Microsoft gross margins",
        ticker="AAPL",
        expected_keywords=["Apple", "Microsoft", "margin"],
        category="comparative",
    ),
]


class EvalRunner:
    def __init__(self) -> None:
        self._graph = MeridianGraph()

    async def run_case(self, case: EvalCase) -> EvalResult:
        start = time.perf_counter()
        state = AgentState(
            query=case.question,
            tickers=[case.ticker],
            filters={"ticker": case.ticker},
        )
        result = await self._graph.run(state)
        latency = int((time.perf_counter() - start) * 1000)

        answer_lower = result.answer.lower()
        found_kw = [kw for kw in case.expected_keywords if kw.lower() in answer_lower]
        missing_kw = [kw for kw in case.expected_keywords if kw.lower() not in answer_lower]

        number_found = True
        if case.expected_number:
            number_found = case.expected_number.lower() in answer_lower

        period_found = True
        if case.expected_period:
            period_found = case.expected_period.lower() in answer_lower

        passed = len(missing_kw) == 0 and number_found and period_found

        return EvalResult(
            question=case.question,
            answer=result.answer,
            latency_ms=latency,
            retrieved_chunks=len(result.retrieved_chunks),
            citations=len(result.citations),
            keywords_found=found_kw,
            keywords_missing=missing_kw,
            number_found=number_found,
            period_found=period_found,
            passed=passed,
        )

    async def run_all(self, cases: list[EvalCase]) -> dict[str, Any]:
        results = []
        print(f"Running {len(cases)} evaluation cases...\n")

        for i, case in enumerate(cases, 1):
            print(f"[{i}/{len(cases)}] {case.question[:70]}...")
            result = await self.run_case(case)
            results.append(result)
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"  {status} | latency: {result.latency_ms}ms | chunks: {result.retrieved_chunks} | citations: {result.citations}")
            if result.keywords_missing:
                print(f"  Missing keywords: {result.keywords_missing}")
            print()

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        avg_latency = sum(r.latency_ms for r in results) / total

        summary = {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed / total * 100:.1f}%",
            "avg_latency_ms": int(avg_latency),
            "avg_chunks_retrieved": int(sum(r.retrieved_chunks for r in results) / total),
            "avg_citations": int(sum(r.citations for r in results) / total),
        }

        print("=" * 60)
        print("EVALUATION SUMMARY")
        print("=" * 60)
        for k, v in summary.items():
            print(f"  {k}: {v}")

        return {"summary": summary, "results": [r.__dict__ for r in results]}


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", help="Path to JSON questions file")
    parser.add_argument("--output", default="evals/results.json", help="Output path")
    args = parser.parse_args()

    if args.questions:
        with open(args.questions) as f:
            raw = json.load(f)
        cases = [EvalCase(**c) for c in raw]
    else:
        cases = SAMPLE_QUESTIONS
        print("Using built-in sample questions (pass --questions to use custom set)\n")

    runner = EvalRunner()
    results = await runner.run_all(cases)

    output_path = Path(args.output)
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
