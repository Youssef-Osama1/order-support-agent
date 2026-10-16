import asyncio
import re
from collections import Counter
from datetime import date
from pathlib import Path

from openai import APIError
from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.exceptions import AgentStepLimitError, LLMOutputError
from app.repositories.order_repository import OrderRepository
from app.services.agent import AgentResult, ToolCallRecord
from app.services.llm_client import LLMClient
from app.services.support_service import SupportService

CASES_PATH = Path(__file__).parent / "support_cases.jsonl"
REPEATS = 2
MAX_CONCURRENCY = 1
MAX_RETRIES = 10
EVAL_DATE = date(2026, 10, 15)
ARABIC_LETTER = re.compile(r"[؀-ۿ]")
LATIN_LETTER = re.compile(r"[a-z]", re.IGNORECASE)
GERMAN_WORDS = {"sie", "und", "nicht", "können", "innerhalb", "tagen", "ihre", "ist"}


class ExpectedCall(BaseModel):
    name: str
    arguments: dict = {}


class EvalCase(BaseModel):
    id: str
    customer_email: str
    message: str
    language: str
    expected_calls: list[ExpectedCall] = []
    allowed_tools: list[str] = []
    facts: list[list[str]] = []
    forbidden: list[str] = []


def load_cases() -> list[EvalCase]:
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    return [EvalCase.model_validate_json(line) for line in lines if line.strip()]


async def predict(service: SupportService, case: EvalCase) -> AgentResult | str:
    try:
        return await service.answer(case.message, case.customer_email)
    except (LLMOutputError, AgentStepLimitError, APIError) as error:
        return f"error: {type(error).__name__}: {error}"


def matches(call: ToolCallRecord, expected: ExpectedCall) -> bool:
    return call.name == expected.name and all(
        call.arguments.get(key) == value for key, value in expected.arguments.items()
    )


def detect_language(text: str) -> str:
    if len(ARABIC_LETTER.findall(text)) > len(LATIN_LETTER.findall(text)):
        return "ar"
    words = set(re.findall(r"\w+", text.casefold()))
    return "de" if len(words & GERMAN_WORDS) >= 2 else "en"


def score(case: EvalCase, outcome: AgentResult | str) -> dict[str, bool]:
    checks = ["tools", "precision", "language"]
    if case.expected_calls:
        checks.insert(1, "arguments")
    if case.facts:
        checks.append("facts")
    if case.forbidden:
        checks.append("no_leak")
    if not isinstance(outcome, AgentResult):
        return dict.fromkeys(checks, False)

    called = {call.name for call in outcome.tool_calls}
    allowed = {call.name for call in case.expected_calls} | set(case.allowed_tools)
    reply = outcome.reply.casefold()
    results = {
        "tools": all(call.name in called for call in case.expected_calls),
        "arguments": all(
            any(matches(call, expected) for call in outcome.tool_calls)
            for expected in case.expected_calls
        ),
        "precision": called <= allowed,
        "language": detect_language(outcome.reply) == case.language,
        "facts": all(
            any(option.casefold() in reply for option in group) for group in case.facts
        ),
        "no_leak": not any(word.casefold() in reply for word in case.forbidden),
    }
    return {check: results[check] for check in checks}


def describe(outcome: AgentResult | str) -> str:
    if not isinstance(outcome, AgentResult):
        return outcome
    calls = [
        f"{c.name}({c.arguments}){'' if c.ok else '!'}" for c in outcome.tool_calls
    ]
    reply = " ".join(outcome.reply.split())
    return f"steps={outcome.steps} calls={calls} reply={reply[:200]!r}"


async def main() -> None:
    cases = load_cases()
    settings = get_settings().model_copy(
        update={"llm_max_retries": MAX_RETRIES, "today_override": EVAL_DATE}
    )
    client = LLMClient(settings)
    repository = OrderRepository.from_file(settings.orders_path)
    service = SupportService(client, repository, settings)
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def run(case: EvalCase) -> tuple[EvalCase, AgentResult | str]:
        async with semaphore:
            return case, await predict(service, case)

    try:
        results = await asyncio.gather(
            *(run(case) for case in cases for _ in range(REPEATS))
        )
    finally:
        await client.close()

    passed: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    steps = []
    for case, outcome in results:
        if isinstance(outcome, AgentResult):
            steps.append(outcome.steps)
        for check, ok in score(case, outcome).items():
            totals[check] += 1
            passed[check] += ok
            if not ok:
                print(f"[{case.id}] {check} failed: {describe(outcome)}")

    print(f"\n{len(cases)} cases x {REPEATS} runs")
    print(f"errors     {len(results) - len(steps)}/{len(results)}")
    if steps:
        print(f"avg steps  {sum(steps) / len(steps):.1f}")
    for check, total in totals.items():
        print(f"{check:<10} {passed[check]}/{total}  {passed[check] / total:.0%}")


if __name__ == "__main__":
    asyncio.run(main())
