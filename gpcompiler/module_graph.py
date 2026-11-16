"""Typed, versioned module-link graph kept separate from GP-IR.

GP-MODULE-GRAPH describes source-level modules and dependency resolution. It is
not embedded in GP-IR v1 or GGPC v2; the linker may lower a validated graph to
the existing flat function namespace until a future IR version is specified.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

MODULE_GRAPH_FORMAT = "GP-MODULE-GRAPH"
MODULE_GRAPH_VERSION = 1
_MAX_MODULES = 128
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class GPModuleUnit:
    """One import instance; importing the same file under two aliases is two units."""

    module_id: str
    namespace: str
    parent_id: str | None
    alias: str | None
    exports: tuple[str, ...]


@dataclass(frozen=True)
class GPModuleImport:
    """A source-level dependency edge from importer to imported module."""

    source_id: str
    target_id: str
    alias: str
    path: str


@dataclass(frozen=True)
class GPModuleGraph:
    """Immutable, deterministic result of module discovery and symbol analysis."""

    entry_id: str
    units: tuple[GPModuleUnit, ...]
    imports: tuple[GPModuleImport, ...]
    dependency_order: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        document = {
            "format": MODULE_GRAPH_FORMAT,
            "version": MODULE_GRAPH_VERSION,
            "entry": self.entry_id,
            "units": [
                {
                    "id": unit.module_id,
                    "namespace": unit.namespace,
                    "parent": unit.parent_id,
                    "alias": unit.alias,
                    "exports": list(unit.exports),
                }
                for unit in self.units
            ],
            "imports": [
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "alias": edge.alias,
                    "path": edge.path,
                }
                for edge in self.imports
            ],
            "order": list(self.dependency_order),
        }
        validate_module_graph_document(document)
        return document

    def fingerprint(self) -> str:
        """SHA-256 of the canonical UTF-8 document, stable across process runs."""
        raw = json.dumps(
            self.to_document(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def validate_module_graph_document(document: object) -> dict[str, Any]:
    """Validate the strict GP-MODULE-GRAPH v1 contract without coercion."""
    required = {"format", "version", "entry", "units", "imports", "order"}
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError("GP-MODULE-GRAPH: envelope inválido")
    if document["format"] != MODULE_GRAPH_FORMAT:
        raise ValueError("GP-MODULE-GRAPH: formato inválido")
    if type(document["version"]) is not int or document["version"] != MODULE_GRAPH_VERSION:
        raise ValueError("GP-MODULE-GRAPH: versão não suportada")

    def text(value: object, where: str) -> str:
        if not isinstance(value, str) or not value or "\x00" in value:
            raise ValueError(f"GP-MODULE-GRAPH: texto inválido em {where}")
        return value

    entry = text(document["entry"], "entry")
    units_raw, imports_raw, order = document["units"], document["imports"], document["order"]
    if not isinstance(units_raw, list) or not 1 <= len(units_raw) <= _MAX_MODULES + 1:
        raise ValueError("GP-MODULE-GRAPH: quantidade de unidades inválida")
    if not isinstance(imports_raw, list) or len(imports_raw) > _MAX_MODULES:
        raise ValueError("GP-MODULE-GRAPH: quantidade de imports inválida")
    if not isinstance(order, list) or len(order) != len(units_raw):
        raise ValueError("GP-MODULE-GRAPH: ordem de dependências inválida")

    units: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(units_raw):
        if not isinstance(raw, dict) or set(raw) != {
            "id", "namespace", "parent", "alias", "exports"
        }:
            raise ValueError(f"GP-MODULE-GRAPH: unidade inválida em units[{index}]")
        module_id = text(raw["id"], f"units[{index}].id")
        namespace = raw["namespace"]
        if not isinstance(namespace, str) or "\x00" in namespace:
            raise ValueError(f"GP-MODULE-GRAPH: namespace inválido em {module_id}")
        parent, alias, exports = raw["parent"], raw["alias"], raw["exports"]
        if parent is not None:
            text(parent, f"{module_id}.parent")
        if alias is not None:
            text(alias, f"{module_id}.alias")
            if not _IDENTIFIER.fullmatch(alias):
                raise ValueError(f"GP-MODULE-GRAPH: alias GP inválido em {module_id}")
        if not isinstance(exports, list):
            raise ValueError(f"GP-MODULE-GRAPH: exports inválidos em {module_id}")
        seen_exports: set[str] = set()
        for name in exports:
            text(name, f"{module_id}.exports")
            if not _IDENTIFIER.fullmatch(name) or name in seen_exports:
                raise ValueError(f"GP-MODULE-GRAPH: export duplicado ou inválido: {name}")
            seen_exports.add(name)
        if module_id in units:
            raise ValueError(f"GP-MODULE-GRAPH: ID duplicado: {module_id}")
        units[module_id] = raw

    if entry not in units:
        raise ValueError("GP-MODULE-GRAPH: unidade de entrada ausente")
    root = units[entry]
    if root["parent"] is not None or root["alias"] is not None or root["namespace"] != "":
        raise ValueError("GP-MODULE-GRAPH: unidade de entrada inconsistente")

    edges_by_source: dict[str, list[dict[str, str]]] = {key: [] for key in units}
    incoming: dict[str, int] = {key: 0 for key in units}
    for index, edge in enumerate(imports_raw):
        if not isinstance(edge, dict) or set(edge) != {"source", "target", "alias", "path"}:
            raise ValueError(f"GP-MODULE-GRAPH: import inválido em imports[{index}]")
        source = text(edge["source"], f"imports[{index}].source")
        target = text(edge["target"], f"imports[{index}].target")
        alias = text(edge["alias"], f"imports[{index}].alias")
        path = text(edge["path"], f"imports[{index}].path")
        if source not in units or target not in units or source == target:
            raise ValueError(f"GP-MODULE-GRAPH: referência de import inválida em imports[{index}]")
        if not _IDENTIFIER.fullmatch(alias):
            raise ValueError(f"GP-MODULE-GRAPH: alias inválido em imports[{index}]")
        if any(item["alias"] == alias for item in edges_by_source[source]):
            raise ValueError(f"GP-MODULE-GRAPH: alias duplicado em {source}: {alias}")
        target_unit = units[target]
        if target_unit["parent"] != source or target_unit["alias"] != alias:
            raise ValueError(f"GP-MODULE-GRAPH: relação pai/alias inconsistente para {target}")
        edges_by_source[source].append(edge)
        incoming[target] += 1

    if incoming[entry] != 0:
        raise ValueError("GP-MODULE-GRAPH: entrada não pode ser dependência")
    for module_id, raw in units.items():
        if module_id == entry:
            continue
        if incoming[module_id] != 1 or raw["parent"] not in units:
            raise ValueError(f"GP-MODULE-GRAPH: unidade órfã ou compartilhada: {module_id}")

    if len(set(order)) != len(order) or set(order) != set(units):
        raise ValueError("GP-MODULE-GRAPH: ordem contém IDs ausentes ou duplicados")
    positions = {module_id: index for index, module_id in enumerate(order)}
    if positions[entry] != len(order) - 1:
        raise ValueError("GP-MODULE-GRAPH: unidade de entrada deve ser a última")
    for source, edges in edges_by_source.items():
        for edge in edges:
            if positions[edge["target"]] >= positions[source]:
                raise ValueError("GP-MODULE-GRAPH: dependência deve preceder o módulo importador")

    # Every unit must be reachable from the entry; parent links must be acyclic.
    reached: set[str] = set()
    pending = [entry]
    while pending:
        current = pending.pop()
        if current in reached:
            continue
        reached.add(current)
        pending.extend(edge["target"] for edge in edges_by_source[current])
    if reached != set(units):
        raise ValueError("GP-MODULE-GRAPH: grafo contém unidades inalcançáveis")
    namespaces: set[str] = {""}
    for module_id, raw in units.items():
        if module_id == entry:
            continue
        parent_id = raw["parent"]
        parent_namespace = units[parent_id]["namespace"]
        alias = raw["alias"]
        expected_namespace = (
            "__gp_namespace_" + alias
            if parent_id == entry
            else parent_namespace + "__" + alias
        )
        if raw["namespace"] != expected_namespace or raw["namespace"] in namespaces:
            raise ValueError(f"GP-MODULE-GRAPH: namespace duplicado ou inconsistente: {module_id}")
        namespaces.add(raw["namespace"])

    for module_id in units:
        ancestry: set[str] = set()
        current: str | None = module_id
        while current is not None:
            if current in ancestry:
                raise ValueError("GP-MODULE-GRAPH: ciclo na hierarquia de módulos")
            ancestry.add(current)
            parent = units[current]["parent"]
            current = parent
    return document


def module_graph_from_document(document: object) -> GPModuleGraph:
    """Parse a validated canonical module graph into immutable typed records."""
    raw = validate_module_graph_document(document)
    units = tuple(
        GPModuleUnit(
            module_id=item["id"], namespace=item["namespace"],
            parent_id=item["parent"], alias=item["alias"],
            exports=tuple(item["exports"]),
        )
        for item in raw["units"]
    )
    imports = tuple(
        GPModuleImport(
            source_id=item["source"], target_id=item["target"],
            alias=item["alias"], path=item["path"],
        )
        for item in raw["imports"]
    )
    return GPModuleGraph(
        entry_id=raw["entry"], units=units, imports=imports,
        dependency_order=tuple(raw["order"]),
    )
