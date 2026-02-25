from chat_guardian.domain import DetectionRule, SessionMatchMode, SessionTarget
from chat_guardian.services import LangChainLLMClient, _extract_json_payload


def test_extract_json_payload_from_text_with_wrapper() -> None:
    raw = "```json\n{\"decisions\": [{\"rule_id\": \"r-1\", \"triggered\": true, \"confidence\": 0.9, \"reason\": \"ok\"}]}\n```"
    parsed = _extract_json_payload(raw)
    assert parsed["decisions"][0]["rule_id"] == "r-1"


def test_parse_decisions_fills_missing_rule_with_safe_default() -> None:
    rules = [
        DetectionRule(
            rule_id="r-1",
            name="rule-1",
            description="d",
            target_session=SessionTarget(mode=SessionMatchMode.EXACT, query="chat-1"),
        ),
        DetectionRule(
            rule_id="r-2",
            name="rule-2",
            description="d",
            target_session=SessionTarget(mode=SessionMatchMode.EXACT, query="chat-1"),
        ),
    ]

    payload = {
        "decisions": [
            {
                "rule_id": "r-1",
                "triggered": True,
                "confidence": 0.8,
                "reason": "matched",
                "extracted_params": {"k": "v"},
            }
        ]
    }
    decisions = LangChainLLMClient._parse_decisions(payload, rules)

    assert len(decisions) == 2
    assert decisions[0].rule_id == "r-1"
    assert decisions[0].triggered is True
    assert decisions[1].rule_id == "r-2"
    assert decisions[1].triggered is False
    assert decisions[1].reason == "LLM response missing this rule"
