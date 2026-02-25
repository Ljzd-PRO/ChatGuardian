from __future__ import annotations

import json
import httpx
import streamlit as st

DEFAULT_API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="ChatGuardian 调试面板", layout="wide")


def call_api(method: str, url: str, **kwargs):
    try:
        resp = httpx.request(method, url, timeout=20, **kwargs)
        return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
    except Exception as exc:
        return {"error": str(exc)}


def main():
    st.title("ChatGuardian 调试面板")
    api_base = st.text_input("API Base URL", value=DEFAULT_API_BASE)

    st.header("健康检查")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("检查 /health"):
            result = call_api("GET", f"{api_base.rstrip('/')}/health")
            st.json(result)
    with col2:
        do_ping = st.checkbox("LLM health 执行 ping", value=False)
        if st.button("检查 /llm/health"):
            params = {"do_ping": "true" if do_ping else "false"}
            result = call_api("GET", f"{api_base.rstrip('/')}/llm/health", params=params)
            st.json(result)

    st.header("Adapter 控制")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("启动 Adapters"):
            result = call_api("POST", f"{api_base.rstrip('/')}/adapters/start")
            st.json(result)
    with col2:
        if st.button("停止 Adapters"):
            result = call_api("POST", f"{api_base.rstrip('/')}/adapters/stop")
            st.json(result)

    st.header("规则管理")
    if st.button("刷新规则列表"):
        rules = call_api("GET", f"{api_base.rstrip('/')}/rules/list")
        if isinstance(rules, list):
            df = []
            for r in rules:
                df.append({
                    "rule_id": r.get("rule_id"),
                    "name": r.get("name"),
                    "enabled": r.get("enabled"),
                    "description": r.get("description"),
                })
            st.dataframe(df)
        else:
            st.json(rules)

    st.subheader("编辑/添加规则")
    default_rule = {
        "rule_id": "rule-temp-1",
        "name": "Topic monitor",
        "description": "generic topic monitor",
        "target_session": {"mode": "exact", "query": "chat-1"},
        "topic_hints": ["topic"],
        "score_threshold": 0.5,
        "enabled": True,
        "parameters": [{"key": "tag", "description": "topic tag", "required": False}],
    }
    rule_json = st.text_area("规则 JSON", value=json.dumps(default_rule, ensure_ascii=False, indent=2), height=200)
    if st.button("提交 /rules"):
        try:
            payload = json.loads(rule_json)
            result = call_api("POST", f"{api_base.rstrip('/')}/rules", json=payload)
            st.json(result)
        except json.JSONDecodeError as exc:
            st.error(f"规则 JSON 解析失败: {exc}")

    st.subheader("删除规则")
    del_rule_id = st.text_input("要删除的 rule_id")
    if st.button("删除规则"):
        result = call_api("POST", f"{api_base.rstrip('/')}/rules/delete/{del_rule_id}")
        st.json(result)

    st.header("一句话生成规则")
    utterance = st.text_area("用户描述", height=100)
    use_external = st.checkbox("使用外部后端")
    override_system_prompt = st.text_area("覆盖系统提示词（可选）", height=100)
    if st.button("调用 /rule-generation"):
        payload = {
            "utterance": utterance,
            "use_external": use_external,
            "override_system_prompt": override_system_prompt.strip() or None,
        }
        result = call_api("POST", f"{api_base.rstrip('/')}/rule-generation", json=payload)
        st.json(result)


if __name__ == "__main__":
    main()
