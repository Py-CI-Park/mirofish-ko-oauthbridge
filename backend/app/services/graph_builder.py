"""
그래프 구축 서비스
인터페이스 2에서 Zep API를 사용해 standalone graph를 구축한다.
"""

import os
import uuid
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from zep_cloud.client import Zep
from zep_cloud import EpisodeData, EntityEdgeSourceTarget

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from .ontology_normalizer import normalize_ontology_for_zep
from .text_processor import TextProcessor


@dataclass
class GraphInfo:
    """그래프 정보"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class OntologyApplyError(RuntimeError):
    """Raised when ontology application fails after graph creation."""

    def __init__(
        self,
        graph_id: str,
        cause: Exception,
        cleanup_error: Optional[Exception] = None,
    ):
        self.graph_id = graph_id
        self.cause = cause
        self.cleanup_error = cleanup_error
        self.cleanup_succeeded = cleanup_error is None

        if cleanup_error is None:
            message = (
                f"Ontology apply failed for graph {graph_id}: {cause}. "
                "Graph cleanup succeeded."
            )
        else:
            message = (
                f"Ontology apply failed for graph {graph_id}: {cause}. "
                f"Graph cleanup also failed: {cleanup_error}"
            )

        super().__init__(message)


class GraphBuilderService:
    """
    그래프 구축 서비스
    Zep API를 호출해 지식 그래프를 구축한다.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY is not configured")
        
        self.client = Zep(api_key=self.api_key)
        self.task_manager = TaskManager()
    
    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        그래프를 비동기로 구축한다.
        
        Args:
            text: 입력 텍스트
            ontology: 온톨로지 정의 (인터페이스 1 출력값)
            graph_name: 그래프 이름
            chunk_size: 텍스트 청크 크기
            chunk_overlap: 청크 중첩 크기
            batch_size: 한 번에 보내는 청크 수
            
        Returns:
            작업 ID
        """
        # 작업 생성
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )
        
        # 백그라운드 스레드에서 구축 실행
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size)
        )
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int
    ):
        """그래프 구축 작업 스레드"""
        graph_id = None
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="Starting graph build..."
            )
            
            # 1. 그래프 생성
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"Graph created: {graph_id}"
            )
            
            # 2. 온톨로지 적용
            self.apply_ontology_with_cleanup(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="Ontology applied"
            )
            
            # 3. 텍스트 분할
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"Text split into {total_chunks} chunks"
            )
            
            # 4. 데이터를 배치 단위로 전송
            episode_uuids = self.add_text_batches(
                graph_id, chunks, batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),  # 20-60%
                    message=msg
                )
            )
            
            # 5. Zep 처리 완료 대기
            self.task_manager.update_task(
                task_id,
                progress=60,
                message="Waiting for Zep to process data..."
            )
            
            self._wait_for_episodes(
                episode_uuids,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=60 + int(prog * 0.3),  # 60-90%
                    message=msg
                )
            )
            
            # 6. 그래프 정보 조회
            self.task_manager.update_task(
                task_id,
                progress=90,
                message="Fetching graph information..."
            )
            
            graph_info = self._get_graph_info(graph_id)
            
            # 완료 처리
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)
    
    def create_graph(self, name: str) -> str:
        """Zep 그래프를 생성한다. (공개 메서드)"""
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        
        self.client.graph.create(
            graph_id=graph_id,
            name=name,
            description="MiroFish Social Simulation Graph"
        )
        
        return graph_id
    
    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """그래프 온톨로지를 설정한다. (공개 메서드)"""
        import warnings
        from typing import Optional
        from pydantic import Field
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel
        
        # Pydantic v2의 Field(default=None) 관련 경고를 숨긴다.
        # Zep SDK가 요구하는 사용 방식이며, 동적 클래스 생성에서 발생하는 경고라 무시 가능하다.
        warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')
        
        # Zep 예약 이름은 속성명으로 사용할 수 없다.
        RESERVED_NAMES = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}
        
        def safe_attr_name(attr_name: str) -> str:
            """예약 이름을 안전한 속성명으로 변환한다."""
            if attr_name.lower() in RESERVED_NAMES:
                return f"entity_{attr_name}"
            return attr_name

        try:
            normalized_ontology = normalize_ontology_for_zep(ontology)
        except Exception as exc:
            raise ValueError(
                f"Ontology normalization failed before Zep set_ontology for graph {graph_id}: {exc}"
            ) from exc
        
        # 엔티티 유형 클래스를 동적으로 생성
        entity_types = {}
        for entity_def in normalized_ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")
            
            # 속성 딕셔너리와 타입 주석 생성 (Pydantic v2 요구)
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in entity_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])  # 안전한 속성명 사용
                attr_desc = attr_def.get("description", attr_name)
                # Zep API는 Field의 description을 요구한다.
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[EntityText]  # 타입 주석
            
            attrs["__annotations__"] = annotations
            
            # 동적 클래스 생성
            entity_class = type(name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[name] = entity_class
        
        # 엣지 유형 클래스를 동적으로 생성
        edge_definitions = {}
        for edge_def in normalized_ontology.get("edge_types", []):
            name = edge_def["name"]
            description = edge_def.get("description", f"A {name} relationship.")
            
            # 속성 딕셔너리와 타입 주석 생성
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in edge_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])  # 안전한 속성명 사용
                attr_desc = attr_def.get("description", attr_name)
                # Zep API는 Field의 description을 요구한다.
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[str]  # 엣지 속성은 str 타입 사용
            
            attrs["__annotations__"] = annotations
            
            # 동적 클래스 생성
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            edge_class = type(class_name, (EdgeModel,), attrs)
            edge_class.__doc__ = description
            
            # source_targets 구성
            source_targets = []
            for st in edge_def.get("source_targets", []):
                source_targets.append(
                    EntityEdgeSourceTarget(
                        source=st.get("source", "Entity"),
                        target=st.get("target", "Entity")
                    )
                )
            
            if source_targets:
                edge_definitions[name] = (edge_class, source_targets)
        
        # Zep API 호출로 온톨로지 설정
        if entity_types or edge_definitions:
            try:
                self.client.graph.set_ontology(
                    graph_ids=[graph_id],
                    entities=entity_types if entity_types else None,
                    edges=edge_definitions if edge_definitions else None,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Zep set_ontology failed for graph {graph_id}: {exc}"
                ) from exc

    def apply_ontology_with_cleanup(self, graph_id: str, ontology: Dict[str, Any]):
        """Apply ontology and delete the graph if apply fails."""
        try:
            self.set_ontology(graph_id, ontology)
        except Exception as exc:
            cleanup_error = None
            try:
                self.delete_graph(graph_id)
            except Exception as cleanup_exc:
                cleanup_error = cleanup_exc

            raise OntologyApplyError(
                graph_id=graph_id,
                cause=exc,
                cleanup_error=cleanup_error,
            ) from exc
    
    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """텍스트를 배치 단위로 그래프에 추가하고 episode UUID 목록을 반환한다."""
        episode_uuids = []
        total_chunks = len(chunks)
        
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size
            
            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    f"Sending batch {batch_num}/{total_batches} ({len(batch_chunks)} chunks)...",
                    progress
                )
            
            # episode 데이터 구성
            episodes = [
                EpisodeData(data=chunk, type="text")
                for chunk in batch_chunks
            ]
            
            # Zep으로 전송
            try:
                batch_result = self.client.graph.add_batch(
                    graph_id=graph_id,
                    episodes=episodes
                )
                
                # 반환된 episode UUID 수집
                if batch_result and isinstance(batch_result, list):
                    for ep in batch_result:
                        ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                        if ep_uuid:
                            episode_uuids.append(ep_uuid)
                
                # 요청이 너무 빨라지지 않도록 잠시 대기
                time.sleep(1)
                
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Batch {batch_num} failed to send: {str(e)}", 0)
                raise
        
        return episode_uuids
    
    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600
    ):
        """모든 episode 처리가 끝날 때까지 기다린다. (각 episode의 processed 상태 조회)"""
        if not episode_uuids:
            if progress_callback:
                progress_callback("No waiting needed (no episodes)", 1.0)
            return
        
        start_time = time.time()
        pending_episodes = set(episode_uuids)
        completed_count = 0
        total_episodes = len(episode_uuids)
        
        if progress_callback:
            progress_callback(f"Waiting for {total_episodes} text chunks to finish processing...", 0)
        
        while pending_episodes:
            if time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(
                        f"Some text chunks timed out, completed {completed_count}/{total_episodes}",
                        completed_count / total_episodes
                    )
                break
            
            # 각 episode의 처리 상태 확인
            for ep_uuid in list(pending_episodes):
                try:
                    episode = self.client.graph.episode.get(uuid_=ep_uuid)
                    is_processed = getattr(episode, 'processed', False)
                    
                    if is_processed:
                        pending_episodes.remove(ep_uuid)
                        completed_count += 1
                        
                except Exception as e:
                    # 개별 조회 오류는 무시하고 계속 진행
                    pass
            
            elapsed = int(time.time() - start_time)
            if progress_callback:
                progress_callback(
                    f"Zep processing... {completed_count}/{total_episodes} completed, {len(pending_episodes)} pending ({elapsed}s)",
                    completed_count / total_episodes if total_episodes > 0 else 0
                )
            
            if pending_episodes:
                time.sleep(3)  # 3초마다 한 번씩 확인
        
        if progress_callback:
            progress_callback(f"Processing complete: {completed_count}/{total_episodes}", 1.0)
    
    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """그래프 정보를 조회한다."""
        # 노드 조회 (페이지 단위)
        nodes = fetch_all_nodes(self.client, graph_id)

        # 엣지 조회 (페이지 단위)
        edges = fetch_all_edges(self.client, graph_id)

        # 엔티티 유형 집계
        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )
    
    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        전체 그래프 데이터를 조회한다. (상세 정보 포함)
        
        Args:
            graph_id: 그래프 ID
            
        Returns:
            nodes와 edges를 포함한 딕셔너리. 시간 정보, 속성 등 상세 데이터를 포함한다.
        """
        nodes = fetch_all_nodes(self.client, graph_id)
        edges = fetch_all_edges(self.client, graph_id)

        # 노드 이름 조회를 위한 노드 매핑 생성
        node_map = {}
        for node in nodes:
            node_map[node.uuid_] = node.name or ""
        
        nodes_data = []
        for node in nodes:
            # 생성 시각 조회
            created_at = getattr(node, 'created_at', None)
            if created_at:
                created_at = str(created_at)
            
            nodes_data.append({
                "uuid": node.uuid_,
                "name": node.name,
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
                "created_at": created_at,
            })
        
        edges_data = []
        for edge in edges:
            # 시간 정보 조회
            created_at = getattr(edge, 'created_at', None)
            valid_at = getattr(edge, 'valid_at', None)
            invalid_at = getattr(edge, 'invalid_at', None)
            expired_at = getattr(edge, 'expired_at', None)
            
            # episodes 조회
            episodes = getattr(edge, 'episodes', None) or getattr(edge, 'episode_ids', None)
            if episodes and not isinstance(episodes, list):
                episodes = [str(episodes)]
            elif episodes:
                episodes = [str(e) for e in episodes]
            
            # fact_type 조회
            fact_type = getattr(edge, 'fact_type', None) or edge.name or ""
            
            edges_data.append({
                "uuid": edge.uuid_,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "fact_type": fact_type,
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": edge.attributes or {},
                "created_at": str(created_at) if created_at else None,
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": episodes or [],
            })
        
        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }
    
    def delete_graph(self, graph_id: str):
        """그래프를 삭제한다."""
        self.client.graph.delete(graph_id=graph_id)
