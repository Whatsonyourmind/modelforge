"""SQLite persistence for the linkage graph.

Simple schema — two tables. Fast, queryable, diffable, portable.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from modelforge.graph.schema import LinkageGraph, GraphNode, GraphEdge, NodeKind, EdgeKind


SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    model_id TEXT NOT NULL,
    id       TEXT NOT NULL,
    kind     TEXT NOT NULL,
    label    TEXT NOT NULL,
    payload  TEXT NOT NULL,
    PRIMARY KEY (model_id, id)
);

CREATE TABLE IF NOT EXISTS edges (
    model_id TEXT NOT NULL,
    src      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    kind     TEXT NOT NULL,
    payload  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(model_id, src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(model_id, dst);
CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(model_id, kind);
"""


class GraphStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, graph: LinkageGraph) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM nodes WHERE model_id = ?", (graph.model_id,))
            c.execute("DELETE FROM edges WHERE model_id = ?", (graph.model_id,))
            c.executemany(
                "INSERT INTO nodes(model_id, id, kind, label, payload) VALUES (?,?,?,?,?)",
                [
                    (graph.model_id, n.id, n.kind.value, n.label, json.dumps(n.payload))
                    for n in graph.nodes.values()
                ],
            )
            c.executemany(
                "INSERT INTO edges(model_id, src, dst, kind, payload) VALUES (?,?,?,?,?)",
                [
                    (graph.model_id, e.src, e.dst, e.kind.value, json.dumps(e.payload))
                    for e in graph.edges
                ],
            )

    def load(self, model_id: str) -> LinkageGraph:
        g = LinkageGraph(model_id=model_id)
        with self._conn() as c:
            for row in c.execute(
                "SELECT id, kind, label, payload FROM nodes WHERE model_id = ?", (model_id,)
            ):
                g.add_node(
                    GraphNode(
                        id=row["id"],
                        kind=NodeKind(row["kind"]),
                        label=row["label"],
                        payload=json.loads(row["payload"]),
                    )
                )
            for row in c.execute(
                "SELECT src, dst, kind, payload FROM edges WHERE model_id = ?", (model_id,)
            ):
                g.add_edge(
                    GraphEdge(
                        src=row["src"],
                        dst=row["dst"],
                        kind=EdgeKind(row["kind"]),
                        payload=json.loads(row["payload"]),
                    )
                )
        return g

    def lineage(self, model_id: str, cell_id: str) -> list[dict]:
        """Walk back from a cell through formulas → drivers → sources → doc pages.

        Returns a flat list of hops, ordered from leaf to root.
        """
        hops: list[dict] = []
        seen: set[str] = set()
        frontier = [cell_id]
        with self._conn() as c:
            while frontier:
                node_id = frontier.pop(0)
                if node_id in seen:
                    continue
                seen.add(node_id)
                nrow = c.execute(
                    "SELECT id, kind, label FROM nodes WHERE model_id=? AND id=?",
                    (model_id, node_id),
                ).fetchone()
                if nrow is None:
                    continue
                hops.append(dict(nrow))
                # Walk backwards: who computes/provides/cites this node?
                for erow in c.execute(
                    "SELECT src, kind FROM edges WHERE model_id=? AND dst=?",
                    (model_id, node_id),
                ):
                    frontier.append(erow["src"])
        return hops

    def list_sources(self, model_id: str | None = None) -> list[dict]:
        """Return all SOURCE nodes across the database (or for a specific model).

        Each entry is a dict of {id, label, **payload} where payload carries
        the doc, page, publisher, date, URL, and verified fields written by the
        template builder.
        """
        with self._conn() as c:
            if model_id is not None:
                rows = c.execute(
                    "SELECT id, label, payload FROM nodes WHERE kind='source' AND model_id=? ORDER BY id",
                    (model_id,),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, label, payload FROM nodes WHERE kind='source' ORDER BY id"
                ).fetchall()
        return [
            {"id": r["id"], "label": r["label"], **json.loads(r["payload"])}
            for r in rows
        ]

    def stats(self, model_id: str) -> dict[str, int]:
        with self._conn() as c:
            node_counts = dict(
                c.execute(
                    "SELECT kind, COUNT(*) FROM nodes WHERE model_id=? GROUP BY kind",
                    (model_id,),
                ).fetchall()
            )
            edge_counts = dict(
                c.execute(
                    "SELECT kind, COUNT(*) FROM edges WHERE model_id=? GROUP BY kind",
                    (model_id,),
                ).fetchall()
            )
        return {f"nodes:{k}": v for k, v in node_counts.items()} | {
            f"edges:{k}": v for k, v in edge_counts.items()
        }
