"""Unit tests for OKF crawler and RAG tool error handling."""
import pytest
from agent.tools.okf_tool import list_concepts, read_concept


def test_list_concepts_returns_concepts():
    res = list_concepts()
    assert "concepts" in res
    assert len(res["concepts"]) > 0
    first = res["concepts"][0]
    assert "id" in first
    assert "title" in first


def test_read_concept_valid():
    res = list_concepts()
    first_id = res["concepts"][0]["id"]
    doc = read_concept(first_id)
    assert "content" in doc
    assert "title" in doc
    assert doc.get("error") is None


def test_read_concept_path_traversal_blocked():
    malicious_id = "../../etc/passwd"
    doc = read_concept(malicious_id)
    assert "error" in doc
    assert "Access outside knowledge directory is prohibited" in doc["error"]


def test_read_concept_not_found():
    doc = read_concept("nonexistent/section/fake-doc")
    assert "error" in doc
    assert "not found" in doc["error"]
