"""Linkage graph — first-class data model.

Every number in a ModelForge workbook is a node. Provenance is an edge.
Excel is one render; the graph is the canonical artifact.

Node kinds:
- DOC_PAGE     — a page in a source document (data room PDF)
- SOURCE       — a cited source (S-001, S-002, ...)
- ASSUMPTION   — an analyst assumption not directly sourced (A-001, ...)
- DRIVER       — a named range on Assumptions sheet
- CELL         — a workbook cell (sheet!ref)
- FORMULA      — the formula that computes a cell
- CHECK        — a QC check cell

Edge kinds:
- CITES          — SOURCE/ASSUMPTION → DOC_PAGE (source material)
- PROVIDES       — SOURCE/ASSUMPTION → DRIVER (the driver's value came from here)
- LIVES_ON       — DRIVER → CELL (the driver cell on Assumptions sheet)
- INPUT_TO       — DRIVER/CELL → FORMULA (the formula reads this cell)
- COMPUTES       — FORMULA → CELL (the formula writes this cell)
- VALIDATES      — CHECK → CELL (the check validates this cell)

Graph persisted to SQLite by GraphStore.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from datetime import date

from pydantic import BaseModel, Field


class NodeKind(str, Enum):
    DOC_PAGE = "doc_page"
    SOURCE = "source"
    ASSUMPTION = "assumption"
    DRIVER = "driver"
    CELL = "cell"
    FORMULA = "formula"
    CHECK = "check"


class EdgeKind(str, Enum):
    CITES = "cites"
    PROVIDES = "provides"
    LIVES_ON = "lives_on"
    INPUT_TO = "input_to"
    COMPUTES = "computes"
    VALIDATES = "validates"


class GraphNode(BaseModel):
    """A node in the linkage graph.

    `id` is a stable human-readable string:
      S-001, A-001, DRV:revenue_growth_y1, CELL:Assumptions!B12,
      FRM:OperatingModel!D7, CHK:QC!B4, DOC:dataroom/fy25.pdf#p14
    """

    id: str
    kind: NodeKind
    label: str = ""
    # Typed payload varies by kind; kept flexible for round-tripping.
    payload: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    src: str
    dst: str
    kind: EdgeKind
    payload: dict = Field(default_factory=dict)


class LinkageGraph(BaseModel):
    """In-memory graph. Persist via GraphStore."""

    model_id: str
    nodes: dict[str, GraphNode] = Field(default_factory=dict)
    edges: list[GraphEdge] = Field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def cite(self, src_id: str, doc_page_id: str, **payload) -> None:
        self.add_edge(GraphEdge(src=src_id, dst=doc_page_id, kind=EdgeKind.CITES, payload=payload))

    def provides(self, source_or_assumption_id: str, driver_id: str, **payload) -> None:
        self.add_edge(
            GraphEdge(
                src=source_or_assumption_id,
                dst=driver_id,
                kind=EdgeKind.PROVIDES,
                payload=payload,
            )
        )

    def lives_on(self, driver_id: str, cell_id: str) -> None:
        self.add_edge(GraphEdge(src=driver_id, dst=cell_id, kind=EdgeKind.LIVES_ON))

    def input_to(self, src_cell_or_driver: str, formula_id: str) -> None:
        self.add_edge(
            GraphEdge(src=src_cell_or_driver, dst=formula_id, kind=EdgeKind.INPUT_TO)
        )

    def computes(self, formula_id: str, cell_id: str) -> None:
        self.add_edge(GraphEdge(src=formula_id, dst=cell_id, kind=EdgeKind.COMPUTES))

    def validates(self, check_id: str, cell_id: str) -> None:
        self.add_edge(GraphEdge(src=check_id, dst=cell_id, kind=EdgeKind.VALIDATES))

    # Helpers to create ID strings consistently.
    @staticmethod
    def cell_id(sheet: str, ref: str) -> str:
        return f"CELL:{sheet}!{ref}"

    @staticmethod
    def driver_id(name: str) -> str:
        return f"DRV:{name}"

    @staticmethod
    def doc_page_id(doc: str, page: int) -> str:
        return f"DOC:{doc}#p{page}"

    @staticmethod
    def formula_id(sheet: str, ref: str) -> str:
        return f"FRM:{sheet}!{ref}"

    @staticmethod
    def check_id(sheet: str, ref: str) -> str:
        return f"CHK:{sheet}!{ref}"
