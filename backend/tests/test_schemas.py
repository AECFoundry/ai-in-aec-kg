"""Tests for Pydantic schema models."""
from __future__ import annotations

from app.models.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    GraphData,
    GraphLink,
    GraphNode,
    SubgraphHighlight,
)


class TestGraphNode:
    def test_create_minimal(self):
        node = GraphNode(id="n1", label="Topic", name="BIM")
        assert node.id == "n1"
        assert node.label == "Topic"
        assert node.name == "BIM"
        assert node.group == ""
        assert node.properties == {}

    def test_create_full(self):
        node = GraphNode(
            id="n2",
            label="Speaker",
            name="Jane Doe",
            group="Speaker",
            properties={"affiliation": "ACME"},
        )
        assert node.properties["affiliation"] == "ACME"

    def test_serialize_deserialize(self):
        node = GraphNode(id="n1", label="Topic", name="BIM", group="Topic")
        data = node.model_dump()
        restored = GraphNode(**data)
        assert restored == node

    def test_json_round_trip(self):
        node = GraphNode(id="n1", label="Topic", name="BIM")
        json_str = node.model_dump_json()
        restored = GraphNode.model_validate_json(json_str)
        assert restored.id == "n1"


class TestGraphLink:
    def test_create(self):
        link = GraphLink(source="n1", target="n2", type="PRESENTED_BY")
        assert link.source == "n1"
        assert link.type == "PRESENTED_BY"

    def test_serialize(self):
        link = GraphLink(source="a", target="b", type="REL", properties={"weight": 1})
        data = link.model_dump()
        assert data["properties"]["weight"] == 1


class TestGraphData:
    def test_compose(self):
        gd = GraphData(
            nodes=[GraphNode(id="n1", label="Topic", name="BIM")],
            links=[GraphLink(source="n1", target="n2", type="RELATES_TO")],
        )
        assert len(gd.nodes) == 1
        assert len(gd.links) == 1


class TestChatModels:
    def test_chat_request(self):
        cr = ChatRequest(message="What sessions cover BIM?")
        assert "BIM" in cr.message

    def test_chat_message(self):
        cm = ChatMessage(role="user", content="hello")
        assert cm.role == "user"

    def test_subgraph_highlight_defaults(self):
        sh = SubgraphHighlight()
        assert sh.node_ids == []
        assert sh.link_ids == []

    def test_chat_response_full(self):
        resp = ChatResponse(
            answer="Here is the answer.",
            subgraph=SubgraphHighlight(node_ids=["n1"], link_ids=["n1->n2"]),
            sources=[{"id": "n1", "name": "BIM Session", "score": 0.92}],
        )
        assert resp.answer.startswith("Here")
        assert len(resp.sources) == 1
        assert resp.subgraph.node_ids == ["n1"]

    def test_chat_response_serialize(self):
        resp = ChatResponse(
            answer="test",
            subgraph=SubgraphHighlight(),
            sources=[],
        )
        data = resp.model_dump()
        restored = ChatResponse(**data)
        assert restored.answer == "test"
