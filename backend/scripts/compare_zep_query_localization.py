"""Compare legacy Chinese and Korean Zep search query wording.

This is an experimental validation helper for prompt/localization work.
It compares the previous Chinese query template with the Korean query template
against the same graph/entities and prints overlap counts.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Iterable

from app.services.zep_entity_reader import ZepEntityReader


@dataclass
class SearchComparison:
    entity_name: str
    old_edges: int
    new_edges: int
    edge_overlap: int
    old_nodes: int
    new_nodes: int
    node_overlap: int


def _search(client, graph_id: str, query: str, scope: str, limit: int) -> list[str]:
    result = client.graph.search(
        query=query,
        graph_id=graph_id,
        limit=limit,
        scope=scope,
        reranker="rrf",
    )

    if scope == "edges":
        edges = getattr(result, "edges", []) or []
        return [getattr(edge, "fact", "") for edge in edges if getattr(edge, "fact", "")]

    nodes = getattr(result, "nodes", []) or []
    output = []
    for node in nodes:
        name = getattr(node, "name", "")
        summary = getattr(node, "summary", "")
        if name or summary:
            output.append(f"{name}: {summary[:160]}")
    return output


def compare_queries(graph_id: str, entity_names: Iterable[str], limit: int) -> list[SearchComparison]:
    reader = ZepEntityReader()
    client = reader.client
    comparisons = []

    for entity_name in entity_names:
        old_query = f"关于{entity_name}的所有信息、活动、事件、关系和背景"
        new_query = f"{entity_name}에 대한 모든 정보, 활동, 사건, 관계, 배경"

        old_edges = _search(client, graph_id, old_query, "edges", limit)
        new_edges = _search(client, graph_id, new_query, "edges", limit)
        old_nodes = _search(client, graph_id, old_query, "nodes", limit)
        new_nodes = _search(client, graph_id, new_query, "nodes", limit)

        comparisons.append(
            SearchComparison(
                entity_name=entity_name,
                old_edges=len(old_edges),
                new_edges=len(new_edges),
                edge_overlap=len(set(old_edges) & set(new_edges)),
                old_nodes=len(old_nodes),
                new_nodes=len(new_nodes),
                node_overlap=len(set(old_nodes) & set(new_nodes)),
            )
        )

    return comparisons


def _default_entity_names(graph_id: str, count: int) -> list[str]:
    reader = ZepEntityReader()
    nodes = reader.get_all_nodes(graph_id)
    names = [node["name"] for node in nodes if node.get("name")]
    return names[:count]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-id", required=True)
    parser.add_argument("--entity", action="append", dest="entities", default=[])
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    entity_names = args.entities or _default_entity_names(args.graph_id, args.sample_count)
    comparisons = compare_queries(args.graph_id, entity_names, args.limit)

    print(f"graph_id={args.graph_id}")
    print("entity\told_edges\tnew_edges\tedge_overlap\told_nodes\tnew_nodes\tnode_overlap")
    for item in comparisons:
        print(
            f"{item.entity_name}\t"
            f"{item.old_edges}\t{item.new_edges}\t{item.edge_overlap}\t"
            f"{item.old_nodes}\t{item.new_nodes}\t{item.node_overlap}"
        )


if __name__ == "__main__":
    main()
