import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "contract" / "examples" / "math-genealogy-graph"
SVG_NS = "http://www.w3.org/2000/svg"
XML_NS_PREFIX = f"{{{SVG_NS}}}"
REQUIRED_UPSTREAM_FILES = ["trace.json", "claim-ledger.json", "report.md", "report.json"]
SUCCESS_FIXTURES = {
    "excluded-claims",
    "happy-path",
    "special-characters",
}
FIXTURE_DIRS = [
    EXAMPLES / "happy-path",
    EXAMPLES / "blocked-no-output",
    EXAMPLES / "excluded-claims",
    EXAMPLES / "special-characters",
]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def stable_id_fragment(value: str) -> str:
    fragment = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return fragment or "blank"


def node_element_id(node_key: str) -> str:
    return f"node-{stable_id_fragment(node_key)}"


def edge_element_id(source_key: str, target_key: str, relation: str) -> str:
    return (
        f"edge-{stable_id_fragment(source_key)}-to-"
        f"{stable_id_fragment(target_key)}-{stable_id_fragment(relation)}"
    )


def svg_child_elements(element: ET.Element) -> list[ET.Element]:
    return [child for child in list(element) if isinstance(child.tag, str)]


def node_labels(report_payload: dict) -> dict[str, str]:
    labels = {report_payload["canonical_work_id"]: report_payload["canonical_work_id"]}
    for row in report_payload.get("seed_ranking", []):
        labels[row["paper_node"]] = row.get("title") or row["paper_node"]
    return labels


def renderable_edge_claims(ledger_payload: dict, target_key: str) -> list[dict]:
    claims = []
    for claim in ledger_payload["claims"]:
        if claim.get("paper_node") == target_key:
            continue
        if claim.get("ancestor_role") is None:
            continue
        if claim.get("adjudication_status") not in {"accepted", "accepted_with_limits"}:
            continue
        if claim.get("renderable") is not True:
            continue
        claims.append(claim)
    return claims


def validate_bundle_contract(bundle_dir: Path) -> tuple[dict, dict]:
    assert_true(bundle_dir.is_dir(), f"missing fixture directory: {bundle_dir}")
    for name in REQUIRED_UPSTREAM_FILES:
        assert_true((bundle_dir / name).is_file(), f"missing required artifact {name} in {bundle_dir.name}")
    assert_true(not (bundle_dir / "monologue.md").exists(), f"{bundle_dir.name} must not contain monologue.md")

    trace_payload = load_json(bundle_dir / "trace.json")
    ledger_payload = load_json(bundle_dir / "claim-ledger.json")
    report_payload = load_json(bundle_dir / "report.json")

    target_key = ledger_payload["target_paper"]["canonical_work_id"]
    assert_true(trace_payload["normalization"]["canonical_work_id"] == target_key, f"trace target mismatch in {bundle_dir.name}")
    assert_true(report_payload["canonical_work_id"] == target_key, f"report target mismatch in {bundle_dir.name}")

    return trace_payload, {"ledger": ledger_payload, "report": report_payload}


def validate_static_svg(bundle_dir: Path, ledger_payload: dict, report_payload: dict) -> str:
    svg_path = bundle_dir / "genealogy.svg"
    assert_true(svg_path.is_file(), f"missing genealogy.svg in {bundle_dir.name}")
    raw_svg = svg_path.read_text()
    root = ET.fromstring(raw_svg)

    assert_true(root.tag == f"{XML_NS_PREFIX}svg", f"{bundle_dir.name} root element must be svg")
    assert_true(root.attrib.get("viewBox"), f"{bundle_dir.name} svg must declare viewBox")

    banned_local_names = {"script", "foreignObject", "image", "iframe", "canvas", "html"}
    for element in root.iter():
        assert_true(isinstance(element.tag, str), f"{bundle_dir.name} contains non-element XML nodes")
        assert_true(element.tag.startswith(XML_NS_PREFIX), f"{bundle_dir.name} contains non-SVG namespace element {element.tag}")
        local_name = element.tag.split("}", 1)[1]
        assert_true(local_name not in banned_local_names, f"{bundle_dir.name} contains forbidden SVG content: {local_name}")

    top_level = svg_child_elements(root)
    assert_true([group.attrib.get("id") for group in top_level] == ["graph-edges", "graph-nodes"], f"{bundle_dir.name} must keep graph-edges then graph-nodes structure")
    edges_group, nodes_group = top_level

    target_key = ledger_payload["target_paper"]["canonical_work_id"]
    labels = node_labels(report_payload)
    edge_claims = renderable_edge_claims(ledger_payload, target_key)
    expected_node_keys = sorted({target_key, *[claim["paper_node"] for claim in edge_claims]})
    expected_edge_ids = [edge_element_id(claim["paper_node"], target_key, claim["ancestor_role"]) for claim in sorted(edge_claims, key=lambda claim: (claim["paper_node"], target_key, claim["ancestor_role"], claim["claim_id"]))]
    expected_node_ids = [node_element_id(node_key) for node_key in expected_node_keys]

    edge_elements = svg_child_elements(edges_group)
    node_elements = svg_child_elements(nodes_group)

    actual_edge_ids = [element.attrib.get("id") for element in edge_elements]
    actual_node_ids = [element.attrib.get("id") for element in node_elements]
    assert_true(actual_edge_ids == expected_edge_ids, f"{bundle_dir.name} edge order/id mismatch: {actual_edge_ids} != {expected_edge_ids}")
    assert_true(actual_node_ids == expected_node_ids, f"{bundle_dir.name} node order/id mismatch: {actual_node_ids} != {expected_node_ids}")
    assert_true(len(set(actual_edge_ids + actual_node_ids)) == len(actual_edge_ids) + len(actual_node_ids), f"{bundle_dir.name} element ids must be unique")

    node_keys_seen = set()
    for element in node_elements:
        node_key = element.attrib.get("data-node-key")
        label = element.attrib.get("data-label")
        assert_true(node_key in expected_node_keys, f"{bundle_dir.name} unexpected node key {node_key}")
        assert_true(element.attrib.get("id") == node_element_id(node_key), f"{bundle_dir.name} node id mismatch for {node_key}")
        assert_true(label == labels[node_key], f"{bundle_dir.name} node label mismatch for {node_key}")
        title_elements = [child for child in svg_child_elements(element) if child.tag == f"{XML_NS_PREFIX}title"]
        text_elements = [child for child in svg_child_elements(element) if child.tag == f"{XML_NS_PREFIX}text"]
        assert_true(len(title_elements) == 1, f"{bundle_dir.name} node {node_key} must contain one title element")
        assert_true(len(text_elements) == 1, f"{bundle_dir.name} node {node_key} must contain one text element")
        assert_true((title_elements[0].text or "") == node_key, f"{bundle_dir.name} node title mismatch for {node_key}")
        assert_true((text_elements[0].text or "") == label, f"{bundle_dir.name} node text mismatch for {node_key}")
        node_keys_seen.add(node_key)
    assert_true(node_keys_seen == set(expected_node_keys), f"{bundle_dir.name} node set mismatch")

    rendered_claim_ids = set()
    for element in edge_elements:
        source_key = element.attrib.get("data-source")
        target_value = element.attrib.get("data-target")
        relation = element.attrib.get("data-relation")
        claim_id = element.attrib.get("data-claim-id")
        assert_true(target_value == target_key, f"{bundle_dir.name} edge target mismatch for {claim_id}")
        assert_true(source_key in node_keys_seen, f"{bundle_dir.name} edge source missing node for {claim_id}")
        assert_true(element.attrib.get("id") == edge_element_id(source_key, target_value, relation), f"{bundle_dir.name} edge id mismatch for {claim_id}")
        rendered_claim_ids.add(claim_id)
    assert_true(rendered_claim_ids == {claim["claim_id"] for claim in edge_claims}, f"{bundle_dir.name} edge claim set mismatch")

    return raw_svg


def validate_happy_path(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(trace_payload.get("fail_closed_reason") is None, "happy-path must not be fail-closed")
    assert_true(report_payload.get("fail_closed_reason") is None, "happy-path report must not be fail-closed")
    edge_claims = renderable_edge_claims(ledger_payload, ledger_payload["target_paper"]["canonical_work_id"])
    assert_true([claim["claim_id"] for claim in edge_claims] == ["c-happy-ab", "c-happy-dou"], "happy-path must expose two stable rendered claims")
    assert_true([row["paper_node"] for row in report_payload["seed_ranking"]] == ["AB24", "Dou05"], "happy-path seed ranking mismatch")
    validate_static_svg(bundle_dir, ledger_payload, report_payload)


def validate_blocked(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(not (bundle_dir / "genealogy.svg").exists(), "blocked-no-output must not contain genealogy.svg")
    assert_true(trace_payload.get("fail_closed_reason") == "no_renderable_genealogy_relations", "blocked-no-output trace reason mismatch")
    assert_true(report_payload.get("fail_closed_reason") == "no_renderable_genealogy_relations", "blocked-no-output report reason mismatch")
    assert_true(renderable_edge_claims(ledger_payload, ledger_payload["target_paper"]["canonical_work_id"]) == [], "blocked-no-output must have no renderable edges")


def validate_excluded_claims(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(trace_payload.get("fail_closed_reason") is None, "excluded-claims must remain renderable")
    raw_svg = validate_static_svg(bundle_dir, ledger_payload, report_payload)
    renderable_ids = {claim["claim_id"] for claim in renderable_edge_claims(ledger_payload, ledger_payload["target_paper"]["canonical_work_id"])}
    assert_true(renderable_ids == {"c-excluded-ab"}, "excluded-claims must render only the accepted AB edge")
    assert_true("c-excluded-gh" not in raw_svg and "c-excluded-fur" not in raw_svg, "excluded-claims svg must omit excluded or downgraded claim ids")
    assert_true("node-gh15" not in raw_svg and "node-fur02" not in raw_svg, "excluded-claims svg must omit excluded or downgraded nodes")


def validate_special_characters(bundle_dir: Path, trace_payload: dict, ledger_payload: dict, report_payload: dict) -> None:
    assert_true(trace_payload.get("fail_closed_reason") is None, "special-characters must remain renderable")
    raw_svg = validate_static_svg(bundle_dir, ledger_payload, report_payload)
    assert_true("A &amp; B &lt;Foundations&gt;" in raw_svg, "special-characters svg must escape ampersands and angle brackets")
    assert_true("Quotes &quot;Matter&quot; &amp; Apostrophes' Too" in raw_svg, "special-characters svg must escape quotes in attributes")


def main() -> None:
    if len(sys.argv) > 2:
        raise SystemExit("usage: python3 contract/validate_math_genealogy_graph_examples.py [bundle-dir]")

    fixture_dirs = [Path(sys.argv[1]).resolve()] if len(sys.argv) == 2 else FIXTURE_DIRS
    payloads_by_name = {}
    for bundle_dir in fixture_dirs:
        trace_payload, payloads = validate_bundle_contract(bundle_dir)
        payloads_by_name[bundle_dir.name] = (trace_payload, payloads["ledger"], payloads["report"])

    for name, (trace_payload, ledger_payload, report_payload) in payloads_by_name.items():
        if len(sys.argv) == 1 and name not in {path.name for path in FIXTURE_DIRS}:
            raise AssertionError(f"unexpected fixture discovered: {name}")
        if name == "happy-path":
            validate_happy_path(EXAMPLES / name if len(sys.argv) == 1 else Path(sys.argv[1]).resolve(), trace_payload, ledger_payload, report_payload)
        elif name == "blocked-no-output":
            validate_blocked(EXAMPLES / name if len(sys.argv) == 1 else Path(sys.argv[1]).resolve(), trace_payload, ledger_payload, report_payload)
        elif name == "excluded-claims":
            validate_excluded_claims(EXAMPLES / name if len(sys.argv) == 1 else Path(sys.argv[1]).resolve(), trace_payload, ledger_payload, report_payload)
        elif name == "special-characters":
            validate_special_characters(EXAMPLES / name if len(sys.argv) == 1 else Path(sys.argv[1]).resolve(), trace_payload, ledger_payload, report_payload)
        else:
            raw_svg = validate_static_svg(Path(sys.argv[1]).resolve(), ledger_payload, report_payload)
            is_blocked = trace_payload.get("fail_closed_reason") is not None or report_payload.get("fail_closed_reason") is not None
            assert_true(not is_blocked, f"custom bundle {name} is blocked and should not be validated as a success case")
            assert_true(bool(raw_svg), f"custom bundle {name} must have non-empty svg")

    print("math-genealogy graph fixtures validated")


if __name__ == "__main__":
    main()
