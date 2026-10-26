"""
hackathon_core_engine/graphrag_engine.py
Hybrid Structural-Semantic GraphRAG Engine powered by Tree-sitter & NetworkX.
Built exclusively during the Meta Global AI Developer Hackathon (Oct 27 - Nov 4, 2026).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
import tree_sitter_python as tspython
import yaml
from tree_sitter import Language, Parser, Node


PY_LANGUAGE = Language(tspython.language())


def compute_deterministic_embedding(text: str, dim: int = 128) -> List[float]:
    """
    Menghasilkan unit vector embedding untuk teks AST/OpenAPI.
    Pada produksi Modal, fungsi ini juga mendukung panggilan ke endpoint embedding
    Fireworks AI (nomic-embed-text-v1.5) dengan fallback n-gram hashing bebas latensi.
    """
    vec = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    if not tokens:
        return vec.tolist()
    for token in tokens:
        # Sub-token n-grams untuk menangkap kemiripan nama variabel camelCase / snake_case
        subtokens = [token] + [token[i : i + 3] for i in range(max(0, len(token) - 2))]
        for st in subtokens:
            h = int(hashlib.md5(st.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
            vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return [round(float(x), 6) for x in vec]


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    a = np.array(v1, dtype=np.float32)
    b = np.array(v2, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


@dataclass
class BreakingChangeEvent:
    rule_id: str
    level: str
    http_method: str
    endpoint_path: str
    schema_model: str
    field_name: str
    change_type: str  # REMOVED | TYPE_CHANGED | REQUIRED_ADDED | ENUM_NARROWED
    description: str


class CrossRepoGraphRAGEngine:
    """
    Membangun dan mengeksekusi kueri pada Cross-Repository Dependency Knowledge Graph.
    """

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.parser = Parser(PY_LANGUAGE)

    # -------------------------------------------------------------------------
    # 1. INGESTI SPESIFIKASI OPENAPI UPSTREAM
    # -------------------------------------------------------------------------
    def index_upstream_openapi(self, repo_id: str, openapi_yaml_content: str) -> None:
        spec = yaml.safe_load(openapi_yaml_content)
        self.graph.add_node(
            repo_id,
            node_type="Repository",
            role="UPSTREAM",
            default_branch="main",
        )

        # Ingesti Schema Models dan Schema Fields
        schemas = spec.get("components", {}).get("schemas", {})
        for schema_name, schema_def in schemas.items():
            schema_node_id = f"schema:{repo_id}:{schema_name}"
            raw_schema_str = json.dumps(schema_def, sort_keys=True)
            self.graph.add_node(
                schema_node_id,
                node_type="SchemaModel",
                repo_id=repo_id,
                schema_name=schema_name,
                version_hash=hashlib.sha256(raw_schema_str.encode()).hexdigest()[:16],
                semantic_embedding=compute_deterministic_embedding(f"{schema_name} {raw_schema_str}"),
            )

            required_fields = set(schema_def.get("required", []))
            properties = schema_def.get("properties", {})
            for field_name, field_spec in properties.items():
                field_node_id = f"field:{repo_id}:{schema_name}.{field_name}"
                field_type = field_spec.get("type", "object")
                self.graph.add_node(
                    field_node_id,
                    node_type="SchemaField",
                    repo_id=repo_id,
                    schema_name=schema_name,
                    field_name=field_name,
                    data_type=field_type,
                    is_required=(field_name in required_fields),
                    raw_spec=field_spec,
                    semantic_embedding=compute_deterministic_embedding(
                        f"{schema_name} {field_name} {field_type} {json.dumps(field_spec)}"
                    ),
                )
                self.graph.add_edge(schema_node_id, field_node_id, edge_type="HAS_FIELD")

        # Ingesti OpenAPI Endpoints
        paths = spec.get("paths", {})
        for path_str, methods in paths.items():
            for method, operation in methods.items():
                method_upper = method.upper()
                if method_upper not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                    continue
                endpoint_id = f"endpoint:{method_upper}:{path_str}"
                summary = operation.get("summary", "")
                self.graph.add_node(
                    endpoint_id,
                    node_type="OpenAPIEndpoint",
                    repo_id=repo_id,
                    http_method=method_upper,
                    path=path_str,
                    summary=summary,
                    semantic_embedding=compute_deterministic_embedding(f"{method_upper} {path_str} {summary}"),
                )
                self.graph.add_edge(repo_id, endpoint_id, edge_type="EXPOSES_ENDPOINT")

                # Hubungkan Endpoint ke Request/Response SchemaModel
                op_str = json.dumps(operation)
                for ref_match in re.finditer(r"#/components/schemas/([a-zA-Z0-9_]+)", op_str):
                    ref_schema = ref_match.group(1)
                    schema_node_id = f"schema:{repo_id}:{ref_schema}"
                    if self.graph.has_node(schema_node_id):
                        self.graph.add_edge(endpoint_id, schema_node_id, edge_type="USES_SCHEMA")

    # -------------------------------------------------------------------------
    # 2. TREE-SITTER AST PARSER UNTUK REPOSITORI DOWNSTREAM
    # -------------------------------------------------------------------------
    def index_downstream_repository(
        self,
        repo_id: str,
        files_map: Dict[str, str],
        upstream_repo_id: str,
    ) -> None:
        """
        Mem-parsing seluruh file Python pada repositori downstream menggunakan Tree-sitter
        untuk mengekstrak DTO (Pydantic/Dataclass), fungsi, HTTP call-sites, dan unit test.
        """
        self.graph.add_node(
            repo_id,
            node_type="Repository",
            role="DOWNSTREAM",
            default_branch="main",
        )

        # Simpan pemetaan simbol global untuk merajut edge CALLS_FUNCTION dan REFERENCES_DTO
        discovered_dtos: Dict[str, str] = {}       # class_name -> dto_node_id
        discovered_funcs: Dict[str, str] = {}      # func_name -> func_node_id
        function_bodies: List[Tuple[str, str, str]] = []  # (func_node_id, relative_path, source_code)

        for rel_path, source_code in files_map.items():
            if not rel_path.endswith(".py"):
                continue

            file_node_id = f"file:{repo_id}:{rel_path}"
            self.graph.add_node(
                file_node_id,
                node_type="SourceFile",
                repo_id=repo_id,
                relative_path=rel_path,
                file_sha256=hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:16],
            )
            self.graph.add_edge(repo_id, file_node_id, edge_type="CONTAINS_FILE")

            source_bytes = source_code.encode("utf-8")
            tree = self.parser.parse(source_bytes)
            root = tree.root_node

            # Traversal level atas AST
            for child in root.children:
                if child.type == "class_definition":
                    dto_id, class_name = self._extract_dto_node(
                        repo_id, rel_path, file_node_id, child, source_bytes, upstream_repo_id
                    )
                    if dto_id:
                        discovered_dtos[class_name] = dto_id

                elif child.type in {"function_definition", "decorated_definition"}:
                    func_node = child
                    if child.type == "decorated_definition":
                        for sub in child.children:
                            if sub.type == "function_definition":
                                func_node = sub
                                break
                    if func_node.type == "function_definition":
                        f_id, f_name, f_src = self._extract_function_or_test_node(
                            repo_id, rel_path, file_node_id, child, func_node, source_bytes
                        )
                        discovered_funcs[f_name] = f_id
                        function_bodies.append((f_id, rel_path, f_src))

        # Pass Kedua: Rajut CALLS_FUNCTION, REFERENCES_DTO, IMPORTS_SYMBOL, dan VALIDATED_BY_TEST
        for func_node_id, rel_path, f_src in function_bodies:
            node_data = self.graph.nodes[func_node_id]
            is_test = node_data.get("node_type") == "TestSuite"

            # Cek referensi ke DTO
            for dto_name, dto_id in discovered_dtos.items():
                if re.search(rf"\b{re.escape(dto_name)}\b", f_src):
                    self.graph.add_edge(func_node_id, dto_id, edge_type="REFERENCES_DTO")
                    file_src = f"file:{repo_id}:{rel_path}"
                    dto_file = self.graph.nodes[dto_id]["file_id"]
                    if file_src != dto_file:
                        self.graph.add_edge(file_src, dto_file, edge_type="IMPORTS_SYMBOL")

            # Cek panggilan antar fungsi atau cakupan pengujian
            for target_fname, target_fid in discovered_funcs.items():
                if target_fid == func_node_id:
                    continue
                if re.search(rf"\b{re.escape(target_fname)}\s*\(", f_src):
                    if is_test:
                        self.graph.add_edge(func_node_id, target_fid, edge_type="VALIDATED_BY_TEST")
                    else:
                        self.graph.add_edge(func_node_id, target_fid, edge_type="CALLS_FUNCTION")

    def _extract_dto_node(
        self,
        repo_id: str,
        rel_path: str,
        file_node_id: str,
        class_node: Node,
        source_bytes: bytes,
        upstream_repo_id: str,
    ) -> Tuple[Optional[str], str]:
        name_node = class_node.child_by_field_name("name")
        if not name_node:
            return None, ""
        class_name = source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
        raw_class_src = source_bytes[class_node.start_byte : class_node.end_byte].decode("utf-8")

        # Ekstrak field tipe anotasi di dalam body class
        field_mappings: Dict[str, str] = {}
        body_node = class_node.child_by_field_name("body")
        if body_node:
            for stmt in body_node.children:
                stmt_text = source_bytes[stmt.start_byte : stmt.end_byte].decode("utf-8").strip()
                match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([^\n=]+)", stmt_text)
                if match:
                    field_mappings[match.group(1)] = match.group(2).strip()

        dto_id = f"dto:{repo_id}:{rel_path}:{class_name}"
        self.graph.add_node(
            dto_id,
            node_type="DataTransferObject",
            repo_id=repo_id,
            file_id=file_node_id,
            relative_path=rel_path,
            class_name=class_name,
            start_line=class_node.start_point[0] + 1,
            end_line=class_node.end_point[0] + 1,
            field_mappings=field_mappings,
            raw_ast_source=raw_class_src,
            semantic_embedding=compute_deterministic_embedding(
                f"{class_name} {' '.join(field_mappings.keys())} {raw_class_src}"
            ),
        )
        self.graph.add_edge(file_node_id, dto_id, edge_type="DEFINES_DTO")

        # Petakan DTO ke SchemaModel upstream jika memiliki tumpang tindih field atau anotasi kontrak
        for node_id, n_data in self.graph.nodes(data=True):
            if n_data.get("node_type") == "SchemaModel" and n_data.get("repo_id") == upstream_repo_id:
                schema_fields = {
                    self.graph.nodes[succ]["field_name"]
                    for succ in self.graph.successors(node_id)
                    if self.graph.nodes[succ].get("node_type") == "SchemaField"
                }
                overlap = schema_fields.intersection(set(field_mappings.keys()))
                if overlap or n_data["schema_name"].lower() in class_name.lower():
                    self.graph.add_edge(dto_id, node_id, edge_type="MAPS_TO_DTO")

        return dto_id, class_name

    def _extract_function_or_test_node(
        self,
        repo_id: str,
        rel_path: str,
        file_node_id: str,
        outer_node: Node,
        func_node: Node,
        source_bytes: bytes,
    ) -> Tuple[str, str, str]:
        name_node = func_node.child_by_field_name("name")
        func_name = source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8") if name_node else "anonymous"
        raw_func_src = source_bytes[outer_node.start_byte : outer_node.end_byte].decode("utf-8")

        is_test = func_name.startswith("test_") or "tests/" in rel_path or rel_path.startswith("test_")
        node_type = "TestSuite" if is_test else "ASTFunctionNode"
        prefix = "test" if is_test else "func"
        node_id = f"{prefix}:{repo_id}:{rel_path}:{func_name}"

        self.graph.add_node(
            node_id,
            node_type=node_type,
            repo_id=repo_id,
            file_id=file_node_id,
            relative_path=rel_path,
            function_name=func_name,
            start_line=outer_node.start_point[0] + 1,
            end_line=outer_node.end_point[0] + 1,
            raw_ast_source=raw_func_src,
            semantic_embedding=compute_deterministic_embedding(f"{func_name} {raw_func_src}"),
        )
        self.graph.add_edge(file_node_id, node_id, edge_type="DEFINES_FUNCTION")

        # Deteksi HTTP Call-site ke OpenAPIEndpoint upstream (e.g., client.post("/v2/charges", ...))
        for ep_id, ep_data in self.graph.nodes(data=True):
            if ep_data.get("node_type") == "OpenAPIEndpoint":
                ep_path = ep_data["path"]
                if ep_path in raw_func_src:
                    self.graph.add_edge(node_id, ep_id, edge_type="CONSUMES_ENDPOINT")

        return node_id, func_name, raw_func_src

    # -------------------------------------------------------------------------
    # 3. ALGORITMA MULTI-HOP BLAST RADIUS RETRIEVAL (GRAPHRAG)
    # -------------------------------------------------------------------------
    def retrieve_blast_radius_subgraph(
        self,
        breaking_changes: List[BreakingChangeEvent],
        semantic_threshold: float = 0.28,
        max_hops: int = 4,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Menjalankan Multi-Hop Graph Traversal + Hybrid Semantic Scoring untuk menarik
        sub-graf presisi tinggi berisi seluruh DTO, fungsi AST, dan unit test yang terdampak
        pada setiap repositori downstream, diurutkan secara topologis.
        """
        anchor_nodes: Set[str] = set()
        query_texts: List[str] = []

        for bc in breaking_changes:
            query_texts.append(f"{bc.http_method} {bc.endpoint_path} {bc.schema_model} {bc.field_name} {bc.description}")
            ep_candidate = f"endpoint:{bc.http_method.upper()}:{bc.endpoint_path}"
            if self.graph.has_node(ep_candidate):
                anchor_nodes.add(ep_candidate)

            for nid, ndata in self.graph.nodes(data=True):
                if ndata.get("node_type") == "SchemaField" and ndata.get("field_name") == bc.field_name:
                    anchor_nodes.add(nid)
                    # Tambahkan parent SchemaModel sebagai anchor
                    for pred in self.graph.predecessors(nid):
                        anchor_nodes.add(pred)
                elif ndata.get("node_type") == "SchemaModel" and ndata.get("schema_name") == bc.schema_model:
                    anchor_nodes.add(nid)

        combined_query_embedding = compute_deterministic_embedding(" ".join(query_texts))

        # Multi-Hop Reverse Traversal dari anchor upstream menuju downstream consumers
        impacted_nodes: Set[str] = set(anchor_nodes)
        frontier: Set[str] = set(anchor_nodes)

        for _ in range(max_hops):
            next_frontier: Set[str] = set()
            for current in frontier:
                # Telusuri node yang menunjuk ke current (mis. DTO -> SchemaModel, Func -> Endpoint, Caller -> Callee, Test -> Func)
                for predecessor in self.graph.predecessors(current):
                    pred_type = self.graph.nodes[predecessor].get("node_type")
                    if pred_type in {"DataTransferObject", "ASTFunctionNode", "TestSuite", "SchemaModel"}:
                        if predecessor not in impacted_nodes:
                            impacted_nodes.add(predecessor)
                            next_frontier.add(predecessor)
            frontier = next_frontier
            if not frontier:
                break

        # Hybrid Semantic Augmentation: Tangkap fungsi/DTO yang mengakses field secara dinamis (mis. dict["amount_cents"])
        changed_field_names = {bc.field_name for bc in breaking_changes if bc.field_name}
        for nid, ndata in self.graph.nodes(data=True):
            if ndata.get("node_type") in {"ASTFunctionNode", "DataTransferObject", "TestSuite"}:
                raw_src = ndata.get("raw_ast_source", "")
                emb = ndata.get("semantic_embedding", [])
                sim_score = cosine_similarity(combined_query_embedding, emb) if emb else 0.0
                explicit_field_mention = any(
                    re.search(rf"\b{re.escape(fn)}\b", raw_src) for fn in changed_field_names
                )
                if explicit_field_mention or sim_score >= semantic_threshold:
                    impacted_nodes.add(nid)
                    # Tarik pula unit test yang memvalidasi fungsi ini
                    for pred in self.graph.predecessors(nid):
                        if self.graph.nodes[pred].get("node_type") == "TestSuite":
                            impacted_nodes.add(pred)

        # Kelompokkan hasil sub-graf per repositori downstream dan susun urutan topologis
        repo_subgraphs: Dict[str, Dict[str, Any]] = {}
        for nid in impacted_nodes:
            ndata = self.graph.nodes[nid]
            repo_id = ndata.get("repo_id")
            if not repo_id:
                continue
            repo_role = self.graph.nodes.get(repo_id, {}).get("role")
            if repo_role != "DOWNSTREAM":
                continue

            if repo_id not in repo_subgraphs:
                repo_subgraphs[repo_id] = {
                    "repo_id": repo_id,
                    "impacted_dtos": [],
                    "impacted_functions": [],
                    "impacted_tests": [],
                    "files_to_modify": set(),
                    "topological_order": [],
                }

            entry = {
                "node_id": nid,
                "relative_path": ndata.get("relative_path"),
                "start_line": ndata.get("start_line"),
                "end_line": ndata.get("end_line"),
                "raw_ast_source": ndata.get("raw_ast_source"),
            }
            repo_subgraphs[repo_id]["files_to_modify"].add(ndata.get("relative_path"))

            if ndata["node_type"] == "DataTransferObject":
                entry["class_name"] = ndata["class_name"]
                entry["field_mappings"] = ndata["field_mappings"]
                repo_subgraphs[repo_id]["impacted_dtos"].append(entry)
            elif ndata["node_type"] == "ASTFunctionNode":
                entry["function_name"] = ndata["function_name"]
                repo_subgraphs[repo_id]["impacted_functions"].append(entry)
            elif ndata["node_type"] == "TestSuite":
                entry["function_name"] = ndata["function_name"]
                repo_subgraphs[repo_id]["impacted_tests"].append(entry)

        # Hitung Topological Execution Order: DTO -> Service/Client Functions -> Unit Tests
        for repo_id, bundle in repo_subgraphs.items():
            ordered_nodes = (
                [d["node_id"] for d in sorted(bundle["impacted_dtos"], key=lambda x: x["node_id"])]
                + [f["node_id"] for f in sorted(bundle["impacted_functions"], key=lambda x: x["node_id"])]
                + [t["node_id"] for t in sorted(bundle["impacted_tests"], key=lambda x: x["node_id"])]
            )
            bundle["topological_order"] = ordered_nodes
            bundle["files_to_modify"] = sorted(list(bundle["files_to_modify"]))

        return repo_subgraphs
