from chat_guardian.services import InternalRuleGenerationBackend


async def test_internal_rule_generation_is_generic() -> None:
    backend = InternalRuleGenerationBackend()
    rule = await backend.generate("在常聊的讨论群里，提到新主题时提醒我，并提取两个参数")

    assert rule.rule_id.startswith("rule-")
    assert rule.description
    assert rule.target_session.query
    assert isinstance(rule.topic_hints, list)
    assert rule.parameters
