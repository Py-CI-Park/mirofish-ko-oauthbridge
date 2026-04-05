"""
온톨로지 생성 서비스
문서와 시뮬레이션 요구를 분석해 사회 시뮬레이션용 엔터티/관계 타입 정의를 생성한다.
"""

import json
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# 온톨로지 생성 시스템 프롬프트
ONTOLOGY_SYSTEM_PROMPT = """너는 소셜 시뮬레이션용 지식그래프 온톨로지 설계 전문가다. 주어진 문서와 시뮬레이션 요구를 분석해 **한국어 중심의 엔터티 타입/관계 타입 스키마**를 설계하라.

**중요: 반드시 유효한 JSON만 출력하고, 설명문이나 마크다운을 덧붙이지 마라.**

## 핵심 배경

우리는 소셜 미디어 여론 시뮬레이션 시스템을 만들고 있다. 이 시스템에서:
- 각 엔터티는 소셜 미디어에서 발화하고 상호작용하며 정보를 전파할 수 있는 계정 또는 주체다.
- 엔터티들은 서로 영향을 주고, 게시물을 올리고, 댓글을 남기고, 반응한다.
- 특정 사건에서 정보 확산 경로와 주체별 반응을 시뮬레이션해야 한다.

따라서 엔터티는 **현실에서 실제로 발화/행동할 수 있는 주체**여야 한다.

### 포함 가능 예시
- 구체적인 개인(공직자, 기자, 전문가, 당사자, 일반 시민 등)
- 기업/기관/단체의 공식 계정
- 정부 부처, 규제기관, 공공기관
- 언론사, 플랫폼, 커뮤니티 운영 주체
- 특정 이해관계 집단을 대표하는 계정

### 포함하면 안 되는 것
- 추상 개념(예: 여론, 공포, 분위기)
- 단순 주제/토픽(예: 세금개편, 교육개혁)
- 관점 자체(예: 찬성파, 반대파)

## 출력 형식

다음 구조의 JSON을 출력하라:

```json
{
  "entity_types": [
    {
      "name": "엔터티 타입명(한국어, 짧은 명사형)",
      "description": "짧은 설명(한국어, 100자 이내)",
      "attributes": [
        {
          "name": "속성명(영문 snake_case)",
          "type": "text",
          "description": "속성 설명(한국어)"
        }
      ],
      "examples": ["예시 엔터티1", "예시 엔터티2"]
    }
  ],
  "edge_types": [
    {
      "name": "관계 타입명(한국어, 짧은 명사/동사구)",
      "description": "짧은 설명(한국어, 100자 이내)",
      "source_targets": [
        {"source": "출발 엔터티 타입", "target": "도착 엔터티 타입"}
      ],
      "attributes": []
    }
  ],
  "analysis_summary": "문서 내용의 간단한 분석 요약(자연스러운 한국어, 중국어 금지)"
}
```

## 언어 규칙

- `entity_types[].name`, `edge_types[].name`, `description`, `examples`, `analysis_summary`는 모두 **한국어**로 작성한다.
- `attributes[].name`만 영문 snake_case를 유지한다.
- 중국어를 쓰지 마라.

## 설계 규칙

### 1) 엔터티 타입 설계
- 반드시 **정확히 10개**의 엔터티 타입을 출력한다.
- 마지막 2개는 반드시 fallback 타입으로 둔다.
  - `개인`: 다른 구체 타입으로 분류되지 않는 자연인
  - `조직`: 다른 구체 타입으로 분류되지 않는 조직/기관
- 앞의 8개는 문서 내용에 맞는 구체 타입으로 설계한다.
- 각 타입은 실제 발화 주체가 되어야 하며, 서로 경계가 겹치지 않게 설계한다.

### 2) 관계 타입 설계
- 6~10개
- 소셜 미디어 상의 실제 상호작용/영향 관계를 반영한다.
- `source_targets`는 정의한 엔터티 타입을 충분히 포괄해야 한다.

### 3) 속성 설계
- 각 엔터티 타입에 1~3개의 핵심 속성만 둔다.
- 속성명은 `name`, `uuid`, `group_id`, `created_at`, `summary` 같은 예약어를 쓰지 마라.
- `full_name`, `org_name`, `role`, `position`, `location`, `description` 같은 이름을 우선 사용하라.
"""


class OntologyGenerator:
    """
    온톨로지 생성기
    텍스트 내용을 분석해 엔티티/관계 유형 정의를 생성한다.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        온톨로지 정의를 생성한다.
        
        Args:
            document_texts: 문서 텍스트 목록
            simulation_requirement: 시뮬레이션 요구사항 설명
            additional_context: 추가 컨텍스트
            
        Returns:
            온톨로지 정의 (entity_types, edge_types 등)
        """
        # 사용자 메시지 구성
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        # LLM 호출
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        # 검증 및 후처리
        result = self._validate_and_process(result)
        
        return result
    
    # LLM에 전달할 최대 텍스트 길이 (5만자)
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """사용자 메시지를 구성한다."""
        
        # 텍스트 병합
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # 텍스트가 5만자를 넘으면 잘라낸다. (LLM 입력에만 영향, 그래프 구축엔 영향 없음)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(원문 총 {original_length}자 중 앞의 {self.MAX_TEXT_LENGTH_FOR_LLM}자만 온톨로지 분석에 사용함)..."
        
        message = f"""## 시뮬레이션 요구

{simulation_requirement}

## 문서 내용

{combined_text}
"""
        
        if additional_context:
            message += f"""
## 추가 설명

{additional_context}
"""
        
        message += """
위 내용을 바탕으로 사회 여론 시뮬레이션에 적합한 엔터티 타입과 관계 타입을 설계하라.

**반드시 지켜야 할 규칙**
1. 엔터티 타입은 정확히 10개여야 한다.
2. 마지막 2개는 fallback 타입 `개인`, `조직` 이어야 한다.
3. 앞의 8개는 문서 내용에 맞는 구체 타입이어야 한다.
4. 모든 엔터티 타입/관계 타입 이름은 한국어로 작성한다.
5. 속성명만 영문 snake_case를 사용한다.
6. `analysis_summary`는 자연스럽고 간결한 한국어로 작성하고 중국어를 쓰지 마라.
"""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """결과를 검증하고 후처리한다."""
        
        # 필수 필드 존재 보장
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        # 엔티티 유형 검증
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # description 길이를 100자 이하로 제한
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # 관계 유형 검증
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API 제한: 사용자 정의 엔티티 유형 최대 10개, 엣지 유형 최대 10개
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10
        
        # fallback 유형 정의
        person_fallback = {
            "name": "개인",
            "description": "다른 구체적 개인 타입에 속하지 않는 자연인",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "개인의 이름"},
                {"name": "role", "type": "text", "description": "직업 또는 역할"}
            ],
            "examples": ["일반 시민", "익명 이용자"]
        }
        
        organization_fallback = {
            "name": "조직",
            "description": "다른 구체적 조직 타입에 속하지 않는 기관 또는 단체",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "조직 이름"},
                {"name": "org_type", "type": "text", "description": "조직 유형"}
            ],
            "examples": ["소규모 단체", "지역 커뮤니티"]
        }
        
        # fallback 유형 존재 여부 확인
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "개인" in entity_names
        has_organization = "조직" in entity_names
        
        # 추가해야 할 fallback 유형
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # 추가 후 10개를 넘으면 기존 유형 일부를 제거해야 한다.
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 제거해야 할 개수 계산
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # 뒤에서부터 제거 (앞쪽의 더 중요한 구체 유형 우선 보존)
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # fallback 유형 추가
            result["entity_types"].extend(fallbacks_to_add)
        
        # 최종적으로 제한을 넘지 않도록 방어적으로 보정
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        온톨로지 정의를 Python 코드(ontology.py 유사 형태)로 변환한다.
        
        Args:
            ontology: 온톨로지 정의
            
        Returns:
            Python 코드 문자열
        """
        code_lines = [
            '"""',
            '사용자 정의 엔티티 유형 정의',
            'MiroFish가 자동 생성한 사회 시뮬레이션용 코드',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== 엔티티 유형 정의 ==============',
            '',
        ]
        
        # 엔티티 유형 생성
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== 관계 유형 정의 ==============')
        code_lines.append('')
        
        # 관계 유형 생성
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # PascalCase 클래스명으로 변환
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # 유형 딕셔너리 생성
        code_lines.append('# ============== 유형 구성 ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # 엣지 source_targets 매핑 생성
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)
