from __future__ import annotations

import asyncio
import base64
import os
import random
import re
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Set, Tuple

from astrbot import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import At, Image, Plain, Record, Video
from astrbot.api.platform import (
    AstrBotMessage,
    MessageMember,
    MessageType,
    Platform,
    PlatformMetadata,
    register_platform_adapter,
)
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from astrbot.core.utils.tencent_record_helper import audio_to_tencent_silk_base64

from defusedxml import ElementTree as eT

from .wxhttp_client import WxHttpClient
from .wxhttp_event import WxHttpMessageEvent


def _safe_get(d: Dict[str, Any], *path: str) -> Any:
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _parse_group_content(content: str) -> Tuple[Optional[str], str]:
    # 群文本形如: "wxid_xxx:\n正文"
    sep = ":\n"
    if sep in content:
        left, right = content.split(sep, 1)
        sender = left.strip() or None
        return sender, right
    return None, content


def _safe_path_part(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "unknown"
    # 文件系统安全：只保留常见字符，其余替换为 _
    s = re.sub(r"[^a-zA-Z0-9@._-]+", "_", s)
    return s[:120] if len(s) > 120 else s


def _detect_image_ext(data: bytes) -> str:
    if not data:
        return "jpg"
    if data.startswith(b"\xFF\xD8\xFF"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    # WebP: RIFF....WEBP
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "jpg"


@register_platform_adapter(
    "webot",
    "webot 微信适配器 (基于 wxhttp 协议)",
    default_config_tmpl={
        "base_url": "",
        "wxid": "",
        "poll_interval_sec": 1.5,
        "use_client_synckey": False,

        # 昵称黑名单（过滤消息，不回复）
        # - 私聊：默认屏蔽昵称包含“微信 / wx / wechat”的联系人
        # - 群聊：默认不启用（保持原有 @/主动触发逻辑）
        # 说明：keywords 为子串匹配（不区分大小写）；regex 为空则不启用。
        "private_nickname_blacklist_keywords": "微信,wx,wechat",
        "private_nickname_blacklist_regex": "",
        "group_nickname_blacklist_keywords": "",
        "group_nickname_blacklist_regex": "",

        # 发送消息延时范围（秒）
        # 格式："最小值,最大值"，例如 "3.5,6.5" 表示每条消息发送前随机延时 3.5-6.5 秒
        # 留空或设为 "0,0" 则不延时
        "send_delay_range": "",
    },
)
class WxHttpPlatformAdapter(Platform):
    def __init__(self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue) -> None:
        super().__init__(platform_config, event_queue)
        self.settings = platform_settings

        base_url = (self.config.get("base_url") or "").strip()
        self_wxid = (self.config.get("wxid") or "").strip()
        if not base_url:
            raise ValueError("wxhttp.base_url is required")
        if not self_wxid:
            raise ValueError("wxhttp.wxid is required")

        self._self_wxid = self_wxid
        
        # 解析 API 请求延时配置
        api_delay_min = 0.0
        api_delay_max = 0.0
        api_delay_range = (self.config.get("api_request_delay_range") or "").strip()
        if api_delay_range:
            try:
                parts = api_delay_range.split(",")
                if len(parts) == 2:
                    min_val = float(parts[0].strip())
                    max_val = float(parts[1].strip())
                    if min_val >= 0 and max_val >= min_val:
                        api_delay_min = min_val
                        api_delay_max = max_val
                        logger.info(f"[webot] API 请求延时: {api_delay_min}-{api_delay_max} 秒")
            except Exception as e:
                logger.warning(f"[webot] 解析 api_request_delay_range 失败: {e}")
        
        self._client = WxHttpClient(
            base_url=base_url,
            request_delay_min=api_delay_min,
            request_delay_max=api_delay_max,
        )

        self._poll_interval_sec = float(self.config.get("poll_interval_sec", 1.5))
        self._use_client_synckey = bool(self.config.get("use_client_synckey", False))
        self._synckey: str = ""  # 客户端游标（可选模式）

        # 尽量对齐 AstrBot 官方配置：平台层的行为由 platform_settings 控制。
        # wxhttp 插件侧仅保留必要的连接配置。
        # 仍保留这些内部开关作为未来兼容点（不出现在默认模板里）。
        self._enable_at_wake = bool(self.config.get("enable_at_wake", True))
        self._enable_group_member_cache = bool(
            self.config.get("enable_group_member_cache", True)
        )

        # 解析发送延时配置
        self._send_delay_min = 0.0
        self._send_delay_max = 0.0
        delay_range = (self.config.get("send_delay_range") or "").strip()
        if delay_range:
            try:
                parts = delay_range.split(",")
                if len(parts) == 2:
                    min_val = float(parts[0].strip())
                    max_val = float(parts[1].strip())
                    if min_val >= 0 and max_val >= min_val:
                        self._send_delay_min = min_val
                        self._send_delay_max = max_val
                        logger.info(f"[webot] 消息发送延时: {self._send_delay_min}-{self._send_delay_max} 秒")
            except Exception as e:
                logger.warning(f"[webot] 解析 send_delay_range 失败: {e}")

        self._chatroom_member_cache_ttl_sec = float(
            self.config.get("chatroom_member_cache_ttl_sec", 600)
        )

        # chatroom_id -> {wxid -> nickname}
        self._chatroom_member_cache: Dict[str, Dict[str, str]] = {}
        self._chatroom_member_cache_at: Dict[str, float] = {}

        self._private_nickname_blacklist_keywords = self._normalize_blacklist_keywords(
            self.config.get("private_nickname_blacklist_keywords"),
        )
        self._private_nickname_blacklist_regex = str(
            self.config.get("private_nickname_blacklist_regex") or "",
        ).strip()
        self._group_nickname_blacklist_keywords = self._normalize_blacklist_keywords(
            self.config.get("group_nickname_blacklist_keywords"),
        )
        self._group_nickname_blacklist_regex = str(
            self.config.get("group_nickname_blacklist_regex") or "",
        ).strip()

        self._seen_ids: Set[int] = set()
        self._seen_order: Deque[int] = deque(maxlen=3000)
        
        # 连续错误计数器（用于检测 wxhttp 服务是否异常）
        self._consecutive_errors = 0
        self._max_consecutive_errors = int(self.config.get("max_consecutive_errors", 10))

    @staticmethod
    def _normalize_blacklist_keywords(value: Any) -> list[str]:
        """解析黑名单关键词，支持字符串（逗号分隔）或列表格式"""
        if value is None:
            return []
        if isinstance(value, str):
            # 支持逗号分隔的字符串，例如 "微信,wx,wechat"
            if "," in value:
                value = [kw.strip() for kw in value.split(",") if kw.strip()]
            else:
                value = [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
        return out

    @staticmethod
    def _match_nickname_blacklist(
        nickname_or_id: str,
        keywords: list[str],
        regex: str,
    ) -> bool:
        if not nickname_or_id:
            return False

        haystack = nickname_or_id.casefold()
        for kw in keywords:
            if kw and kw.casefold() in haystack:
                return True

        if regex:
            try:
                return re.search(regex, nickname_or_id, flags=re.IGNORECASE) is not None
            except re.error as e:
                logger.warning(f"[wxhttp] invalid blacklist regex={regex!r}: {e}")
        return False

    async def _refresh_chatroom_member_cache(self, chatroom_id: str) -> None:
        if not self._enable_group_member_cache:
            return

        resp = await self._client.get_chatroom_member_detail(
            qid=chatroom_id,
            wxid=self._self_wxid,
        )
        data = resp.get("Data") or {}
        new_data = data.get("NewChatroomData") or {}
        members = new_data.get("ChatRoomMember") or []
        if not isinstance(members, list):
            return

        m: Dict[str, str] = {}
        for item in members:
            if not isinstance(item, dict):
                continue
            wxid = item.get("UserName")
            nickname = item.get("NickName")
            if isinstance(wxid, str) and wxid:
                if isinstance(nickname, str) and nickname:
                    m[wxid] = nickname
                else:
                    m.setdefault(wxid, wxid)

        if m:
            self._chatroom_member_cache[chatroom_id] = m
            self._chatroom_member_cache_at[chatroom_id] = time.monotonic()

    async def _ensure_chatroom_member_cache(self, chatroom_id: str) -> None:
        if not self._enable_group_member_cache:
            return

        now = time.monotonic()
        last = self._chatroom_member_cache_at.get(chatroom_id, 0.0)
        if chatroom_id not in self._chatroom_member_cache:
            await self._refresh_chatroom_member_cache(chatroom_id)
            return
        if self._chatroom_member_cache_ttl_sec <= 0:
            return
        if now - last >= self._chatroom_member_cache_ttl_sec:
            await self._refresh_chatroom_member_cache(chatroom_id)

    async def _get_chatroom_member_nickname(self, chatroom_id: str, wxid: str) -> str:
        if not chatroom_id or not wxid:
            return ""
        await self._ensure_chatroom_member_cache(chatroom_id)
        return (self._chatroom_member_cache.get(chatroom_id) or {}).get(wxid, "")

    async def _get_self_nickname_in_chatroom(self, chatroom_id: str) -> str:
        return await self._get_chatroom_member_nickname(chatroom_id, self._self_wxid)

    @staticmethod
    def _strip_at_prefix(text: str, nickname: str) -> str:
        # WeChat @ 昵称后通常跟空格/特殊空格（\u00A0/\u2005 等）
        if not nickname:
            return text
        pattern = r"^@" + re.escape(nickname) + r"[\s\u00A0\u2005\u2006\u2009]*"
        return re.sub(pattern, "", text, count=1).strip()

    @staticmethod
    def _remove_at_mentions(text: str, nickname: str) -> str:
        """移除文本中出现的 @昵称 片段（用于降噪，不影响唤醒标记）。"""
        if not nickname:
            return text
        # 匹配 @昵称 后可能跟的空白
        pattern = r"@" + re.escape(nickname) + r"[\s\u00A0\u2005\u2006\u2009]*"
        cleaned = re.sub(pattern, "", text)
        # 简单压缩多余空白
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _parse_atuserlist_by_msgsource(self, raw_msg: Dict[str, Any]) -> list[str]:
        """从 MsgSource 的 <atuserlist> 判断是否 @ 了机器人。

        注意：不同实现可能返回空列表、逗号分隔 wxid 或其它格式；这里做最宽松的包含判断。
        """
        msg_source = raw_msg.get("MsgSource")
        if not isinstance(msg_source, str) or not msg_source:
            return []
        m = re.search(r"<atuserlist>(.*?)</atuserlist>", msg_source, flags=re.S)
        if not m:
            return []
        inner = (m.group(1) or "").strip()
        if not inner:
            return []
        # 常见是 wxid 用逗号分隔，也可能包含空白/换行
        return [p.strip() for p in re.split(r"[\s,]+", inner) if p.strip()]

    def _is_at_self_by_msgsource(self, raw_msg: Dict[str, Any]) -> bool:
        parts = self._parse_atuserlist_by_msgsource(raw_msg)
        return bool(parts) and (str(self._self_wxid) in parts)

    async def _detect_at_bot_and_clean_text(
        self, *, chatroom_id: str, text: str, raw_msg: Dict[str, Any]
    ) -> tuple[bool, str]:
        if not self._enable_at_wake:
            return False, text
        if not chatroom_id:
            return False, text

        # 1) 优先用 MsgSource atuserlist 判断（不依赖昵称）
        #    但 MsgSource 不一定可靠/不一定填，所以同时做文本昵称匹配。
        # atuserlist 若能提供 wxid 列表，这是最稳的判断方式。
        is_at_by_source = self._is_at_self_by_msgsource(raw_msg)

        bot_nick = ""
        try:
            bot_nick = await self._get_self_nickname_in_chatroom(chatroom_id)
        except Exception:
            bot_nick = ""

        is_at_by_text = False
        cleaned = text
        if bot_nick:
            token = f"@{bot_nick}"
            if token in text:
                is_at_by_text = True
                # 去掉开头 @昵称，并清理正文里的重复 @昵称（降噪）
                cleaned = self._strip_at_prefix(cleaned, bot_nick)
                cleaned = self._remove_at_mentions(cleaned, bot_nick)

        return (is_at_by_source or is_at_by_text), cleaned

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="webot",
            description="webot 微信适配器 (基于 wxhttp 协议)",
            id=self.config.get("id", "webot"),
            adapter_display_name="webot",
            logo_path="logo.svg",
            support_streaming_message=False,
        )

    async def send_by_session(self, session: MessageSesion, message_chain: MessageChain):
        to_wxid = session.session_id
        for item in message_chain.chain:
            # 发送消息前随机延时
            if self._send_delay_max > 0:
                delay = random.uniform(self._send_delay_min, self._send_delay_max)
                logger.debug(f"[webot] 延时 {delay:.2f} 秒后发送消息")
                await asyncio.sleep(delay)

            if isinstance(item, Plain) and item.text:
                content = item.text
                logger.info(f"[wxhttp] send_by_session(text) -> {to_wxid} (len={len(content)})")
                await self._client.send_txt(
                    wxid=self._self_wxid,
                    to_wxid=to_wxid,
                    content=content,
                    at="",
                    type_=1,
                )
            elif isinstance(item, Image):
                try:
                    b64 = await item.convert_to_base64()
                except Exception as e:
                    logger.error(f"[wxhttp] send_by_session image convert failed: {e}")
                    continue
                await self._client.upload_img(
                    wxid=self._self_wxid,
                    to_wxid=to_wxid,
                    base64_data=b64,
                )
            elif isinstance(item, Record):
                try:
                    record_path = await item.convert_to_file_path()
                    b64, duration_sec = await audio_to_tencent_silk_base64(record_path)
                    voice_time_ms = max(1000, int(float(duration_sec) * 1000))
                except Exception as e:
                    logger.error(f"[wxhttp] send_by_session record convert failed: {e}")
                    continue
                await self._client.send_voice(
                    wxid=self._self_wxid,
                    to_wxid=to_wxid,
                    base64_data=b64,
                    type_=4,
                    voice_time_ms=voice_time_ms,
                )

    async def run(self):
        logger.info("wxhttp adapter started")
        while True:
            try:
                synckey = self._synckey if self._use_client_synckey else ""
                resp = await self._client.sync(wxid=self._self_wxid, scene=0, synckey=synckey)

                # 请求成功，重置错误计数器
                self._consecutive_errors = 0

                data = resp.get("Data") or {}
                keybuf = data.get("KeyBuf") or {}
                if self._use_client_synckey:
                    kb = keybuf.get("buffer")
                    if isinstance(kb, str) and kb:
                        self._synckey = kb

                add_msgs = data.get("AddMsgs") or []
                if isinstance(add_msgs, list):
                    for raw_msg in add_msgs:
                        abm = await self.convert_message(raw_msg)
                        if abm is None:
                            continue
                        await self.handle_msg(abm)
            except Exception as e:
                self._consecutive_errors += 1
                logger.exception(f"[webot] 轮询异常 ({self._consecutive_errors}/{self._max_consecutive_errors}): {e}")
                
                if self._consecutive_errors >= self._max_consecutive_errors:
                    logger.error(
                        f"[webot] 连续 {self._max_consecutive_errors} 次轮询异常，插件终止运行。"
                        f"请检查 wxhttp 服务是否正常运行，以及 base_url 配置是否正确。"
                    )
                    break

            await asyncio.sleep(self._poll_interval_sec)

    async def convert_message(self, raw_msg: Dict[str, Any]) -> Optional[AstrBotMessage]:
        msg_type = raw_msg.get("MsgType")
        # 先做到“能识别类型”，发送侧后续再逐步补齐。
        supported_types = {1, 3, 34, 43, 47, 49}
        if msg_type not in supported_types:
            return None

        new_msg_id = raw_msg.get("NewMsgId")
        msg_id = raw_msg.get("MsgId")
        dedup_id: Optional[int] = None
        if isinstance(new_msg_id, int):
            dedup_id = new_msg_id
        elif isinstance(msg_id, int):
            dedup_id = msg_id

        if dedup_id is not None:
            if dedup_id in self._seen_ids:
                return None
            self._seen_ids.add(dedup_id)
            self._seen_order.append(dedup_id)
            if len(self._seen_order) == self._seen_order.maxlen:
                # 淘汰旧的
                while len(self._seen_ids) > self._seen_order.maxlen:
                    old = self._seen_order.popleft()
                    self._seen_ids.discard(old)

        from_user = _safe_get(raw_msg, "FromUserName", "string")
        to_user = _safe_get(raw_msg, "ToUserName", "string")
        content = _safe_get(raw_msg, "Content", "string") or ""

        if not isinstance(from_user, str) or not isinstance(to_user, str):
            return None

        is_group = from_user.endswith("@chatroom")

        sender_id: str
        session_id: str
        message_str: str
        group_id: Optional[str] = None

        payload_content: str
        if is_group:
            group_id = from_user
            parsed_sender, parsed_text = _parse_group_content(content)
            sender_id = parsed_sender or ""
            payload_content = (parsed_text or "").strip()
            message_str = payload_content
            session_id = group_id
            if sender_id == self._self_wxid:
                return None
        else:
            sender_id = from_user
            payload_content = (content or "").strip()
            message_str = payload_content
            session_id = sender_id
            if sender_id == self._self_wxid:
                return None

        components: list[Any] = []
        placeholder_map = {
            3: "[图片]",
            34: "[语音]",
            43: "[视频]",
            47: "[表情]",
            49: "[引用/分享]",
        }

        if msg_type == 1:
            if not message_str:
                return None
        else:
            message_str = placeholder_map.get(int(msg_type), f"[MsgType={msg_type}]")

            if msg_type == 3:
                img = await self._try_build_image_component(
                    raw_msg=raw_msg,
                    from_user=from_user,
                    to_user=to_user,
                    payload_content=payload_content,
                )
                if img is not None:
                    components.append(img)
            elif msg_type == 34:
                rec = await self._try_build_record_component(
                    raw_msg=raw_msg,
                    from_user=from_user,
                    new_msg_id=new_msg_id if isinstance(new_msg_id, int) else None,
                    payload_content=payload_content,
                )
                if rec is not None:
                    components.append(rec)
            elif msg_type == 43:
                vid = await self._try_build_video_component(
                    raw_msg=raw_msg,
                    from_user=from_user,
                    payload_content=payload_content,
                )
                if vid is not None:
                    components.append(vid)

        nickname = ""
        push = raw_msg.get("PushContent")
        if isinstance(push, str) and " : " in push:
            nickname = push.split(" : ", 1)[0].strip()

        if is_group and group_id and sender_id:
            try:
                resolved = await self._get_chatroom_member_nickname(group_id, sender_id)
                if resolved:
                    nickname = resolved
            except Exception as e:
                logger.debug(f"[wxhttp] resolve sender nickname failed: {e}")

        # 昵称黑名单：在适配器侧直接丢弃事件，避免进入 AstrBot 后续处理链路。
        # - 私聊：默认启用（见配置 private_nickname_blacklist_*）
        # - 群聊：默认不启用（见配置 group_nickname_blacklist_*）
        nickname_or_id = (
            nickname
            if isinstance(nickname, str) and nickname
            else (sender_id or from_user or "")
        )
        if is_group:
            if self._match_nickname_blacklist(
                nickname_or_id,
                self._group_nickname_blacklist_keywords,
                self._group_nickname_blacklist_regex,
            ):
                logger.info(
                    f"[wxhttp] ignored group sender due to nickname blacklist: {nickname_or_id} ({sender_id})",
                )
                return None
        else:
            if self._match_nickname_blacklist(
                nickname_or_id,
                self._private_nickname_blacklist_keywords,
                self._private_nickname_blacklist_regex,
            ):
                logger.info(
                    f"[wxhttp] ignored private sender due to nickname blacklist: {nickname_or_id} ({sender_id})",
                )
                return None

        is_at_bot = False
        if msg_type == 1 and is_group and group_id:
            try:
                is_at_bot, message_str = await self._detect_at_bot_and_clean_text(
                    chatroom_id=group_id,
                    text=message_str,
                    raw_msg=raw_msg,
                )
            except Exception as e:
                logger.debug(f"[wxhttp] detect @bot failed: {e}")

        abm = AstrBotMessage()
        abm.type = MessageType.GROUP_MESSAGE if is_group else MessageType.FRIEND_MESSAGE
        abm.group_id = group_id
        abm.message_str = message_str
        abm.sender = MessageMember(user_id=sender_id or from_user, nickname=nickname or (sender_id or from_user))
        if msg_type == 1:
            if is_at_bot:
                abm.message = [At(qq=self._self_wxid), Plain(text=message_str)]
            else:
                abm.message = [Plain(text=message_str)]
        else:
            # 多媒体/系统消息：尽量用真实组件，补一个 Plain 占位方便日志/上下文
            abm.message = [*components, Plain(text=message_str)] if components else [Plain(text=message_str)]
        abm.raw_message = raw_msg
        abm.self_id = self._self_wxid
        abm.session_id = session_id
        abm.message_id = str(new_msg_id or msg_id or "")

        return abm

    @staticmethod
    def _resp_ok(resp: Dict[str, Any]) -> bool:
        if not isinstance(resp, dict):
            return False
        if resp.get("Success") is True:
            return True
        code = resp.get("Code")
        return code in (0, 200)

    @staticmethod
    def _extract_base64_payload(resp: Dict[str, Any]) -> str | None:
        data = resp.get("Data")
        if isinstance(data, str) and data.strip():
            return data.strip()
        if not isinstance(data, dict):
            return None

        # 常见字段兜底：Base64 / Buffer / buffer
        for key in ("Base64", "Buffer", "buffer"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

        nested_paths = [
            ("Data", "Base64"),
            ("Data", "Buffer"),
            ("Data", "buffer"),
            ("Data", "Data", "Buffer"),
            ("Data", "Data", "buffer"),
        ]
        for path in nested_paths:
            cur: Any = data
            ok = True
            for p in path:
                if not isinstance(cur, dict):
                    ok = False
                    break
                cur = cur.get(p)
            if ok and isinstance(cur, str) and cur.strip():
                return cur.strip()
        return None

    @staticmethod
    def _extract_download_chunk_b64(resp: Dict[str, Any]) -> str | None:
        """按《下载接口使用指南》读取下载分片 base64 数据。

        规范路径：resp.Data.data.buffer
        """

        if not isinstance(resp, dict):
            return None
        data = resp.get("Data")
        if not isinstance(data, dict):
            return None

        node = data.get("data")
        if isinstance(node, dict):
            buf = node.get("buffer")
            if isinstance(buf, str) and buf.strip():
                return buf.strip()

        # 少量兼容：部分实现可能把 Data 包了一层
        nested = data.get("Data")
        if isinstance(nested, dict):
            node = nested.get("data")
            if isinstance(node, dict):
                buf = node.get("buffer")
                if isinstance(buf, str) and buf.strip():
                    return buf.strip()

        return None

    @staticmethod
    def _parse_int(s: str | None) -> int | None:
        if not s:
            return None
        try:
            return int(s)
        except Exception:
            return None

    @classmethod
    def _parse_image_total_len_from_xml(cls, xml_text: str) -> int | None:
        try:
            root = eT.fromstring(xml_text)
        except Exception:
            return None
        img = root.find(".//img")
        if img is None:
            return None
        # 尽量取高清长度
        for attr in ("hdlength", "totalLen", "length", "len"):
            v = cls._parse_int(img.get(attr))
            if v and v > 0:
                return v
        return None

    @classmethod
    def _parse_voice_meta_from_xml(cls, xml_text: str) -> tuple[str | None, int | None]:
        try:
            root = eT.fromstring(xml_text)
        except Exception:
            return None, None
        voicemsg = root.find(".//voicemsg")
        if voicemsg is None:
            return None, None
        bufid = voicemsg.get("bufid")
        length = cls._parse_int(voicemsg.get("length"))
        return (bufid or None), (length if (length and length > 0) else None)

    @classmethod
    def _parse_video_meta_from_xml(
        cls, xml_text: str
    ) -> tuple[int | None, str | None, int | None, int | None, str | None]:
        """解析视频消息 XML。

        Returns:
            (len_bytes, cdn_video_url, play_length_sec, raw_len_bytes, cdn_raw_video_url)
        """

        try:
            root = eT.fromstring(xml_text)
        except Exception:
            return None, None, None, None, None
        videomsg = root.find(".//videomsg")
        if videomsg is None:
            return None, None, None, None, None

        total_len = cls._parse_int(videomsg.get("length"))
        cdn_url = videomsg.get("cdnvideourl")
        play_len = cls._parse_int(videomsg.get("playlength"))

        raw_len = cls._parse_int(videomsg.get("rawlength"))
        cdn_raw_url = videomsg.get("cdnrawvideourl")

        return (
            total_len if (total_len and total_len > 0) else None,
            (cdn_url.strip() if isinstance(cdn_url, str) and cdn_url.strip() else None),
            play_len if (play_len and play_len > 0) else None,
            raw_len if (raw_len and raw_len > 0) else None,
            (cdn_raw_url.strip() if isinstance(cdn_raw_url, str) and cdn_raw_url.strip() else None),
        )

    @classmethod
    def _parse_cdn_image_params_from_xml(cls, xml_text: str) -> tuple[str | None, str | None]:
        """从图片 XML 解析 CdnDownloadImage 所需参数。

        FileAesKey: <img aeskey="...">
        FileNo: 优先取 cdnbigimgurl/cdnmidimgurl/cdnthumburl。
        - 若是 http(s) URL：取倒数第二段
        - 否则：直接使用该字段字符串（很多实现就是一个长 ID）
        """

        try:
            root = eT.fromstring(xml_text)
        except Exception:
            return None, None
        img = root.find(".//img")
        if img is None:
            return None, None

        aes_key = img.get("aeskey") or img.get("cdnthumbaeskey")
        if isinstance(aes_key, str) and aes_key.strip():
            aes_key = aes_key.strip()
        else:
            aes_key = None

        raw = img.get("cdnbigimgurl") or img.get("cdnmidimgurl") or img.get("cdnthumburl")
        if not isinstance(raw, str) or not raw.strip():
            return None, aes_key
        raw = raw.strip()

        if raw.startswith("http://") or raw.startswith("https://"):
            parts = [p for p in raw.split("/") if p]
            file_no = parts[-2] if len(parts) >= 2 else None
        else:
            file_no = raw

        return file_no, aes_key

    async def _try_build_image_component(
        self,
        *,
        raw_msg: Dict[str, Any],
        from_user: str,
        to_user: str,
        payload_content: str,
    ) -> Image | None:
        msg_id = raw_msg.get("MsgId")
        if not isinstance(msg_id, int):
            return None

        def _media_dir() -> str:
            temp_dir = os.path.join(get_astrbot_data_path(), "temp")
            day = time.strftime("%Y%m%d")
            origin = _safe_path_part(from_user)
            out_dir = os.path.join(temp_dir, "wxhttp_media", origin, day, "images")
            os.makedirs(out_dir, exist_ok=True)
            return out_dir

        async def _bytes_to_image_component(image_bytes: bytes) -> Image | None:
            if not image_bytes:
                return None
            ext = _detect_image_ext(image_bytes)
            file_path = os.path.join(_media_dir(), f"wxhttp_image_{msg_id}.{ext}")
            try:
                await asyncio.to_thread(self._write_bytes, file_path, image_bytes)
            except Exception as e:
                logger.debug(f"[wxhttp] write image file failed {file_path}: {e}")
                return None
            try:
                img = Image.fromFileSystem(file_path)
                
                # 尝试将图片转为公网 URL（给智谱等仅接受 URL 的 provider 使用）
                # 如果 callback_api_base 未配置，则回退到本地路径（provider 会转 base64）
                try:
                    public_url = await img.register_to_file_service()
                    logger.info(f"[webot] 图片已生成公网链接: {public_url}")
                    # 改用 URL 形式的 Image 组件，智谱等 provider 可以直接使用
                    return Image.fromURL(public_url, path=file_path)
                except Exception as url_err:
                    logger.debug(f"[wxhttp] 无法生成图片公网 URL（{url_err}），将使用本地路径")
                    # 回退到本地路径（OpenAI 等支持 base64 的 provider 仍可用）
                    return img
            except Exception:
                return None

        # 1) 优先：CDN 下载（不依赖 total_len）
        file_no, aes_key = self._parse_cdn_image_params_from_xml(payload_content)
        if file_no and aes_key:
            try:
                cdn_resp = await self._client.cdn_download_image(
                    wxid=self._self_wxid,
                    file_no=file_no,
                    file_aes_key=aes_key,
                )
                if self._resp_ok(cdn_resp):
                    data = cdn_resp.get("Data")
                    if isinstance(data, dict):
                        img_b64 = data.get("Image")
                        if isinstance(img_b64, str) and img_b64.strip():
                            try:
                                return await _bytes_to_image_component(
                                    base64.b64decode(img_b64.strip(), validate=False),
                                )
                            except Exception as e:
                                logger.debug(f"[wxhttp] decode cdn image base64 failed msg_id={msg_id}: {e}")
            except Exception as e:
                logger.debug(f"[wxhttp] cdn_download_image failed msg_id={msg_id}: {e}")

        # 2) 分片下载：需要能解析到 total_len
        total_len = self._parse_image_total_len_from_xml(payload_content)
        if total_len:
            # 按下载指南：ToWxid 统一传消息来源（FromUserName）
            to_wxid = from_user

            chunk_size = 65536
            total_len_i = int(total_len)
            start_pos = 0
            merged = bytearray()

            while start_pos < total_len_i:
                part_len = min(chunk_size, total_len_i - start_pos)
                try:
                    resp = await self._client.download_img(
                        wxid=self._self_wxid,
                        to_wxid=to_wxid,
                        msg_id=msg_id,
                        data_len=total_len_i,
                        compress_type=0,
                        section_start_pos=start_pos,
                        section_data_len=part_len,
                    )
                except Exception as e:
                    logger.debug(
                        f"[wxhttp] download_img failed (ToWxid={to_wxid}) msg_id={msg_id} start={start_pos}: {e}",
                    )
                    break

                if not self._resp_ok(resp):
                    break

                chunk_b64 = self._extract_download_chunk_b64(resp)
                if not chunk_b64:
                    # 兜底：保留旧路径解析，便于快速定位返回结构差异
                    chunk_b64 = self._extract_base64_payload(resp)
                if not chunk_b64:
                    logger.debug(
                        f"[wxhttp] download_img missing chunk buffer msg_id={msg_id} start={start_pos}",
                    )
                    break

                try:
                    merged.extend(base64.b64decode(chunk_b64, validate=False))
                except Exception as e:
                    logger.debug(
                        f"[wxhttp] decode img chunk base64 failed msg_id={msg_id} start={start_pos}: {e}",
                    )
                    break

                start_pos += part_len

            if merged:
                built = await _bytes_to_image_component(bytes(merged))
                if built is not None:
                    return built
        else:
            logger.debug(f"[wxhttp] image xml missing length, MsgId={msg_id}")

        # 3) 最后兜底：直接用 Sync 自带缩略图（ImgBuf.buffer）
        thumb_b64 = _safe_get(raw_msg, "ImgBuf", "buffer")
        if isinstance(thumb_b64, str) and thumb_b64.strip():
            try:
                return await _bytes_to_image_component(
                    base64.b64decode(thumb_b64.strip(), validate=False),
                )
            except Exception as e:
                logger.debug(f"[wxhttp] decode ImgBuf thumbnail base64 failed msg_id={msg_id}: {e}")
                return None

        return None

    async def _try_build_record_component(
        self,
        *,
        raw_msg: Dict[str, Any],
        from_user: str,
        new_msg_id: int | None,
        payload_content: str,
    ) -> Record | None:
        msg_id = raw_msg.get("MsgId")
        if not isinstance(msg_id, int):
            return None

        # 优先使用 Sync 自带的语音数据（若存在），避免额外下载
        img_buf_b64 = _safe_get(raw_msg, "ImgBuf", "buffer")
        if isinstance(img_buf_b64, str) and img_buf_b64.strip():
            try:
                voice_bytes = base64.b64decode(img_buf_b64.strip(), validate=False)
                temp_dir = os.path.join(
                    get_astrbot_data_path(),
                    "temp",
                    "wxhttp_media",
                    _safe_path_part(from_user),
                    time.strftime("%Y%m%d"),
                    "records",
                )
                os.makedirs(temp_dir, exist_ok=True)
                file_path = os.path.join(temp_dir, f"wxhttp_voice_{msg_id}.silk")
                await asyncio.to_thread(self._write_bytes, file_path, voice_bytes)
                return Record(file=file_path, url=file_path)
            except Exception as e:
                logger.debug(f"[wxhttp] decode/write ImgBuf voice failed msg_id={msg_id}: {e}")

        bufid, length = self._parse_voice_meta_from_xml(payload_content)
        if bufid == "0":
            bufid = None
        if not bufid and new_msg_id is not None:
            # 按下载指南：Bufid 很多情况下等于 NewMsgId
            bufid = str(new_msg_id)
        if not length:
            img_len = _safe_get(raw_msg, "ImgBuf", "iLen")
            if isinstance(img_len, int) and img_len > 0:
                length = img_len
        if not bufid or not length:
            logger.debug(f"[wxhttp] voice xml missing bufid/length, MsgId={msg_id} NewMsgId={new_msg_id}")
            return None

        try:
            resp = await self._client.download_voice(
                wxid=self._self_wxid,
                from_user_name=from_user,
                msg_id=msg_id,
                bufid=bufid,
                length=length,
            )
        except Exception as e:
            logger.debug(f"[wxhttp] download_voice failed msg_id={msg_id}: {e}")
            return None

        if not self._resp_ok(resp):
            return None

        b64 = self._extract_download_chunk_b64(resp)
        if not b64:
            b64 = self._extract_base64_payload(resp)
        if not b64:
            return None

        try:
            voice_bytes = base64.b64decode(b64, validate=False)
        except Exception as e:
            logger.debug(f"[wxhttp] decode voice base64 failed msg_id={msg_id}: {e}")
            return None

        temp_dir = os.path.join(
            get_astrbot_data_path(),
            "temp",
            "wxhttp_media",
            _safe_path_part(from_user),
            time.strftime("%Y%m%d"),
            "records",
        )
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"wxhttp_voice_{msg_id}.silk")

        try:
            await asyncio.to_thread(self._write_bytes, file_path, voice_bytes)
        except Exception as e:
            logger.debug(f"[wxhttp] write voice file failed {file_path}: {e}")
            return None

        return Record(file=file_path, url=file_path)

    async def _try_build_video_component(
        self,
        *,
        raw_msg: Dict[str, Any],
        from_user: str,
        payload_content: str,
    ) -> Video | None:
        msg_id = raw_msg.get("MsgId")
        if not isinstance(msg_id, int):
            return None

        total_len, cdn_url, _play_len, raw_len, cdn_raw_url = self._parse_video_meta_from_xml(payload_content)

        # 超大文件优先：如果 CDN 字段本身就是可直连 URL，直接交给 Video(URL)
        for candidate_url in (cdn_raw_url, cdn_url):
            if isinstance(candidate_url, str) and (
                candidate_url.startswith("http://") or candidate_url.startswith("https://")
            ):
                try:
                    return Video.fromURL(candidate_url)
                except Exception:
                    pass

        if not total_len and not raw_len:
            return None

        temp_dir = os.path.join(
            get_astrbot_data_path(),
            "temp",
            "wxhttp_media",
            _safe_path_part(from_user),
            time.strftime("%Y%m%d"),
            "videos",
        )
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"wxhttp_video_{msg_id}.mp4")

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

        async def download_to_file(data_len: int) -> bool:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

            chunk_size = 65536
            total_len_i = int(data_len)
            start_pos = 0
            while start_pos < total_len_i:
                part_len = min(chunk_size, total_len_i - start_pos)
                try:
                    resp = await self._client.download_video(
                        wxid=self._self_wxid,
                        msg_id=msg_id,
                        data_len=total_len_i,
                        compress_type=0,
                        section_start_pos=start_pos,
                        section_data_len=part_len,
                        to_wxid=from_user,
                    )
                except Exception as e:
                    logger.debug(f"[wxhttp] download_video failed msg_id={msg_id} start={start_pos}: {e}")
                    return False

                if not self._resp_ok(resp):
                    return False

                chunk_b64 = self._extract_download_chunk_b64(resp)
                if not chunk_b64:
                    chunk_b64 = self._extract_base64_payload(resp)
                if not chunk_b64:
                    logger.debug(
                        f"[wxhttp] download_video missing chunk buffer msg_id={msg_id} start={start_pos}",
                    )
                    return False

                try:
                    chunk = base64.b64decode(chunk_b64, validate=False)
                except Exception as e:
                    logger.debug(
                        f"[wxhttp] decode video chunk base64 failed msg_id={msg_id} start={start_pos}: {e}",
                    )
                    return False

                try:
                    with open(file_path, "ab") as f:
                        f.write(chunk)
                except Exception as e:
                    logger.debug(f"[wxhttp] write video file failed {file_path}: {e}")
                    return False

                start_pos += part_len

            return True

        # 按指南优先用 length；若失败且存在 rawlength，则再尝试 rawlength
        tried: list[int] = []
        for cand in (total_len, raw_len):
            if not cand or cand in tried:
                continue
            tried.append(int(cand))
            ok = await download_to_file(int(cand))
            if ok:
                try:
                    return Video.fromFileSystem(file_path)
                except Exception:
                    return None

        return None

    @staticmethod
    def _write_bytes(path: str, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    async def handle_msg(self, message: AstrBotMessage):
        event = WxHttpMessageEvent(
            message_str=message.message_str,
            message_obj=message,
            platform_meta=self.meta(),
            session_id=message.session_id,
            client=self._client,
            self_wxid=self._self_wxid,
            reply_with_mention=bool(self.settings.get("reply_with_mention", False)),
            reply_with_quote=bool(self.settings.get("reply_with_quote", False)),
            nickname_resolver=self._get_chatroom_member_nickname,
        )
        self.commit_event(event)
