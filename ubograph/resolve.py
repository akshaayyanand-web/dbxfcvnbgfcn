"""Entity resolution: deciding when two records describe the same entity.

Three layers, strongest first:
  1. Exact identifiers  -> merge  (registration number + jurisdiction, source ID)
  2. Strong fuzzy match -> merge  (name >= MERGE_THRESHOLD + a corroborating attribute)
  3. Weak fuzzy match   -> link   (dashed `possibly_same_as` edge, nothing merged)

A false merge invents a claim about a real person. A "possible match" edge just
shows the lawyer something to check. When in doubt, layer 3.
"""
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from schema import (
    COMPANY,
    PERSON,
    POSSIBLY_SAME_AS,
    UNKNOWN,
    Edge,
    Node,
    norm_country,
    normalise_name,
    year_of,
)

MERGE_THRESHOLD = 92
LINK_THRESHOLD = 84


class EntityStore:
    """Accumulates normalised records from every adapter into one graph."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._alias: Dict[str, str] = {}          # source-native id -> canonical id
        self._by_ident: Dict[Tuple, str] = {}     # strong identifier -> canonical id
        self._by_name: Dict[Tuple[str, str], List[str]] = {}  # (type, name key) -> ids
        self._edge_seen: set = set()

    # -- lookup helpers -------------------------------------------------

    def canonical(self, node_id: Optional[str]) -> Optional[str]:
        if node_id is None:
            return None
        seen = set()
        current = node_id
        while current in self._alias and current not in seen:
            seen.add(current)
            current = self._alias[current]
        return current

    def get(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(self.canonical(node_id) or "")

    @staticmethod
    def _identifiers(node: Node) -> List[Tuple]:
        idents = []
        if node.reg_number:
            reg = str(node.reg_number).strip().lower().replace(" ", "")
            juris = norm_country(node.jurisdiction or node.country) or ""
            if reg:
                idents.append(("reg", juris, reg))
        return idents

    # -- the main entry point -------------------------------------------

    def add_node(self, node: Node) -> str:
        """Insert a record; returns the canonical id it ended up under."""
        existing_id = self.canonical(node.id)
        if existing_id in self.nodes:
            self.nodes[existing_id].merge(node)
            self._index(self.nodes[existing_id])
            return existing_id

        # Layer 1 — exact identifier.
        for ident in self._identifiers(node):
            target = self._by_ident.get(ident)
            if target and target in self.nodes:
                return self._absorb(target, node)

        # Layers 2 and 3 — fuzzy.
        best_id, best_score = self._best_name_match(node)
        if best_id is not None:
            other = self.nodes[best_id]
            if best_score >= MERGE_THRESHOLD and self._corroborated(node, other):
                return self._absorb(best_id, node)
            if best_score >= LINK_THRESHOLD:
                self._store_new(node)
                self.add_edge(
                    Edge(
                        source=node.id,
                        target=best_id,
                        type=POSSIBLY_SAME_AS,
                        confidence=round(best_score / 100.0, 3),
                        origin="resolver",
                        role=f"name similarity {int(best_score)}%",
                    )
                )
                return node.id

        self._store_new(node)
        return node.id

    def merge_nodes(self, keeper_id: str, other_id: str) -> Optional[str]:
        """Force two existing records together.

        Used when a source asserts the identity itself (an OpenSanctions
        referent, or a 100% match with no contradicting identifier) rather than
        when the resolver has merely inferred it.
        """
        keeper = self.canonical(keeper_id)
        other = self.canonical(other_id)
        if not keeper or not other or keeper == other:
            return keeper
        if keeper not in self.nodes or other not in self.nodes:
            return keeper
        absorbed = self.nodes.pop(other)
        self.nodes[keeper].merge(absorbed)
        self._alias[other] = keeper
        self._index(self.nodes[keeper])
        self._rewire(other, keeper)
        self.edges = [
            e for e in self.edges
            if not (e.type == POSSIBLY_SAME_AS and {e.source, e.target} == {keeper})
        ]
        return keeper

    def add_edge(self, edge: Edge) -> None:
        source = self.canonical(edge.source)
        target = self.canonical(edge.target)
        if not source or not target or source == target:
            return
        edge.source, edge.target = source, target
        signature = (source, target, edge.type, edge.role, edge.share_pct)
        if signature in self._edge_seen:
            return
        self._edge_seen.add(signature)
        self.edges.append(edge)

    # -- internals -------------------------------------------------------

    def _store_new(self, node: Node) -> None:
        self.nodes[node.id] = node
        self._index(node)

    def _absorb(self, keeper_id: str, incoming: Node) -> str:
        self.nodes[keeper_id].merge(incoming)
        self._alias[incoming.id] = keeper_id
        self._index(self.nodes[keeper_id])
        self._rewire(incoming.id, keeper_id)
        return keeper_id

    def _rewire(self, old_id: str, new_id: str) -> None:
        for edge in self.edges:
            if edge.source == old_id:
                edge.source = new_id
            if edge.target == old_id:
                edge.target = new_id
        self.edges = [e for e in self.edges if e.source != e.target]

    def _index(self, node: Node) -> None:
        for ident in self._identifiers(node):
            self._by_ident[ident] = node.id
        for name in {node.name, *node.aliases}:
            key = (node.type, normalise_name(name, node.type))
            if not key[1]:
                continue
            bucket = self._by_name.setdefault(key, [])
            if node.id not in bucket:
                bucket.append(node.id)

    def _best_name_match(self, node: Node) -> Tuple[Optional[str], float]:
        key = node.key_name
        if not key:
            return None, 0.0
        best_id, best_score = None, 0.0
        for (other_type, other_key), ids in self._by_name.items():
            if other_type != node.type and UNKNOWN not in (other_type, node.type):
                continue
            score = fuzz.token_sort_ratio(key, other_key)
            if score <= best_score:
                continue
            for candidate in ids:
                if candidate in self.nodes and candidate != node.id:
                    best_id, best_score = candidate, float(score)
                    break
        return best_id, best_score

    @staticmethod
    def _corroborated(a: Node, b: Node) -> bool:
        """A name match alone is never enough to merge — require a second signal."""
        a_country, b_country = norm_country(a.country), norm_country(b.country)
        if a_country and b_country and a_country != b_country:
            return False

        if a.type == PERSON or b.type == PERSON:
            a_year, b_year = year_of(a.birth_date), year_of(b.birth_date)
            if a_year and b_year:
                return a_year == b_year
            # Same country plus a shared source identity is weak-but-usable; a bare
            # name match with no birth year stays a link, not a merge.
            return bool(a_country and b_country and a_country == b_country
                        and (a.reg_number or b.reg_number))

        if a.type == COMPANY or b.type == COMPANY:
            if a.reg_number and b.reg_number:
                return str(a.reg_number).lower() == str(b.reg_number).lower()
            return bool(a_country and b_country and a_country == b_country)

        return bool(a_country and b_country and a_country == b_country)
