"""
OASIS 시뮬레이션 관리자
Twitter와 Reddit 이중 플랫폼 시뮬레이션을 관리한다.
프리셋 스크립트와 LLM 기반 설정 생성을 함께 사용한다.
"""

import os
import json
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import ZepEntityReader, FilteredEntities
from .oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile
from .simulation_config_generator import SimulationConfigGenerator, SimulationParameters

logger = get_logger('mirofish.simulation')


class SimulationStatus(str, Enum):
    """시뮬레이션 상태"""
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"      # 수동 중지됨
    COMPLETED = "completed"  # 자연 종료됨
    FAILED = "failed"


class PlatformType(str, Enum):
    """플랫폼 유형"""
    TWITTER = "twitter"
    REDDIT = "reddit"


@dataclass
class SimulationState:
    """시뮬레이션 상태"""
    simulation_id: str
    project_id: str
    graph_id: str
    
    # 플랫폼 활성화 상태
    enable_twitter: bool = True
    enable_reddit: bool = True
    
    # 상태
    status: SimulationStatus = SimulationStatus.CREATED
    
    # 준비 단계 데이터
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)
    entity_filter_mode: str = "strict"
    entity_readiness: Dict[str, Any] = field(default_factory=dict)
    failure_stage: Optional[str] = None
    failure_kind: Optional[str] = None
    
    # 설정 생성 정보
    config_generated: bool = False
    config_reasoning: str = ""
    prepare_task_id: Optional[str] = None
    prepare_cancelled: bool = False
    
    # 실행 중 데이터
    current_round: int = 0
    twitter_status: str = "not_started"
    reddit_status: str = "not_started"
    
    # 타임스탬프
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 오류 정보
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """전체 상태 딕셔너리 (내부용)."""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "enable_twitter": self.enable_twitter,
            "enable_reddit": self.enable_reddit,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "entity_filter_mode": self.entity_filter_mode,
            "entity_readiness": self.entity_readiness,
            "failure_stage": self.failure_stage,
            "failure_kind": self.failure_kind,
            "config_generated": self.config_generated,
            "config_reasoning": self.config_reasoning,
            "prepare_task_id": self.prepare_task_id,
            "prepare_cancelled": self.prepare_cancelled,
            "current_round": self.current_round,
            "twitter_status": self.twitter_status,
            "reddit_status": self.reddit_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """축약 상태 딕셔너리 (API 응답용)."""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "entity_filter_mode": self.entity_filter_mode,
            "entity_readiness": self.entity_readiness,
            "failure_stage": self.failure_stage,
            "failure_kind": self.failure_kind,
            "config_generated": self.config_generated,
            "error": self.error,
        }


class SimulationManager:
    """
    시뮬레이션 관리자

    핵심 기능:
    1. Zep 그래프에서 엔티티를 읽고 필터링한다.
    2. OASIS Agent Profile을 생성한다.
    3. LLM으로 시뮬레이션 설정 파라미터를 생성한다.
    4. 프리셋 스크립트 실행에 필요한 파일을 준비한다.
    """
    
    # 시뮬레이션 데이터 저장 디렉터리
    SIMULATION_DATA_DIR = os.path.join(
        os.path.dirname(__file__), 
        '../../uploads/simulations'
    )
    
    def __init__(self):
        # 디렉터리가 존재하도록 보장한다.
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)
        
        # 메모리 내 시뮬레이션 상태 캐시
        self._simulations: Dict[str, SimulationState] = {}
    
    def _get_simulation_dir(self, simulation_id: str) -> str:
        """시뮬레이션 데이터 디렉터리를 반환한다."""
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir
    
    def _save_simulation_state(self, state: SimulationState):
        """시뮬레이션 상태를 파일로 저장한다."""
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        state.updated_at = datetime.now().isoformat()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        
        self._simulations[state.simulation_id] = state
    
    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        """파일에서 시뮬레이션 상태를 불러온다."""
        if simulation_id in self._simulations:
            return self._simulations[simulation_id]
        
        sim_dir = self._get_simulation_dir(simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        if not os.path.exists(state_file):
            return None
        
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=data.get("project_id", ""),
            graph_id=data.get("graph_id", ""),
            enable_twitter=data.get("enable_twitter", True),
            enable_reddit=data.get("enable_reddit", True),
            status=SimulationStatus(data.get("status", "created")),
            entities_count=data.get("entities_count", 0),
            profiles_count=data.get("profiles_count", 0),
            entity_types=data.get("entity_types", []),
            entity_filter_mode=data.get("entity_filter_mode", "strict"),
            entity_readiness=data.get("entity_readiness", {}),
            failure_stage=data.get("failure_stage"),
            failure_kind=data.get("failure_kind"),
            config_generated=data.get("config_generated", False),
            config_reasoning=data.get("config_reasoning", ""),
            prepare_task_id=data.get("prepare_task_id"),
            prepare_cancelled=data.get("prepare_cancelled", False),
            current_round=data.get("current_round", 0),
            twitter_status=data.get("twitter_status", "not_started"),
            reddit_status=data.get("reddit_status", "not_started"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            error=data.get("error"),
        )
        
        self._simulations[simulation_id] = state
        return state
    
    def create_simulation(
        self,
        project_id: str,
        graph_id: str,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
    ) -> SimulationState:
        """
        새 시뮬레이션을 생성한다.
        
        Args:
            project_id: 프로젝트 ID
            graph_id: Zep 그래프 ID
            enable_twitter: Twitter 시뮬레이션 활성화 여부
            enable_reddit: Reddit 시뮬레이션 활성화 여부
            
        Returns:
            SimulationState
        """
        import uuid
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
            status=SimulationStatus.CREATED,
        )
        
        self._save_simulation_state(state)
        logger.info(f"시뮬레이션 생성: {simulation_id}, project={project_id}, graph={graph_id}")
        
        return state

    def _clear_failure_state(self, state: SimulationState) -> None:
        state.error = None
        state.failure_stage = None
        state.failure_kind = None

    def _mark_failure(
        self,
        state: SimulationState,
        *,
        stage: str,
        kind: str,
        message: str,
    ) -> None:
        state.status = SimulationStatus.FAILED
        state.error = message
        state.failure_stage = stage
        state.failure_kind = kind
        self._save_simulation_state(state)
    
    def prepare_simulation(
        self,
        simulation_id: str,
        simulation_requirement: str,
        document_text: str,
        defined_entity_types: Optional[List[str]] = None,
        entity_match_mode: str = "strict",
        use_llm_for_profiles: bool = True,
        progress_callback: Optional[callable] = None,
        parallel_profile_count: int = 3
    ) -> SimulationState:
        """
        시뮬레이션 환경을 준비한다. (전 과정 자동화)

        단계:
        1. Zep 그래프에서 엔티티를 읽고 필터링한다.
        2. 각 엔티티의 OASIS Agent Profile을 생성한다. (선택적 LLM 보강, 병렬 지원)
        3. LLM으로 시뮬레이션 설정 파라미터(시간, 활동성, 발언 빈도 등)를 생성한다.
        4. 설정 파일과 Profile 파일을 저장한다.
        5. 실행에 필요한 시뮬레이션 상태를 정리한다.
        
        Args:
            simulation_id: 시뮬레이션 ID
            simulation_requirement: 시뮬레이션 요구사항 설명 (LLM 설정 생성용)
            document_text: 원문 문서 내용 (LLM 배경 이해용)
            defined_entity_types: 미리 정의한 엔티티 유형 목록 (선택)
            use_llm_for_profiles: LLM으로 상세 페르소나를 생성할지 여부
            progress_callback: 진행률 콜백 함수 (stage, progress, message)
            parallel_profile_count: 병렬 페르소나 생성 수, 기본 3
            
        Returns:
            SimulationState
        """
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"Simulation not found: {simulation_id}")

        failure_stage = "prepare"
        failure_kind = "prepare_runtime"

        try:
            state.entity_filter_mode = (entity_match_mode or "strict").lower()
            self._clear_failure_state(state)
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)
            
            sim_dir = self._get_simulation_dir(simulation_id)
            
            # ========== 1단계: 엔티티 조회 및 필터링 ==========
            if progress_callback:
                progress_callback("reading", 0, "Connecting to the Zep graph...")
            
            reader = ZepEntityReader()
            
            if progress_callback:
                progress_callback("reading", 30, "Reading graph nodes...")
            
            filtered = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=defined_entity_types,
                enrich_with_edges=True,
                match_mode=state.entity_filter_mode,
            )
            
            state.entities_count = filtered.filtered_count
            state.entity_types = list(filtered.entity_types)
            state.entity_filter_mode = filtered.readiness.get("match_mode", state.entity_filter_mode)
            state.entity_readiness = dict(filtered.readiness)
            
            if progress_callback:
                progress_callback(
                    "reading", 100, 
                    f"Completed, found {filtered.filtered_count} entities",
                    current=filtered.filtered_count,
                    total=filtered.filtered_count
                )
            
            if filtered.filtered_count == 0:
                self._mark_failure(
                    state,
                    stage="prepare",
                    kind="entity_matching",
                    message=(
                        "No matching entities were found for simulation preparation. "
                        "Review the graph contents or try a different entity_match_mode."
                    ),
                )
                return state
            
            # ========== 2단계: Agent Profile 생성 ==========
            total_entities = len(filtered.entities)
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 0, 
                    "Starting profile generation...",
                    current=0,
                    total=total_entities
                )
            
            # graph_id를 전달해 Zep 조회를 활성화하고 더 풍부한 컨텍스트를 얻는다.
            generator = OasisProfileGenerator(graph_id=state.graph_id)
            
            def profile_progress(current, total, msg):
                if progress_callback:
                    progress_callback(
                        "generating_profiles", 
                        int(current / total * 100), 
                        msg,
                        current=current,
                        total=total,
                        item_name=msg
                    )
            
            # 실시간 저장 파일 경로 설정 (Reddit JSON 형식 우선)
            realtime_output_path = None
            realtime_platform = "reddit"
            if state.enable_reddit:
                realtime_output_path = os.path.join(sim_dir, "reddit_profiles.json")
                realtime_platform = "reddit"
            elif state.enable_twitter:
                realtime_output_path = os.path.join(sim_dir, "twitter_profiles.csv")
                realtime_platform = "twitter"
            
            profiles = generator.generate_profiles_from_entities(
                entities=filtered.entities,
                use_llm=use_llm_for_profiles,
                progress_callback=profile_progress,
                graph_id=state.graph_id,  # Zep 조회를 위한 graph_id
                parallel_count=parallel_profile_count,  # 병렬 생성 수
                realtime_output_path=realtime_output_path,  # 실시간 저장 경로
                output_platform=realtime_platform  # 출력 형식
            )
            
            state.profiles_count = len(profiles)
            
            # Profile 파일 저장 (Twitter는 CSV, Reddit는 JSON 형식 사용)
            # Reddit는 생성 중 실시간 저장되지만, 여기서 한 번 더 저장해 완전성을 보장한다.
            if progress_callback:
                progress_callback(
                    "generating_profiles", 95, 
                    "Saving profile files...",
                    current=total_entities,
                    total=total_entities
                )
            
            if state.enable_reddit:
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "reddit_profiles.json"),
                    platform="reddit"
                )
            
            if state.enable_twitter:
                # Twitter는 CSV 형식을 사용해야 한다. (OASIS 요구사항)
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "twitter_profiles.csv"),
                    platform="twitter"
                )
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 100, 
                    f"Completed, generated {len(profiles)} profiles",
                    current=len(profiles),
                    total=len(profiles)
                )
            
            # ========== 3단계: LLM 기반 시뮬레이션 설정 생성 ==========
            failure_stage = "config"
            failure_kind = "config_generation"
            if progress_callback:
                progress_callback(
                    "generating_config", 0, 
                    "Analyzing simulation requirement...",
                    current=0,
                    total=3
                )
            
            config_generator = SimulationConfigGenerator()
            
            if progress_callback:
                progress_callback(
                    "generating_config", 30, 
                    "Generating configuration with the LLM...",
                    current=1,
                    total=3
                )
            
            sim_params = config_generator.generate_config(
                simulation_id=simulation_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_requirement=simulation_requirement,
                document_text=document_text,
                entities=filtered.entities,
                enable_twitter=state.enable_twitter,
                enable_reddit=state.enable_reddit
            )
            
            if progress_callback:
                progress_callback(
                    "generating_config", 70, 
                    "Saving configuration files...",
                    current=2,
                    total=3
                )
            
            # 설정 파일 저장
            config_path = os.path.join(sim_dir, "simulation_config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(sim_params.to_json())
            
            state.config_generated = True
            state.config_reasoning = sim_params.generation_reasoning
            
            if progress_callback:
                progress_callback(
                    "generating_config", 100, 
                    "Configuration generation complete",
                    current=3,
                    total=3
                )
            
            # 실행 스크립트는 backend/scripts/에 유지한다.
            # 시뮬레이션 시작 시 simulation_runner가 scripts/ 디렉터리의 스크립트를 사용한다.
            
            # 상태 갱신
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)
            
            logger.info(f"시뮬레이션 준비 완료: {simulation_id}, "
                       f"entities={state.entities_count}, profiles={state.profiles_count}")
            
            return state
            
        except Exception as e:
            logger.error(f"시뮬레이션 준비 실패: {simulation_id}, error={str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self._mark_failure(
                state,
                stage=failure_stage,
                kind=failure_kind,
                message=str(e),
            )
            raise
    
    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        """시뮬레이션 상태를 조회한다."""
        return self._load_simulation_state(simulation_id)
    
    def list_simulations(self, project_id: Optional[str] = None) -> List[SimulationState]:
        """전체 시뮬레이션 목록을 조회한다."""
        simulations = []
        
        if os.path.exists(self.SIMULATION_DATA_DIR):
            for sim_id in os.listdir(self.SIMULATION_DATA_DIR):
                # 숨김 파일(.DS_Store 등)과 디렉터리가 아닌 파일은 건너뛴다.
                sim_path = os.path.join(self.SIMULATION_DATA_DIR, sim_id)
                if sim_id.startswith('.') or not os.path.isdir(sim_path):
                    continue
                
                state = self._load_simulation_state(sim_id)
                if state:
                    if project_id is None or state.project_id == project_id:
                        simulations.append(state)
        
        return simulations
    
    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        """시뮬레이션의 Agent Profile을 조회한다."""
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"시뮬레이션이 없습니다: {simulation_id}")
        
        sim_dir = self._get_simulation_dir(simulation_id)
        profile_path = os.path.join(sim_dir, f"{platform}_profiles.json")
        
        if not os.path.exists(profile_path):
            return []
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_simulation_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """시뮬레이션 설정을 조회한다."""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_run_instructions(self, simulation_id: str) -> Dict[str, str]:
        """실행 안내를 반환한다."""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        return {
            "simulation_dir": sim_dir,
            "scripts_dir": scripts_dir,
            "config_file": config_path,
            "commands": {
                "twitter": f"python {scripts_dir}/run_twitter_simulation.py --config {config_path}",
                "reddit": f"python {scripts_dir}/run_reddit_simulation.py --config {config_path}",
                "parallel": f"python {scripts_dir}/run_parallel_simulation.py --config {config_path}",
            },
            "instructions": (
                f"1. conda 환경을 활성화합니다: conda activate MiroFish\n"
                f"2. 시뮬레이션을 실행합니다 (스크립트 위치: {scripts_dir}):\n"
                f"   - Twitter만 실행: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\n"
                f"   - Reddit만 실행: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\n"
                f"   - 두 플랫폼 병렬 실행: python {scripts_dir}/run_parallel_simulation.py --config {config_path}"
            )
        }
