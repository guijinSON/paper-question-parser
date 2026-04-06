import json
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "contract" / "examples" / "math-genealogy-trajectory"
REQUIRED_UPSTREAM_FILES = ["trace.json", "claim-ledger.json", "report.md", "report.json"]
FIXTURE_DIRS = [
    EXAMPLES / "happy-path",
    EXAMPLES / "blocked-no-output",
    EXAMPLES / "sparse-evidence",
    EXAMPLES / "insufficient-target-access",
    EXAMPLES / "summary-only-target-access",
    EXAMPLES / "upstream-insufficient-target-access",
    EXAMPLES / "upstream-trace-only-insufficient-target-access",
    EXAMPLES / "upstream-report-only-insufficient-target-access",
    EXAMPLES / "upstream-conflicting-blockers",
    EXAMPLES / "missing-required-bundle-artifact",
    EXAMPLES / "missing-tags",
    EXAMPLES / "too-short",
    EXAMPLES / "leakage-trap",
]
RUNNER = ROOT / "contract" / "run_math_genealogy_research_trajectory.py"
ALLOWED_BLOCKERS = {
    "missing_required_bundle_artifact",
    "blocked_by_upstream_failure",
    "insufficient_target_access",
    "insufficient_grounded_ideation_evidence",
}


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_runner_module():
    spec = importlib.util.spec_from_file_location("trajectory_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RUNNER_MODULE = load_runner_module()
REQUIRED_TAGS = RUNNER_MODULE.REQUIRED_TAGS
REQUIRED_SECTION_MARKERS = RUNNER_MODULE.SECTION_MARKERS


def cleanup_pycache() -> None:
    pycache = ROOT / "contract" / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)


def validate_bundle_contract(bundle_dir: Path) -> tuple[dict, dict, dict]:
    assert_true(bundle_dir.is_dir(), f"missing fixture directory: {bundle_dir}")
    for name in REQUIRED_UPSTREAM_FILES:
        assert_true((bundle_dir / name).is_file(), f"missing required artifact {name} in {bundle_dir.name}")

    trace_payload = load_json(bundle_dir / "trace.json")
    ledger_payload = load_json(bundle_dir / "claim-ledger.json")
    report_payload = load_json(bundle_dir / "report.json")

    target_key = ledger_payload["target_paper"]["canonical_work_id"]
    assert_true(trace_payload["normalization"]["canonical_work_id"] == target_key, f"trace target mismatch in {bundle_dir.name}")
    assert_true(report_payload["canonical_work_id"] == target_key, f"report target mismatch in {bundle_dir.name}")
    return trace_payload, ledger_payload, report_payload


def claim_ids(ledger_payload: dict) -> set[str]:
    return {claim["claim_id"] for claim in ledger_payload.get("claims", [])}


def renderable_non_target_claims(ledger_payload: dict) -> list[dict]:
    target_key = ledger_payload["target_paper"]["canonical_work_id"]
    claims = []
    for claim in ledger_payload.get("claims", []):
        if claim.get("paper_node") == target_key:
            continue
        if claim.get("adjudication_status") not in {"accepted", "accepted_with_limits"}:
            continue
        if claim.get("renderable") is not True:
            continue
        claims.append(claim)
    return claims


def load_generated_outputs(bundle_dir: Path) -> tuple[str, dict]:
    trajectory_path = bundle_dir / "trajectory.md"
    manifest_path = bundle_dir / "trajectory.manifest.json"
    assert_true(trajectory_path.is_file(), f"missing trajectory.md in {bundle_dir.name}")
    assert_true(manifest_path.is_file(), f"missing trajectory.manifest.json in {bundle_dir.name}")
    return trajectory_path.read_text(encoding="utf-8"), load_json(manifest_path)


def validate_manifest_common(bundle_dir: Path, manifest_payload: dict, ledger_payload: dict) -> None:
    assert_true(manifest_payload.get("schema_version") == "1.0", f"{bundle_dir.name} manifest schema_version must be 1.0")
    assert_true(manifest_payload.get("artifact") == {"path": "trajectory.md", "kind": "research_trajectory"}, f"{bundle_dir.name} manifest artifact shape mismatch")
    assert_true(manifest_payload.get("bundle", {}).get("canonical_work_id") == ledger_payload["target_paper"]["canonical_work_id"], f"{bundle_dir.name} manifest canonical work mismatch")
    assert_true(manifest_payload.get("status") == "ok", f"{bundle_dir.name} manifest status must be ok")
    blocker = manifest_payload.get("blocker")
    assert_true(blocker is None, f"{bundle_dir.name} manifest blocker must be null for success outputs")
    refs = manifest_payload.get("evidence_refs")
    assert_true(isinstance(refs, list), f"{bundle_dir.name} evidence_refs must be a list")
    ledger_ids = claim_ids(ledger_payload)
    for ref in refs:
        assert_true(ref in ledger_ids, f"{bundle_dir.name} manifest references unknown claim id {ref}")


def validate_generated_success(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(trace_payload.get("fail_closed_reason") is None, f"{bundle_dir.name} trace must not be fail-closed")
    assert_true(report_payload.get("fail_closed_reason") is None, f"{bundle_dir.name} report must not be fail-closed")
    raw_text, manifest_payload = load_generated_outputs(bundle_dir)
    validate_manifest_common(bundle_dir, manifest_payload, ledger_payload)

    for tag in REQUIRED_TAGS:
        assert_true(f"<TOOL>{tag} |" in raw_text, f"{bundle_dir.name} missing required tag {tag}")
    for section in REQUIRED_SECTION_MARKERS:
        assert_true(f"## {section}" in raw_text, f"{bundle_dir.name} missing section marker {section}")
    assert_true(raw_text.startswith("Opening note:"), f"{bundle_dir.name} must start with opening note")
    assert_true("Plausible reconstruction:" in raw_text or "Tentative route:" in raw_text, f"{bundle_dir.name} must mark speculation visibly")
    assert_true(len(raw_text.split()) >= 180, f"{bundle_dir.name} trajectory is too short for success fixture")
    assert_true(manifest_payload.get("required_tags_present") == REQUIRED_TAGS, f"{bundle_dir.name} manifest required_tags_present mismatch")
    assert_true(manifest_payload.get("section_markers_present") == REQUIRED_SECTION_MARKERS, f"{bundle_dir.name} manifest section markers mismatch")
    assert_true(manifest_payload.get("failed_route_count", 0) >= 2, f"{bundle_dir.name} must report at least two failed routes")
    assert_true(manifest_payload.get("revision_count", 0) >= 2, f"{bundle_dir.name} must report at least two revisions")
    assert_true(manifest_payload.get("revision_pass_count", 0) >= 2, f"{bundle_dir.name} must report at least two revision passes")
    assert_true(manifest_payload.get("speculation_marker_count", 0) >= 1, f"{bundle_dir.name} must report at least one speculation marker")
    assert_true(manifest_payload.get("descendant_overlap_included") is False, f"{bundle_dir.name} must not include descendant overlap")
    assert_true(renderable_non_target_claims(ledger_payload), f"{bundle_dir.name} success fixture needs renderable non-target claims")


def validate_blocked_no_output(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "trajectory.md").exists(), "blocked-no-output must not contain trajectory.md")
    assert_true(not (bundle_dir / "trajectory.manifest.json").exists(), "blocked-no-output must not contain trajectory.manifest.json")
    assert_true(trace_payload.get("fail_closed_reason") == "blocked_by_upstream_failure", "blocked-no-output trace reason mismatch")
    assert_true(report_payload.get("fail_closed_reason") == "blocked_by_upstream_failure", "blocked-no-output report reason mismatch")
    assert_true(ledger_payload.get("monologue_readiness", {}).get("status") == "blocked_by_upstream_failure", "blocked-no-output readiness mismatch")


def validate_sparse_evidence(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "trajectory.md").exists(), "sparse-evidence must not contain trajectory.md")
    assert_true(not (bundle_dir / "trajectory.manifest.json").exists(), "sparse-evidence must not contain trajectory.manifest.json")
    assert_true(trace_payload.get("fail_closed_reason") is None, "sparse-evidence should not be upstream fail-closed")
    assert_true(report_payload.get("fail_closed_reason") is None, "sparse-evidence report should remain factual")
    assert_true(renderable_non_target_claims(ledger_payload) == [], "sparse-evidence must have no non-target renderable route claims")
    assert_true(not report_payload.get("pressure_points"), "sparse-evidence should have empty pressure points")


def validate_insufficient_target_access(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "trajectory.md").exists(), "insufficient-target-access must not contain trajectory.md")
    assert_true(not (bundle_dir / "trajectory.manifest.json").exists(), "insufficient-target-access must not contain trajectory.manifest.json")
    assert_true(trace_payload.get("fail_closed_reason") is None, "insufficient-target-access should not be upstream fail-closed")
    assert_true(report_payload.get("fail_closed_reason") is None, "insufficient-target-access report should remain factual")
    assert_true(len(renderable_non_target_claims(ledger_payload)) >= 2, "insufficient-target-access should retain route-bearing claims")


def validate_summary_only_target_access(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "trajectory.md").exists(), "summary-only-target-access must not contain trajectory.md")
    assert_true(not (bundle_dir / "trajectory.manifest.json").exists(), "summary-only-target-access must not contain trajectory.manifest.json")
    assert_true(trace_payload.get("fail_closed_reason") is None, "summary-only-target-access should not be upstream fail-closed")
    assert_true(report_payload.get("fail_closed_reason") is None, "summary-only-target-access report should remain factual")
    assert_true(len(renderable_non_target_claims(ledger_payload)) >= 2, "summary-only-target-access should retain route-bearing claims")


def validate_upstream_insufficient_target_access(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "trajectory.md").exists(), "upstream-insufficient-target-access must not contain trajectory.md")
    assert_true(not (bundle_dir / "trajectory.manifest.json").exists(), "upstream-insufficient-target-access must not contain trajectory.manifest.json")
    assert_true(trace_payload.get("fail_closed_reason") == "insufficient_target_access", "upstream-insufficient-target-access trace reason mismatch")
    assert_true(report_payload.get("fail_closed_reason") == "insufficient_target_access", "upstream-insufficient-target-access report reason mismatch")


def validate_upstream_trace_only_insufficient_target_access(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "trajectory.md").exists(), "upstream-trace-only-insufficient-target-access must not contain trajectory.md")
    assert_true(not (bundle_dir / "trajectory.manifest.json").exists(), "upstream-trace-only-insufficient-target-access must not contain trajectory.manifest.json")
    assert_true(trace_payload.get("fail_closed_reason") == "insufficient_target_access", "upstream-trace-only-insufficient-target-access trace reason mismatch")
    assert_true(report_payload.get("fail_closed_reason") is None, "upstream-trace-only-insufficient-target-access report should remain open")


def validate_upstream_report_only_insufficient_target_access(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "trajectory.md").exists(), "upstream-report-only-insufficient-target-access must not contain trajectory.md")
    assert_true(not (bundle_dir / "trajectory.manifest.json").exists(), "upstream-report-only-insufficient-target-access must not contain trajectory.manifest.json")
    assert_true(trace_payload.get("fail_closed_reason") is None, "upstream-report-only-insufficient-target-access trace should remain open")
    assert_true(report_payload.get("fail_closed_reason") == "insufficient_target_access", "upstream-report-only-insufficient-target-access report reason mismatch")


def validate_upstream_conflicting_blockers(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "trajectory.md").exists(), "upstream-conflicting-blockers must not contain trajectory.md")
    assert_true(not (bundle_dir / "trajectory.manifest.json").exists(), "upstream-conflicting-blockers must not contain trajectory.manifest.json")
    assert_true(trace_payload.get("fail_closed_reason") == "blocked_by_upstream_failure", "upstream-conflicting-blockers trace reason mismatch")
    assert_true(report_payload.get("fail_closed_reason") == "insufficient_target_access", "upstream-conflicting-blockers report reason mismatch")


def validate_missing_required_bundle_artifact(bundle_dir: Path) -> None:
    assert_true(bundle_dir.is_dir(), f"missing fixture directory: {bundle_dir}")
    assert_true(not (bundle_dir / "report.md").exists(), "missing-required-bundle-artifact should omit report.md")
    assert_true((bundle_dir / "trace.json").is_file(), "missing-required-bundle-artifact must still contain trace.json")
    assert_true((bundle_dir / "claim-ledger.json").is_file(), "missing-required-bundle-artifact must still contain claim-ledger.json")
    assert_true((bundle_dir / "report.json").is_file(), "missing-required-bundle-artifact must still contain report.json")


def run_runner_on_temp_copy(source_dir: Path, remove_outputs: bool = False, seed_outputs: bool = False) -> tuple[int, str, dict]:
    with tempfile.TemporaryDirectory(prefix="trajectory-fixture-") as temp_dir:
        temp_path = Path(temp_dir) / source_dir.name
        shutil.copytree(source_dir, temp_path)
        if seed_outputs:
            (temp_path / "trajectory.md").write_text("stale output\n", encoding="utf-8")
            (temp_path / "trajectory.manifest.json").write_text('{"schema_version":"1.0"}\n', encoding="utf-8")
        if remove_outputs:
            for name in ["trajectory.md", "trajectory.manifest.json"]:
                output_path = temp_path / name
                if output_path.exists():
                    output_path.unlink()
        result = subprocess.run([sys.executable, str(RUNNER), str(temp_path)], capture_output=True, text=True)
        output = result.stdout + result.stderr
        generated: dict = {}
        if result.returncode == 0:
            trace_payload, ledger_payload, report_payload = validate_bundle_contract(temp_path)
            validate_generated_success(temp_path, trace_payload, ledger_payload, report_payload)
            generated = {
                "trajectory": (temp_path / "trajectory.md").read_text(encoding="utf-8"),
                "manifest": load_json(temp_path / "trajectory.manifest.json"),
            }
        else:
            generated = {
                "trajectory_exists": (temp_path / "trajectory.md").exists(),
                "manifest_exists": (temp_path / "trajectory.manifest.json").exists(),
            }
        return result.returncode, output, generated


def validate_invalid_output(bundle_dir: Path, reason_substring: str) -> None:
    try:
        trace_payload, ledger_payload, report_payload = validate_bundle_contract(bundle_dir)
        validate_generated_success(bundle_dir, trace_payload, ledger_payload, report_payload)
    except AssertionError as error:
        assert_true(reason_substring in str(error), f"{bundle_dir.name} failure reason mismatch: {error}")
        return
    raise AssertionError(f"{bundle_dir.name} should have failed validation")


def assert_invalid_fixture_cli(bundle_dir: Path, reason_substring: str) -> None:
    try:
        trace_payload, ledger_payload, report_payload = validate_bundle_contract(bundle_dir)
        validate_generated_success(bundle_dir, trace_payload, ledger_payload, report_payload)
    except AssertionError as error:
        assert_true(reason_substring in str(error), f"{bundle_dir.name} targeted failure reason mismatch: {error}")
        raise
    raise AssertionError(f"{bundle_dir.name} should have failed validation")


def validate_runner_guardrails(bundle_dir: Path) -> None:
    raw_text, _ = load_generated_outputs(bundle_dir)
    violations = RUNNER_MODULE.guardrail_violations(raw_text)
    assert_true(bool(violations), f"{bundle_dir.name} should trigger runner guardrail violations")
    assert_true(RUNNER_MODULE.draft_is_compliant(raw_text) is False, f"{bundle_dir.name} should not satisfy runner compliance")


def main() -> None:
    if len(sys.argv) > 2:
        raise SystemExit("usage: python3 contract/validate_math_genealogy_trajectory_examples.py [bundle-dir]")

    fixture_dirs = [Path(sys.argv[1]).resolve()] if len(sys.argv) == 2 else FIXTURE_DIRS
    for bundle_dir in fixture_dirs:
        name = bundle_dir.name
        if name == "missing-required-bundle-artifact":
            validate_missing_required_bundle_artifact(bundle_dir)
            returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
            assert_true(returncode == 1, "missing-required-bundle-artifact runner should fail closed")
            assert_true("missing_required_bundle_artifact" in output, "missing-required-bundle-artifact runner output mismatch")
            assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "missing-required-bundle-artifact must not emit outputs")
            continue

        trace_payload, ledger_payload, report_payload = validate_bundle_contract(bundle_dir)
        if len(sys.argv) == 1 and name not in {path.name for path in FIXTURE_DIRS}:
            raise AssertionError(f"unexpected fixture discovered: {name}")
        if name == "happy-path":
            validate_generated_success(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, remove_outputs=True)
                assert_true(returncode == 0, f"happy-path runner should succeed: {output}")
                assert_true(generated["trajectory"] == (bundle_dir / "trajectory.md").read_text(encoding="utf-8"), "happy-path trajectory fixture drifted from runner output")
                assert_true(generated["manifest"] == load_json(bundle_dir / "trajectory.manifest.json"), "happy-path manifest fixture drifted from runner output")
        elif name == "blocked-no-output":
            validate_blocked_no_output(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                assert_true(returncode == 1, "blocked-no-output runner should fail closed")
                assert_true("blocked_by_upstream_failure" in output, "blocked-no-output runner output mismatch")
                assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "blocked-no-output must not emit outputs")
        elif name == "sparse-evidence":
            validate_sparse_evidence(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                assert_true(returncode == 1, "sparse-evidence runner should fail closed")
                assert_true("insufficient_grounded_ideation_evidence" in output, "sparse-evidence runner output mismatch")
                assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "sparse-evidence must not emit outputs")
        elif name == "insufficient-target-access":
            validate_insufficient_target_access(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                assert_true(returncode == 1, "insufficient-target-access runner should fail closed")
                assert_true("insufficient_target_access" in output, "insufficient-target-access runner output mismatch")
                assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "insufficient-target-access must not emit outputs")
        elif name == "summary-only-target-access":
            validate_summary_only_target_access(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                assert_true(returncode == 1, "summary-only-target-access runner should fail closed")
                assert_true("insufficient_target_access" in output, "summary-only-target-access runner output mismatch")
                assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "summary-only-target-access must not emit outputs")
        elif name == "upstream-insufficient-target-access":
            validate_upstream_insufficient_target_access(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                assert_true(returncode == 1, "upstream-insufficient-target-access runner should fail closed")
                assert_true("insufficient_target_access" in output, "upstream-insufficient-target-access runner output mismatch")
                assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "upstream-insufficient-target-access must not emit outputs")
        elif name == "upstream-trace-only-insufficient-target-access":
            validate_upstream_trace_only_insufficient_target_access(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                assert_true(returncode == 1, "upstream-trace-only-insufficient-target-access runner should fail closed")
                assert_true("insufficient_target_access" in output, "upstream-trace-only-insufficient-target-access runner output mismatch")
                assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "upstream-trace-only-insufficient-target-access must not emit outputs")
        elif name == "upstream-report-only-insufficient-target-access":
            validate_upstream_report_only_insufficient_target_access(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                assert_true(returncode == 1, "upstream-report-only-insufficient-target-access runner should fail closed")
                assert_true("insufficient_target_access" in output, "upstream-report-only-insufficient-target-access runner output mismatch")
                assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "upstream-report-only-insufficient-target-access must not emit outputs")
        elif name == "upstream-conflicting-blockers":
            validate_upstream_conflicting_blockers(bundle_dir, trace_payload, ledger_payload, report_payload)
            if len(sys.argv) == 1:
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                assert_true(returncode == 1, "upstream-conflicting-blockers runner should fail closed")
                assert_true("blocked_by_upstream_failure" in output, "upstream-conflicting-blockers runner output mismatch")
                assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "upstream-conflicting-blockers must not emit outputs")
        elif name == "missing-tags":
            if len(sys.argv) == 2:
                assert_invalid_fixture_cli(bundle_dir, "missing required tag")
            else:
                validate_invalid_output(bundle_dir, "missing required tag")
                validate_runner_guardrails(bundle_dir)
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                if returncode == 0:
                    assert_true(generated["manifest"]["status"] == "ok", "missing-tags runner must emit an ok manifest on success")
                else:
                    assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "missing-tags blocked rerun must remove stale outputs")
        elif name == "too-short":
            if len(sys.argv) == 2:
                assert_invalid_fixture_cli(bundle_dir, "trajectory is too short")
            else:
                validate_invalid_output(bundle_dir, "trajectory is too short")
                validate_runner_guardrails(bundle_dir)
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                if returncode == 0:
                    assert_true(generated["manifest"]["status"] == "ok", "too-short runner must emit an ok manifest on success")
                else:
                    assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "too-short blocked rerun must remove stale outputs")
        elif name == "leakage-trap":
            if len(sys.argv) == 2:
                raw_text, manifest_payload = load_generated_outputs(bundle_dir)
                assert_true(manifest_payload.get("descendant_overlap_included") is False, f"{bundle_dir.name} manifest must not include descendant overlap")
                leakage_markers = [
                    "later descendant method",
                    "hidden solution path",
                    "unseen 1997 precursor paper",
                    "2031",
                ]
                for marker in leakage_markers:
                    assert_true(marker not in raw_text, f"{bundle_dir.name} contains forbidden descendant leakage: {marker}")
            else:
                try:
                    raw_text, manifest_payload = load_generated_outputs(bundle_dir)
                    assert_true(manifest_payload.get("descendant_overlap_included") is False, f"{bundle_dir.name} manifest must not include descendant overlap")
                    leakage_markers = [
                        "later descendant method",
                        "hidden solution path",
                        "unseen 1997 precursor paper",
                        "2031",
                    ]
                    for marker in leakage_markers:
                        assert_true(marker not in raw_text, f"{bundle_dir.name} contains forbidden descendant leakage: {marker}")
                except AssertionError as error:
                    assert_true("forbidden descendant leakage" in str(error) or "must not include descendant overlap" in str(error), f"{bundle_dir.name} failure reason mismatch: {error}")
                else:
                    raise AssertionError(f"{bundle_dir.name} should have failed validation")
                validate_runner_guardrails(bundle_dir)
                returncode, output, generated = run_runner_on_temp_copy(bundle_dir, seed_outputs=True)
                if returncode == 0:
                    assert_true(generated["manifest"]["status"] == "ok", "leakage-trap runner must emit an ok manifest on success")
                else:
                    assert_true(generated["trajectory_exists"] is False and generated["manifest_exists"] is False, "leakage-trap blocked rerun must remove stale outputs")
        else:
            validate_generated_success(bundle_dir, trace_payload, ledger_payload, report_payload)

    print("math-genealogy trajectory fixtures validated")


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_pycache()
