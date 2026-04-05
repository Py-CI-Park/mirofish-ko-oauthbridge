"""
Zep 그래프 기억 업데이트 서비스
시뮬레이션 중 발생한 Agent 활동을 Zep 그래프에 동적으로 반영한다.
"""

import os
import time
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.zep_graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent 활동 기록"""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str
    
    def to_episode_text(self) -> str:
        """
        활동을 Zep에 보낼 자연어 설명 텍스트로 변환한다.

        자연어 설명 형식을 사용해 Zep가 엔티티와 관계를 추출할 수 있게 한다.
        시뮬레이션 관련 접두어는 추가하지 않아 그래프 업데이트를 오도하지 않도록 한다.
        """
        # 액션 유형별 설명 생성기 선택
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }
        
        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()
        
        # Return "agent_name: activity description" without a simulation prefix.
        return f"{self.agent_name}: {description}"
    
    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"published a post: \"{content}\""
        return "published a post"
    
    def _describe_like_post(self) -> str:
        """게시글 좋아요 - 원문과 작성자 정보 포함"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"liked {post_author}'s post: \"{post_content}\""
        elif post_content:
            return f"liked a post: \"{post_content}\""
        elif post_author:
            return f"liked a post by {post_author}"
        return "liked a post"
    
    def _describe_dislike_post(self) -> str:
        """게시글 비추천 - 원문과 작성자 정보 포함"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"downvoted {post_author}'s post: \"{post_content}\""
        elif post_content:
            return f"downvoted a post: \"{post_content}\""
        elif post_author:
            return f"downvoted a post by {post_author}"
        return "downvoted a post"
    
    def _describe_repost(self) -> str:
        """게시글 리포스트 - 원문과 작성자 정보 포함"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        
        if original_content and original_author:
            return f"reposted {original_author}'s post: \"{original_content}\""
        elif original_content:
            return f"reposted a post: \"{original_content}\""
        elif original_author:
            return f"reposted a post by {original_author}"
        return "reposted a post"
    
    def _describe_quote_post(self) -> str:
        """게시글 인용 - 원문, 작성자 정보, 인용 코멘트 포함"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        
        base = ""
        if original_content and original_author:
            base = f"quoted {original_author}'s post \"{original_content}\""
        elif original_content:
            base = f"quoted a post \"{original_content}\""
        elif original_author:
            base = f"quoted a post by {original_author}"
        else:
            base = "quoted a post"
        
        if quote_content:
            base += f" and commented: \"{quote_content}\""
        return base
    
    def _describe_follow(self) -> str:
        """사용자 팔로우 - 대상 사용자 이름 포함"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"followed user \"{target_user_name}\""
        return "followed a user"
    
    def _describe_create_comment(self) -> str:
        """댓글 작성 - 댓글 내용과 대상 게시글 정보 포함"""
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if content:
            if post_content and post_author:
                return f"commented on {post_author}'s post \"{post_content}\": \"{content}\""
            elif post_content:
                return f"commented on a post \"{post_content}\": \"{content}\""
            elif post_author:
                return f"commented on a post by {post_author}: \"{content}\""
            return f"commented: \"{content}\""
        return "posted a comment"
    
    def _describe_like_comment(self) -> str:
        """댓글 좋아요 - 댓글 내용과 작성자 정보 포함"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"liked {comment_author}'s comment: \"{comment_content}\""
        elif comment_content:
            return f"liked a comment: \"{comment_content}\""
        elif comment_author:
            return f"liked a comment by {comment_author}"
        return "liked a comment"
    
    def _describe_dislike_comment(self) -> str:
        """댓글 비추천 - 댓글 내용과 작성자 정보 포함"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"downvoted {comment_author}'s comment: \"{comment_content}\""
        elif comment_content:
            return f"downvoted a comment: \"{comment_content}\""
        elif comment_author:
            return f"downvoted a comment by {comment_author}"
        return "downvoted a comment"
    
    def _describe_search(self) -> str:
        """게시글 검색 - 검색 키워드 포함"""
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"searched for \"{query}\"" if query else "performed a search"
    
    def _describe_search_user(self) -> str:
        """사용자 검색 - 검색 키워드 포함"""
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"searched for user \"{query}\"" if query else "searched for a user"
    
    def _describe_mute(self) -> str:
        """사용자 뮤트 - 대상 사용자 이름 포함"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"muted user \"{target_user_name}\""
        return "muted a user"
    
    def _describe_generic(self) -> str:
        # 알 수 없는 액션 유형이면 일반 설명 생성
        return f"performed the action {self.action_type}"


class ZepGraphMemoryUpdater:
    """
    Zep 그래프 기억 업데이트기

    시뮬레이션 actions 로그를 감시해 새로운 agent 활동을 Zep 그래프에 실시간 반영한다.
    플랫폼별로 묶어서 BATCH_SIZE만큼 쌓이면 배치로 전송한다.

    의미 있는 행동은 모두 Zep에 반영하며, action_args에는 전체 컨텍스트가 포함된다.
    - 좋아요/비추천한 게시글 원문
    - 리포스트/인용한 게시글 원문
    - 팔로우/뮤트 대상 사용자명
    - 좋아요/비추천한 댓글 원문
    """
    
    # 배치 전송 크기 (플랫폼별 누적 전송 수)
    BATCH_SIZE = 5
    
    # 플랫폼 표시 이름 (콘솔 출력용)
    PLATFORM_DISPLAY_NAMES = {
        'twitter': 'World 1',
        'reddit': 'World 2',
    }
    
    # 전송 간격(초), 요청이 너무 빨라지지 않도록 함
    SEND_INTERVAL = 0.5
    
    # 재시도 설정
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # 초
    
    def __init__(self, graph_id: str, api_key: Optional[str] = None):
        """
        업데이트기를 초기화한다.
        
        Args:
            graph_id: Zep 그래프 ID
            api_key: Zep API Key (선택, 기본은 설정에서 읽음)
        """
        self.graph_id = graph_id
        self.api_key = api_key or Config.ZEP_API_KEY
        
        if not self.api_key:
            raise ValueError("ZEP_API_KEY is not configured")
        
        self.client = Zep(api_key=self.api_key)
        
        # 활동 큐
        self._activity_queue: Queue = Queue()
        
        # 플랫폼별 활동 버퍼 (각 플랫폼에서 BATCH_SIZE만큼 누적 후 배치 전송)
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()
        
        # 제어 플래그
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # 통계
        self._total_activities = 0  # 큐에 실제로 추가된 활동 수
        self._total_sent = 0        # Zep에 성공적으로 보낸 배치 수
        self._total_items_sent = 0  # Zep에 성공적으로 보낸 활동 수
        self._failed_count = 0      # 전송 실패 배치 수
        self._skipped_count = 0     # 필터링으로 건너뛴 활동 수 (DO_NOTHING)
        
        logger.info(f"ZepGraphMemoryUpdater initialized: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")
    
    def _get_platform_display_name(self, platform: str) -> str:
        """플랫폼 표시 이름을 반환한다."""
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)
    
    def start(self):
        """백그라운드 작업 스레드를 시작한다."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"ZepMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"ZepGraphMemoryUpdater 시작: graph_id={self.graph_id}")
    
    def stop(self):
        """백그라운드 작업 스레드를 중지한다."""
        self._running = False
        
        # 남은 활동 전송
        self._flush_remaining()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        
        logger.info(f"ZepGraphMemoryUpdater 중지: graph_id={self.graph_id}, "
                   f"total_activities={self._total_activities}, "
                   f"batches_sent={self._total_sent}, "
                   f"items_sent={self._total_items_sent}, "
                   f"failed={self._failed_count}, "
                   f"skipped={self._skipped_count}")
    
    def add_activity(self, activity: AgentActivity):
        """
        하나의 agent 활동을 큐에 추가한다.

        의미 있는 모든 행동을 큐에 추가한다. 예:
        - CREATE_POST (게시)
        - CREATE_COMMENT (댓글)
        - QUOTE_POST (인용)
        - SEARCH_POSTS (게시글 검색)
        - SEARCH_USER (사용자 검색)
        - LIKE_POST / DISLIKE_POST (게시글 좋아요/비추천)
        - REPOST (리포스트)
        - FOLLOW (팔로우)
        - MUTE (뮤트)
        - LIKE_COMMENT / DISLIKE_COMMENT (댓글 좋아요/비추천)

        action_args에는 게시글 원문, 사용자명 등 전체 컨텍스트가 포함된다.
        
        Args:
            activity: Agent 활동 기록
        """
        # DO_NOTHING 유형은 건너뜀
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        
        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"Zep 큐에 활동 추가: {activity.agent_name} - {activity.action_type}")
    
    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """
        딕셔너리 데이터에서 활동을 추가한다.
        
        Args:
            data: actions.jsonl에서 파싱한 딕셔너리 데이터
            platform: 플랫폼 이름 (twitter/reddit)
        """
        # 이벤트 타입 항목은 건너뜀
        if "event_type" in data:
            return
        
        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        
        self.add_activity(activity)
    
    def _worker_loop(self):
        """백그라운드 작업 루프 - 플랫폼별로 활동을 묶어 Zep에 배치 전송한다."""
        while self._running or not self._activity_queue.empty():
            try:
                # 큐에서 활동을 가져오려 시도 (1초 타임아웃)
                try:
                    activity = self._activity_queue.get(timeout=1)
                    
                    # 활동을 해당 플랫폼 버퍼에 추가
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)
                        
                        # 해당 플랫폼이 배치 크기에 도달했는지 확인
                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            # 락을 해제한 뒤 전송
                            self._send_batch_activities(batch, platform)
                            # 전송 간격을 두어 요청이 너무 빨라지지 않게 함
                            time.sleep(self.SEND_INTERVAL)
                    
                except Empty:
                    pass
                    
            except Exception as e:
                logger.error(f"작업 루프 예외: {e}")
                time.sleep(1)
    
    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """
        활동을 Zep 그래프에 배치 전송한다. (한 줄 텍스트로 병합)
        
        Args:
            activities: Agent 활동 목록
            platform: 플랫폼 이름
        """
        if not activities:
            return
        
        # 여러 활동을 줄바꿈으로 구분해 하나의 텍스트로 병합
        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)
        
        # 재시도 포함 전송
        for attempt in range(self.MAX_RETRIES):
            try:
                self.client.graph.add(
                    graph_id=self.graph_id,
                    type="text",
                    data=combined_text
                )
                
                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(f"{display_name} 활동 {len(activities)}건을 그래프 {self.graph_id}에 배치 전송했습니다")
                logger.debug(f"배치 내용 미리보기: {combined_text[:200]}...")
                return
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Zep 배치 전송 실패 (시도 {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"Zep 배치 전송이 {self.MAX_RETRIES}회 재시도 후에도 실패했습니다: {e}")
                    self._failed_count += 1
    
    def _flush_remaining(self):
        """큐와 버퍼에 남아 있는 활동을 모두 전송한다."""
        # 먼저 큐에 남은 활동을 버퍼에 옮긴다.
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break
        
        # 각 플랫폼 버퍼에 남은 활동을 전송한다. (BATCH_SIZE보다 적어도 전송)
        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"{display_name} 플랫폼의 남은 활동 {len(buffer)}건을 전송합니다")
                    self._send_batch_activities(buffer, platform)
            # 모든 버퍼를 비운다
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 정보를 반환한다."""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,  # 큐에 실제로 추가된 활동 수
            "batches_sent": self._total_sent,            # Zep에 성공적으로 보낸 배치 수
            "items_sent": self._total_items_sent,        # Zep에 성공적으로 보낸 활동 수
            "failed_count": self._failed_count,          # 전송 실패 배치 수
            "skipped_count": self._skipped_count,        # 필터링으로 건너뛴 활동 수 (DO_NOTHING)
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,                # 각 플랫폼 버퍼 크기
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """
    여러 시뮬레이션의 Zep 그래프 기억 업데이트기를 관리한다.

    각 시뮬레이션은 자체 업데이트기 인스턴스를 가질 수 있다.
    """
    
    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()
    
    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        """
        시뮬레이션용 그래프 기억 업데이트기를 생성한다.
        
        Args:
            simulation_id: 시뮬레이션 ID
            graph_id: Zep 그래프 ID
            
        Returns:
            ZepGraphMemoryUpdater 인스턴스
        """
        with cls._lock:
            # 이미 있으면 기존 인스턴스를 먼저 중지
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            
            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            
            logger.info(f"그래프 기억 업데이트기 생성: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater
    
    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[ZepGraphMemoryUpdater]:
        """시뮬레이션의 업데이트기를 조회한다."""
        return cls._updaters.get(simulation_id)
    
    @classmethod
    def stop_updater(cls, simulation_id: str):
        """시뮬레이션의 업데이트기를 중지하고 제거한다."""
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"그래프 기억 업데이트기 중지: simulation_id={simulation_id}")
    
    # stop_all 중복 호출 방지 플래그
    _stop_all_done = False
    
    @classmethod
    def stop_all(cls):
        """모든 업데이트기를 중지한다."""
        # 중복 호출 방지
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        
        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"업데이트기 중지 실패: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info("모든 그래프 기억 업데이트기를 중지했습니다")
    
    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """모든 업데이트기의 통계 정보를 반환한다."""
        return {
            sim_id: updater.get_stats() 
            for sim_id, updater in cls._updaters.items()
        }
