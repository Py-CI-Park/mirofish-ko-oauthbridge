"""
시뮬레이션 설정 지능 생성기
LLM으로 시뮬레이션 요구사항, 문서 내용, 그래프 정보를 바탕으로 세부 시뮬레이션 파라미터를 생성한다.

단계별 생성 전략을 사용해 한 번에 너무 긴 출력을 만들다가 실패하지 않도록 한다.
1. 시간 설정 생성
2. 이벤트 설정 생성
3. Agent 설정을 배치 단위로 생성
4. 플랫폼 설정 생성
"""

import json
import math
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from ..utils.active_hours import normalize_active_hours
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.simulation_config')

# 기본 활동 시간대 설정 (KST 기준)
CHINA_TIMEZONE_CONFIG = {
    # 심야 시간대 (거의 활동 없음)
    "dead_hours": [0, 1, 2, 3, 4, 5],
    # 아침 시간대 (점진적 활성화)
    "morning_hours": [6, 7, 8],
    # 업무 시간대
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    # 저녁 피크 시간대 (가장 활발함)
    "peak_hours": [19, 20, 21, 22],
    # 야간 시간대 (활동 감소)
    "night_hours": [23],
    # 활동 계수
    "activity_multipliers": {
        "dead": 0.05,      # 새벽에는 거의 활동 없음
        "morning": 0.4,    # 아침에 점진적으로 활성화
        "work": 0.7,       # 업무 시간대는 중간 수준
        "peak": 1.5,       # 저녁 피크 시간대
        "night": 0.5       # 밤에는 활동 감소
    }
}


@dataclass
class AgentActivityConfig:
    """단일 Agent의 활동 설정"""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str

    # 활동성 설정 (0.0-1.0)
    activity_level: float = 0.5  # 전체 활동성

    # 발언 빈도 (시간당 예상 발언 횟수)
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0

    # 활동 시간대 (24시간제, 0-23)
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))

    # 반응 속도 (핫이슈 반응 지연, 단위: 시뮬레이션 분)
    response_delay_min: int = 5
    response_delay_max: int = 60

    # 감정 편향 (-1.0 ~ 1.0, 부정에서 긍정)
    sentiment_bias: float = 0.0

    # 입장 (특정 주제에 대한 태도)
    stance: str = "neutral"  # supportive, opposing, neutral, observer

    # 영향력 가중치 (다른 Agent가 해당 발언을 볼 확률에 영향)
    influence_weight: float = 1.0


@dataclass
class TimeSimulationConfig:
    """시간 시뮬레이션 설정 (기본 시간대 가정 기반)"""
    # 시뮬레이션 총 시간 (단위: 시뮬레이션 시간)
    total_simulation_hours: int = 72  # 기본값 72시간 (3일)

    # 각 라운드가 의미하는 시간 (시뮬레이션 분) - 기본 60분(1시간)
    minutes_per_round: int = 60

    # 시간당 활성 Agent 수 범위
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20

    # 피크 시간대 (기본 19~22시)
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5

    # 저활동 시간대 (기본 0~5시)
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # 새벽 활동성 매우 낮음

    # 아침 시간대
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4

    # 업무 시간대
    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """이벤트 설정"""
    # 초기 이벤트 (시뮬레이션 시작 시점에 트리거)
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)

    # 예약 이벤트 (특정 시간에 트리거)
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)

    # 핵심 화제 키워드
    hot_topics: List[str] = field(default_factory=list)

    # 여론/서사 유도 방향
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """플랫폼 특화 설정"""
    platform: str  # twitter or reddit

    # 추천 알고리즘 가중치
    recency_weight: float = 0.4  # 최신성
    popularity_weight: float = 0.3  # 인기
    relevance_weight: float = 0.3  # 관련성

    # 확산 임계치 (얼마나 상호작용해야 확산되는지)
    viral_threshold: int = 10

    # 에코 챔버 강도 (유사 관점 군집화 정도)
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """전체 시뮬레이션 파라미터 설정"""
    # 기본 정보
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str

    # 시간 설정
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)

    # Agent 설정 목록
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)

    # 이벤트 설정
    event_config: EventConfig = field(default_factory=EventConfig)

    # 플랫폼 설정
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None

    # LLM 설정
    llm_model: str = ""
    llm_base_url: str = ""

    # 생성 메타데이터
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # LLM 생성 근거 설명

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환한다."""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }

    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열로 변환한다."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    시뮬레이션 설정 지능 생성기

    LLM으로 시뮬레이션 요구사항, 문서 내용, 그래프 엔티티 정보를 분석해
    적절한 시뮬레이션 설정 파라미터를 자동 생성한다.

    단계별 생성 전략:
    1. 시간 설정과 이벤트 설정 생성 (가벼운 단계)
    2. Agent 설정을 배치 단위로 생성
    3. 플랫폼 설정 생성
    """

    # 최대 컨텍스트 길이(문자 수)
    MAX_CONTEXT_LENGTH = 50000
    # 배치당 생성할 Agent 수
    AGENTS_PER_BATCH = 15

    # 단계별 컨텍스트 절단 길이 (문자 수)
    TIME_CONFIG_CONTEXT_LENGTH = 10000   # 시간 설정
    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # 이벤트 설정
    ENTITY_SUMMARY_LENGTH = 300          # 엔티티 요약
    AGENT_SUMMARY_LENGTH = 300           # Agent 설정용 엔티티 요약
    ENTITIES_PER_TYPE_DISPLAY = 20       # 유형별 표시 엔티티 수

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY가 설정되지 않았습니다")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        전체 시뮬레이션 설정을 지능적으로 생성한다. (단계별 생성)

        Args:
            simulation_id: 시뮬레이션 ID
            project_id: 프로젝트 ID
            graph_id: 그래프 ID
            simulation_requirement: 시뮬레이션 요구사항 설명
            document_text: 원문 문서 내용
            entities: 필터링된 엔티티 목록
            enable_twitter: Twitter 활성화 여부
            enable_reddit: Reddit 활성화 여부
            progress_callback: 진행률 콜백 함수(current_step, total_steps, message)

        Returns:
            SimulationParameters: 전체 시뮬레이션 파라미터
        """
        logger.info(f"시뮬레이션 설정 생성 시작: simulation_id={simulation_id}, 엔티티 수={len(entities)}")

        # 전체 단계 수 계산
        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # 시간 설정 + 이벤트 설정 + N개 Agent 배치 + 플랫폼 설정
        current_step = 0

        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")

        # 1. 기본 컨텍스트 구성
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )

        reasoning_parts = []

        # ========== 1단계: 시간 설정 생성 ==========
        report_progress(1, "시간 설정 생성 중...")
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"시간 설정: {time_config_result.get('reasoning', '성공')}")

        # ========== 2단계: 이벤트 설정 생성 ==========
        report_progress(2, "이벤트 설정과 핵심 화제 생성 중...")
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"이벤트 설정: {event_config_result.get('reasoning', '성공')}")

        # ========== 3단계~N단계: Agent 설정을 배치로 생성 ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]

            report_progress(
                3 + batch_idx,
                f"Agent 설정 생성 중 ({start_idx + 1}-{end_idx}/{len(entities)})..."
            )

            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)

        reasoning_parts.append(f"Agent 설정: {len(all_agent_configs)}개 생성 성공")

        # ========== 초기 게시물에 게시자 Agent 배정 ==========
        logger.info("초기 게시물에 적절한 게시자 Agent를 배정하는 중...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(f"초기 게시물 배정: {assigned_count}개 게시물에 게시자 배정 완료")

        # ========== 마지막 단계: 플랫폼 설정 생성 ==========
        report_progress(total_steps, "플랫폼 설정 생성 중...")
        twitter_config = None
        reddit_config = None

        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )

        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )

        # 构建最终参数
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts)
        )

        logger.info(f"시뮬레이션 설정 생성 완료: Agent 설정 {len(params.agent_configs)}개")

        return params

    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """LLM 컨텍스트를 구성하고 최대 길이에 맞춰 자른다."""

        # 엔티티 요약
        entity_summary = self._summarize_entities(entities)

        # 컨텍스트 구성
        context_parts = [
            f"## 模拟需求\n{simulation_requirement}",
            f"\n## 实体信息 ({len(entities)}个)\n{entity_summary}",
        ]

        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # 留500字符余量

        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(文档已截断)"
            context_parts.append(f"\n## 原始文档内容\n{doc_text}")

        return "\n".join(context_parts)

    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """엔티티 요약 문자열을 생성한다."""
        lines = []

        # 유형별로 그룹화
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)

        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)}개)")
            # 使用配置的显示数量和摘要长度
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... 추가 {len(type_entities) - display_count}개")

        return "\n".join(lines)

    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """재시도와 JSON 복구 로직을 포함한 LLM 호출."""
        import re

        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # 재시도할수록 temperature를 낮춤
                    # max_tokens는 제한하지 않는다.
                )

                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason

                # 출력이 잘렸는지 확인
                if finish_reason == 'length':
                    logger.warning(f"LLM 출력이 잘렸습니다 (attempt {attempt+1})")
                    content = self._fix_truncated_json(content)

                # JSON 파싱 시도
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 파싱 실패 (attempt {attempt+1}): {str(e)[:80]}")

                    # JSON 복구 시도
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed

                    last_error = e

            except Exception as e:
                logger.warning(f"LLM 호출 실패 (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))

        raise last_error or Exception("LLM 호출 실패")

    def _fix_truncated_json(self, content: str) -> str:
        """修复被截断的JSON"""
        content = content.strip()

        # 计算未闭合的括号
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')

        # 检查是否有未闭合的字符串
        if content and content[-1] not in '",}]':
            content += '"'

        # 闭合括号
        content += ']' * open_brackets
        content += '}' * open_braces

        return content

    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """尝试修复配置JSON"""
        import re

        # 修复被截断的情况
        content = self._fix_truncated_json(content)

        # 提取JSON部分
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()

            # 移除字符串中的换行符
            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s

            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)

            try:
                return json.loads(json_str)
            except:
                # 尝试移除所有控制字符
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass

        return None

    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """生成时间配置"""
        # 使用配置的上下文截断长度
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]

        # 计算最大允许值（80%的agent数）
        max_agents_allowed = max(1, int(num_entities * 0.9))

        prompt = f"""아래 시뮬레이션 요구사항을 바탕으로 시간 시뮬레이션 설정 JSON을 생성하세요.

{context_truncated}

## 작업
시간 설정 JSON만 출력하세요. Markdown은 금지합니다.

### 기본 원칙(참고용, 실제 사건과 집단 특성에 맞게 조정)
- 기본 기준 시간대는 한국 표준시(Asia/Seoul)로 가정합니다.
- 일반적으로 0~5시는 활동이 매우 낮습니다(활동 계수 0.05).
- 6~8시는 점진적으로 활동이 증가합니다(활동 계수 0.4).
- 9~18시는 중간 수준의 활동 구간입니다(활동 계수 0.7).
- 19~22시는 주요 피크 시간대입니다(활동 계수 1.5).
- 23시 이후에는 활동이 다시 감소합니다(활동 계수 0.5).
- 단, 이 값은 고정 규칙이 아니라 기본 가이드입니다.
  - 예: 학생 집단은 21~23시에 더 활발할 수 있습니다.
  - 예: 언론/미디어는 하루 대부분 활동할 수 있습니다.
  - 예: 공식 기관은 업무 시간 중심으로 움직일 수 있습니다.
  - 예: 급박한 이슈는 심야 시간에도 토론이 살아 있을 수 있습니다.

### 반환 형식(JSON only)
예시:
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "이 사건에 대해 이런 시간 설정을 선택한 이유"
}}

필드 설명:
- total_simulation_hours (int): 총 시뮬레이션 시간, 24~168 권장
- minutes_per_round (int): 라운드당 분 단위 시간, 30~120 권장, 기본 60
- agents_per_hour_min (int): 시간당 최소 활성 Agent 수 (1-{max_agents_allowed})
- agents_per_hour_max (int): 시간당 최대 활성 Agent 수 (1-{max_agents_allowed})
- peak_hours (int 배열): 피크 시간대
- off_peak_hours (int 배열): 저활동 시간대
- morning_hours (int 배열): 아침 시간대
- work_hours (int 배열): 업무/일과 시간대
- reasoning (string): 설정 이유를 짧게 설명"""

        system_prompt = "너는 소셜 시뮬레이션 시간 설정 전문가다. 순수 JSON만 출력하고, 기본적으로 한국 사용자/KST 기준에 맞게 설계하라."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"时间配置LLM生成失败: {e}, 使用默认配置")
            return self._get_default_time_config(num_entities)

    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """获取默认时间配置（中国人作息）"""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # 每轮1小时，加快时间流速
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "使用默认中国人作息配置（每轮1小时）"
        }

    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """解析时间配置结果，并验证agents_per_hour值不超过总agent数"""
        # 获取原始值
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))

        # 验证并修正：确保不超过总agent数
        if agents_per_hour_min > num_entities:
            logger.warning(f"agents_per_hour_min ({agents_per_hour_min}) 超过总Agent数 ({num_entities})，已修正")
            agents_per_hour_min = max(1, num_entities // 10)

        if agents_per_hour_max > num_entities:
            logger.warning(f"agents_per_hour_max ({agents_per_hour_max}) 超过总Agent数 ({num_entities})，已修正")
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)

        # 确保 min < max
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= max，已修正为 {agents_per_hour_min}")

        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # 默认每轮1小时
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # 凌晨几乎无人
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )

    def _generate_event_config(
        self,
        context: str,
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """生成事件配置"""

        # 获取可用的实体类型列表，供 LLM 参考
        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))

        # 为每种类型列出代表性实体名称
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)

        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}"
            for t, examples in type_examples.items()
        ])

        # 使用配置的上下文截断长度
        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]

        prompt = f"""아래 시뮬레이션 요구사항을 바탕으로 사건 설정 JSON을 생성하세요.

시뮬레이션 요구사항: {simulation_requirement}

{context_truncated}

## 사용 가능한 엔티티 유형과 예시
{type_info}

## 작업
아래 항목을 포함한 사건 설정 JSON만 출력하세요.
- 핵심 화제어(hot_topics)
- 여론/서사 전개 방향(narrative_direction)
- 초기 게시물(initial_posts)

중요 규칙:
- initial_posts의 각 항목은 반드시 poster_type(게시 주체 유형)을 포함해야 합니다.
- poster_type은 반드시 위의 "사용 가능한 엔티티 유형" 중 하나를 정확히 사용해야 합니다.
- 예: 공식 입장문은 Official/University 계열, 뉴스 보도는 MediaOutlet, 학생 반응은 Student

반환 형식(JSON only):
{{
    "hot_topics": ["키워드1", "키워드2"],
    "narrative_direction": "여론이 어떤 방향으로 전개되는지 설명",
    "initial_posts": [
        {{"content": "게시물 내용", "poster_type": "사용 가능한 엔티티 유형 중 하나"}}
    ],
    "reasoning": "설정 이유"
}}"""

        system_prompt = "너는 여론/이벤트 설계 전문가다. 순수 JSON만 출력하고, poster_type은 제공된 엔티티 유형과 정확히 일치시켜라."

        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"事件配置LLM生成失败: {e}, 使用默认配置")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "使用默认配置"
            }

    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """解析事件配置结果"""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", "")
        )

    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        为初始帖子分配合适的发布者 Agent

        根据每个帖子的 poster_type 匹配最合适的 agent_id
        """
        if not event_config.initial_posts:
            return event_config

        # 按实体类型建立 agent 索引
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)

        # 类型映射表（处理 LLM 可能输出的不同格式）
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }

        # 记录每种类型已使用的 agent 索引，避免重复使用同一个 agent
        used_indices: Dict[str, int] = {}

        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")

            # 尝试找到匹配的 agent
            matched_agent_id = None

            # 1. 直接匹配
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. 使用别名匹配
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break

            # 3. 如果仍未找到，使用影响力最高的 agent
            if matched_agent_id is None:
                logger.warning(f"未找到类型 '{poster_type}' 的匹配 Agent，使用影响力最高的 Agent")
                if agent_configs:
                    # 按影响力排序，选择影响力最高的
                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0

            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id
            })

            logger.info(f"初始帖子分配: poster_type='{poster_type}' -> agent_id={matched_agent_id}")

        event_config.initial_posts = updated_posts
        return event_config

    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """分批生成Agent配置"""

        # 构建实体信息（使用配置的摘要长度）
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })

        prompt = f"""아래 정보를 바탕으로 각 엔티티의 소셜 활동 설정 JSON을 생성하세요.

시뮬레이션 요구사항: {simulation_requirement}

## 엔티티 목록
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## 작업
각 엔티티에 대해 아래 속성을 포함한 agent_configs를 생성하세요.

설계 가이드:
- **기본 시간대는 한국 표준시 기준**으로 가정합니다.
- **공식 기관**(University/GovernmentAgency): 활동도 낮음(0.1~0.3), 업무 시간 중심(9~17), 반응 느림(60~240분), 영향력 높음(2.5~3.0)
- **미디어**(MediaOutlet): 활동도 중간(0.4~0.6), 하루 대부분 활동(8~23), 반응 빠름(5~30분), 영향력 높음(2.0~2.5)
- **개인**(Student/Person/Alumni): 활동도 높음(0.6~0.9), 저녁 중심(18~23), 반응 빠름(1~15분), 영향력 낮음(0.8~1.2)
- **전문가/오피니언 리더**: 활동도 중간(0.4~0.6), 영향력 중상(1.5~2.0)
- 단, 위 수치는 고정값이 아니라 사건 맥락과 요약 정보를 보고 조정해야 합니다.
- **중요**: active_hours는 반드시 0~23 사이의 정수 배열로만 반환하세요.
  - 예: [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22]
  - 금지 예시: ["08:00-23:00"], ["9-17"], ["09:00", "10:00"]

반환 형식(JSON only):
{{
    "agent_configs": [
        {{
            "agent_id": <입력과 동일해야 함>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <게시 빈도>,
            "comments_per_hour": <댓글 빈도>,
            "active_hours": [<0~23 정수 시간대 목록>],
            "response_delay_min": <최소 반응 지연(분)>,
            "response_delay_max": <최대 반응 지연(분)>,
            "sentiment_bias": <-1.0~1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <영향력 가중치>
        }}
    ]
}}"""

        system_prompt = "너는 소셜 행동 모델링 전문가다. 순수 JSON만 출력하고, 한국어 사용자/한국 시간대 기준으로 자연스럽게 설정하라."

        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"Agent配置批次LLM生成失败: {e}, 使用规则生成")
            llm_configs = {}

        # 构建AgentActivityConfig对象
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})

            # 如果LLM没有生成，使用规则生成
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)

            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=normalize_active_hours(
                    cfg.get("active_hours"),
                    default=list(range(9, 23))
                ),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0)
            )
            configs.append(config)

        return configs

    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """基于规则生成单个Agent配置（中国人作息）"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()

        if entity_type in ["university", "governmentagency", "ngo"]:
            # 官方机构：工作时间活动，低频率，高影响力
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0
            }
        elif entity_type in ["mediaoutlet"]:
            # 媒体：全天活动，中等频率，高影响力
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5
            }
        elif entity_type in ["professor", "expert", "official"]:
            # 专家/教授：工作+晚间活动，中等频率
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0
            }
        elif entity_type in ["student"]:
            # 学生：晚间为主，高频率
            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # 上午+晚间
                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8
            }
        elif entity_type in ["alumni"]:
            # 校友：晚间为主
            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23],  # 午休+晚间
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
        else:
            # 普通人：晚间高峰
            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # 白天+晚间
                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
