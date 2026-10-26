"""
scripts/trigger_live_demo_webhook.py
Triggers the end-to-end SynchroAPI pipeline locally or against the deployed Modal endpoint,
and renders real-time GraphRAG + Multi-Agent Self-Healing telemetry in Rich TUI.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from hackathon_core_engine.dashboard_cli import (
    render_blast_radius_tree,
    render_breaking_changes_table,
    render_downstream_execution_results,
    render_synchro_banner,
)
from hackathon_core_engine.graphrag_engine import BreakingChangeEvent, CrossRepoGraphRAGEngine
from hackathon_core_engine.modal_app import (
    run_downstream_repo_remediation_workflow,
    run_oasdiff_breaking,
)


def load_mock_repo_files(repo_dir: Path) -> Dict[str, str]:
    files_map: Dict[str, str] = {}
    for file_path in sorted(repo_dir.rglob("*.py")):
        rel = file_path.relative_to(repo_dir).as_posix()
        files_map[rel] = file_path.read_text(encoding="utf-8")
    return files_map


async def run_live_demo(simulate_self_healing: bool = True) -> None:
    upstream_repo = "org/payment-core-api"
    pr_number = 42

    mocks_root = ROOT_DIR / "pre_existing_mocks"
    base_yaml = (mocks_root / "payment-core-api" / "openapi_v1_base.yaml").read_text(encoding="utf-8")
    head_yaml = (mocks_root / "payment-core-api" / "openapi_v2_breaking_pr.yaml").read_text(encoding="utf-8")

    downstream_repos_snapshot = {
        "org/checkout-worker": load_mock_repo_files(mocks_root / "checkout-worker"),
        "org/billing-analytics": load_mock_repo_files(mocks_root / "billing-analytics"),
    }

    render_synchro_banner(upstream_repo, pr_number)

    # 1. Deterministic OpenAPI Breaking Change Detection
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
    render_breaking_changes_table([ev.__dict__ for ev in breaking_events])

    # 2. Hybrid Structural-Semantic GraphRAG Indexing & Blast Radius Extraction
    kg_engine = CrossRepoGraphRAGEngine()
    kg_engine.index_upstream_openapi(upstream_repo, base_yaml)
    for d_repo, d_files in downstream_repos_snapshot.items():
        kg_engine.index_downstream_repository(d_repo, d_files, upstream_repo)

    blast_radius = kg_engine.retrieve_blast_radius_subgraph(breaking_events)
    render_blast_radius_tree(blast_radius)

    # 3. Parallel Multi-Agent Execution & Self-Validating Sandbox Loop
    tasks = []
    for target_repo, subgraph in blast_radius.items():
        bundle = {
            "target_repo": target_repo,
            "upstream_repo": upstream_repo,
            "upstream_pr_number": pr_number,
            "breaking_changes": [ev.__dict__ for ev in breaking_events],
            "repo_subgraph": subgraph,
            "repo_files": downstream_repos_snapshot[target_repo],
        }
        # Aktifkan self-healing demo pada checkout-worker agar iterasi 1->2 terlihat jelas
        heal_flag = simulate_self_healing and ("checkout-worker" in target_repo)
        tasks.append(run_downstream_repo_remediation_workflow(bundle, simulate_self_healing_on_iter1=heal_flag))

    results = await asyncio.gather(*tasks)
    render_downstream_execution_results(list(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger SynchroAPI Live Demo Pipeline")
    parser.add_argument(
        "--no-self-heal-demo",
        action="store_true",
        help="Disable deliberate Iteration-1 failure demonstration on checkout-worker",
    )
    args = parser.parse_args()
    asyncio.run(run_live_demo(simulate_self_healing=not args.no_self_heal_demo))
