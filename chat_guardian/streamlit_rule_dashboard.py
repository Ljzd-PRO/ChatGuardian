"""Streamlit 可视化控制台：规则触发统计与记录详情。"""

from __future__ import annotations

import copy
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import streamlit as st


DEFAULT_API_BASE = os.getenv("CHAT_GUARDIAN_STREAMLIT_API_BASE", "http://127.0.0.1:8000")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@st.cache_data(ttl=5, show_spinner=False)
def _api_get(api_base: str, path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{api_base.rstrip('/')}{path}"
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
    return response.json()


def _api_post(api_base: str, path: str, json_data: dict[str, Any]) -> Any:
    url = f"{api_base.rstrip('/')}{path}"
    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, json=json_data)
        response.raise_for_status()
    return response.json()


def _extract_message_text(message: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in message.get("contents", []):
        item_type = item.get("type")
        if item_type == "text" and item.get("text"):
            parts.append(str(item["text"]))
        elif item_type == "mention" and item.get("mention_user_id"):
            parts.append(f"@{item['mention_user_id']}")
        elif item_type == "image" and item.get("image_url"):
            parts.append("[image]")
    return " ".join(parts).strip()


def _message_rows(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, message in enumerate(messages):
        rows.append(
            {
                "index": str(index),
                "sender_name": message.get("sender_name") or "匿名用户",
                "sender_id": message.get("sender_id", ""),
                "timestamp": message.get("timestamp", ""),
                "text": _extract_message_text(message),
            }
        )
    return rows


def _to_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if hasattr(raw_rows, "to_dict"):
        return raw_rows.to_dict("records")
    if isinstance(raw_rows, list):
        return [row for row in raw_rows if isinstance(row, dict)]
    return []


def _render_chat(messages: list[dict[str, Any]]) -> None:
    if not messages:
        st.info("该触发记录没有上下文聊天消息。")
        return

    for index, message in enumerate(messages):
        sender_name = message.get("sender_name") or "匿名用户"
        sender_id = message.get("sender_id", "")
        timestamp = message.get("timestamp", "")
        text = _extract_message_text(message)

        with st.chat_message("user", avatar="💬"):
            st.markdown(f"**{sender_name}**  ")
            if sender_id:
                st.caption(f"ID: {sender_id} · {timestamp}")
            elif timestamp:
                st.caption(timestamp)
            st.markdown(text if text else "（无文本内容）")

            image_urls = [
                item.get("image_url")
                for item in message.get("contents", [])
                if item.get("type") == "image" and item.get("image_url")
            ]
            for image_url in image_urls:
                st.image(image_url, caption=f"图片内容 #{index + 1}")



def _render_dashboard() -> None:
    st.set_page_config(
        page_title="ChatGuardian 规则触发看板",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        .cg-card {
            border: 1px solid rgba(120,120,120,0.2);
            border-radius: 14px;
            padding: 14px;
            margin-bottom: 10px;
            background: linear-gradient(180deg, rgba(40,40,60,0.06), rgba(40,40,60,0.02));
        }
        .cg-card-title {
            font-weight: 600;
            font-size: 1.02rem;
            margin-bottom: 4px;
        }
        .cg-muted {
            color: rgba(130,130,130,0.95);
            font-size: 0.88rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🛡️ ChatGuardian 规则触发可视化控制台")
    st.caption("规则统计、触发记录、结构化属性图形化展示与可编辑预览")

    with st.sidebar:
        st.subheader("连接设置")
        api_base = st.text_input("API Base URL", value=DEFAULT_API_BASE)
        include_suppressed = st.checkbox("包含抑制记录", value=False)
        manual_refresh = st.button("刷新数据", use_container_width=True)
        if manual_refresh:
            _api_get.clear()

        st.markdown("---")
        st.caption("后端需已启动并可访问 `/results/rules-summary` 与 `/results/rules/{rule_id}/triggers`。")

    main_tab, add_rule_tab = st.tabs(["🚀 规则看板", "➕ 创建规则"])

    with add_rule_tab:
        st.subheader("创建/更新检测规则")
        with st.form("create_rule_form"):
            rule_id = st.text_input("规则 ID (需唯一)", "new-rule-id")
            rule_name = st.text_input("规则名称", "新增安全规则")
            rule_desc = st.text_area("规则描述", "检测某些安全问题...")
            
            c1, c2 = st.columns(2)
            match_mode = c1.selectbox("会话匹配模式", ["exact", "fuzzy"], index=1)
            target_query = c2.text_input("匹配目标 (群ID等)", "test-group")
            
            topic_hints_str = st.text_input("主题提示 (逗号分隔)", "安全, 告警")
            score_threshold = st.slider("触发阈值", 0.0, 1.0, 0.6, 0.05)
            is_enabled = st.checkbox("是否启用", value=True)
            
            st.markdown("##### 需提取参数 (可选)")
            params_df = pd.DataFrame([{"key": "", "description": "", "required": True}])
            edited_params = st.data_editor(
                params_df, 
                num_rows="dynamic",
                column_config={
                    "key": st.column_config.TextColumn("参数键名"),
                    "description": st.column_config.TextColumn("参数描述"),
                    "required": st.column_config.CheckboxColumn("必填"),
                }
            )

            submitted = st.form_submit_button("保存规则", use_container_width=True)
            if submitted:
                payload = {
                    "rule_id": rule_id.strip(),
                    "name": rule_name.strip(),
                    "description": rule_desc.strip(),
                    "target_session": {"mode": match_mode, "query": target_query.strip()},
                    "topic_hints": [x.strip() for x in topic_hints_str.split(",") if x.strip()],
                    "score_threshold": score_threshold,
                    "enabled": bool(is_enabled),
                    "parameters": [
                        {
                            "key": str(row.get("key", "")).strip(),
                            "description": str(row.get("description", "")).strip(),
                            "required": bool(row.get("required", True)),
                        }
                        for row in _to_rows(edited_params) if str(row.get("key", "")).strip()
                    ],
                }
                try:
                    result = _api_post(api_base, "/rules", payload)
                    st.success(f"规则保存成功！ID: {result.get('rule_id')}")
                    _api_get.clear() # 刷新缓存
                except httpx.HTTPError as exc:
                    st.error(f"保存失败: {exc}")

    with main_tab:
        try:
            summaries = _api_get(api_base, "/results/rules-summary")
        except httpx.HTTPError as exc:
            st.error(f"请求失败：{exc}")
            st.stop()

    if not summaries:
        st.info("当前暂无规则数据。请先创建规则并触发检测。")
        st.stop()

    totals = {
        "rules": len(summaries),
        "triggered": sum(int(item.get("total_triggered", 0)) for item in summaries),
        "results": sum(int(item.get("total_results", 0)) for item in summaries),
    }

    metric_cols = st.columns(3)
    metric_cols[0].metric("规则总数", totals["rules"])
    metric_cols[1].metric("累计触发次数", totals["triggered"])
    metric_cols[2].metric("累计检测结果", totals["results"])

    chart_df = pd.DataFrame(
        [
            {
                "规则": item.get("rule_name", item.get("rule_id", "未知规则")),
                "触发次数": int(item.get("total_triggered", 0)),
                "检测结果": int(item.get("total_results", 0)),
            }
            for item in summaries
        ]
    ).set_index("规则")
    st.bar_chart(chart_df[["触发次数", "检测结果"]], use_container_width=True)

    st.subheader("各规则统计")
    for item in summaries:
        last_triggered_at = item.get("last_triggered_at") or "-"
        st.markdown(
            (
                "<div class='cg-card'>"
                f"<div class='cg-card-title'>{item.get('rule_name', item.get('rule_id'))}</div>"
                f"<div class='cg-muted'>rule_id: {item.get('rule_id')}</div>"
                f"<div>触发次数：<b>{item.get('total_triggered', 0)}</b> ｜ 检测结果：<b>{item.get('total_results', 0)}</b></div>"
                f"<div class='cg-muted'>最近触发：{last_triggered_at}</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    rule_options = {
        f"{item.get('rule_name', item.get('rule_id'))} ({item.get('total_triggered', 0)}次触发)": item.get("rule_id")
        for item in summaries
    }
    selected_rule_label = st.selectbox("选择规则查看触发记录", list(rule_options.keys()))
    selected_rule_id = rule_options[selected_rule_label]

    try:
        records = _api_get(
            api_base,
            f"/results/rules/{selected_rule_id}/triggers",
            params={"include_suppressed": include_suppressed},
        )
    except httpx.HTTPError as exc:
        st.error(f"获取触发记录失败：{exc}")
        st.stop()

    st.subheader("触发记录列表")
    if not records:
        st.warning("该规则暂无触发记录。")
        st.stop()

    for record in records:
        record_id = record.get("result_id", "unknown-result")
        state_key = f"edited-record:{record_id}"
        if state_key not in st.session_state:
            st.session_state[state_key] = copy.deepcopy(record)
        edited_record = st.session_state[state_key]

        decision = edited_record.get("decision", {})
        confidence = float(decision.get("confidence", 0.0) or 0.0)
        confidence = min(1.0, max(0.0, confidence))

        generated_at = edited_record.get("generated_at", "")
        status_text = "已触发" if decision.get("triggered") else "未触发"
        if edited_record.get("trigger_suppressed"):
            status_text = f"{status_text}（已抑制）"

        with st.expander(f"{generated_at} · {record_id} · {status_text}", expanded=False):
            tabs = st.tabs(["概览图形", "属性编辑", "聊天记录"])

            with tabs[0]:
                top_cols = st.columns(4)
                top_cols[0].metric("置信度", f"{confidence * 100:.1f}%")
                top_cols[1].metric("上下文消息数", len(edited_record.get("context_messages", [])))
                top_cols[2].metric("提取参数数", len(decision.get("extracted_params", {})))
                top_cols[3].metric("抑制状态", "是" if edited_record.get("trigger_suppressed") else "否")
                st.progress(int(confidence * 100), text="置信度")

                feature_df = pd.DataFrame(
                    [
                        {"属性": "置信度", "数值": round(confidence * 100, 2)},
                        {"属性": "上下文消息数", "数值": len(edited_record.get("context_messages", []))},
                        {"属性": "提取参数数", "数值": len(decision.get("extracted_params", {}))},
                    ]
                ).set_index("属性")
                st.bar_chart(feature_df, use_container_width=True)

                st.text_area("触发原因", value=str(decision.get("reason", "")), disabled=True, key=f"reason-view-{record_id}")

            with tabs[1]:
                with st.form(key=f"edit-form-{record_id}"):
                    col_a, col_b = st.columns(2)
                    edited_record["chat_id"] = col_a.text_input("chat_id", value=str(edited_record.get("chat_id", "")))
                    edited_record["message_id"] = col_b.text_input("message_id", value=str(edited_record.get("message_id", "")))

                    col_c, col_d = st.columns(2)
                    decision["triggered"] = col_c.checkbox("triggered", value=bool(decision.get("triggered", False)))
                    edited_record["trigger_suppressed"] = col_d.checkbox(
                        "trigger_suppressed",
                        value=bool(edited_record.get("trigger_suppressed", False)),
                    )

                    decision["confidence"] = st.slider(
                        "confidence",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(decision.get("confidence", 0.0) or 0.0),
                        step=0.01,
                    )
                    decision["reason"] = st.text_area("reason", value=str(decision.get("reason", "")))
                    edited_record["generated_at"] = st.text_input("generated_at", value=str(edited_record.get("generated_at", "")))
                    edited_record["suppression_reason"] = st.text_input(
                        "suppression_reason",
                        value=str(edited_record.get("suppression_reason") or ""),
                    )

                    params_rows = [
                        {"key": key, "value": value}
                        for key, value in dict(decision.get("extracted_params", {})).items()
                    ]
                    edited_params_rows = st.data_editor(
                        params_rows,
                        num_rows="dynamic",
                        use_container_width=True,
                        key=f"params-editor-{record_id}",
                        column_config={
                            "key": st.column_config.TextColumn("参数名"),
                            "value": st.column_config.TextColumn("参数值"),
                        },
                    )

                    message_rows = _message_rows(edited_record.get("context_messages", []))
                    edited_message_rows = st.data_editor(
                        message_rows,
                        num_rows="dynamic",
                        use_container_width=True,
                        key=f"message-editor-{record_id}",
                        column_config={
                            "index": st.column_config.TextColumn("序号", disabled=True),
                            "sender_name": st.column_config.TextColumn("发送者名称"),
                            "sender_id": st.column_config.TextColumn("发送者ID"),
                            "timestamp": st.column_config.TextColumn("时间"),
                            "text": st.column_config.TextColumn("消息文本"),
                        },
                    )

                    submitted = st.form_submit_button("保存当前编辑", use_container_width=True)
                    if submitted:
                        normalized_params: dict[str, str] = {}
                        for row in _to_rows(edited_params_rows):
                            key = str(row.get("key", "")).strip()
                            if not key:
                                continue
                            normalized_params[key] = str(row.get("value", ""))
                        decision["extracted_params"] = normalized_params

                        rebuilt_messages: list[dict[str, Any]] = []
                        for row in _to_rows(edited_message_rows):
                            sender_name = str(row.get("sender_name", "")).strip() or "匿名用户"
                            sender_id = str(row.get("sender_id", "")).strip()
                            timestamp = str(row.get("timestamp", "")).strip()
                            text = str(row.get("text", "")).strip()
                            rebuilt_messages.append(
                                {
                                    "message_id": f"{record_id}-edited-{len(rebuilt_messages)}",
                                    "chat_id": edited_record.get("chat_id", ""),
                                    "sender_id": sender_id,
                                    "sender_name": sender_name,
                                    "contents": [{"type": "text", "text": text}] if text else [],
                                    "reply_from": None,
                                    "timestamp": timestamp,
                                }
                            )
                        edited_record["context_messages"] = rebuilt_messages

                        st.session_state[state_key] = edited_record
                        st.success("已保存当前记录的本地编辑视图（仅前端会话内生效）。")

            with tabs[2]:
                st.caption("聊天框展示发送者姓名与消息内容")
                _render_chat(edited_record.get("context_messages", []))



def run() -> None:
    """以 Poetry 脚本方式启动 Streamlit。"""
    from streamlit.web.cli import main as stcli

    script_path = Path(__file__).resolve()
    sys.argv = ["streamlit", "run", str(script_path)]
    raise SystemExit(stcli())


if __name__ == "__main__":
    _render_dashboard()
