from types import SimpleNamespace

from app.services.oasis_profile_generator import OasisAgentProfile, OasisProfileGenerator
from app.services.zep_entity_reader import EntityNode


class _FakeGraph:
    def __init__(self):
        self.queries = []

    def search(self, **kwargs):
        self.queries.append(kwargs)
        if kwargs["scope"] == "edges":
            return SimpleNamespace(edges=[SimpleNamespace(fact="테스트 사실")])
        return SimpleNamespace(nodes=[SimpleNamespace(name="관련 계정", summary="관련 노드 요약")])


class _FakeZepClient:
    def __init__(self):
        self.graph = _FakeGraph()


def _make_generator():
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    generator.zep_client = _FakeZepClient()
    generator.graph_id = "graph-1"
    return generator


def test_zep_search_query_uses_korean_source_text():
    generator = _make_generator()
    entity = EntityNode(
        uuid="entity-1",
        name="개인 투자자",
        labels=["개인"],
        summary="시장 반응을 말하는 계정",
        attributes={},
    )

    result = generator._search_zep_for_entity(entity)

    queries = [call["query"] for call in generator.zep_client.graph.queries]
    assert queries
    assert all("개인 투자자" in query for query in queries)
    assert all("정보" in query and "활동" in query and "관계" in query for query in queries)
    assert all("关于" not in query for query in queries)
    assert "사실 정보" in result["context"]
    assert "관련 엔티티" in result["context"]


def test_entity_context_uses_korean_headings_and_relationship_placeholders():
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    generator.graph_id = None
    generator.zep_client = None

    entity = EntityNode(
        uuid="entity-1",
        name="개인 투자자",
        labels=["개인"],
        summary="시장 반응을 말하는 계정",
        attributes={"role": "투자자"},
        related_edges=[
            {"direction": "outgoing", "edge_name": "영향", "fact": "", "target_node_uuid": "entity-2"},
            {"direction": "incoming", "edge_name": "언급", "fact": "", "source_node_uuid": "entity-3"},
        ],
        related_nodes=[
            {"uuid": "entity-2", "name": "증권사", "labels": ["조직"], "summary": "시장 분석 기관"},
        ],
    )

    context = generator._build_entity_context(entity)

    assert "### 엔티티 속성" in context
    assert "### 관련 사실과 관계" in context
    assert "### 연관 엔티티 정보" in context
    assert "(관련 엔티티)" in context
    assert "实体属性" not in context
    assert "相关实体" not in context


def test_generated_profile_console_labels_are_korean(capsys):
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    profile = OasisAgentProfile(
        user_id=1,
        user_name="tester",
        name="테스터",
        bio="소개",
        persona="상세 페르소나",
        age=30,
        gender="other",
        mbti="ISTJ",
        country="대한민국",
        profession="테스트 계정",
        interested_topics=["테스트"],
    )

    generator._print_generated_profile("테스터", "개인", profile)
    output = capsys.readouterr().out

    assert "사용자명" in output
    assert "상세 페르소나" in output
    assert "年龄" not in output
    assert "用户名" not in output
