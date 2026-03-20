from __future__ import annotations

import asyncio
import ipaddress
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Iterable, Literal

from fastapi import Request
from fastmcp import FastMCP
from fastmcp.client.transports import FastMCPTransport
from fastmcp.server.http import Middleware
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from chat_guardian.adapters import AdapterManager, build_adapters_from_settings
from chat_guardian.domain import DetectionRule, UserMemoryFact
from chat_guardian.llm_client import build_llm_client
from chat_guardian.notifiers.base import get_default_notification_template
from chat_guardian.prompts import (
    ADMIN_AGENT_SYSTEM_PROMPT,
    RULE_DETECTION_SYSTEM_PROMPT,
    USER_PROFILE_SYSTEM_PROMPT,
)
from chat_guardian.settings import Settings, settings


class OperationError(Exception):
    """Business logic error that carries an HTTP-style status code."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def normalize_mcp_transport(transport: str | None) -> Literal["sse", "streamable-http"]:
    """Normalize MCP transport value, defaulting to streamable-http."""
    return "sse" if transport == "sse" else "streamable-http"


def _is_loopback_host(host: str | None) -> bool:
    """Return True if host is loopback or localhost."""
    if not host:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback
    except ValueError:
        return host in {"localhost"}


class ChatGuardianOperations:
    """Shared API/MCP business logic for reuse and testing."""

    def __init__(
            self,
            container: Any,
            env_only_keys: Iterable[str],
            log_buffer: deque[dict[str, Any]] | None = None,
    ):
        self.container = container
        self.log_buffer = log_buffer
        self.env_only_keys = set(env_only_keys)
        self.settings_allowlist = set(Settings.model_fields.keys()) - self.env_only_keys

    @staticmethod
    async def health() -> dict[str, str]:
        return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

    async def llm_health(self, do_ping: bool = True) -> dict[str, object]:
        diagnostics = self.container.llm_client.diagnostics()
        scheduler_diagnostics = self.container.detection_engine.batch_scheduler.diagnostics()
        result: dict[str, object] = {
            "status": "ok",
            "time": datetime.now(timezone.utc).isoformat(),
            "llm": diagnostics,
            "scheduler": scheduler_diagnostics,
        }

        if do_ping:
            ping_ok, ping_error, latency_ms = await self.container.llm_client.ping()
            result["ping"] = {
                "ok": ping_ok,
                "latency_ms": round(latency_ms, 2),
                "error": ping_error,
            }
            if not ping_ok:
                result["status"] = "degraded"

        return result

    async def auth_login(self, username: str, password: str) -> dict[str, object]:
        if not username or not password:
            raise OperationError("Username and password are required.", status_code=400)
        if username == self.container.admin_username and password == self.container.admin_password:
            token = self.container.token_manager.issue(username)
            return {
                "token": token,
                "username": username,
                "using_default_credentials": self.container.using_default_credentials,
            }
        raise OperationError("Invalid credentials", status_code=401)

    async def auth_status(self, current_user: str | None) -> dict[str, object]:
        if not current_user:
            raise OperationError("Unauthorized", status_code=401)
        return {
            "authenticated": True,
            "username": current_user,
            "using_default_credentials": self.container.using_default_credentials,
        }

    async def auth_logout(self, token: str | None) -> dict[str, str]:
        if token:
            self.container.token_manager.revoke(token)
        return {"status": "logged_out"}

    async def start_adapters(self) -> dict[str, Any]:
        await self.container.adapter_manager.start_all()
        return {
            "status": "started",
            "enabled_adapters": [adapter.name for adapter in self.container.adapter_manager.adapters],
        }

    async def stop_adapters(self) -> dict[str, Any]:
        await self.container.adapter_manager.stop_all()
        return {
            "status": "stopped",
            "enabled_adapters": [adapter.name for adapter in self.container.adapter_manager.adapters],
        }

    async def upsert_rule(self, payload: DetectionRule) -> DetectionRule:
        return await self.container.rule_repository.upsert(payload)

    async def list_rules(self) -> list[DetectionRule]:
        return await self.container.rule_repository.list_all()

    async def delete_rule(self, rule_id: str) -> dict[str, Any]:
        deleted = await self.container.rule_repository.delete(rule_id)
        if not deleted:
            raise OperationError(f"Rule not found: {rule_id}", status_code=404)
        return {"status": "deleted", "rule_id": rule_id, "deleted": True}

    async def get_rule_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        for rule_id, results in self.container.detection_result_repository.results_by_rule.items():
            rule = await self.container.rule_repository.get(rule_id)
            if not rule:
                continue

            triggered_results = [r for r in results if r.decision.triggered]
            if not triggered_results:
                continue

            records = []
            for r in triggered_results:
                records.append(
                    {
                        "id": r.result_id,
                        "result_id": r.result_id,
                        "event_id": r.event_id,
                        "rule_id": r.rule_id,
                        "adapter": r.adapter,
                        "chat_type": r.chat_type,
                        "chat_id": r.chat_id,
                        "message_id": r.message_id,
                        "trigger_time": r.generated_at.isoformat(),
                        "confidence": round(r.decision.confidence, 2),
                        "result": "Triggered (Suppressed)" if r.trigger_suppressed else "Triggered",
                        "trigger_suppressed": r.trigger_suppressed,
                        "suppression_reason": r.suppression_reason,
                        "rule_name": rule.name,
                        "messages": [
                            {"sender": m.sender_name or m.sender_id, "content": str(m)}
                            for m in r.context_messages
                        ],
                        "extracted_params": r.decision.extracted_params,
                        "reason": r.decision.reason,
                    }
                )

            stats[rule.name] = {
                "count": len(triggered_results),
                "description": rule.description,
                "records": sorted(records, key=lambda x: x["trigger_time"], reverse=True),
            }

        return {"stats": "ok", "data": stats}

    async def get_queues(self) -> dict[str, Any]:
        store = self.container.chat_history_store

        def _flatten_bucket(tree: dict[str, Any]) -> list[dict[str, str]]:
            rows: list[dict[str, str]] = []
            for adapter, by_type in tree.items():
                for chat_type, by_chat in by_type.items():
                    for chat_id, messages in by_chat.items():
                        for message in messages:
                            rows.append(
                                {
                                    "adapter": adapter,
                                    "platform": adapter,
                                    "chat_type": chat_type,
                                    "chat_id": chat_id,
                                    "message_id": message.message_id,
                                    "sender_name": message.sender_name or message.sender_id,
                                    "content": str(message),
                                    "timestamp": message.timestamp.isoformat(),
                                }
                            )
            return rows

        return {
            "pending": _flatten_bucket(store.pending),
            "history": _flatten_bucket(store.history),
        }

    async def delete_history_messages(self, payload: dict) -> dict[str, Any]:
        store = self.container.chat_history_store
        clear_all = bool(payload.get("clear_all"))
        if clear_all:
            cleared = await store.clear_history()
            return {"cleared": cleared}

        items_raw = payload.get("items") or []
        items: list[tuple[str, str, str, str]] = []
        for item in items_raw:
            platform = (item or {}).get("platform") or (item or {}).get("adapter")
            chat_type = (item or {}).get("chat_type")
            chat_id = (item or {}).get("chat_id")
            message_id = (item or {}).get("message_id")
            if not all([platform, chat_type, chat_id, message_id]):
                continue
            items.append((str(platform), str(chat_type), str(chat_id), str(message_id)))
        deleted = await store.delete_history_messages(items)
        return {"deleted": deleted}

    async def get_adapters_status(self) -> list[dict[str, Any]]:
        return [
            {
                "name": adapter.name,
                "running": True,
            }
            for adapter in self.container.adapter_manager.adapters
        ]

    async def get_dashboard(self) -> dict[str, Any]:
        rules = await self.container.rule_repository.list_all()
        total_rules = len(rules)
        enabled_rules = sum(1 for r in rules if r.enabled)

        today = date.today()
        triggers_today = 0
        for results in self.container.detection_result_repository.results_by_rule.values():
            for r in results:
                if r.decision.triggered and r.generated_at.date() == today:
                    triggers_today += 1

        messages_today = sum(
            1 for r in self.container.detection_result_repository.results if r.generated_at.date() == today
        )
        total_results = sum(len(v) for v in self.container.detection_result_repository.results_by_rule.values())
        triggered_total = sum(
            sum(1 for r in v if r.decision.triggered)
            for v in self.container.detection_result_repository.results_by_rule.values()
        )
        trigger_rate = round(triggered_total / total_results, 4) if total_results else 0.0

        llm_diag = self.container.llm_client.diagnostics()

        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "triggers_today": triggers_today,
            "trigger_rate": trigger_rate,
            "messages_today": messages_today,
            "llm_status": llm_diag,
        }

    async def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.log_buffer:
            return []
        return list(reversed(list(self.log_buffer)[-limit:]))

    async def clear_logs(self) -> dict[str, int]:
        if not self.log_buffer:
            return {"cleared": 0}
        cleared = len(self.log_buffer)
        self.log_buffer.clear()
        return {"cleared": cleared}

    async def list_user_profiles(self) -> list[UserMemoryFact]:
        return list(self.container.memory_repository.profiles.values())

    async def get_user_profile(self, user_id: str) -> UserMemoryFact:
        profile = await self.container.memory_repository.get_profile(user_id)
        if not profile:
            raise OperationError(f"User not found: {user_id}", status_code=404)
        return profile

    async def delete_user_profile(self, user_id: str) -> dict[str, Any]:
        deleted = await self.container.memory_repository.delete_profile(user_id)
        if not deleted:
            raise OperationError(f"User not found: {user_id}", status_code=404)
        return {"status": "deleted", "user_id": user_id}

    async def _get_profile_or_raise(self, user_id: str) -> "UserMemoryFact":
        profile = await self.container.memory_repository.get_profile(user_id)
        if not profile:
            raise OperationError(f"User not found: {user_id}", status_code=404)
        return profile

    async def delete_profile_interest(self, user_id: str, topic: str) -> "UserMemoryFact":
        """删除用户画像中指定的兴趣话题。"""

        def updater(profile: UserMemoryFact) -> UserMemoryFact:
            if topic not in profile.interests:
                raise OperationError(
                    f"Interest '{topic}' not found for user {user_id}",
                    status_code=404,
                )
            del profile.interests[topic]
            return profile

        updated = await self.container.memory_repository.update_profile(user_id, updater)
        if not updated:
            raise OperationError(f"User not found: {user_id}", status_code=404)
        return updated

    async def delete_profile_interest_chat(self, user_id: str, topic: str, chat_id: str) -> "UserMemoryFact":
        """删除用户兴趣话题中的指定相关聊天记录。"""

        def updater(profile: UserMemoryFact) -> UserMemoryFact:
            if topic not in profile.interests:
                raise OperationError(
                    f"Interest '{topic}' not found for user {user_id}",
                    status_code=404,
                )
            stat = profile.interests[topic]
            if chat_id not in stat.related_chat:
                raise OperationError(
                    f"Chat '{chat_id}' not found in interest '{topic}'",
                    status_code=404,
                )
            stat.related_chat = [c for c in stat.related_chat if c != chat_id]
            return profile

        updated = await self.container.memory_repository.update_profile(user_id, updater)
        if not updated:
            raise OperationError(f"User not found: {user_id}", status_code=404)
        return updated

    async def delete_profile_interest_keyword(self, user_id: str, topic: str, keyword: str) -> "UserMemoryFact":
        """删除用户兴趣话题中的指定关键词。"""

        def updater(profile: UserMemoryFact) -> UserMemoryFact:
            if topic not in profile.interests:
                raise OperationError(
                    f"Interest '{topic}' not found for user {user_id}",
                    status_code=404,
                )
            stat = profile.interests[topic]
            if keyword not in stat.keywords:
                raise OperationError(
                    f"Keyword '{keyword}' not found in interest '{topic}'",
                    status_code=404,
                )
            stat.keywords = [k for k in stat.keywords if k != keyword]
            return profile

        updated = await self.container.memory_repository.update_profile(user_id, updater)
        if not updated:
            raise OperationError(f"User not found: {user_id}", status_code=404)
        return updated

    async def delete_profile_active_group(self, user_id: str, group_id: str) -> "UserMemoryFact":
        """删除用户画像中指定的活跃群组。"""
        profile = await self._get_profile_or_raise(user_id)
        original_len = len(profile.active_groups)
        profile.active_groups = [g for g in profile.active_groups if g.group_id != group_id]
        if len(profile.active_groups) == original_len:
            raise OperationError(f"Active group '{group_id}' not found for user {user_id}", status_code=404)
        await self.container.memory_repository.upsert_profile(profile)
        return profile

    async def delete_profile_contact(self, user_id: str, contact_id: str) -> "UserMemoryFact":
        """删除用户画像中指定的常联系人。"""
        profile = await self._get_profile_or_raise(user_id)
        if contact_id not in profile.frequent_contacts:
            raise OperationError(f"Contact '{contact_id}' not found for user {user_id}", status_code=404)
        del profile.frequent_contacts[contact_id]
        await self.container.memory_repository.upsert_profile(profile)
        return profile

    async def delete_profile_contact_topic(self, user_id: str, contact_id: str, topic: str) -> "UserMemoryFact":
        """删除用户常联系人中指定的相关话题。"""
        profile = await self._get_profile_or_raise(user_id)
        if contact_id not in profile.frequent_contacts:
            raise OperationError(f"Contact '{contact_id}' not found for user {user_id}", status_code=404)
        contact = profile.frequent_contacts[contact_id]
        if topic not in contact.related_topics:
            raise OperationError(f"Topic '{topic}' not found in contact '{contact_id}'", status_code=404)
        del contact.related_topics[topic]
        await self.container.memory_repository.upsert_profile(profile)
        return profile

    async def delete_profile_contact_group(self, user_id: str, contact_id: str, group_id: str) -> "UserMemoryFact":
        """删除用户常联系人中指定的相关群组。"""
        profile = await self._get_profile_or_raise(user_id)
        if contact_id not in profile.frequent_contacts:
            raise OperationError(f"Contact '{contact_id}' not found for user {user_id}", status_code=404)
        contact = profile.frequent_contacts[contact_id]
        if group_id not in contact.related_groups:
            raise OperationError(f"Group '{group_id}' not found in contact '{contact_id}'", status_code=404)
        contact.related_groups = [g for g in contact.related_groups if g != group_id]
        await self.container.memory_repository.upsert_profile(profile)
        return profile

    async def get_rule_stat(self, rule_id: str) -> dict[str, Any]:
        """获取指定规则的触发统计数据（包含完整记录）。"""
        rule = await self.container.rule_repository.get(rule_id)
        if not rule:
            raise OperationError(f"Rule not found: {rule_id}", status_code=404)

        results = self.container.detection_result_repository.results_by_rule.get(rule_id, [])
        triggered_results = [r for r in results if r.decision.triggered]

        records = []
        for r in triggered_results:
            records.append(
                {
                    "id": r.result_id,
                    "result_id": r.result_id,
                    "event_id": r.event_id,
                    "rule_id": r.rule_id,
                    "adapter": r.adapter,
                    "chat_type": r.chat_type,
                    "chat_id": r.chat_id,
                    "message_id": r.message_id,
                    "trigger_time": r.generated_at.isoformat(),
                    "confidence": round(r.decision.confidence, 2),
                    "result": "Triggered (Suppressed)" if r.trigger_suppressed else "Triggered",
                    "trigger_suppressed": r.trigger_suppressed,
                    "suppression_reason": r.suppression_reason,
                    "rule_name": rule.name,
                    "messages": [
                        {"sender": m.sender_name or m.sender_id, "content": str(m)}
                        for m in r.context_messages
                    ],
                    "extracted_params": r.decision.extracted_params,
                    "reason": r.decision.reason,
                }
            )

        return {
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "description": rule.description,
            "count": len(triggered_results),
            "records": sorted(records, key=lambda x: x["trigger_time"], reverse=True),
        }

    async def delete_rule_records(self, rule_id: str, record_ids: list[str] | None = None) -> dict[str, Any]:
        """删除指定规则的触发记录。若提供 record_ids 则只删除这些，否则删除全部。"""
        rule = await self.container.rule_repository.get(rule_id)
        if not rule:
            raise OperationError(f"Rule not found: {rule_id}", status_code=404)
        deleted = await self.container.detection_result_repository.delete_by_rule(rule_id, record_ids)
        return {"deleted": deleted}

    @staticmethod
    def _settings_subset() -> Settings:
        return settings

    async def get_settings(self) -> Settings:
        return self._settings_subset()

    @staticmethod
    def get_default_prompts() -> dict[str, str]:
        return {
            "rule_detection_system_prompt": RULE_DETECTION_SYSTEM_PROMPT,
            "user_profile_system_prompt": USER_PROFILE_SYSTEM_PROMPT,
            "admin_agent_system_prompt": ADMIN_AGENT_SYSTEM_PROMPT,
        }

    @staticmethod
    def get_default_notification_template() -> dict[str, str]:
        return {
            "notification_text_template": get_default_notification_template(),
        }

    async def update_settings(self, payload: dict) -> dict[str, Any]:
        updates = {k: v for k, v in payload.items() if k in self.settings_allowlist}
        disallowed = set(payload.keys()) - set(self.settings_allowlist)
        if disallowed:
            raise OperationError(
                f"Unknown or disallowed setting(s): {', '.join(sorted(disallowed))}",
                status_code=400,
            )

        current = settings.model_dump()
        current.update(updates)
        current["database_url"] = settings.database_url

        try:
            validated = Settings.model_validate(current)
        except Exception as exc:
            raise OperationError(str(exc), status_code=422) from exc

        adapter_related_keys = {
            "enabled_adapters",
            "onebot_host",
            "onebot_port",
            "onebot_access_token",
            "telegram_bot_token",
            "telegram_polling_timeout",
            "telegram_drop_pending_updates",
            "discord_bot_token",
            "discord_guild_ids",
            "wechat_token",
            "wechat_encoding_aes_key",
            "wechat_corp_id",
            "wechat_host",
            "wechat_port",
            "dingtalk_client_id",
            "dingtalk_client_secret",
            "feishu_app_id",
            "virtual_adapter_chat_count",
            "virtual_adapter_members_per_chat",
            "virtual_adapter_messages_per_chat",
            "virtual_adapter_interval_min_seconds",
            "virtual_adapter_interval_max_seconds",
            "virtual_adapter_script_path",
        }
        update_keys = set(updates.keys())
        adapter_updates = adapter_related_keys & update_keys
        new_adapters = None
        if adapter_updates:
            try:
                new_adapters = build_adapters_from_settings(validated)
            except Exception as exc:
                raise OperationError(str(exc), status_code=422) from exc

        # 处理 MCP HTTP 配置动态生效（先校验，后保存）
        mcp_keys = {
            "mcp_http_enabled",
            "mcp_http_transport",
            "mcp_http_host",
            "mcp_http_port",
            "mcp_http_path",
            "mcp_http_auth_key",
        }
        mcp_updates = mcp_keys & update_keys
        mcp_changed = {
            key for key in mcp_updates if getattr(settings, key) != getattr(validated, key)
        }
        mcp_restart_keys = {
            "mcp_http_enabled",
            "mcp_http_transport",
            "mcp_http_host",
            "mcp_http_port",
            "mcp_http_path",
        }
        mcp_requires_restart = bool(mcp_changed & mcp_restart_keys)
        if mcp_updates:
            if not _is_loopback_host(validated.mcp_http_host):
                raise OperationError(
                    "MCP HTTP host must be loopback only (e.g., 127.0.0.1/localhost).",
                    status_code=400,
                )
            if validated.mcp_http_enabled and not (validated.mcp_http_auth_key or "").strip():
                raise OperationError(
                    "MCP HTTP auth key is required when HTTP MCP is enabled.",
                    status_code=400,
                )

        validated_dict = validated.model_dump(exclude={"database_url"})
        to_save = {k: validated_dict[k] for k in updates.keys()}
        self.container.settings_repository.save(to_save)

        for key, value in to_save.items():
            setattr(settings, key, value)

        if mcp_updates:
            mcp_service = getattr(self.container, "mcp_service", None)
            if mcp_service:
                if mcp_requires_restart:
                    await mcp_service.stop_http_server()
                    if settings.mcp_http_enabled:
                        try:
                            await mcp_service.start_http_server(
                                transport=settings.mcp_http_transport,
                                host=settings.mcp_http_host,
                                port=settings.mcp_http_port,
                                path=settings.mcp_http_path,
                            )
                        except Exception as exc:
                            raise OperationError(
                                f"Failed to start MCP HTTP server: {exc}", status_code=500
                            ) from exc
                elif "mcp_http_auth_key" in mcp_changed:
                    logger.info("🔑 MCP HTTP auth key updated without restarting HTTP server")

        if adapter_updates and new_adapters is not None:
            try:
                await self.container.adapter_manager.stop_all()
            except Exception as exc:
                raise OperationError(f"Failed to stop existing adapters: {exc}", status_code=500) from exc
            try:
                self.container.adapter_manager = AdapterManager(new_adapters)
                for adapter in self.container.adapter_manager.adapters:
                    adapter.register_handler(self.container.handle_adapter_event)
            except Exception as exc:
                raise OperationError(f"Failed to rebuild adapters: {exc}", status_code=500) from exc

        # 处理 LLM 配置动态生效：当 LLM 相关设置变更时立即重建 LLM 客户端
        llm_related_keys = {
            "llm_langchain_backend",
            "llm_langchain_model",
            "llm_langchain_api_base",
            "llm_langchain_api_key",
            "llm_langchain_temperature",
            "llm_timeout_seconds",
        }
        llm_updates = llm_related_keys & update_keys
        llm_rebuild_warning: str | None = None
        if llm_updates:
            try:
                new_llm_client = build_llm_client()
                self.container.llm_client = new_llm_client
                self.container.detection_engine.llm_client = new_llm_client
                self.container.detection_engine.batch_scheduler.llm_client = new_llm_client
                self.container.user_memory_service.llm_client = new_llm_client
                logger.info("🔄 LLM 客户端已根据新配置重建并立即生效")
            except Exception as exc:
                llm_rebuild_warning = str(exc)
                logger.warning(f"⚠️ LLM 客户端重建失败，将继续使用旧配置: {exc}")

        result: dict[str, Any] = {"status": "saved",
                                  "settings": self._settings_subset().model_dump(exclude={"database_url"})}
        if llm_rebuild_warning:
            result["warning"] = f"Settings saved but LLM client rebuild failed: {llm_rebuild_warning}"
        return result

    @staticmethod
    def get_notifications_config() -> dict[str, Any]:
        s = settings
        return {
            "email": {
                "enabled": s.email_notifier_enabled,
                "smtp_host": s.smtp_host,
                "smtp_port": s.smtp_port,
                "smtp_username": s.smtp_username,
                "smtp_password": s.smtp_password,
                "smtp_sender": s.smtp_sender,
                "to_email": s.email_notifier_to_email,
            },
            "bark": {
                "enabled": s.bark_notifier_enabled,
                "device_key": s.bark_device_key,
                "device_keys": s.bark_device_keys,
                "server_url": s.bark_server_url,
                "group": s.bark_group,
                "level": s.bark_level,
            },
        }

    @staticmethod
    def get_llm_config() -> dict[str, Any]:
        s = settings
        return {
            "backend": s.llm_langchain_backend,
            "model": s.llm_langchain_model,
            "api_base": s.llm_langchain_api_base,
            "temperature": s.llm_langchain_temperature,
            "timeout_seconds": s.llm_timeout_seconds,
            "max_parallel_batches": s.llm_max_parallel_batches,
            "rules_per_batch": s.llm_rules_per_batch,
        }


class ChatGuardianMCPService:
    """封装 FastMCP 服务器，提供内存连接与可选 HTTP/SSE 传输。"""

    def __init__(self, container: Any, operations: ChatGuardianOperations):
        self.container = container
        self.operations = operations
        self.server = FastMCP(
            name="ChatGuardian MCP",
            version="0.1.0",
            instructions=(
                "ChatGuardian MCP 提供与 FastAPI 同步的工具集合，包括健康检查、鉴权、规则管理、"
                "设置、日志等。所有工具直接调用内部服务而非 HTTP，返回值字段详见各函数文档。"
            ),
        )
        self._http_task: asyncio.Task | None = None
        self._register_tools()

    def _serialize(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._serialize(v) for v in value]
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value

    def _register_tools(self) -> None:
        @self.server.tool(name="health", description="健康检查，返回 status 与 time。")
        async def tool_health() -> dict[str, str]:
            """
            健康检查。

            Returns:
                dict[str, str]: ``status`` 为 ``\"ok\"``，``time`` 为当前 UTC 时间 ISO8601 字符串。
            """
            return await self.operations.health()

        @self.server.tool(name="llm_health", description="LLM 与调度器诊断，可选 ping。")
        async def tool_llm_health(do_ping: bool = True) -> dict[str, object]:
            """
            返回 LLM 与批处理调度器诊断信息。

            Args:
                do_ping: 是否执行 LLM ping。

            Returns:
                dict[str, object]: 字段 ``status``、``time``、``llm``、``scheduler``，可选 ``ping``。
            """
            return await self.operations.llm_health(do_ping=do_ping)

        @self.server.tool(name="auth_login", description="管理员登录，返回 token。")
        async def tool_auth_login(username: str, password: str) -> dict[str, object]:
            """
            使用管理员凭据换取访问令牌。

            Args:
                username: 管理员用户名。
                password: 管理员密码。

            Returns:
                dict[str, object]: ``token``、``username``、``using_default_credentials``。

            Raises:
                ValueError: 当凭据缺失或错误。
            """
            try:
                return await self.operations.auth_login(username=username, password=password)
            except OperationError as exc:
                raise ValueError(str(exc)) from exc

        @self.server.tool(name="auth_status", description="校验当前用户名称并返回认证状态。")
        async def tool_auth_status(username: str | None) -> dict[str, object]:
            """
            根据用户名返回认证状态（适用于内存 token 已验证场景）。

            Args:
                username: 已认证用户名。

            Returns:
                dict[str, object]: ``authenticated``、``username``、``using_default_credentials``。

            Raises:
                ValueError: 当用户名为空。
            """
            try:
                return await self.operations.auth_status(current_user=username)
            except OperationError as exc:
                raise ValueError(str(exc)) from exc

        @self.server.tool(name="auth_logout", description="撤销给定 token。")
        async def tool_auth_logout(token: str | None = None) -> dict[str, str]:
            """
            撤销指定 token。

            Args:
                token: Bearer token 字符串，可为空（为空时返回已登出）。

            Returns:
                dict[str, str]: ``status`` 为 ``\"logged_out\"``。
            """
            return await self.operations.auth_logout(token=token)

        @self.server.tool(name="adapters_start", description="启动所有 adapter。")
        async def tool_adapters_start() -> dict[str, Any]:
            """
            启动所有已启用 adapter。

            Returns:
                dict[str, Any]: ``status`` 与 ``enabled_adapters`` 列表。
            """
            return await self.operations.start_adapters()

        @self.server.tool(name="adapters_stop", description="停止所有 adapter。")
        async def tool_adapters_stop() -> dict[str, Any]:
            """
            停止所有已启用 adapter。

            Returns:
                dict[str, Any]: ``status`` 与 ``enabled_adapters`` 列表。
            """
            return await self.operations.stop_adapters()

        @self.server.tool(name="rules_upsert", description="创建或更新规则。")
        async def tool_rules_upsert(rule: DetectionRule) -> dict[str, Any]:
            """
            创建或更新检测规则。

            Args:
                rule: 规则实体。

            Returns:
                dict: 规则的序列化内容。
            """
            return self._serialize(await self.operations.upsert_rule(rule))

        @self.server.tool(name="rules_list", description="列出所有规则。")
        async def tool_rules_list() -> list[dict[str, Any]]:
            """
            列出所有规则。

            Returns:
                list[dict]: 规则列表（序列化后）。
            """
            return self._serialize(await self.operations.list_rules())

        @self.server.tool(name="rules_delete", description="删除指定规则。")
        async def tool_rules_delete(rule_id: str) -> dict[str, Any]:
            """
            删除规则。

            Args:
                rule_id: 规则 ID。

            Returns:
                dict: ``status``、``rule_id``、``deleted``。

            Raises:
                ValueError: 当规则不存在。
            """
            try:
                return await self.operations.delete_rule(rule_id)
            except OperationError as exc:
                raise ValueError(str(exc)) from exc

        @self.server.tool(name="rule_stats", description="规则触发统计。")
        async def tool_rule_stats() -> dict[str, Any]:
            """
            返回规则触发统计。

            Returns:
                dict: 包含 ``stats`` 与 ``data``。
            """
            return await self.operations.get_rule_stats()

        @self.server.tool(name="queues_get", description="获取待处理与历史消息。")
        async def tool_queues_get() -> dict[str, Any]:
            """
            返回消息队列。

            Returns:
                dict: ``pending`` 与 ``history`` 列表。
            """
            return await self.operations.get_queues()

        @self.server.tool(name="queues_delete_history", description="删除历史消息或清空。")
        async def tool_queues_delete_history(
                clear_all: bool = False, items: list[dict[str, Any]] | None = None
        ) -> dict[str, Any]:
            """
            删除历史消息。

            Args:
                clear_all: 为 True 时清空历史。
                items: 待删除的消息标识列表。

            Returns:
                dict: ``cleared`` 或 ``deleted`` 计数。
            """
            payload = {"clear_all": clear_all, "items": items or []}
            return await self.operations.delete_history_messages(payload)

        @self.server.tool(name="adapters_status", description="查询 adapter 状态。")
        async def tool_adapters_status() -> list[dict[str, Any]]:
            """
            查询 adapter 状态。

            Returns:
                list[dict]: 每条包含 ``name`` 与 ``running``。
            """
            return await self.operations.get_adapters_status()

        @self.server.tool(name="dashboard", description="仪表盘概览数据。")
        async def tool_dashboard() -> dict[str, Any]:
            """
            返回仪表盘数据。

            Returns:
                dict: ``total_rules``、``enabled_rules``、``triggers_today``、``trigger_rate``、``messages_today``、``llm_status``。
            """
            return await self.operations.get_dashboard()

        @self.server.tool(name="logs_get", description="读取运行日志。")
        async def tool_logs_get(limit: int = 100) -> list[dict[str, Any]]:
            """
            读取最近日志。

            Args:
                limit: 最大返回条数。

            Returns:
                list[dict]: ``timestamp``、``level``、``message``。
            """
            return await self.operations.get_logs(limit=limit)

        @self.server.tool(name="logs_clear", description="清空内存日志。")
        async def tool_logs_clear() -> dict[str, int]:
            """
            清空日志缓冲区。

            Returns:
                dict[str, int]: ``cleared`` 为删除条数。
            """
            return await self.operations.clear_logs()

        @self.server.tool(name="user_profiles_list", description="列出用户画像。")
        async def tool_user_profiles_list() -> list[Any]:
            """
            列出所有用户画像。

            Returns:
                list: 用户画像列表。
            """
            return await self.operations.list_user_profiles()

        @self.server.tool(name="user_profile_get", description="获取指定用户画像。")
        async def tool_user_profile_get(user_id: str) -> Any:
            """
            获取指定用户画像。

            Args:
                user_id: 用户 ID。

            Returns:
                dict: 用户画像。

            Raises:
                ValueError: 当用户不存在。
            """
            try:
                return await self.operations.get_user_profile(user_id)
            except OperationError as exc:
                raise ValueError(str(exc)) from exc

        @self.server.tool(name="settings_get", description="获取当前配置。")
        async def tool_settings_get() -> Settings:
            """
            获取配置（不含 database_url）。

            Returns:
                dict[str, object]: 当前配置字典。
            """
            return await self.operations.get_settings()

        @self.server.tool(name="settings_update", description="更新配置并即时生效。")
        async def tool_settings_update(payload: dict) -> dict[str, Any]:
            """
            更新配置并写入数据库，成功后立即生效。

            Args:
                payload: 待更新的键值对，``database_url`` 不允许修改。

            Returns:
                dict: ``status`` 为 ``\"saved\"``，``settings`` 为最新配置。

            Raises:
                ValueError: 当字段非法或校验失败。
            """
            try:
                return await self.operations.update_settings(payload)
            except OperationError as exc:
                raise ValueError(str(exc)) from exc

        @self.server.tool(name="notifications_config", description="获取通知配置。")
        async def tool_notifications_config() -> dict[str, Any]:
            """
            获取通知配置。

            Returns:
                dict: ``email`` 与 ``bark`` 配置字典。
            """
            return self.operations.get_notifications_config()

        @self.server.tool(name="llm_config", description="获取 LLM 配置。")
        async def tool_llm_config() -> dict[str, Any]:
            """
            获取 LLM 配置。

            Returns:
                dict: 见 ``GET /api/llm/config``。
            """
            return self.operations.get_llm_config()

    async def start_http_server(
            self,
            *,
            transport: str = "streamable-http",
            host: str | None = None,
            port: int | None = None,
            path: str | None = None,
    ) -> asyncio.Task | None:
        """Start HTTP/SSE server in the background and return the task."""
        if self._http_task and not self._http_task.done():
            return self._http_task
        if not _is_loopback_host(host):
            raise ValueError("MCP HTTP host must be loopback (127.0.0.1/localhost).")
        auth_key = (settings.mcp_http_auth_key or "").strip()
        middleware = None
        if auth_key:

            class MCPKeyAuthMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request: Request, call_next):
                    expected_key = (settings.mcp_http_auth_key or "").strip()
                    provided_key = request.headers.get("Authorization")
                    if provided_key and provided_key.lower().startswith("bearer "):
                        provided_key = provided_key[7:].strip()
                    if provided_key != expected_key:
                        return JSONResponse(status_code=401, content={"detail": "Invalid MCP key"})
                    return await call_next(request)

            middleware = [Middleware(MCPKeyAuthMiddleware)]

        async def _run():
            try:
                await self.server.run_http_async(
                    transport=normalize_mcp_transport(transport),
                    host=host,
                    port=port,
                    path=path,
                    show_banner=False,
                    middleware=middleware,
                )
            except asyncio.CancelledError:
                raise
            except SystemExit as exc:
                logger.exception(
                    "HTTP/SSE server terminated unexpectedly (transport={}, host={}, port={}, path={})",
                    transport,
                    host,
                    port,
                    path,
                )
                raise RuntimeError("HTTP/SSE server exited during startup") from exc
            except Exception as exc:
                logger.exception(
                    "HTTP/SSE server failed to start (transport={}, host={}, port={}, path={})",
                    transport,
                    host,
                    port,
                    path,
                )
                raise RuntimeError("HTTP/SSE server failed to start") from exc

        def _on_done(task: asyncio.Task) -> None:
            with suppress(asyncio.CancelledError):
                exc = task.exception()
                if exc is not None:
                    logger.exception("HTTP/SSE server task exited with exception: {}", exc)

        self._http_task = asyncio.create_task(_run())
        self._http_task.add_done_callback(_on_done)
        return self._http_task

    async def stop_http_server(self) -> None:
        """Stop the background HTTP/SSE server task."""
        if self._http_task:
            self._http_task.cancel()
            with suppress(asyncio.CancelledError, RuntimeError):
                await self._http_task
            self._http_task = None

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """直接调用工具（适用于内部协程场景）。"""
        args = arguments or {}
        if hasattr(self.server, "call_tool"):
            return await self.server.call_tool(name, args)
        # FastMCP 2.x 使用内部 _call_tool_middleware
        return await self.server._call_tool_middleware(  # type: ignore[attr-defined]
            key=name, arguments=args
        )

    @asynccontextmanager
    async def in_process_session(self, **session_kwargs: Any) -> AsyncIterator[Any]:
        """创建内存传输的 MCP ClientSession，供额外 LLM 客户端复用。"""
        transport = FastMCPTransport(self.server, raise_exceptions=True)
        async with transport.connect_session(**session_kwargs) as session:
            yield session
