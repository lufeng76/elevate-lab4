"""Unit tests for GroundingEvaluator."""
import pytest
from agent.security.grounding import GroundingEvaluator


def test_grounding_evaluator_grounded_response():
    evaluator = GroundingEvaluator(threshold=0.5)
    evidence = [
        {
            "payload": {
                "content": "Full-time employees in Singapore are eligible for 14 days of paid outpatient sick leave.",
                "title": "Sick Leave Policy",
                "resource": "https://hr.corp/policies/sick-leave",
            }
        }
    ]
    response = "You are entitled to 14 days of paid outpatient sick leave under the Singapore policy."
    result = evaluator.evaluate(response, evidence)
    assert result.is_grounded is True
    assert result.score >= 0.5
    assert "https://hr.corp/policies/sick-leave" in result.citations_found


def test_grounding_evaluator_ungrounded_response():
    evaluator = GroundingEvaluator(threshold=0.7)
    evidence = [
        {
            "payload": {
                "content": "Bereavement leave provides 5 consecutive business days of leave for immediate family.",
                "title": "Bereavement Leave",
            }
        }
    ]
    # Completely unrelated response
    response = "You can claim free gym memberships and dental insurance benefits from our health provider."
    result = evaluator.evaluate(response, evidence)
    assert result.is_grounded is False
    assert result.score < 0.7
