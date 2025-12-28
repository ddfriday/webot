from __future__ import annotations

from collections.abc import Awaitable, Callable

from astrbot import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Image, Plain, Record
from astrbot.api.platform import AstrBotMessage, MessageType, PlatformMetadata
from astrbot.core.utils.tencent_record_helper import audio_to_tencent_silk_base64

from .wxhttp_client import WxHttpClient


class WxHttpMessageEvent(AstrMessageEvent):
    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
        client: WxHttpClient,
        self_wxid: str,
        reply_with_mention: bool = False,
        reply_with_quote: bool = False,
        nickname_resolver: Callable[[str, str], Awaitable[str]] | None = None,
    ):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self._client = client
        self._self_wxid = self_wxid
        self._reply_with_mention = reply_with_mention
        self._reply_with_quote = reply_with_quote
        self._nickname_resolver = nickname_resolver

    async def send(self, message: MessageChain):
        # 支持：文本、图片、语音
        is_group = bool(getattr(self.message_obj, "group_id", None)) or (
            getattr(self.message_obj, "type", None) == MessageType.GROUP_MESSAGE
        )

        quote_prefix = ""
        if is_group and self._reply_with_quote:
            # 平台侧没有真正的“引用发送”接口时，做一个简单摘要即可。
            sender_nick = (
                getattr(getattr(self.message_obj, "sender", None), "nickname", "")
                or ""
            )
            origin = (getattr(self.message_obj, "message_str", "") or "").strip()
            if origin:
                if len(origin) > 80:
                    origin = origin[:80] + "…"
                quote_prefix = f"> {sender_nick or '对方'}: {origin}\n"

        for item in message.chain:
            if isinstance(item, Plain) and item.text:
                at = ""
                content = quote_prefix + item.text
                if is_group and self._reply_with_mention:
                    group_id = getattr(self.message_obj, "group_id", "") or ""
                    sender_id = (
                        getattr(getattr(self.message_obj, "sender", None), "user_id", "")
                        or ""
                    )
                    sender_nick = (
                        getattr(getattr(self.message_obj, "sender", None), "nickname", "")
                        or ""
                    )
                    if group_id and sender_id:
                        at = sender_id
                        if self._nickname_resolver:
                            try:
                                resolved = await self._nickname_resolver(
                                    group_id,
                                    sender_id,
                                )
                                if resolved:
                                    sender_nick = resolved
                            except Exception as e:
                                logger.debug(f"[wxhttp] resolve @nickname failed: {e}")
                        if sender_nick:
                            content = f"@{sender_nick} {content}"

                logger.info(
                    f"[wxhttp] event.send(text) -> {self.session_id} (len={len(content)})",
                )
                await self._client.send_txt(
                    wxid=self._self_wxid,
                    to_wxid=self.session_id,
                    content=content,
                    at=at,
                    type_=1,
                )

            elif isinstance(item, Image):
                try:
                    b64 = await item.convert_to_base64()
                except Exception as e:
                    logger.error(f"[wxhttp] convert image to base64 failed: {e}")
                    continue
                await self._client.upload_img(
                    wxid=self._self_wxid,
                    to_wxid=self.session_id,
                    base64_data=b64,
                )

            elif isinstance(item, Record):
                try:
                    record_path = await item.convert_to_file_path()
                    b64, duration_sec = await audio_to_tencent_silk_base64(record_path)
                    voice_time_ms = max(1000, int(float(duration_sec) * 1000))
                except Exception as e:
                    logger.error(f"[wxhttp] convert record failed: {e}")
                    continue
                await self._client.send_voice(
                    wxid=self._self_wxid,
                    to_wxid=self.session_id,
                    base64_data=b64,
                    type_=4,
                    voice_time_ms=voice_time_ms,
                )

        await super().send(message)
