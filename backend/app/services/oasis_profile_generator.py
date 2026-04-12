"""
OASIS Agent Profile 생성기
Zep 그래프의 엔터티를 OASIS 시뮬레이션용 에이전트 프로필로 변환한다.
"""

import json
import random
import re
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profile 데이터 구조"""
    # 공통 필드
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # 선택 필드 - Reddit 스타일
    karma: int = 1000
    
    # 선택 필드 - Twitter 스타일
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # 추가 페르소나 정보
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # 원본 엔티티 정보
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """Reddit 플랫폼 형식으로 변환한다."""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 라이브러리는 username 필드명을 요구한다.
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # 추가 페르소나 정보가 있으면 포함
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """Twitter 플랫폼 형식으로 변환한다."""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 라이브러리는 username 필드명을 요구한다.
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # 추가 페르소나 정보가 있으면 포함
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """전체 딕셔너리 형식으로 변환한다."""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profile 생성기

    Zep 그래프의 엔티티를 OASIS 시뮬레이션에 필요한 Agent Profile로 변환한다.

    최적화 포인트:
    1. Zep 그래프 검색을 사용해 더 풍부한 컨텍스트를 가져온다.
    2. 기본 정보, 직업/경력, 성격 특성, 소셜 행동 등을 포함한 상세 페르소나를 생성한다.
    3. 개인 엔티티와 추상 집단/기관 엔티티를 구분한다.
    """
    
    # MBTI 유형 목록
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # 자주 쓰는 국가 목록
    COUNTRIES = [
        "대만", "중국", "일본", "미국", "영국", "독일",
        "프랑스", "캐나다", "호주", "인도", "대한민국"
    ]
    
    # 개인 유형 엔터티(구체적 인물 프로필 생성)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist",
        "학생", "동문", "교수", "개인", "공인", "전문가", "교직원", "공무원", "기자", "활동가"
    ]
    
    # 집단/기관 유형 엔터티(대표 계정 프로필 생성)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community",
        "대학", "정부기관", "조직", "시민단체", "언론사", "기업", "기관", "집단", "커뮤니티"
    ]

    COUNTRY_KEYWORDS = {
        "대만": ["taiwan", "taipei", "adiz", "taiwanese", "roc", "대만", "타이완"],
        "중국": ["china", "prc", "pla", "beijing", "중국", "중화", "인민해방군"],
        "일본": ["japan", "tokyo", "일본"],
        "미국": ["united states", "u.s.", "us ", "washington", "indo-pacific", "미국"],
        "대한민국": ["south korea", "korea", "seoul", "대한민국", "한국"],
    }

    SUPPORTED_PERSONA_PROMPT_LANGUAGES = {"legacy", "ko", "en", "zh"}
    SUPPORTED_PERSONA_OUTPUT_LANGUAGES = {"ko", "en"}
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None,
        persona_prompt_locale: Optional[str] = None,
        persona_prompt_language: Optional[str] = None,
        persona_output_language: Optional[str] = None,
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
        
        # 풍부한 컨텍스트 조회용 Zep 클라이언트
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        if persona_prompt_language is not None:
            configured_prompt_language = persona_prompt_language
        elif persona_prompt_locale is not None:
            configured_prompt_language = persona_prompt_locale
        else:
            configured_prompt_language = Config.LLM_PROMPT_LANGUAGE

        self.persona_prompt_language = self._normalize_persona_prompt_language(configured_prompt_language)
        self.persona_prompt_locale = self.persona_prompt_language
        configured_output_language = (
            persona_output_language if persona_output_language is not None else Config.LLM_OUTPUT_LANGUAGE
        )
        self.persona_output_language = self._normalize_persona_output_language(
            configured_output_language
        )
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep 클라이언트 초기화 실패: {e}")

    def _normalize_persona_prompt_language(self, value: Optional[str]) -> str:
        language = "legacy" if value is None else value.strip().lower()
        if language not in self.SUPPORTED_PERSONA_PROMPT_LANGUAGES:
            supported = ", ".join(sorted(self.SUPPORTED_PERSONA_PROMPT_LANGUAGES))
            raise ValueError(f"Unsupported persona prompt language: {value}. Supported values: {supported}")
        return language

    def _normalize_persona_output_language(self, value: Optional[str]) -> str:
        language = "ko" if value is None else value.strip().lower()
        if language not in self.SUPPORTED_PERSONA_OUTPUT_LANGUAGES:
            supported = ", ".join(sorted(self.SUPPORTED_PERSONA_OUTPUT_LANGUAGES))
            raise ValueError(f"Unsupported persona output language: {value}. Supported values: {supported}")
        return language

    def _prompt_language(self) -> str:
        return getattr(self, "persona_prompt_language", getattr(self, "persona_prompt_locale", "legacy"))

    def _output_language(self) -> str:
        return getattr(self, "persona_output_language", "ko")

    def _empty_prompt_value(self) -> str:
        language = self._prompt_language()
        if language == "ko":
            return "없음"
        if language == "en":
            return "None"
        return "无"

    def _empty_context_value(self) -> str:
        language = self._prompt_language()
        if language == "ko":
            return "추가 컨텍스트 없음"
        if language == "en":
            return "No additional context"
        return "无额外上下文"
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        Zep 엔티티에서 OASIS Agent Profile을 생성한다.
        
        Args:
            entity: Zep 엔티티 노드
            user_id: 사용자 ID (OASIS용)
            use_llm: LLM으로 상세 페르소나를 생성할지 여부
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # 기본 정보
        name = entity.name
        user_name = self._generate_username(name)
        
        # 컨텍스트 정보 구성
        context = self._build_entity_context(entity)
        
        if use_llm:
            # LLM으로 상세 페르소나 생성
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # 규칙 기반으로 기본 페르소나 생성
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"{name}는 {entity_type} 유형의 시뮬레이션 개체입니다."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country") or self._infer_country_label(name, entity_type, entity.summary, context),
            profession=profile_data.get("profession") or self._infer_profession_label(entity_type),
            interested_topics=self._normalize_topics(profile_data.get("interested_topics", [])),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """사용자명을 생성한다."""
        # 특수문자를 제거하고 소문자로 변환
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # 중복 방지를 위한 랜덤 접미사 추가
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        Zep 그래프 혼합 검색을 사용해 엔티티 관련 풍부한 정보를 얻는다.
        
        Zep에는 혼합 검색 전용 인터페이스가 없으므로 edges와 nodes를 각각 검색해 합친다.
        병렬 요청으로 동시에 검색해 효율을 높인다.
        
        Args:
            entity: 엔티티 노드 객체
            
        Returns:
            facts, node_summaries, context를 포함한 딕셔너리
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # 검색을 하려면 graph_id가 반드시 있어야 한다.
        if not self.graph_id:
            logger.debug("graph_id가 없어 Zep 검색을 건너뜁니다")
            return results
        
        comprehensive_query = f"{entity_name}에 대한 모든 정보, 활동, 사건, 관계, 배경"
        
        def search_edges():
            """엣지(사실/관계) 검색 - 재시도 포함"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep 엣지 검색 제 {attempt + 1}회 실패: {str(e)[:80]}, 재시도 중...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep 엣지 검색이 {max_retries}회 시도 후에도 실패했습니다: {e}")
            return None
        
        def search_nodes():
            """노드(엔티티 요약) 검색 - 재시도 포함"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep 노드 검색 제 {attempt + 1}회 실패: {str(e)[:80]}, 재시도 중...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep 노드 검색이 {max_retries}회 시도 후에도 실패했습니다: {e}")
            return None
        
        try:
            # edges와 nodes 검색을 병렬 실행
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # 결과 수집
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            # 엣지 검색 결과 처리
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # 노드 검색 결과 처리
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"관련 엔티티: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # 종합 컨텍스트 구성
            context_parts = []
            if results["facts"]:
                context_parts.append("사실 정보:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("관련 엔티티:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zep 혼합 검색 완료: {entity_name}, 사실 {len(results['facts'])}건, 관련 노드 {len(results['node_summaries'])}개 확보")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zep 검색 타임아웃 ({entity_name})")
        except Exception as e:
            logger.warning(f"Zep 검색 실패 ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        엔티티의 전체 컨텍스트 정보를 구성한다.
        
        포함 요소:
        1. 엔티티 자체의 엣지 정보(사실)
        2. 연결 노드의 상세 정보
        3. Zep 혼합 검색으로 얻은 추가 정보
        """
        context_parts = []
        
        # 1. 엔티티 속성 정보 추가
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### 엔티티 속성\n" + "\n".join(attrs))
        
        # 2. 관련 엣지 정보 추가 (사실/관계)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # 수량 제한 없음
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (관련 엔티티)")
                    else:
                        relationships.append(f"- (관련 엔티티) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### 관련 사실과 관계\n" + "\n".join(relationships))
        
        # 3. 연결 노드의 상세 정보 추가
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # 수량 제한 없음
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # 기본 라벨은 제외
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### 연관 엔티티 정보\n" + "\n".join(related_info))
        
        # 4. Zep 혼합 검색으로 더 풍부한 정보 획득
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # 중복 제거: 이미 포함된 사실은 제외
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zep 검색으로 얻은 사실 정보\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zep 검색으로 얻은 관련 노드\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _normalize_entity_type_key(self, entity_type: str) -> str:
        return re.sub(r'[\s_-]+', '', (entity_type or '').strip().lower())

    def _is_individual_entity(self, entity_type: str) -> bool:
        """개인 유형 엔터티인지 판단"""
        return self._normalize_entity_type_key(entity_type) in {
            self._normalize_entity_type_key(item) for item in self.INDIVIDUAL_ENTITY_TYPES
        }
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """집단/기관 유형 엔터티인지 판단"""
        return self._normalize_entity_type_key(entity_type) in {
            self._normalize_entity_type_key(item) for item in self.GROUP_ENTITY_TYPES
        }
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        LLM을 사용해 매우 상세한 페르소나를 생성한다.

        엔터티 유형별 생성 방식:
        - 개인 엔터티: 구체적인 인물 설정 생성
        - 집단/기관 엔터티: 대표 계정 설정 생성
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # 성공하거나 최대 재시도 횟수에 도달할 때까지 여러 번 생성 시도
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # 재시도할 때마다 temperature를 낮춤
                    # max_tokens를 설정하지 않아 LLM 출력을 제한하지 않음
                )
                
                content = response.choices[0].message.content
                
                # 출력이 잘렸는지 확인(finish_reason이 'stop'이 아닌 경우)
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLM 출력이 잘렸습니다 (attempt {attempt+1}). 복구를 시도합니다...")
                    content = self._fix_truncated_json(content)
                
                # JSON 파싱 시도
                try:
                    result = json.loads(content)
                    
                    # 필수 필드 검증
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name}는 {entity_type} 유형의 시뮬레이션 개체입니다."
                    if "country" not in result or not result["country"]:
                        result["country"] = self._infer_country_label(entity_name, entity_type, entity_summary, context)
                    if "profession" not in result or not result["profession"]:
                        result["profession"] = self._infer_profession_label(entity_type)
                    result["interested_topics"] = self._normalize_topics(result.get("interested_topics", []))
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON 파싱 실패 (attempt {attempt+1}): {str(je)[:80]}")
                    
                    # JSON 복구 시도
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLM 호출 실패 (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # 지수 백오프
        
        logger.warning(f"LLM 페르소나 생성 실패({max_attempts}회 시도): {last_error}. 규칙 기반 생성을 사용합니다.")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """잘린 JSON을 복구한다(max_tokens 제한 등으로 출력이 잘린 경우)."""
        import re
        
        # JSON이 잘렸다면 닫히지 않은 구조를 보완한다.
        content = content.strip()
        
        # 닫히지 않은 괄호 수 계산
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # 닫히지 않은 문자열이 있는지 확인
        # 단순 확인: 마지막 문자가 쉼표나 닫는 괄호가 아니면 문자열이 잘렸을 수 있다.
        if content and content[-1] not in '",}]':
            # 문자열 닫기 시도
            content += '"'
        
        # 괄호 닫기
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """손상된 JSON 복구를 시도한다."""
        import re
        
        # 1. 먼저 잘린 JSON을 복구한다.
        content = self._fix_truncated_json(content)
        
        # 2. JSON 부분 추출을 시도한다.
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. 문자열 내부 줄바꿈 문제 처리
            # 모든 문자열 값을 찾아 내부 줄바꿈을 치환한다.
            def fix_string_newlines(match):
                s = match.group(0)
                # 문자열 내부의 실제 줄바꿈을 공백으로 치환
                s = s.replace('\n', ' ').replace('\r', ' ')
                # 중복 공백 치환
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # JSON 문자열 값 매칭
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. 파싱 시도
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. 계속 실패하면 더 적극적인 복구를 시도한다.
                try:
                    # 모든 제어 문자 제거
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # 모든 연속 공백 치환
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. 내용에서 일부 정보 추출 시도
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # 잘렸을 수 있음
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name}는 {entity_type} 유형의 시뮬레이션 개체입니다.")
        
        # 의미 있는 내용을 추출했다면 복구된 것으로 표시한다.
        if bio_match or persona_match:
            logger.info("손상된 JSON에서 일부 정보를 추출했습니다.")
            return {
                "bio": bio,
                "persona": persona,
                "country": self._infer_country_label(entity_name, entity_type, entity_summary),
                "profession": self._infer_profession_label(entity_type),
                "interested_topics": self._normalize_topics([]),
                "_fixed": True
            }
        
        # 7. 완전히 실패하면 기본 구조를 반환한다.
        logger.warning("JSON 복구 실패. 기본 구조를 반환합니다.")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}는 {entity_type} 유형의 시뮬레이션 개체입니다.",
            "country": self._infer_country_label(entity_name, entity_type, entity_summary),
            "profession": self._infer_profession_label(entity_type),
            "interested_topics": self._normalize_topics([]),
        }
    
    def _output_language_name(self) -> str:
        return "English" if self._output_language() == "en" else "Korean"

    def _output_language_instruction_ko(self) -> str:
        if self._output_language() == "en":
            return "bio, persona, profession, interested_topics, country 는 모두 영어로 작성하라."
        return "bio, persona, profession, interested_topics, country 는 모두 한국어로 작성하라."

    def _output_language_instruction_en(self) -> str:
        if self._output_language() == "en":
            return "Write string values in English."
        return "Write string values in Korean."

    def _get_system_prompt(self, is_individual: bool) -> str:
        """시스템 프롬프트를 반환한다."""
        if self._prompt_language() == "en":
            output_language = self._output_language_name()
            return (
                "You are an expert social media simulation persona generator. "
                "Create detailed, natural personas that preserve realistic context and article clues. "
                "Return only a valid JSON object, and do not include unescaped line breaks in string values. "
                f"bio, persona, profession, interested_topics, country must be written in {output_language}. "
                "Do not use Chinese. Return the gender field only as one of male/female/other."
            )

        return (
            "너는 소셜 미디어 시뮬레이션용 사용자 페르소나 생성 전문가다. "
            "현실 맥락과 기사 단서를 최대한 살려 상세하고 자연스러운 페르소나를 작성하라. "
            "반드시 유효한 JSON 객체만 반환하고, 문자열 값에는 이스케이프되지 않은 줄바꿈을 넣지 마라. "
            f"{self._output_language_instruction_ko()} "
            "중국어를 사용하지 마라. gender 필드만 male/female/other 중 하나의 영문 값으로 반환하라."
        )
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """개인 엔터티용 상세 페르소나 프롬프트를 구성한다."""
        if self._prompt_language() == "en":
            return self._build_individual_persona_prompt_en(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else self._empty_prompt_value()
        context_str = context[:3000] if context else self._empty_context_value()
        output_instruction = self._output_language_instruction_ko()
        
        return f"""아래 엔터티를 바탕으로 소셜 미디어 시뮬레이션용 상세 사용자 페르소나를 생성하라. 가능한 한 현실 맥락을 살리고, 지정된 출력 언어를 엄격히 따르라.

엔터티 이름: {entity_name}
엔터티 유형: {entity_type}
엔터티 요약: {entity_summary}
엔터티 속성: {attrs_str}

문맥 정보:
{context_str}

아래 필드를 포함하는 JSON을 생성하세요:

1. bio: 소셜 미디어 소개문, 지정된 출력 언어 2~3문장
2. persona: 상세 페르소나 설명(지정된 출력 언어 순문단), 다음 내용을 포함:
   - 기본 정보(연령대, 직업, 교육/경력, 활동 지역)
   - 사건과의 연결 배경
   - 성격 특성(MBTI, 감정 표현 방식, 판단 습관)
   - 소셜 미디어 행동 패턴(발언 빈도, 선호 콘텐츠, 상호작용 방식)
   - 주제에 대한 입장과 민감 포인트
   - 기억/경험(이 사건과 관련해 왜 이런 반응을 보이는지)
3. age: 나이 숫자(정수)
4. gender: 영문 값만 허용 - "male" 또는 "female"
5. mbti: MBTI 유형
6. country: 국가/지역명 (지정된 출력 언어)
7. profession: 직업/역할 (지정된 출력 언어)
8. interested_topics: 관심 주제 배열 (지정된 출력 언어)

중요:
- {output_instruction}
- 모든 필드 값은 문자열 또는 숫자만 사용하고 null은 쓰지 마세요.
- persona는 하나의 연속된 문단으로 작성하세요.
- 중국어를 쓰지 마세요.
- 내용은 엔티티 정보와 문맥에 맞아야 합니다.
- age는 유효한 정수, gender는 "male" 또는 "female" 이어야 합니다.
"""

    def _build_individual_persona_prompt_en(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build a detailed persona prompt for individual entities in English."""
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else self._empty_prompt_value()
        context_str = context[:3000] if context else self._empty_context_value()
        output_instruction = self._output_language_instruction_en()

        return f"""Create a detailed social media user persona for the entity below. Preserve realistic context as much as possible and strictly follow the output language instruction.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Generate JSON with these exact field names:

1. bio: 2-3 sentence social media profile introduction
2. persona: detailed persona description in one continuous paragraph, including:
   - Basic information such as age range, profession, education or career, and active region
   - Background connection to the event
   - Personality traits such as MBTI, emotional expression, and judgment habits
   - Social media behavior patterns such as posting frequency, preferred content, and interaction style
   - Position on the topic and sensitive points
   - Memories or experiences explaining why this entity reacts this way
3. age: integer age
4. gender: English value only - "male" or "female"
5. mbti: MBTI type
6. country: country or region name
7. profession: profession or role
8. interested_topics: array of interested topics

Important:
- {output_instruction}
- Use only strings or numbers for field values and do not use null.
- Write persona as one continuous paragraph.
- Do not use Chinese.
- Content must match the entity information and context.
- age must be a valid integer, and gender must be "male" or "female".
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """집단/기관 엔터티용 상세 페르소나 프롬프트를 구성한다."""
        if self._prompt_language() == "en":
            return self._build_group_persona_prompt_en(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else self._empty_prompt_value()
        context_str = context[:3000] if context else self._empty_context_value()
        output_instruction = self._output_language_instruction_ko()
        
        return f"""아래 기관/집단 엔터티를 바탕으로 소셜 미디어 시뮬레이션용 상세 공식 계정 설정을 생성하라. 가능한 한 현실 맥락을 살리고, 지정된 출력 언어를 엄격히 따르라.

엔터티 이름: {entity_name}
엔터티 유형: {entity_type}
엔터티 요약: {entity_summary}
엔터티 속성: {attrs_str}

문맥 정보:
{context_str}

아래 필드를 포함하는 JSON을 생성하세요:

1. bio: 공식 계정 소개문, 지정된 출력 언어 2~3문장
2. persona: 상세 계정/기관 설정 설명(지정된 출력 언어 순문단), 다음 내용을 포함:
   - 기관 기본 정보(성격, 배경, 기능)
   - 계정 포지션과 목표 독자
   - 발화 스타일과 금기 표현
   - 게시 패턴과 활동 시간대
   - 핵심 이슈에 대한 입장과 대응 방식
   - 이 사건과 관련된 기존 반응과 기억
3. age: 고정값 30
4. gender: 고정값 "other"
5. mbti: 계정 스타일을 설명하는 MBTI
6. country: 국가/지역명 (지정된 출력 언어)
7. profession: 기관/조직 역할 설명 (지정된 출력 언어)
8. interested_topics: 주요 관심 주제 배열 (지정된 출력 언어)

중요:
- {output_instruction}
- 모든 필드 값은 문자열 또는 숫자만 사용하고 null은 쓰지 마세요.
- persona는 하나의 연속된 문단으로 작성하세요.
- 중국어를 쓰지 마세요.
- age는 30, gender는 "other" 로 고정하세요.
- 기관 계정의 발화 스타일은 해당 조직의 역할과 위상에 맞아야 합니다."""

    def _build_group_persona_prompt_en(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build a detailed official account prompt for group entities in English."""
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else self._empty_prompt_value()
        context_str = context[:3000] if context else self._empty_context_value()
        output_instruction = self._output_language_instruction_en()

        return f"""Create a detailed official account profile for the organization or group entity below. Preserve realistic context as much as possible and strictly follow the output language instruction.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Generate JSON with these exact field names:

1. bio: 2-3 sentence official account introduction
2. persona: detailed account or organization profile in one continuous paragraph, including:
   - Basic organization information such as nature, background, and function
   - Account position and target audience
   - Speaking style and prohibited expressions
   - Posting pattern and active hours
   - Position on key issues and response style
   - Prior reactions and memories related to this event
3. age: fixed value 30
4. gender: fixed value "other"
5. mbti: MBTI type describing the account style
6. country: country or region name
7. profession: organization or institution role description
8. interested_topics: array of main interested topics

Important:
- {output_instruction}
- Use only strings or numbers for field values and do not use null.
- Write persona as one continuous paragraph.
- Do not use Chinese.
- age must be 30, and gender must be "other".
- The account speaking style must fit the organization's role and status."""
    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """규칙 기반으로 기본 페르소나를 생성한다."""
        
        # 엔터티 유형에 따라 다른 페르소나를 생성한다.
        entity_type_lower = self._normalize_entity_type_key(entity_type)
        
        if entity_type_lower in ["student", "alumni", "학생", "동문"]:
            return {
                "bio": f"{entity_name} 계정은 학업과 사회 이슈에 민감하게 반응하며 또래와의 대화에 적극적으로 참여한다.",
                "persona": f"{entity_name}는 {entity_type.lower()} 배경을 가진 인물로, 사회 이슈와 교육 문제를 자신의 경험과 연결해 해석하는 경향이 있다. 온라인에서는 또래 관점에서 체감되는 불안과 기대를 함께 전달하며, 사실 확인과 감정 표현을 모두 중시한다.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": self._infer_country_label(entity_name, entity_type, entity_summary),
                "profession": "학생 또는 청년 커뮤니티 구성원",
                "interested_topics": ["교육", "사회 이슈", "기술"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty", "공인", "전문가", "교직원"]:
            return {
                "bio": f"{entity_name} 계정은 전문성과 해설 능력을 바탕으로 공공 이슈에 대한 해석과 의견을 제시한다.",
                "persona": f"{entity_name}는 {entity_type.lower()} 역할을 맡은 전문가형 인물이다. 사건을 단순한 감정 반응보다 구조적 맥락과 제도적 의미 속에서 해석하려 하며, 온라인에서는 신중하지만 영향력 있는 어조로 핵심 논점을 정리한다.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": self._infer_country_label(entity_name, entity_type, entity_summary),
                "profession": entity_attributes.get("occupation", "전문가"),
                "interested_topics": ["정치", "경제", "사회 문화"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform", "언론사", "플랫폼"]:
            return {
                "bio": f"{entity_name} 계정은 주요 현안과 속보를 빠르게 전달하고 공적 담론을 연결하는 매체 성격의 계정이다.",
                "persona": f"{entity_name}는 뉴스와 이슈 해설을 제공하는 매체형 계정이다. 핵심 사실을 빠르게 전달하면서도 확산력이 큰 표현을 선호하며, 대중이 사건을 어떻게 받아들이는지 민감하게 반영한다.",
                "age": 30,  # 기관 가상 나이
                "gender": "other",  # 기관은 other 사용
                "mbti": "ISTJ",  # 기관 스타일: 엄격하고 보수적
                "country": self._infer_country_label(entity_name, entity_type, entity_summary),
                "profession": "미디어 또는 플랫폼 운영 계정",
                "interested_topics": ["일반 뉴스", "현안", "공공 이슈"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization", "대학", "정부기관", "시민단체", "조직"]:
            return {
                "bio": f"{entity_name} 계정은 공식 입장과 공지를 전달하며 이해관계자와의 소통을 담당하는 기관 계정이다.",
                "persona": f"{entity_name}는 제도적 책임과 공식성을 가진 기관형 계정이다. 이슈가 발생하면 사실관계 정리, 입장 표명, 대응 계획 안내를 중심으로 발언하며, 조직의 신뢰도와 일관성을 유지하는 데 초점을 둔다.",
                "age": 30,  # 기관 가상 나이
                "gender": "other",  # 기관은 other 사용
                "mbti": "ISTJ",  # 기관 스타일: 엄격하고 보수적
                "country": self._infer_country_label(entity_name, entity_type, entity_summary),
                "profession": self._infer_profession_label(entity_type),
                "interested_topics": ["공공 정책", "커뮤니티", "공식 공지"],
            }
        
        else:
            # 기본 페르소나
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name}는 온라인 공론장에서 의견을 내고 반응을 주고받는 {entity_type.lower()} 유형의 개체다.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": self._infer_country_label(entity_name, entity_type, entity_summary),
                "profession": self._infer_profession_label(entity_type),
                "interested_topics": ["일반 이슈", "사회 현안"],
            }
    
    def set_graph_id(self, graph_id: str):
        """Zep 검색에 사용할 graph ID를 설정한다."""
        self.graph_id = graph_id

    def _infer_country_label(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str = "",
        context: str = ""
    ) -> str:
        haystack = f"{entity_name}\n{entity_type}\n{entity_summary}\n{context}".lower()
        for country, keywords in self.COUNTRY_KEYWORDS.items():
            if any(keyword in haystack for keyword in keywords):
                return country
        return random.choice(self.COUNTRIES)

    def _infer_profession_label(self, entity_type: str) -> str:
        normalized = (entity_type or "Entity").strip()
        mapping = {
            "governmentagency": "정부·공공기관 계정",
            "organization": "조직·기관 계정",
            "ngo": "시민단체·비영리 기관 계정",
            "mediaoutlet": "언론·미디어 계정",
            "company": "기업·브랜드 계정",
            "university": "대학·교육기관 계정",
            "community": "커뮤니티 운영 계정",
            "socialmediaplatform": "플랫폼 운영 계정",
            "정부기관": "정부·공공기관 계정",
            "조직": "조직·기관 계정",
            "시민단체": "시민단체·비영리 기관 계정",
            "언론사": "언론·미디어 계정",
            "기업": "기업·브랜드 계정",
            "대학": "대학·교육기관 계정",
            "커뮤니티": "커뮤니티 운영 계정",
            "플랫폼": "플랫폼 운영 계정",
            "개인": "개인 계정",
        }
        return mapping.get(normalized.lower(), normalized)

    def _normalize_topics(self, topics: Any) -> List[str]:
        if not topics:
            return []
        if isinstance(topics, str):
            topics = [topics]
        return [str(topic).strip() for topic in topics if str(topic).strip()]
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        엔터티 목록에서 Agent Profile을 일괄 생성한다(병렬 생성 지원).
        
        Args:
            entities: 엔터티 목록
            use_llm: LLM으로 상세 페르소나를 생성할지 여부
            progress_callback: 진행률 콜백 함수 (current, total, message)
            graph_id: Zep 검색으로 더 풍부한 문맥을 가져올 graph ID
            parallel_count: 병렬 생성 개수, 기본값 5
            realtime_output_path: 실시간으로 쓸 파일 경로(제공 시 하나 생성할 때마다 저장)
            output_platform: 출력 플랫폼 형식("reddit" 또는 "twitter")
            
        Returns:
            Agent Profile 목록
        """
        import concurrent.futures
        from threading import Lock
        
        # Zep 검색에 사용할 graph_id 설정
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total  # 순서 유지를 위해 목록을 미리 할당
        completed_count = [0]  # 클로저에서 수정할 수 있도록 목록 사용
        lock = Lock()
        
        # 파일에 실시간으로 쓰는 보조 함수
        def save_profiles_realtime():
            """생성된 profiles를 파일에 실시간으로 저장한다."""
            if not realtime_output_path:
                return
            
            with lock:
                # 생성이 완료된 profiles만 필터링
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON 형식
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV 형식
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"profiles 실시간 저장 실패: {e}")
        
        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """단일 profile을 생성하는 작업 함수."""
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # 생성된 페르소나를 콘솔에 실시간 출력
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"엔터티 {entity.name}의 페르소나 생성 실패: {str(e)}")
                # 기본 profile 생성
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"Agent 페르소나 {total}개를 병렬 생성 시작 (병렬 수: {parallel_count})...")
        print(f"\n{'='*60}")
        print(f"Agent 페르소나 생성 시작 - 총 {total}개 엔터티, 병렬 수: {parallel_count}")
        print(f"{'='*60}\n")
        
        # 스레드 풀로 병렬 실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # 모든 작업 제출
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # 결과 수집
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # 파일에 실시간 쓰기
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"완료 {current}/{total}: {entity.name}({entity_type})"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} 에 fallback 페르소나 사용: {error}")
                    else:
                        logger.info(f"[{current}/{total}] 페르소나 생성 성공: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"엔티티 {entity.name} 처리 중 예외 발생: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # 대체 페르소나도 파일에 실시간 쓰기
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"페르소나 생성 완료! 총 {len([p for p in profiles if p])}개 Agent 생성")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """생성된 페르소나를 콘솔에 실시간 출력한다(전체 내용, 자르지 않음)."""
        separator = "-" * 70
        
        # 전체 출력 내용을 구성한다(자르지 않음).
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else '없음'
        
        output_lines = [
            f"\n{separator}",
            f"[생성됨] {entity_name} ({entity_type})",
            f"{separator}",
            f"사용자명: {profile.user_name}",
            f"",
            f"【소개】",
            f"{profile.bio}",
            f"",
            f"【상세 페르소나】",
            f"{profile.persona}",
            f"",
            f"【기본 속성】",
            f"나이: {profile.age} | 성별: {profile.gender} | MBTI: {profile.mbti}",
            f"직업: {profile.profession} | 국가: {profile.country}",
            f"관심 주제: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # 콘솔에만 출력한다(중복 방지를 위해 logger에는 전체 내용을 남기지 않음).
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        Profile을 파일로 저장한다(플랫폼에 맞는 형식 선택).

        OASIS 플랫폼 형식 요구사항:
        - Twitter: CSV 형식
        - Reddit: JSON 형식
        
        Args:
            profiles: Profile 목록
            file_path: 파일 경로
            platform: 플랫폼 유형("reddit" 또는 "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Twitter Profile을 CSV 형식으로 저장한다(OASIS 공식 요구사항 준수).

        OASIS Twitter가 요구하는 CSV 필드:
        - user_id: 사용자 ID(CSV 순서 기준 0부터 시작)
        - name: 사용자 실명
        - username: 시스템의 사용자명
        - user_char: 상세 페르소나 설명(LLM 시스템 프롬프트에 주입되어 Agent 행동을 안내)
        - description: 짧은 공개 소개(사용자 프로필 페이지에 표시)

        user_char vs description 차이:
        - user_char: 내부 사용, LLM 시스템 프롬프트, Agent의 사고와 행동 결정
        - description: 외부 표시, 다른 사용자에게 보이는 소개
        """
        import csv
        
        # 파일 확장자가 .csv인지 확인
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # OASIS가 요구하는 헤더 쓰기
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # 데이터 행 쓰기
            for idx, profile in enumerate(profiles):
                # user_char: 전체 페르소나(bio + persona), LLM 시스템 프롬프트에 사용
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # 줄바꿈 처리(CSV에서는 공백으로 대체)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: 외부 표시에 사용할 짧은 소개
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: 0부터 시작하는 순차 ID
                    profile.name,           # name: 실명
                    profile.user_name,      # username: 사용자명
                    user_char,              # user_char: 전체 페르소나(내부 LLM 사용)
                    description             # description: 짧은 소개(외부 표시)
                ]
                writer.writerow(row)
        
        logger.info(f"Twitter Profile {len(profiles)}개를 {file_path}에 저장했습니다 (OASIS CSV 형식)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        gender 필드를 OASIS가 요구하는 영어 형식으로 정규화한다.

        OASIS 요구사항: male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # 기존 중국어 매핑
        gender_map = {
            "男": "male",
            "女": "female",
            "机构": "other",
            "其他": "other",
            # 기존 영어 값
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Reddit Profile을 JSON 형식으로 저장한다.

        to_reddit_format()과 일치하는 형식을 사용해 OASIS가 올바르게 읽도록 한다.
        user_id 필드는 OASIS agent_graph.get_agent() 매칭에 필요하므로 반드시 포함한다.

        필수 필드:
        - user_id: 사용자 ID(정수, initial_posts의 poster_agent_id 매칭에 사용)
        - username: 사용자명
        - name: 표시 이름
        - bio: 소개
        - persona: 상세 페르소나
        - age: 나이(정수)
        - gender: "male", "female" 또는 "other"
        - mbti: MBTI 유형
        - country: 국가
        """
        data = []
        for idx, profile in enumerate(profiles):
            # to_reddit_format()과 일치하는 형식 사용
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # 핵심: user_id를 반드시 포함
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name}는 공적 논의에 참여하는 시뮬레이션 개체입니다.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS 필수 필드 - 모두 기본값을 갖도록 보장
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "미상",
            }
            
            # 선택 필드
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Reddit Profile {len(profiles)}개를 {file_path}에 저장했습니다 (JSON 형식, user_id 포함)")
    
    # 이전 메서드명을 별칭으로 보존해 하위 호환 유지
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[폐기 예정] save_profiles() 메서드를 사용한다."""
        logger.warning("save_profiles_to_json은 폐기 예정입니다. save_profiles를 사용하세요")
        self.save_profiles(profiles, file_path, platform)
