# SynchroAPI: Autonomous Cross-Repository CI/CD Multi-Agent Remediation Engine

> **Meta Global AI Developer Hackathon Submission** (Indie Developer Track & \$5,000 Agentic Architecture Bonus Prize)
> Powered by **Meta Muse Spark Open** (Baseten 2M TPM), **Meta Muse Code** (Fireworks AI Speculative Decoding), **Hybrid Tree-sitter GraphRAG**, and **Modal.com Serverless Sandboxes**.

---

## Overview

**SynchroAPI** transforms passive CI/CD breaking-change alerts into autonomous, verified cross-repository Pull Requests. When an upstream service modifies its OpenAPI contract, SynchroAPI:

1. **Detects Deterministic Breaking Changes:** Executes `oasdiff breaking` inside a custom `modal.Image` container.
2. **Extracts Multi-Hop Blast Radius via Hybrid GraphRAG:** Parses downstream repositories into a directed AST property graph (`Repository`, `OpenAPIEndpoint`, `SchemaModel`, `SchemaField`, `DataTransferObject`, `ASTFunctionNode`, `TestSuite`) using `tree-sitter-python` and `NetworkX` to uncover 1st, 2nd, and 3rd-hop downstream callers in strict topological order (`DTO -> Function -> Unit Test`).
3. **Plans Topological Migrations (`Muse Spark Open` on Baseten):** Generates a structured JSON `RepoMigrationPlan` with invariant business logic assertions.
4. **Synthesizes & Self-Heals Multi-File AST Patches (`Muse Code` on Fireworks AI + `modal.Sandbox`):** Executes a up-to-3-iteration self-validating loop running `mypy` static type checks and `pytest` inside isolated ephemeral containers, audited by a **Semantic Critic Agent (`Muse Spark Open`)** before opening ready-to-merge GitHub Pull Requests.

---

## Repository Structure

```text
.
├── README.md                                  # Architecture blueprint & quickstart
├── requirements.txt                           # Python dependencies
├── scripts/
│   ├── verify_hackathon_compliance.sh         # Git log & SHA compliance auditor (Oct 27 - Nov 4)
│   └── trigger_live_demo_webhook.py           # Live Rich TUI 3-minute demo runner
├── pre_existing_mocks/                        # Isolated Mock Ecosystem (Upstream + 2 Downstream Repos)
│   ├── payment-core-api/
│   │   ├── openapi_v1_base.yaml
│   │   └── openapi_v2_breaking_pr.yaml
│   ├── checkout-worker/
│   │   ├── src/models.py
│   │   ├── src/client.py
│   │   └── tests/test_client.py
│   └── billing-analytics/
│       ├── src/schemas.py
│       ├── src/aggregator.py
│       └── tests/test_aggregator.py
├── hackathon_core_engine/                     # Core Engine (GraphRAG, Multi-Agent, Modal, CLI)
│   ├── __init__.py
│   ├── graphrag_engine.py
│   ├── agents_orchestrator.py
│   ├── modal_app.py
│   └── dashboard_cli.py
└── tests/
    └── test_synchro_pipeline.py               # End-to-end unit & sandbox self-healing verification suite
```

---

## Quickstart & Local Verification

### 1. Run End-to-End Pytest Suite
```bash
pytest -v
```

### 2. Run the Live Rich TUI Demo (with Self-Healing Iteration 1 -> 2 Trace)
```bash
python scripts/trigger_live_demo_webhook.py
```

### 3. Deploy to Modal.com Serverless Cloud
```bash
modal deploy hackathon_core_engine/modal_app.py
```
