import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parent.parent
EVAL_EXAMPLES = ROOT / "contract" / "examples" / "math-genealogy-trajectory-eval"
EVALUATOR = ROOT / "contract" / "evaluate_math_genealogy_method_overlap.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def cleanup_pycache() -> None:
    pycache = ROOT / "contract" / "__pycache__"
    if pycache.exists():
        for child in pycache.iterdir():
            child.unlink()
        pycache.rmdir()


def main() -> None:
    for name in ["happy-path", "medium-overlap", "low-overlap"]:
        fixture_dir = EVAL_EXAMPLES / name
        assert_true((fixture_dir / "trajectory.md").is_file(), f"missing trajectory.md in {name}")
        payload = load_json(fixture_dir / "descendants.json")
        assert_true(isinstance(payload.get("descendant_methods"), list) and payload["descendant_methods"], f"missing descendant methods in {name}")
        for row in payload["descendant_methods"]:
            assert_true(set(row.keys()) == {"method_id", "label", "match_phrases"}, f"invalid descendant method shape in {name}")
            assert_true(bool(row["match_phrases"]), f"empty match_phrases in {name}")

        result = subprocess.run(
            [sys.executable, str(EVALUATOR), str(fixture_dir / "trajectory.md"), str(fixture_dir / "descendants.json")],
            capture_output=True,
            text=True,
            check=True,
        )
        report = json.loads(result.stdout)
        assert_true(set(report.keys()) == {"schema_version", "method_candidates", "matched_descendant_methods", "overlap_ratio", "confidence", "reasons"}, f"unexpected evaluator report keys in {name}")
        if name == "happy-path":
            assert_true(report["overlap_ratio"] == 1.0, "happy-path overlap_ratio mismatch")
            assert_true(report["confidence"] == "high", "happy-path confidence mismatch")
            assert_true({row["method_id"] for row in report["matched_descendant_methods"]} == {"stable-home", "twisted-comparison"}, "happy-path matched method ids mismatch")
        elif name == "medium-overlap":
            assert_true(report["overlap_ratio"] == 0.5, "medium-overlap overlap_ratio mismatch")
            assert_true(report["confidence"] == "medium", "medium-overlap confidence mismatch")
            assert_true({row["method_id"] for row in report["matched_descendant_methods"]} == {"stable-home"}, "medium-overlap matched method ids mismatch")
        else:
            assert_true(report["overlap_ratio"] == 0.0, "low-overlap overlap_ratio mismatch")
            assert_true(report["confidence"] == "low", "low-overlap confidence mismatch")
            assert_true(report["matched_descendant_methods"] == [], "low-overlap should have no matches")

    print("math-genealogy trajectory eval fixtures validated")


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_pycache()
