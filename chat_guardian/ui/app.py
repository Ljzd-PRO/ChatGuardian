import streamlit as st
import requests
import os
import json
from datetime import datetime
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
    except Exception as e:
        pass
    return default if default is not None else {}

def post_json(url, payload):
    try:
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code in (200, 201), resp.json() if resp.status_code in (200, 201) else resp.text
    except Exception as e:
        return False, str(e)
        
def delete_req(url):
    try:
        resp = requests.post(url, timeout=5)
        return resp.status_code in (200, 201)
    except Exception as e:
        return False

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
            st.success("请求已发送") if success else st.error(f"失败: {res}")
            st.rerun()
        if st.button("停止所有 Adapter"):
            success, res = post_json(f"{API_ROOT}/adapters/stop", {})
            st.success("请求已发送") if success else st.error(f"失败: {res}")
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
    st.markdown("在此页面可以可视化添加、编辑和删除规则。")
    
    rules = fetch_json(f"{API_ROOT}/rules/list", default=[])
    
    # 添加规则表单
    with st.expander("➕ 添加新规则", expanded=False):
        with st.form("add_rule_form"):
            r_id = st.text_input("规则标识 (rule_id)")
            r_name = st.text_input("规则名称 (name)")
            r_desc = st.text_area("规则描述 (description)")
            
            st.markdown("🎯 **作用域 (Target Session)**")
            col1, col2 = st.columns(2)
            s_mode = col1.selectbox("模式", ["fuzzy", "exact"])
            s_query = col2.text_input("查询词 (query)")
            
            st.markdown("⚙️ **高级设置**")
            c1, c2 = st.columns(2)
            t_hints = c1.text_area("主题提示 (topic_hints, 逗号分隔)")
            s_threshold = c2.slider("触发阈值", 0.0, 1.0, 0.6, 0.05)
            is_enabled = st.checkbox("立即启用", value=True)
            
            if st.form_submit_button("提交保存"):
                hints_list = [h.strip() for h in t_hints.split(",") if h.strip()]
                payload = {
                    "rule_id": r_id,
                    "name": r_name,
                    "description": r_desc,
                    "target_session": {"mode": s_mode, "query": s_query},
                    "topic_hints": hints_list,
                    "score_threshold": s_threshold,
                    "enabled": is_enabled,
                    "parameters": []
                }
                ok, res = post_json(f"{API_ROOT}/rules", payload)
                if ok:
                    st.success("添加成功！")
                    st.rerun()
                else:
                    st.error(f"添加失败: {res}")
    
    st.markdown("---")
    st.subheader("📚 现有规则列表")
    
    for r in rules:
        with st.expander(f"📌 {r.get('name', '未命名')} (ID: {r.get('rule_id')}) - {'🟢' if r.get('enabled') else '🔴'}", expanded=False):
            # 编辑表单
            with st.form(f"edit_{r['rule_id']}"):
                er_name = st.text_input("名称", value=r.get('name', ''))
                er_desc = st.text_area("描述", value=r.get('description', ''))
                
                ec1, ec2 = st.columns(2)
                es_mode = ec1.selectbox("模式", ["fuzzy", "exact"], index=0 if r.get('target_session',{}).get('mode')=='fuzzy' else 1)
                es_query = ec2.text_input("查询词", value=r.get('target_session',{}).get('query',''))
                
                ethre = st.slider("阈值", 0.0, 1.0, float(r.get('score_threshold', 0.6)), 0.05)
                eenab = st.checkbox("启用状态", value=bool(r.get('enabled', True)))
                
                et_hints = st.text_area("主题提示 (逗号分隔)", value=",".join(r.get('topic_hints', [])))
                
                cols_b = st.columns([1, 1, 4])
                if cols_b[0].form_submit_button("保存修改"):
                    hints_list = [h.strip() for h in et_hints.split(",") if h.strip()]
                    payload = {
                        "rule_id": r['rule_id'],
                        "name": er_name,
                        "description": er_desc,
                        "target_session": {"mode": es_mode, "query": es_query},
                        "topic_hints": hints_list,
                        "score_threshold": ethre,
                        "enabled": eenab,
                        "parameters": r.get('parameters', [])
                    }
                    ok, res = post_json(f"{API_ROOT}/rules", payload)
                    if ok: st.success("已保存")
                    else: st.error("保存失败")
                
            if st.button("🗑️ 删除该规则", key=f"del_{r['rule_id']}"):
                if delete_req(f"{API_ROOT}/rules/delete/{r['rule_id']}"):
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
                        c_note = st.text_input("备注/修正标签", value=record.get('note', ''))
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
