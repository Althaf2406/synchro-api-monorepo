"""
tests/test_synchro_pipeline.py
End-to-end unit and integration tests for SynchroAPI:
1. Tree-sitter AST parsing & Multi-Hop GraphRAG Blast Radius Extraction
2. Deterministic OpenAPI Breaking Change Diffing (oasdiff compatible)
3. Multi-Agent Self-Validating Sandbox Loop (Iteration 1 failure -> Iteration 2 self-healing -> Approved PR)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict

from hackathon_core_engine.graphrag_engine import (
    BreakingChangeEvent,
    CrossRepoGraphRAGEngine,
)
from hackathon_core_engine.modal_app import (
    run_downstream_repo_remediation_workflow,
    run_oasdiff_breaking,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
MOCKS_DIR = ROOT_DIR / "pre_existing_mocks"


def _load_repo_files(repo_dir: Path) -> Dict[str, str]:
    files_map: Dict[str, str] = {}
    for file_path in sorted(repo_dir.rglob("*.py")):
        rel = file_path.relative_to(repo_dir).as_posix()
        files_map[rel] = file_path.read_text(encoding="utf-8")
    return files_map


def test_oasdiff_breaking_detects_compound_changes() -> None:
    base_yaml = (MOCKS_DIR / "payment-core-api" / "openapi_v1_base.yaml").read_text(encoding="utf-8")
    head_yaml = (MOCKS_DIR / "payment-core-api" / "openapi_v2_breaking_pr.yaml").read_text(encoding="utf-8")

    diffs = run_oasdiff_breaking(base_yaml, head_yaml)
    assert len(diffs) >= 3
    change_types = {d["change_type"] for d in diffs}
    assert "REMOVED" in change_types
    assert "REQUIRED_ADDED" in change_types
    assert "ENUM_NARROWED" in change_types


def test_graphrag_multi_hop_blast_radius_extraction() -> None:
    upstream_repo = "org/payment-core-api"
    base_yaml = (MOCKS_DIR / "payment-core-api" / "openapi_v1_base.yaml").read_text(encoding="utf-8")

    checkout_files = _load_repo_files(MOCKS_DIR / "checkout-worker")
    billing_files = _load_repo_files(MOCKS_DIR / "billing-analytics")

    engine = CrossRepoGraphRAGEngine()
    engine.index_upstream_openapi(upstream_repo, base_yaml)
    engine.index_downstream_repository("org/checkout-worker", checkout_files, upstream_repo)
    engine.index_downstream_repository("org/billing-analytics", billing_files, upstream_repo)

    breaking_events = [
        BreakingChangeEvent(
            rule_id="request-property-removed",
            level="ERR",
            http_method="POST",
            endpoint_path="/v2/charges",
            schema_model="ChargeRequest",
            field_name="amount_cents",
            change_type="REMOVED",
            description="amount_cents removed in favor of monetary_value",
        )
    ]

    blast_radius = engine.retrieve_blast_radius_subgraph(breaking_events)

    assert "org/checkout-worker" in blast_radius
    assert "org/billing-analytics" in blast_radius

    cw_order = blast_radius["org/checkout-worker"]["topological_order"]
    ba_order = blast_radius["org/billing-analytics"]["topological_order"]

    # Verify DTO comes first, Function comes second, Test comes last
    assert cw_order[0].startswith("dto:")
    assert any(n.startswith("func:") for n in cw_order)
    assert cw_order[-1].startswith("test:")

    # Verify multi-hop function in billing-analytics (calculate_daily_settled_volume_cents) was discovered
    assert any("calculate_daily_settled_volume_cents" in n for n in ba_order)


def test_self_validating_sandbox_loop_and_self_healing() -> None:
    upstream_repo = "org/payment-core-api"
    base_yaml = (MOCKS_DIR / "payment-core-api" / "openapi_v1_base.yaml").read_text(encoding="utf-8")
    head_yaml = (MOCKS_DIR / "payment-core-api" / "openapi_v2_breaking_pr.yaml").read_text(encoding="utf-8")

    checkout_files = _load_repo_files(MOCKS_DIR / "checkout-worker")
    billing_files = _load_repo_files(MOCKS_DIR / "billing-analytics")

    engine = CrossRepoGraphRAGEngine()
    engine.index_upstream_openapi(upstream_repo, base_yaml)
    engine.index_downstream_repository("org/checkout-worker", checkout_files, upstream_repo)
    engine.index_downstream_repository("org/billing-analytics", billing_files, upstream_repo)

    raw_diffs = run_oasdiff_breaking(base_yaml, head_yaml)
    breaking_events = [
        BreakingChangeEvent(
            rule_id=item["id"],
            level=item["level"],
            http_method=item["operation"],
            endpoint_path=item["path"],
            schema_model=item.get("schema_model", "ChargeRequest"),
            field_name=item.get("source_field", "amount_cents"),
            change_type=item.get("change_type", "REMOVED"),
            description=item["text"],
        )
        for item in raw_diffs
    ]
    blast_radius = engine.retrieve_blast_radius_subgraph(breaking_events)

    # Test checkout-worker WITH deliberate Iteration 1 self-healing trigger
    cw_bundle = {
        "target_repo": "org/checkout-worker",
        "upstream_repo": upstream_repo,
        "upstream_pr_number": 42,
        "breaking_changes": [ev.__dict__ for ev in breaking_events],
        "repo_subgraph": blast_radius["org/checkout-worker"],
        "repo_files": checkout_files,
    }
    cw_result = asyncio.run(
        run_downstream_repo_remediation_workflow(cw_bundle, simulate_self_healing_on_iter1=True)
    )

    assert cw_result["status"] == "READY_TO_MERGE_PR_OPENED"
    assert cw_result["iterations_used"] == 2
    assert cw_result["iteration_history"][0]["critic_approved"] is False
    assert cw_result["iteration_history"][1]["critic_approved"] is True
    assert cw_result["iteration_history"][1]["mypy_passed"] is True
    assert cw_result["iteration_history"][1]["pytest_passed"] is True

    # Test billing-analytics passing on Iteration 1
    ba_bundle = {
        "target_repo": "org/billing-analytics",
        "upstream_repo": upstream_repo,
        "upstream_pr_number": 42,
        "breaking_changes": [ev.__dict__ for ev in breaking_events],
        "repo_subgraph": blast_radius["org/billing-analytics"],
        "repo_files": billing_files,
    }
    ba_result = asyncio.run(
        run_downstream_repo_remediation_workflow(ba_bundle, simulate_self_healing_on_iter1=False)
    )
    assert ba_result["status"] == "READY_TO_MERGE_PR_OPENED"
    assert ba_result["iterations_used"] == 1
    assert ba_result["iteration_history"][0]["critic_approved"] is True
