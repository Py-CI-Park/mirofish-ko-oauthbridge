"""
Zep 엔티티 조회 및 필터링 서비스
Zep 그래프에서 노드를 읽고, 사전에 정의한 엔티티 유형에 맞는 노드를 선별한다.
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('mirofish.zep_entity_reader')

# 제네릭 반환 타입용
T = TypeVar('T')

ACTOR_KEYWORD_TYPES = [
    ("개인", "개인"),
    ("투자자", "개인"),
    ("트레이더", "개인"),
    ("운영자", "커뮤니티"),
    ("커뮤니티", "커뮤니티"),
    ("조직", "조직"),
    ("기관", "조직"),
    ("미디어", "미디어"),
    ("분석가", "전문가"),
    ("전문가", "전문가"),
]

ACTOR_TYPE_PRIORITY = {
    "조직": 3,
    "미디어": 3,
    "전문가": 3,
    "커뮤니티": 2,
    "개인": 1,
}

ACTOR_FIELD_WEIGHTS = {
    "name": 3,
    "summary": 2,
    "attributes": 1,
}

NON_ACTOR_KEYWORDS = (
    "지표",
    "변수",
    "함수",
    "수식",
    "조건",
    "indicator",
    "ratio",
    "signal",
    "strategy",
)


@dataclass
class EntityNode:
    """엔티티 노드 데이터 구조"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # 관련 엣지 정보
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # 관련된 다른 노드 정보
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }
    
    def get_entity_type(self) -> Optional[str]:
        """기본 Entity/Node 라벨을 제외한 엔티티 유형을 반환한다."""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return self.attributes.get("derived_entity_type")


@dataclass
class FilteredEntities:
    """필터링된 엔티티 집합"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    readiness: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
            "readiness": self.readiness,
        }


class ZepEntityReader:
    """
    Zep 엔티티 조회 및 필터링 서비스

    주요 기능:
    1. Zep 그래프에서 전체 노드를 조회한다.
    2. 사전에 정의한 엔티티 유형에 맞는 노드를 선별한다.
    3. 각 엔티티의 관련 엣지와 연결 노드 정보를 수집한다.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY가 설정되지 않았습니다")
        
        self.client = Zep(api_key=self.api_key)
    
    def _call_with_retry(
        self, 
        func: Callable[[], T], 
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
        재시도 로직이 포함된 Zep API 호출
        
        Args:
            func: 실행할 함수 (인자 없는 lambda 또는 callable)
            operation_name: 로그에 사용할 작업 이름
            max_retries: 최대 재시도 횟수
            initial_delay: 초기 지연 시간(초)
            
        Returns:
            API 호출 결과
        """
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} 제 {attempt + 1}회 시도 실패: {str(e)[:100]}, "
                        f"{delay:.1f}초 후 다시 시도합니다..."
                    )
                    time.sleep(delay)
                    delay *= 2  # 지수 백오프
                else:
                    logger.error(f"Zep {operation_name} 총 {max_retries}회 시도 후에도 실패했습니다: {str(e)}")
        
        raise last_exception
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        그래프의 전체 노드를 조회한다. (페이지 단위)

        Args:
            graph_id: 그래프 ID

        Returns:
            노드 목록
        """
        logger.info(f"그래프 조회: {graph_id}의 전체 노드를 가져오는 중...")

        nodes = fetch_all_nodes(self.client, graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"총 {len(nodes_data)}개 노드를 가져왔습니다")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        그래프의 전체 엣지를 조회한다. (페이지 단위)

        Args:
            graph_id: 그래프 ID

        Returns:
            엣지 목록
        """
        logger.info(f"그래프 조회: {graph_id}의 전체 엣지를 가져오는 중...")

        edges = fetch_all_edges(self.client, graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"총 {len(edges_data)}개 엣지를 가져왔습니다")
        return edges_data
    
    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        지정한 노드의 관련 엣지를 모두 가져온다. (재시도 포함)
        
        Args:
            node_uuid: 노드 UUID
            
        Returns:
            엣지 목록
        """
        try:
            # 재시도 로직으로 Zep API 호출
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f"노드 엣지 조회(node={node_uuid[:8]}...)"
            )
            
            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })
            
            return edges_data
        except Exception as e:
            logger.warning(f"노드 {node_uuid}의 엣지 조회 실패: {str(e)}")
            return []
    
    @staticmethod
    def _get_custom_labels(labels: List[str]) -> List[str]:
        return [label for label in labels if label not in ["Entity", "Node"]]

    @staticmethod
    def _increment_reason(rejection_reasons: Dict[str, int], reason: str) -> None:
        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

    @staticmethod
    def _build_text_blob(node: Dict[str, Any]) -> str:
        return " ".join(
            part
            for part in ZepEntityReader._iter_text_sections(node).values()
            if part
        )

    @staticmethod
    def _iter_text_sections(node: Dict[str, Any]) -> Dict[str, str]:
        attributes = node.get("attributes", {}) or {}
        attribute_parts = []
        if isinstance(attributes, dict):
            for key, value in attributes.items():
                attribute_parts.append(str(key))
                attribute_parts.append(str(value))
        else:
            attribute_parts.append(str(attributes))

        return {
            "name": str(node.get("name", "")).lower(),
            "summary": str(node.get("summary", "")).lower(),
            "attributes": " ".join(attribute_parts).lower(),
        }

    def _derive_entity_type_from_text(self, node: Dict[str, Any]) -> Optional[str]:
        text_sections = self._iter_text_sections(node)
        matched_scores: Dict[str, int] = {}
        for keyword, entity_type in ACTOR_KEYWORD_TYPES:
            for section_name, section_text in text_sections.items():
                if keyword in section_text:
                    matched_scores[entity_type] = matched_scores.get(entity_type, 0) + (
                        ACTOR_FIELD_WEIGHTS.get(section_name, 0)
                        * ACTOR_TYPE_PRIORITY.get(entity_type, 0)
                    )

        if matched_scores:
            return max(
                matched_scores,
                key=lambda entity_type: matched_scores[entity_type],
            )

        text = self._build_text_blob(node)
        if any(keyword in text for keyword in NON_ACTOR_KEYWORDS):
            return None

        return None

    def _matches_defined_type(
        self,
        entity_type: str,
        defined_entity_types: Optional[List[str]],
        rejection_reasons: Dict[str, int],
    ) -> bool:
        if not defined_entity_types:
            return True
        if entity_type in defined_entity_types:
            return True
        self._increment_reason(rejection_reasons, "entity_type_mismatch")
        return False

    def filter_defined_entities(
        self, 
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
        match_mode: str = "strict"
    ) -> FilteredEntities:
        """
        사전에 정의한 엔티티 유형에 맞는 노드를 필터링한다.

        필터링 로직:
        - 노드의 labels가 `Entity` 하나뿐이면, 사전 정의 타입이 없는 것으로 보고 제외한다.
        - labels에 `Entity`, `Node` 외의 값이 있으면 사전 정의 타입으로 인정한다.
        - `relaxed` 모드에서는 라벨이 없어도 이름/요약/속성의 actor-like 텍스트를 이용해 유형을 추정한다.
        
        Args:
            graph_id: 그래프 ID
            defined_entity_types: 허용할 엔티티 유형 목록(선택)
            enrich_with_edges: 각 엔티티의 관련 엣지 정보를 함께 가져올지 여부
            match_mode: 매칭 모드 (`strict` / `relaxed`)
            
        Returns:
            FilteredEntities: 필터링된 엔티티 집합
        """
        logger.info(f"그래프 필터링 시작: {graph_id}의 엔티티를 검사합니다...")

        normalized_match_mode = (match_mode or "strict").lower()
        if normalized_match_mode not in {"strict", "relaxed"}:
            raise ValueError(f"지원하지 않는 match_mode입니다: {match_mode}")
        
        # 전체 노드 조회
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        
        # 후속 연관 조회에 사용할 엣지 조회
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        
        # 노드 UUID -> 노드 데이터 매핑 구성
        node_map = {n["uuid"]: n for n in all_nodes}
        
        # 조건에 맞는 엔티티 필터링
        filtered_entities = []
        entity_types_found = set()
        labels_present_count = 0
        relaxed_candidate_count = 0
        rejection_reasons: Dict[str, int] = {
            "entity_type_mismatch": 0,
            "missing_actor_labels": 0,
            "non_actor_text": 0,
        }
        
        for node in all_nodes:
            labels = node.get("labels", [])
            
            # labels에는 Entity/Node 외에 실제 엔티티 유형이 있어야 한다.
            custom_labels = self._get_custom_labels(labels)
            entity_attributes = dict(node.get("attributes", {}) or {})
            
            if custom_labels:
                labels_present_count += 1
                entity_type = custom_labels[0]
                if not self._matches_defined_type(entity_type, defined_entity_types, rejection_reasons):
                    continue
            else:
                derived_entity_type = self._derive_entity_type_from_text(node)
                if derived_entity_type:
                    relaxed_candidate_count += 1

                if normalized_match_mode == "strict":
                    self._increment_reason(rejection_reasons, "missing_actor_labels")
                    continue

                if not derived_entity_type:
                    self._increment_reason(rejection_reasons, "non_actor_text")
                    continue

                if not self._matches_defined_type(derived_entity_type, defined_entity_types, rejection_reasons):
                    continue

                entity_attributes["derived_entity_type"] = derived_entity_type
                entity_type = derived_entity_type
            
            entity_types_found.add(entity_type)
            
            # 엔티티 노드 객체 생성
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=entity_attributes,
            )
            
            # 관련 엣지와 노드 조회
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])
                
                entity.related_edges = related_edges
                
                # 연결된 노드의 기본 정보 수집
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })
                
                entity.related_nodes = related_nodes
            
            filtered_entities.append(entity)
        
        readiness = {
            "match_mode": normalized_match_mode,
            "total_nodes": total_count,
            "matched_entities": len(filtered_entities),
            "labels_present_count": labels_present_count,
            "labels_present_ratio": (labels_present_count / total_count) if total_count else 0.0,
            "relaxed_candidate_count": relaxed_candidate_count,
            "rejection_reasons": rejection_reasons,
        }

        logger.info(f"필터링 완료: 총 노드 {total_count}, 조건 충족 {len(filtered_entities)}, "
                   f"엔티티 유형: {entity_types_found}")
        
        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
            readiness=readiness,
        )
    
    def get_entity_with_context(
        self, 
        graph_id: str, 
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        단일 엔티티와 그 전체 컨텍스트(엣지/연결 노드)를 가져온다.
        
        Args:
            graph_id: 그래프 ID
            entity_uuid: 엔티티 UUID
            
        Returns:
            EntityNode 또는 None
        """
        try:
            # 재시도 로직으로 노드 조회
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=entity_uuid),
                operation_name=f"노드 상세 조회(uuid={entity_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            # 노드의 엣지 조회
            edges = self.get_node_edges(entity_uuid)
            
            # 연결 노드 조회를 위해 전체 노드 목록 확보
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}
            
            # 관련 엣지와 노드 정리
            related_edges = []
            related_node_uuids = set()
            
            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])
            
            # 연결 노드 정보 수집
            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })
            
            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )
            
        except Exception as e:
            logger.error(f"엔티티 조회 실패: {entity_uuid} / {str(e)}")
            return None
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
        지정한 유형의 엔티티를 모두 가져온다.
        
        Args:
            graph_id: 그래프 ID
            entity_type: 엔티티 유형 (예: Student, PublicFigure)
            enrich_with_edges: 관련 엣지 정보 포함 여부
            
        Returns:
            엔티티 목록
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities


