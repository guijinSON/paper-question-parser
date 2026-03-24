import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "contract" / "examples"

REQUIRED_KEYS = {
    "schema_version",
    "input",
    "target_reader",
    "rewrite_kind",
    "verdict",
    "original_question",
    "original_paper",
    "rewritten_question",
    "paper_evidence",
    "consulted_papers",
    "rubric_scores",
    "trace",
    "persist",
}

FILES = [
    EXAMPLES / "paper-question-refiner.context-only.success.json",
    EXAMPLES / "paper-question-refiner.reformulation.success.json",
    EXAMPLES / "paper-question-refiner.failure.json",
]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_common(payload: dict) -> None:
    assert_true(set(payload.keys()) == REQUIRED_KEYS, f"unexpected keys: {sorted(payload.keys())}")
    assert_true(payload["schema_version"] == "1.0", "schema_version must be 1.0")
    assert_true(payload["target_reader"] == "broad_mathematician", "target_reader must be broad_mathematician")
    assert_true(payload["rewrite_kind"] in {"context_only", "reformulation"}, "invalid rewrite_kind")
    assert_true(set(payload["input"].keys()) == {"question", "arxiv_id"}, "invalid input shape")
    assert_true(payload["input"]["arxiv_id"], "arxiv_id must be non-empty")
    assert_true(set(payload["verdict"].keys()) == {"status", "reasons"}, "invalid verdict shape")
    assert_true(payload["verdict"]["status"] in {"accepted", "needs_review", "error"}, "invalid verdict status")
    assert_true(set(payload["original_paper"].keys()) == {"title", "locator", "source_id"}, "invalid original_paper shape")
    assert_true(payload["original_paper"]["locator"].startswith("https://"), "original paper locator must be https")
    assert_true(set(payload["rubric_scores"].keys()) == {"difficulty", "perfectness"}, "invalid rubric_scores shape")
    assert_true(payload["persist"]["run_path"].startswith("outputs/"), "run_path must be under outputs/")
    assert_true(payload["persist"]["latest_path"] == "outputs/paper-question-refiner.latest.json", "latest_path must be outputs/paper-question-refiner.latest.json")
    assert_true(any(p["role"] == "primary" for p in payload["consulted_papers"]), "consulted_papers must include a primary paper")
    source_ids = {paper["source_id"] for paper in payload["consulted_papers"]}
    source_ids.add(payload["original_paper"]["source_id"])
    for evidence in payload["paper_evidence"]:
        assert_true(evidence["source_id"] in source_ids, f"unknown evidence source_id: {evidence['source_id']}")


def validate_scores(payload: dict) -> None:
    for family in ("difficulty", "perfectness"):
        for row in payload["rubric_scores"][family]:
            assert_true(set(row.keys()) == {"id", "label", "score", "direction", "rationale"}, "invalid rubric row shape")
            assert_true(1 <= row["score"] <= 10, "rubric score must be between 1 and 10")
            assert_true(row["direction"] == "higher_is_better", "rubric direction must be higher_is_better")
            assert_true("\\(" not in row["rationale"] and "\\[" not in row["rationale"] and "\\math" not in row["rationale"] and "\\operatorname" not in row["rationale"], "rationale must avoid raw TeX/LaTeX markup")


def validate_generated_text(payload: dict) -> None:
    generated_strings = [payload["rewritten_question"]]
    generated_strings.extend(item["notes"] for item in payload["trace"])
    for value in generated_strings:
        assert_true("\\(" not in value and "\\[" not in value and "\\math" not in value and "\\operatorname" not in value, "generated prose must avoid raw TeX/LaTeX markup")


def main() -> None:
    payloads = []
    for path in FILES:
        with path.open() as handle:
            payload = json.load(handle)
        validate_common(payload)
        validate_scores(payload)
        validate_generated_text(payload)
        payloads.append((path.name, payload))

    by_name = {name: payload for name, payload in payloads}

    assert_true(by_name["paper-question-refiner.context-only.success.json"]["rewrite_kind"] == "context_only", "context-only fixture must use context_only")
    assert_true(by_name["paper-question-refiner.context-only.success.json"]["verdict"]["status"] == "accepted", "context-only fixture must be accepted")
    assert_true(by_name["paper-question-refiner.reformulation.success.json"]["rewrite_kind"] == "reformulation", "reformulation fixture must use reformulation")
    assert_true(by_name["paper-question-refiner.reformulation.success.json"]["verdict"]["status"] == "accepted", "reformulation fixture must be accepted")
    assert_true(by_name["paper-question-refiner.failure.json"]["verdict"]["status"] == "needs_review", "failure fixture must be needs_review")
    assert_true(by_name["paper-question-refiner.failure.json"]["rewritten_question"] == "", "failure fixture rewritten_question must be empty")

    print("paper-question-refiner fixtures validated")


if __name__ == "__main__":
    main()
