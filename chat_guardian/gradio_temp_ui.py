"""临时 Gradio 调试面板。

该界面通过 HTTP 调用 ChatGuardian API，便于本地联调：
- 健康检查
- LLM 健康检查
- Adapter 启停
- 规则创建/更新
- 一句话生成规则
"""

from __future__ import annotations

import json
from typing import Any

import gradio as gr
import httpx

DEFAULT_API_BASE = "http://127.0.0.1:8000"


def _pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _request(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None) -> str:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.request(method=method, url=url, json=payload)
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        return _pretty(
            {
                "ok": response.is_success,
                "status_code": response.status_code,
                "url": url,
                "body": body,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _pretty({"ok": False, "url": url, "error": str(exc)})


def do_health(base_url: str) -> str:
    return _request("GET", base_url, "/health")


def do_llm_health(base_url: str, do_ping: bool) -> str:
    path = "/llm/health?do_ping=true" if do_ping else "/llm/health?do_ping=false"
    return _request("GET", base_url, path)


def do_adapter_start(base_url: str) -> str:
    return _request("POST", base_url, "/adapters/start")


def do_adapter_stop(base_url: str) -> str:
    return _request("POST", base_url, "/adapters/stop")


def do_upsert_rule(base_url: str, rule_json: str) -> str:
    try:
        payload = json.loads(rule_json)
    except json.JSONDecodeError as exc:
        return _pretty({"ok": False, "error": f"规则 JSON 解析失败: {exc}"})
    return _request("POST", base_url, "/rules", payload)


def do_generate_rule(
    base_url: str,
    utterance: str,
    use_external: bool,
    override_system_prompt: str,
) -> str:
    payload = {
        "utterance": utterance,
        "use_external": use_external,
        "override_system_prompt": override_system_prompt.strip() or None,
    }
    return _request("POST", base_url, "/rule-generation", payload)



# 新增规则管理 API
def do_list_rules(base_url: str) -> list[dict]:
    url = f"{base_url.rstrip('/')}/rules/list"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url)
        return resp.json() if resp.is_success else []
    except Exception:
        return []

def do_delete_rule(base_url: str, rule_id: str) -> str:
    url = f"{base_url.rstrip('/')}/rules/delete/{rule_id}"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url)
        return _pretty({"ok": resp.is_success, "status_code": resp.status_code, "rule_id": rule_id})
    except Exception as exc:
        return _pretty({"ok": False, "error": str(exc)})

def build_demo() -> gr.Blocks:
    with gr.Blocks(title="ChatGuardian 临时调试面板") as demo:
        gr.Markdown("# ChatGuardian 临时调试面板")
        gr.Markdown("该界面仅用于联调，不作为正式产品 UI。")

        api_base = gr.Textbox(label="API Base URL", value=DEFAULT_API_BASE)

        with gr.Tab("健康检查"):
            with gr.Row():
                health_btn = gr.Button("检查 /health", variant="primary")
                llm_health_btn = gr.Button("检查 /llm/health")
            ping_checkbox = gr.Checkbox(label="LLM health 执行 ping", value=False)
            health_out = gr.Code(label="结果", language="json")

            health_btn.click(fn=do_health, inputs=[api_base], outputs=[health_out])
            llm_health_btn.click(fn=do_llm_health, inputs=[api_base, ping_checkbox], outputs=[health_out])

        with gr.Tab("Adapter"):
            with gr.Row():
                start_btn = gr.Button("启动 Adapters", variant="primary")
                stop_btn = gr.Button("停止 Adapters")
            adapter_out = gr.Code(label="结果", language="json")

            start_btn.click(fn=do_adapter_start, inputs=[api_base], outputs=[adapter_out])
            stop_btn.click(fn=do_adapter_stop, inputs=[api_base], outputs=[adapter_out])

        with gr.Tab("规则管理"):
            gr.Markdown("### 规则列表")
            rule_list = gr.Dataframe(headers=["rule_id", "name", "enabled", "description"], datatype=["str", "str", "bool", "str"], label="已配置规则", interactive=False)
            refresh_btn = gr.Button("刷新规则列表")
            def _refresh_rules(api_base):
                rules = do_list_rules(api_base)
                return [[r.get("rule_id"), r.get("name"), r.get("enabled"), r.get("description")] for r in rules]
            refresh_btn.click(fn=_refresh_rules, inputs=[api_base], outputs=[rule_list])

            gr.Markdown("### 编辑/添加规则")
            rule_json = gr.Code(
                label="规则 JSON",
                language="json",
                value=_pretty(
                    {
                        "rule_id": "rule-temp-1",
                        "name": "Topic monitor",
                        "description": "generic topic monitor",
                        "target_session": {"mode": "exact", "query": "chat-1"},
                        "topic_hints": ["topic"],
                        "score_threshold": 0.5,
                        "enabled": True,
                        "parameters": [
                            {
                                "key": "tag",
                                "description": "topic tag",
                                "required": False,
                            }
                        ],
                    }
                ),
            )
            upsert_btn = gr.Button("提交 /rules", variant="primary")
            rule_out = gr.Code(label="结果", language="json")
            upsert_btn.click(fn=do_upsert_rule, inputs=[api_base, rule_json], outputs=[rule_out])

            gr.Markdown("### 删除规则")
            del_rule_id = gr.Textbox(label="要删除的 rule_id")
            del_btn = gr.Button("删除规则", variant="stop")
            del_out = gr.Code(label="结果", language="json")
            del_btn.click(fn=do_delete_rule, inputs=[api_base, del_rule_id], outputs=[del_out])

        with gr.Tab("一句话生成规则"):
            utterance = gr.Textbox(label="用户描述", lines=3, placeholder="例如：监控群里关于退款投诉的话题")
            use_external = gr.Checkbox(label="使用外部后端", value=False)
            override_system_prompt = gr.Textbox(label="覆盖系统提示词（可选）", lines=6)
            gen_btn = gr.Button("调用 /rule-generation", variant="primary")
            gen_out = gr.Code(label="结果", language="json")

            gen_btn.click(
                fn=do_generate_rule,
                inputs=[api_base, utterance, use_external, override_system_prompt],
                outputs=[gen_out],
            )

    return demo


def run() -> None:
    demo = build_demo()
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)


if __name__ == "__main__":
    run()
