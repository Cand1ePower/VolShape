from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.prompt_versions import get_prompt_manifest, iter_prompt_specs  # noqa: E402
from app.services.media_analysis import fallback_media_gate  # noqa: E402
from app.services.memory import MEMORY_EXTRACTION_SYSTEM_FLEX, should_capture_long_term_memory  # noqa: E402


CASES_PATH = Path(__file__).resolve().parent / "cases" / "core_cases.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _contains_all(text: str, terms: List[str]) -> List[str]:
    return [term for term in terms if term not in text]


def _prompt_text_by_name(name: str) -> str:
    for spec in iter_prompt_specs():
        if spec.name == name:
            return spec.text
    raise KeyError(f"Unknown prompt in eval case: {name}")


def _run_media_gate_case(case: Dict[str, Any]) -> Dict[str, Any]:
    result = fallback_media_gate(case["input"], case["media_kind"])
    expected = case["expected"]
    failures = []
    for key in ("should_invoke", "capability"):
        if result.get(key) != expected.get(key):
            failures.append(f"{key}: expected {expected.get(key)!r}, got {result.get(key)!r}")
    return {
        "actual": result,
        "passed": not failures,
        "failures": failures,
    }


def _run_memory_prompt_case(case: Dict[str, Any]) -> Dict[str, Any]:
    expected = case["expected"]
    should_capture = should_capture_long_term_memory(case["input"])
    missing_terms = _contains_all(MEMORY_EXTRACTION_SYSTEM_FLEX, expected.get("required_prompt_terms", []))
    failures = []
    if should_capture != expected.get("should_capture"):
        failures.append(
            f"should_capture: expected {expected.get('should_capture')!r}, got {should_capture!r}"
        )
    if missing_terms:
        failures.append(f"memory prompt missing terms: {', '.join(missing_terms)}")
    return {
        "actual": {
            "should_capture": should_capture,
            "missing_prompt_terms": missing_terms,
        },
        "passed": not failures,
        "failures": failures,
    }


def _run_prompt_audit_case(case: Dict[str, Any]) -> Dict[str, Any]:
    prompt_text = _prompt_text_by_name(case["prompt_name"])
    missing_terms = _contains_all(prompt_text, case["expected"].get("required_prompt_terms", []))
    return {
        "actual": {
            "prompt_name": case["prompt_name"],
            "missing_prompt_terms": missing_terms,
        },
        "passed": not missing_terms,
        "failures": [f"prompt missing terms: {', '.join(missing_terms)}"] if missing_terms else [],
    }


def _recommendation(case: Dict[str, Any], failures: List[str]) -> str | None:
    if not failures:
        return None
    category = case.get("category")
    if category == "media_gate":
        return "Tune media intent gating keywords or LLM gate prompt; keep upload-only requests from invoking tools."
    if category == "memory_prompt":
        return "Strengthen memory extraction prompt and persistence path for dynamic state/injury/event keys."
    if category == "prompt_audit" and case.get("prompt_name") == "movement_response":
        return "Add evidence constraints so movement responses do not identify exercises from pose geometry alone."
    return "Inspect this case and add a targeted prompt or routing constraint."


def run_all_evals() -> Dict[str, Any]:
    suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    results = []
    for case in suite["cases"]:
        category = case["category"]
        if category == "media_gate":
            result = _run_media_gate_case(case)
        elif category == "memory_prompt":
            result = _run_memory_prompt_case(case)
        elif category == "prompt_audit":
            result = _run_prompt_audit_case(case)
        else:
            result = {
                "actual": {},
                "passed": False,
                "failures": [f"Unsupported eval category: {category}"],
            }
        result["id"] = case["id"]
        result["category"] = category
        result["recommendation"] = _recommendation(case, result["failures"])
        results.append(result)

    passed = sum(1 for item in results if item["passed"])
    failed = len(results) - passed
    return {
        "suite": suite["suite"],
        "suite_version": suite["version"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "prompt_manifest": get_prompt_manifest(),
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
        },
        "results": results,
    }


def write_report(report: Dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"eval_report_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VolShape offline prompt/routing evals.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any eval fails.")
    parser.add_argument("--no-report", action="store_true", help="Do not write a JSON report file.")
    args = parser.parse_args()

    report = run_all_evals()
    if not args.no_report:
        report_path = write_report(report)
        print(f"report={report_path}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    if args.strict and report["summary"]["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
