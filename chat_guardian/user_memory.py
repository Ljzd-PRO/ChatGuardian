from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from chat_guardian.context_window import ContextWindowService
from chat_guardian.domain import (
    ActiveGroupStat,
    ChatEvent,
    FrequentContactStat,
    InterestTopicStat,
    RelatedTopicStat,
    UserMemoryFact,
)
from chat_guardian.llm_client import LangChainLLMClient
from chat_guardian.repositories import MemoryRepository
from chat_guardian.settings import settings


class UserMemoryService:
    """基于配置的用户 ID 列表更新用户画像的服务。"""

    def __init__(
            self,
            llm_client: LangChainLLMClient,
            memory_repository: MemoryRepository,
            context_service: ContextWindowService,
    ):
        self.llm_client = llm_client
        self.memory_repository = memory_repository
        self.context_service = context_service
        self._user_msg_counts: dict[str, int] = {}
        self._last_context_msg_ids: dict[str, set[str]] = {}
        self._last_topics: dict[str, set[str]] = {}
        self._last_interactions: dict[str, dict[str, set[str]]] = {}

    async def process_user_memory(self, event: ChatEvent) -> int:
        user_id = event.message.sender_id
        configured_targets = {str(uid).strip() for uid in settings.memory_target_user_ids if str(uid).strip()}
        if not configured_targets:
            logger.debug("ℹ️ 用户画像未启用，memory_target_user_ids 为空")
            return 0
        if user_id not in configured_targets:
            logger.debug(f"ℹ️ 非画像目标用户，跳过处理 | 发送者={user_id}")
            return 0

        min_new = max(1, getattr(settings, "user_memory_min_new_messages", 1))
        self._user_msg_counts[user_id] = self._user_msg_counts.get(user_id, 0) + 1
        current_count = self._user_msg_counts[user_id]

        if current_count < min_new:
            logger.debug(f"⏳ 用户 {user_id} 消息数不足，当前={current_count}，最小触发={min_new}")
            return 0

        self._user_msg_counts[user_id] = 0
        logger.debug(
            f"💾 用户画像检测 | 发送者={user_id} | 消息ID={event.message.message_id} | 触发消息数={current_count}")

        context_messages = await self.context_service.build_context(event)
        logger.debug(f"  ✓ 构建上下文 | 消息数={len(context_messages)}")

        existing_profile = await self.memory_repository.get_profile(user_id)
        existing_topics = [
            {
                "name": topic_name,
                "keywords": list(topic_stat.keywords),
            }
            for topic_name, topic_stat in (existing_profile.interests.items() if existing_profile else [])
        ]
        logger.debug(f"  ✓ 已有话题 | 数量={len(existing_topics)}")

        extract = await self.llm_client.extract_self_participation(event, context_messages, existing_topics)
        if extract is None:
            logger.warning(f"⚠️ 参与画像提取失败，跳过更新 | 用户={user_id}")
            return 0
        logger.debug(f"  ✓ LLM 提取完成 | 话题数={len(extract.get('topics', []))}")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        profile = existing_profile or UserMemoryFact(
            user_id=user_id,
            user_name=event.message.sender_name,
        )
        profile.user_name = event.message.sender_name or profile.user_name

        current_msg_ids = {msg.message_id for msg in context_messages}
        last_msg_ids = self._last_context_msg_ids.get(user_id, set())
        has_overlap = bool(current_msg_ids & last_msg_ids)
        last_topics = self._last_topics.get(user_id, set())
        last_interactions = self._last_interactions.get(user_id, {})

        new_extracted_topics = set()

        for topic_data in extract.get("topics", []):
            if not isinstance(topic_data, dict):
                continue
            name = str(topic_data.get("name", "")).strip()
            if not name:
                continue

            new_extracted_topics.add(name)
            participation_count = 1

            if has_overlap and name in last_topics:
                logger.debug(f"⚠️ 用户 {user_id} 画像抑制: 话题 '{name}' 已在最近上下文提取过，跳过参与次数增加")
                participation_count = 0

            keywords = [str(k).strip() for k in topic_data.get("keywords", []) if str(k).strip()]

            if name in profile.interests:
                stat = profile.interests[name]
                stat.score += participation_count
                stat.last_active = now_str
                existing_kw = set(stat.keywords)
                stat.keywords.extend(kw for kw in keywords if kw not in existing_kw)
                if event.chat_id not in stat.related_chat:
                    stat.related_chat.append(event.chat_id)
            else:
                profile.interests[name] = InterestTopicStat(
                    score=participation_count,
                    last_active=now_str,
                    related_chat=[event.chat_id],
                    keywords=keywords,
                )
            logger.debug(f"    ✓ 更新话题: {name} | 参与次数+={participation_count}")

        for group_stat in profile.active_groups:
            if group_stat.group_id == event.chat_id:
                group_stat.frequency += 1
                group_stat.last_talk = today_str
                break
        else:
            profile.active_groups.append(ActiveGroupStat(
                group_id=event.chat_id,
                frequency=1,
                last_talk=today_str,
            ))

        sender_name_by_id: dict[str, str] = {}
        for message in context_messages:
            sender_id = str(message.sender_id or "").strip()
            sender_name = str(message.sender_name or "").strip()
            if sender_id and sender_name:
                sender_name_by_id[sender_id] = sender_name

        new_extracted_interactions: dict[str, set[str]] = {}
        for interaction in extract.get("interactions", []):
            if not isinstance(interaction, dict):
                continue
            uid = str(interaction.get("user_id", "")).strip()
            uname = sender_name_by_id.get(uid, "")
            interact_topics = [str(t).strip() for t in interaction.get("topics", []) if str(t).strip()]
            if not uid:
                continue

            new_extracted_interactions[uid] = set(interact_topics)
            is_interaction_suppressed = False
            if has_overlap and uid in last_interactions:
                is_interaction_suppressed = True
                logger.debug(f"⚠️ 用户 {user_id} 画像抑制: 与 '{uid}' 的互动已在最近上下文提取过，跳过互动次数增加")

            if uid not in profile.frequent_contacts:
                profile.frequent_contacts[uid] = FrequentContactStat(
                    name=uname,
                    interaction_count=0,
                    last_interact=now_str,
                )
            contact = profile.frequent_contacts[uid]
            if uname:
                contact.name = uname

            if not is_interaction_suppressed:
                contact.interaction_count += 1
            contact.last_interact = now_str
            if event.chat_id not in contact.related_groups:
                contact.related_groups.append(event.chat_id)

            for topic in interact_topics:
                is_topic_suppressed = False
                if is_interaction_suppressed and topic in last_interactions.get(uid, set()):
                    is_topic_suppressed = True
                    logger.debug(
                        f"⚠️ 用户 {user_id} 画像抑制: 与 '{uid}' 的互动话题 '{topic}' 已提取过，跳过参与次数增加")

                if topic in contact.related_topics:
                    if not is_topic_suppressed:
                        contact.related_topics[topic].score += 1
                    contact.related_topics[topic].last_talk = now_str
                else:
                    contact.related_topics[topic] = RelatedTopicStat(
                        score=0 if is_topic_suppressed else 1,
                        last_talk=now_str,
                    )
            logger.debug(f"    ✔️ 更新互动: uid={uid} | 话题={interact_topics}")

        if has_overlap:
            self._last_context_msg_ids[user_id].update(current_msg_ids)
            self._last_topics[user_id].update(new_extracted_topics)
            if user_id not in self._last_interactions:
                self._last_interactions[user_id] = {}
            for uid, topics in new_extracted_interactions.items():
                if uid not in self._last_interactions[user_id]:
                    self._last_interactions[user_id][uid] = set()
                self._last_interactions[user_id][uid].update(topics)
        else:
            self._last_context_msg_ids[user_id] = current_msg_ids
            self._last_topics[user_id] = new_extracted_topics
            self._last_interactions[user_id] = new_extracted_interactions

        await self.memory_repository.upsert_profile(profile)
        logger.success(f"✅ 用户画像已更新 | 用户={user_id} | 话题总数={len(profile.interests)}")
        return 1
