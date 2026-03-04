import streamlit as st
import requests
import os
import json
import copy
from dotenv import set_key

# Ensure local imports work if running from root
import sys
sys.path.append(os.getcwd())

from chat_guardian.settings import Settings, settings

st.set_page_config(page_title="ChatGuardian 仪表盘", page_icon="🛡️", layout="wide")

API_BASE = "http://localhost:8000/api"
API_ROOT = "http://localhost:8000"

# ================= Utils =================
def fetch_json(url, default=None):
    try:
        resp = requests.get(url, timeout=2)
        if resp.status_code == 200:
            return resp.json()
    except (requests.RequestException, ValueError):
        pass
    return default if default is not None else {}

def post_json(url, payload):
    try:
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code in (200, 201), resp.json() if resp.status_code in (200, 201) else resp.text
    except requests.RequestException as e:
        return False, str(e)
        
def delete_req(url):
    try:
        resp = requests.post(url, timeout=5)
        return resp.status_code in (200, 201)
    except requests.RequestException:
        return False

# ================= Matcher Editor Helpers =================

MATCHER_TYPE_LABELS = {
    "all": "🌟 全匹配 (Match All)",
    "sender": "👤 发送者 (Sender)",
    "mention": "📢 @提及 (Mention)",
    "chat": "💬 聊天室ID (Chat ID)",
    "chat_type": "📝 聊天类型 (Chat Type)",
    "adapter": "🔌 适配器 (Adapter)",
    "and": "🔵 AND 组 (全部满足)",
    "or": "🟣 OR 组 (任一满足)",
    "not": "🟥 NOT 组 (条件取反)",
}

LEAF_TYPES = ["all", "sender", "mention", "chat", "chat_type", "adapter"]
COMPOUND_TYPES = ["and", "or", "not"]
ALL_TYPES = COMPOUND_TYPES + LEAF_TYPES


def _default_matcher(type_: str) -> dict:
    """Return a fresh default matcher dict for the given type."""
    defaults = {
        "all": {"type": "all"},
        "sender": {"type": "sender", "user_id": None, "display_name": None},
        "mention": {"type": "mention", "user_id": None, "display_name": None},
        "chat": {"type": "chat", "chat_id": ""},
        "chat_type": {"type": "chat_type", "chat_type": "group"},
        "adapter": {"type": "adapter", "adapter_name": ""},
        "and": {"type": "and", "matchers": []},
        "or": {"type": "or", "matchers": []},
        "not": {"type": "not", "matcher": {"type": "all"}},
    }
    return copy.deepcopy(defaults.get(type_, {"type": "all"}))


def _get_node(root: dict, path: list):
    """Traverse the matcher tree using a path of alternating keys/indices."""
    node = root
    for key in path:
        node = node[key]
    return node


def _render_matcher_node(root: dict, path: list, sk: str, depth: int = 0) -> None:
    """
    Recursively render a single matcher node.
    All mutations operate on `root` (stored in session state) in-place, then call st.rerun().
    """
    node = _get_node(root, path)
    mat_type = node.get("type", "all")
    is_root = len(path) == 0
    # Build a unique string key for widget de-duplication
    path_key = "_".join(str(p) for p in path) if path else "root"

    if mat_type in COMPOUND_TYPES:
        is_and = mat_type == "and"
        is_or = mat_type == "or"
        is_not = mat_type == "not"

        border_color = "#1565C0" if is_and else ("#6A1B9A" if is_or else "#B71C1C")
        bg_color = "#EBF5FB" if is_and else ("#F5EEF8" if is_or else "#FDEDEC")
        label = (
            "🔵 AND — 所有条件都要满足"
            if is_and
            else ("🟣 OR — 任一条件满足即可" if is_or else "🟥 NOT — 子条件结果取反")
        )

        # Visual container using a styled div
        st.markdown(
            f"<div style='border-left: 4px solid {border_color}; "
            f"background:{bg_color}; border-radius:4px; "
            f"padding:6px 10px; margin:4px 0 2px {depth * 18}px;'>"
            f"<strong>{label}</strong></div>",
            unsafe_allow_html=True,
        )

        # Controls row: switch AND↔OR | delete (non-root)
        ctrl_cols = st.columns([3, 2, 2, 6] if (not is_root and not is_not) else ([3, 2, 9] if (is_root and not is_not) else ([3, 3, 6] if not is_root else [3, 9])))
        with ctrl_cols[0]:
            switch_target = "or" if is_and else ("and" if is_or else "or")
            if st.button(
                f"切换为 {switch_target.upper()}",
                key=f"{sk}_switch_{path_key}",
            ):
                node["type"] = switch_target
                if node["type"] != "not" and "matchers" not in node:
                    existing = node.get("matcher")
                    node.pop("matcher", None)
                    node["matchers"] = [existing] if isinstance(existing, dict) else []
                if node["type"] == "not":
                    first = node.get("matchers", [{}])
                    node.pop("matchers", None)
                    node["matcher"] = first[0] if first and isinstance(first[0], dict) else {"type": "all"}
                st.rerun()
        if not is_not:
            with ctrl_cols[1]:
                if st.button("➕ 子AND", key=f"{sk}_add_and_{path_key}"):
                    node.setdefault("matchers", []).append(_default_matcher("and"))
                    st.rerun()
            with ctrl_cols[2]:
                if st.button("➕ 子OR", key=f"{sk}_add_or_{path_key}"):
                    node.setdefault("matchers", []).append(_default_matcher("or"))
                    st.rerun()
            if not is_root:
                with ctrl_cols[3]:
                    if st.button("🗑️ 删除此组", key=f"{sk}_del_{path_key}"):
                        parent = _get_node(root, path[:-2])
                        if path[-2] == "matchers":
                            parent["matchers"].pop(path[-1])
                        else:
                            parent[path[-2]] = {"type": "all"}
                        st.rerun()

            children = node.get("matchers", [])
            if not children:
                st.caption(
                    f"{'　' * (depth + 1)}（此组内暂无条件，请通过下方按钮添加子条件）"
                )
            for i in range(len(children)):
                _render_matcher_node(root, path + ["matchers", i], sk, depth + 1)

            add_cols = st.columns(len(LEAF_TYPES) + 1)
            if add_cols[0].button("➕ 子NOT", key=f"{sk}_add_not_{path_key}"):
                node.setdefault("matchers", []).append(_default_matcher("not"))
                st.rerun()
            for j, lt in enumerate(LEAF_TYPES, start=1):
                if add_cols[j].button(
                    f"➕ {MATCHER_TYPE_LABELS[lt]}",
                    key=f"{sk}_addleaf_{lt}_{path_key}",
                ):
                    node.setdefault("matchers", []).append(_default_matcher(lt))
                    st.rerun()
        else:
            with ctrl_cols[1]:
                if st.button("切换为 AND", key=f"{sk}_not_to_and_{path_key}"):
                    current_child = node.get("matcher")
                    node["type"] = "and"
                    node["matchers"] = [current_child] if isinstance(current_child, dict) else []
                    node.pop("matcher", None)
                    st.rerun()
            if not is_root:
                with ctrl_cols[2]:
                    if st.button("🗑️ 删除此组", key=f"{sk}_del_not_{path_key}"):
                        parent = _get_node(root, path[:-2])
                        if path[-2] == "matchers":
                            parent["matchers"].pop(path[-1])
                        else:
                            parent[path[-2]] = {"type": "all"}
                        st.rerun()

            child = node.get("matcher")
            if not isinstance(child, dict):
                node["matcher"] = {"type": "all"}

            _render_matcher_node(root, path + ["matcher"], sk, depth + 1)

    else:
        # Leaf matcher
        indent_px = depth * 18
        st.markdown(
            f"<div style='margin-left:{indent_px}px; border-left: 3px solid #AAB7B8; "
            f"padding:4px 8px; margin-bottom:4px; background:#FDFEFE; border-radius:3px;'>"
            f"<em>{MATCHER_TYPE_LABELS.get(mat_type, mat_type)}</em></div>",
            unsafe_allow_html=True,
        )

        # Type selector + delete in one row
        type_col, del_col = st.columns([5, 1])
        with type_col:
            all_leaf_options = LEAF_TYPES
            cur_idx = all_leaf_options.index(mat_type) if mat_type in all_leaf_options else 0
            new_type = st.selectbox(
                "条件类型",
                options=all_leaf_options,
                index=cur_idx,
                format_func=lambda t: MATCHER_TYPE_LABELS[t],
                key=f"{sk}_typeSel_{path_key}",
            )
            if new_type != mat_type:
                new_node = _default_matcher(new_type)
                if is_root:
                    root.clear()
                    root.update(new_node)
                else:
                    parent = _get_node(root, path[:-2])
                    if path[-2] == "matchers":
                        parent["matchers"][path[-1]] = new_node
                    else:
                        parent[path[-2]] = new_node
                st.rerun()

        with del_col:
            st.write("")  # spacer for alignment
            if not is_root and st.button("🗑️", key=f"{sk}_del_{path_key}"):
                parent = _get_node(root, path[:-2])
                if path[-2] == "matchers":
                    parent["matchers"].pop(path[-1])
                else:
                    parent[path[-2]] = {"type": "all"}
                st.rerun()

        # Editable fields for this leaf type
        st.markdown(
            f"<div style='margin-left:{indent_px + 12}px'>",
            unsafe_allow_html=True,
        )
        if mat_type == "all":
            st.info("匹配所有消息（无过滤条件）", icon="ℹ️")

        elif mat_type in ("sender", "mention"):
            label_prefix = "发送者" if mat_type == "sender" else "被提及用户"
            uid = st.text_input(
                f"{label_prefix} 用户ID（可选）",
                value=node.get("user_id") or "",
                key=f"{sk}_uid_{path_key}",
            )
            dname = st.text_input(
                f"{label_prefix} 显示名称（可选）",
                value=node.get("display_name") or "",
                key=f"{sk}_dname_{path_key}",
            )
            node["user_id"] = uid.strip() or None
            node["display_name"] = dname.strip() or None

        elif mat_type == "chat":
            cid = st.text_input(
                "聊天室 ID",
                value=node.get("chat_id") or "",
                key=f"{sk}_cid_{path_key}",
            )
            node["chat_id"] = cid.strip()

        elif mat_type == "chat_type":
            options = ["group", "private"]
            cur = node.get("chat_type", "group")
            ct = st.selectbox(
                "聊天类型",
                options,
                index=options.index(cur) if cur in options else 0,
                format_func=lambda v: "群聊 (group)" if v == "group" else "私聊 (private)",
                key=f"{sk}_ct_{path_key}",
            )
            node["chat_type"] = ct

        elif mat_type == "adapter":
            aname = st.text_input(
                "适配器名称",
                value=node.get("adapter_name") or "",
                key=f"{sk}_aname_{path_key}",
            )
            node["adapter_name"] = aname.strip()

        st.markdown("</div>", unsafe_allow_html=True)


def _matcher_to_root_type_options(root: dict) -> str:
    """Return the current root type label."""
    if not isinstance(root, dict):
        return "未知"
    return MATCHER_TYPE_LABELS.get(root.get("type", "all"), "未知")


def render_matcher_editor(session_key: str, initial_matcher: dict) -> dict:
    """
    Render the visual matcher editor widget block.

    Args:
        session_key: Unique Streamlit session state key for this editor instance.
        initial_matcher: The existing matcher dict (used to initialize session state).

    Returns:
        The current matcher dict from session state (may differ from initial_matcher
        if the user has made edits).
    """
    if session_key not in st.session_state:
        st.session_state[session_key] = copy.deepcopy(initial_matcher)

    root = st.session_state[session_key]

    st.markdown("#### 🎯 Matcher 条件编辑器")
    st.caption(
        "在此处可视化地构建规则的触发条件。 "
        "🔵 AND 组要求所有子条件都满足，🟣 OR 组只需任一子条件满足，🟥 NOT 组会对子条件取反。 "
        "支持混合嵌套 AND/OR/NOT 组实现复杂逻辑。"
    )

    # Allow changing the root type
    root_type = root.get("type", "all")
    new_root_type = st.selectbox(
        "根条件类型",
        options=ALL_TYPES,
        index=ALL_TYPES.index(root_type) if root_type in ALL_TYPES else 0,
        format_func=lambda t: MATCHER_TYPE_LABELS[t],
        key=f"{session_key}_rootType",
    )
    if new_root_type != root_type:
        new_root = _default_matcher(new_root_type)
        root.clear()
        root.update(new_root)
        st.rerun()

    st.markdown("---")

    # Render the tree
    _render_matcher_node(root, [], session_key, depth=0)

    st.markdown("---")

    # JSON preview (collapsible)
    with st.expander("🔍 当前 Matcher JSON（高级预览/编辑）", expanded=False):
        json_str = st.text_area(
            "Matcher JSON",
            value=json.dumps(root, ensure_ascii=False, indent=2),
            height=200,
            key=f"{session_key}_jsonEdit",
        )
        if st.button("从 JSON 应用", key=f"{session_key}_applyJson"):
            try:
                parsed = json.loads(json_str)
                root.clear()
                root.update(parsed)
                st.success("已从 JSON 更新 Matcher！")
                st.rerun()
            except (json.JSONDecodeError, ValueError) as exc:
                st.error(f"JSON 解析失败: {exc}")

    return root


# ================= Components =================

def page_dashboard():
    st.title("📊 仪表盘与运行状态")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔌 Adapter 状态")
        adapters = fetch_json(f"{API_BASE}/adapters/status", default=[])
        if not adapters:
            st.info("暂无Adapter或后端未启动")
        for adp in adapters:
            status_color = "🟢" if adp.get("running") else "🔴"
            st.markdown(f"**{status_color} {adp.get('name', 'Unknown')}**")
            
        st.markdown("---")
        st.subheader("🚀 启停控制")
        if st.button("启动所有 Adapter"):
            success, res = post_json(f"{API_ROOT}/adapters/start", {})
            if success:
                st.success("请求已发送")
            else:
                st.error(f"失败: {res}")
            st.rerun()
        if st.button("停止所有 Adapter"):
            success, res = post_json(f"{API_ROOT}/adapters/stop", {})
            if success:
                st.success("请求已发送")
            else:
                st.error(f"失败: {res}")
            st.rerun()

    with col2:
        st.subheader("🏥 系统健康状态")
        if st.button("刷新健康状态"):
            st.rerun()
            
        health = fetch_json(f"{API_ROOT}/health")
        llm_health = fetch_json(f"{API_ROOT}/llm/health?do_ping=false")
        
        if health:
            st.success(f"✅ 核心 API 服务正常 (最后检查: {health.get('time', '未知')})")
        else:
            st.error("❌ 后端核心 API 服务未连接，请检查是否已启动 Uvicorn。")
            
        if llm_health:
            st.markdown("#### LLM 引擎健康指标")
            llm_info = llm_health.get("llm", {})
            
            # 使用 metric 组件展示基础信息
            hc1, hc2 = st.columns(2)
            backend_type = llm_info.get("backend", "未知")
            model_name = llm_info.get("model", "未知")
            key_status = "✔️ 已配置" if llm_info.get("api_key_configured") else "⚠️ 未配置/不需要"
            
            hc1.metric("LLM 后端", backend_type)
            hc2.metric("加载模型", model_name)
            
            st.info(f"API 密钥状态: {key_status}  | 客户端: {llm_info.get('client_class', '未知')}")
            
            # 批处理调度器统计 (如果后端返回了该数据)
            scheduler = llm_health.get("scheduler", {})
            if scheduler:
                with st.expander("⚙️ 引擎调度器运行诊断", expanded=False):
                    metrics = scheduler.get("metrics", {})
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.metric("总请求数", metrics.get("total_requests", 0))
                    sc2.metric("总批次数", metrics.get("total_batches", 0))
                    sc3.metric("总调用数", metrics.get("total_llm_calls", 0))
                    
                    sc4, sc5, sc6 = st.columns(3)
                    sc4.metric("成功批次", metrics.get("successful_batches", 0))
                    sc5.metric("回退批次", metrics.get("fallback_batches", 0))
                    sc6.metric("重试次数", metrics.get("retry_attempts", 0))
                    
                    st.caption(f"当前并发上限: {scheduler.get('max_parallel_batches', '未知')} | 缓存命中数: {metrics.get('idempotency_completed_hits', 0)}")

def page_queues():
    st.title("🗂️ 消息队列管理")
    queues = fetch_json(f"{API_BASE}/queues", default={"pending": [], "history": []})
    
    tab1, tab2 = st.tabs(["待处理队列 (Pending)", "历史消息 (History)"])
    
    def render_queue(queue_list):
        if not queue_list:
            st.info("队列为空")
            return
            
        # 按照 adapter-chat_type-chat_id 分类
        grouped = {}
        for item in queue_list:
            key = f"{item.get('adapter')}-{item.get('chat_type')}-{item.get('chat_id')}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(item)
            
        for key, msgs in grouped.items():
            with st.expander(f"📁 会话: {key} ({len(msgs)} 条消息)", expanded=False):
                for msg in msgs:
                    st.markdown(f"""
                    <div style='background-color: #f1f3f5; padding: 10px; border-radius: 10px; margin-bottom: 5px; color: #333'>
                        <strong style='color: #0066cc;'>{msg.get('sender_name', 'User')}</strong>
                        <span style='color: #888; font-size: 0.8em;'> {msg.get('timestamp', '')}</span>
                        <br/>
                        <span>{msg.get('content', '')}</span>
                    </div>
                    """, unsafe_allow_html=True)
            
    with tab1:
        st.write("等待检测引擎处理的新消息")
        render_queue(queues.get("pending", []))
        
    with tab2:
        st.write("已处理并被缓存的滚动历史消息")
        render_queue(queues.get("history", []))

def page_rule_management():
    st.title("📜 规则管理与编辑")
    st.markdown("在此页面可以可视化添加、编辑和删除规则，包括对每条规则的 Matcher 进行可视化的增删改查。")
    
    rules = fetch_json(f"{API_ROOT}/rules/list", default=[])
    
    # ---- Add new rule ----
    with st.expander("➕ 添加新规则", expanded=False):
        r_id = st.text_input("规则标识 (rule_id)", key="new_rule_id")
        r_name = st.text_input("规则名称 (name)", key="new_rule_name")
        r_desc = st.text_area("规则描述 (description)", key="new_rule_desc")

        st.markdown("⚙️ **高级设置**")
        c1, c2 = st.columns(2)
        t_hints = c1.text_area("主题提示 (topic_hints, 逗号分隔)", key="new_rule_hints")
        s_threshold = c2.slider("触发阈值", 0.0, 1.0, 0.6, 0.05, key="new_rule_thresh")
        is_enabled = st.checkbox("立即启用", value=True, key="new_rule_enabled")

        # Matcher editor for the new rule
        new_matcher = render_matcher_editor(
            session_key="matcher_new",
            initial_matcher={"type": "all"},
        )

        if st.button("提交保存", key="new_rule_submit"):
            hints_list = [h.strip() for h in t_hints.split(",") if h.strip()]
            payload = {
                "rule_id": r_id,
                "name": r_name,
                "description": r_desc,
                "matcher": new_matcher,
                "topic_hints": hints_list,
                "score_threshold": s_threshold,
                "enabled": is_enabled,
                "parameters": [],
            }
            ok, res = post_json(f"{API_ROOT}/rules", payload)
            if ok:
                st.success("添加成功！")
                # Clear the matcher session state for the new rule form
                if "matcher_new" in st.session_state:
                    del st.session_state["matcher_new"]
                st.rerun()
            else:
                st.error(f"添加失败: {res}")
    
    st.markdown("---")
    st.subheader("📚 现有规则列表")
    
    for r in rules:
        rule_id = r.get("rule_id", "")
        with st.expander(
            f"📌 {r.get('name', '未命名')} (ID: {rule_id}) - {'🟢' if r.get('enabled') else '🔴'}",
            expanded=False,
        ):
            er_name = st.text_input("名称", value=r.get("name", ""), key=f"edit_name_{rule_id}")
            er_desc = st.text_area("描述", value=r.get("description", ""), key=f"edit_desc_{rule_id}")

            ethre = st.slider(
                "阈值", 0.0, 1.0, float(r.get("score_threshold", 0.6)), 0.05,
                key=f"edit_thresh_{rule_id}",
            )
            eenab = st.checkbox(
                "启用状态", value=bool(r.get("enabled", True)), key=f"edit_enab_{rule_id}"
            )
            et_hints = st.text_area(
                "主题提示 (逗号分隔)",
                value=",".join(r.get("topic_hints", [])),
                key=f"edit_hints_{rule_id}",
            )

            # Matcher editor for this rule
            # Normalize the raw matcher dict coming from the API
            raw_matcher = r.get("matcher") or {}
            if not isinstance(raw_matcher, dict) or "type" not in raw_matcher:
                raw_matcher = {"type": "all"}
            current_matcher = render_matcher_editor(
                session_key=f"matcher_{rule_id}",
                initial_matcher=raw_matcher,
            )

            col_save, col_del, _ = st.columns([1, 1, 4])
            if col_save.button("💾 保存修改", key=f"save_{rule_id}"):
                hints_list = [h.strip() for h in et_hints.split(",") if h.strip()]
                payload = {
                    "rule_id": rule_id,
                    "name": er_name,
                    "description": er_desc,
                    "matcher": current_matcher,
                    "topic_hints": hints_list,
                    "score_threshold": ethre,
                    "enabled": eenab,
                    "parameters": r.get("parameters", []),
                }
                ok, res = post_json(f"{API_ROOT}/rules", payload)
                if ok:
                    st.success("已保存")
                else:
                    st.error(f"保存失败: {res}")

            if col_del.button("🗑️ 删除该规则", key=f"del_{rule_id}"):
                if delete_req(f"{API_ROOT}/rules/delete/{rule_id}"):
                    # Remove cached matcher state for this rule
                    sk = f"matcher_{rule_id}"
                    if sk in st.session_state:
                        del st.session_state[sk]
                    st.success("已删除")
                    st.rerun()

def page_rule_stats():
    st.title("📈 规则触发统计与记录")
    
    if st.button("刷新数据"):
        st.rerun()
        
    stats_response = fetch_json(f"{API_BASE}/rule_stats", default={})
    
    # Check if backend provides actual data
    if stats_response.get("stats") == "ok":
        stats = stats_response.get("data", {})
    else:
        st.warning("从后端获取数据失败，展示模拟数据！")
        stats = {
            "spam_detection": {
                "count": 12,
                "description": "检测垃圾广告信息",
                "records": [
                    {
                        "id": "res_123",
                        "trigger_time": "2026-03-01 12:00:00",
                        "confidence": 0.95,
                        "result": "Triggered",
                        "rule_name": "垃圾广告",
                        "messages": [
                            {"sender": "UserA", "content": "你好"},
                            {"sender": "Spammer", "content": "加微买片！便宜！"}
                        ],
                        "reason": "包含违禁词：买片，便宜"
                    }
                ]
            }
        }
    
    if not stats:
        st.info("暂无任何规则触发记录。请等待检测引擎捕获违规消息，或者检查您的规则是否开启。")
        return
        
    for rule_name, stat in stats.items():
        with st.expander(f"📏 规则：{rule_name} | 🎯 触发次数：{stat.get('count', 0)}次", expanded=False):
            st.write(f"**规则描述**：{stat.get('description', '无')}")
            
            records = stat.get("records", [])
            for idx, record in enumerate(records):
                with st.expander(f"🔍 记录 #{idx+1} ({record.get('trigger_time', '未知时间')})", expanded=False):
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.metric("置信度 (Confidence)", record.get('confidence', 0.0))
                    rc2.metric("操作结果", record.get('result', 'None'))
                    rc3.metric("触发原因", record.get('reason', 'None'))
                    
                    st.markdown("#### 💬 聊天上下文", unsafe_allow_html=True)
                    msgs = record.get("messages", [])
                    if not msgs:
                        st.info("无上下文消息数据。")
                    for msg in msgs:
                        is_self = False # Can check logic
                        bg_color = "#e2f0cb" if is_self else "#f1f3f5"
                        align = "right" if is_self else "left"
                        st.markdown(f"""
                        <div style='background-color: {bg_color}; padding: 10px; border-radius: 10px; margin-bottom: 5px; text-align: {align}; color: #333;'>
                            <strong style='color: {'#2b8a3e' if is_self else '#0066cc'};'>{msg.get('sender', 'Unknown')}</strong>
                            <br/>
                            <span>{msg.get('content', '')}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Editable attributes for debugging or marking manually
                    with st.form(f"edit_rec_{rule_name}_{idx}"):
                        st.write("##### 编辑结果记录标签")
                        st.text_input("备注/修正标签", value=record.get('note', ''), key=f"note_{idx}")
                        if st.form_submit_button("保存备注"):
                            st.success("编辑保存成功 (Mock)")

def page_settings():
    st.title("⚙️ 系统配置管理 (Settings)")
    st.markdown("通过图形化界面修改 `.env` 环境变量中的配置。")
    
    # Group fields roughly by prefix
    fields = Settings.model_fields
    groups = {"LLM 设置": ["llm_"], "检测行为": ["detection_", "context_", "history_", "pending_"], "适配器": ["onebot_", "telegram_", "wechat_", "feishu_", "enabled_adapters"], "基础配置": []}
    
    # Categorize keys
    categorized = {k: [] for k in groups.keys()}
    for key, field in fields.items():
        matched = False
        for g_name, prefixes in groups.items():
            if any(key.startswith(p) for p in prefixes):
                categorized[g_name].append((key, field))
                matched = True
                break
        if not matched:
            categorized["基础配置"].append((key, field))
    
    envs_path = os.path.join(os.getcwd(), ".env")
    
    with st.form("settings_form"):
        tabs = st.tabs(list(categorized.keys()))
        new_values = {}
        
        for tab, (g_name, g_fields) in zip(tabs, categorized.items()):
            with tab:
                for key, field in g_fields:
                    current_val = getattr(settings, key)
                    annotation = str(field.annotation).lower()
                    
                    # Create appropriate widget
                    if "bool" in annotation:
                        new_values[key] = st.checkbox(key, value=bool(current_val))
                    elif "int" in annotation:
                        new_values[key] = st.number_input(key, value=int(current_val) if current_val is not None else 0, step=1)
                    elif "float" in annotation:
                        new_values[key] = st.number_input(key, value=float(current_val) if current_val is not None else 0.0, step=0.1)
                    elif "list" in annotation:
                        # comma separated
                        c_str = ",".join(current_val) if isinstance(current_val, list) else ""
                        r_str = st.text_input(key + " (逗号分隔列表)", value=c_str)
                        new_values[key] = [x.strip() for x in r_str.split(",") if x.strip()]
                    else:
                        new_values[key] = st.text_input(key, value=str(current_val) if current_val is not None else "")
                        
        if st.form_submit_button("保存配置到 .env 文件"):
            # Update .env using set_key
            for k, val in new_values.items():
                if isinstance(val, list):
                    val_str = json.dumps(val)
                else:
                    val_str = str(val)
                # Setting config format usually depends on how bash parses. 
                # For basic fields, strings are fine. 
                # Pydantic parses lists properly from JSON strings usually.
                set_key(envs_path, f"CHAT_GUARDIAN_{k.upper()}", val_str)
                
            st.success("配置已保存，请手动重启后端服务以生效！")

# ================= Main =================

pages = {
    "📊 仪表盘": page_dashboard,
    "📜 规则管理": page_rule_management,
    "📈 触发统计": page_rule_stats,
    "🗂️ 消息队列": page_queues,
    "⚙️ 系统配置": page_settings,
}

selection = st.sidebar.radio("导航", list(pages.keys()))

pages[selection]()
