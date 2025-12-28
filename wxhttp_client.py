from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from astrbot import logger


@dataclass
class WxHttpClient:
    base_url: str
    timeout_sec: float = 60.0

    def _url(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        p = path if path.startswith("/") else f"/{path}"
        return f"{base}{p}"

    def _post_json_sync(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise RuntimeError(f"HTTP {e.code} calling {url}: {body}") from e
        except Exception as e:
            raise RuntimeError(f"Failed calling {url}: {e}") from e

        try:
            return json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"Invalid JSON from {url}: {raw[:500]}") from e

    async def post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._url(path)
        return await asyncio.to_thread(self._post_json_sync, url, payload)

    async def sync(self, *, wxid: str, scene: int = 0, synckey: str = "") -> Dict[str, Any]:
        return await self.post_json(
            "/Msg/Sync",
            {
                "Scene": scene,
                "Synckey": synckey,
                "Wxid": wxid,
            },
        )

    async def send_txt(
        self,
        *,
        wxid: str,
        to_wxid: str,
        content: str,
        at: str = "",
        type_: int = 1,
    ) -> Dict[str, Any]:
        logger.info(f"[wxhttp] SendTxt -> {to_wxid} (len={len(content)})")
        resp = await self.post_json(
            "/Msg/SendTxt",
            {
                "At": at,
                "Content": content,
                "ToWxid": to_wxid,
                "Type": type_,
                "Wxid": wxid,
            },
        )
        code = resp.get("Code")
        msg = resp.get("Message")
        logger.info(f"[wxhttp] SendTxt <- Code={code} Message={msg}")
        return resp

    async def upload_img(
        self,
        *,
        wxid: str,
        to_wxid: str,
        base64_data: str,
    ) -> Dict[str, Any]:
        logger.info(f"[wxhttp] UploadImg -> {to_wxid} (b64_len={len(base64_data)})")
        resp = await self.post_json(
            "/Msg/UploadImg",
            {
                "Base64": base64_data,
                "ToWxid": to_wxid,
                "Wxid": wxid,
            },
        )
        logger.info(
            f"[wxhttp] UploadImg <- Code={resp.get('Code')} Message={resp.get('Message')}",
        )
        return resp

    async def send_voice(
        self,
        *,
        wxid: str,
        to_wxid: str,
        base64_data: str,
        type_: int = 4,
        voice_time_ms: int = 1000,
    ) -> Dict[str, Any]:
        logger.info(
            f"[wxhttp] SendVoice -> {to_wxid} (b64_len={len(base64_data)} time_ms={voice_time_ms} type={type_})",
        )
        resp = await self.post_json(
            "/Msg/SendVoice",
            {
                "Base64": base64_data,
                "ToWxid": to_wxid,
                "Type": int(type_),
                "VoiceTime": int(voice_time_ms),
                "Wxid": wxid,
            },
        )
        logger.info(
            f"[wxhttp] SendVoice <- Code={resp.get('Code')} Message={resp.get('Message')}",
        )
        return resp

    async def download_img(
        self,
        *,
        wxid: str,
        to_wxid: str,
        msg_id: int,
        data_len: int,
        compress_type: int = 0,
        section_start_pos: int = 0,
        section_data_len: int = 61440,
    ) -> Dict[str, Any]:
        return await self.post_json(
            "/Tools/DownloadImg",
            {
                "CompressType": int(compress_type),
                "DataLen": int(data_len),
                "MsgId": int(msg_id),
                "Section": {
                    "DataLen": int(section_data_len),
                    "StartPos": int(section_start_pos),
                },
                "ToWxid": to_wxid,
                "Wxid": wxid,
            },
        )

    async def cdn_download_image(
        self,
        *,
        wxid: str,
        file_no: str,
        file_aes_key: str,
    ) -> Dict[str, Any]:
        return await self.post_json(
            "/Tools/CdnDownloadImage",
            {
                "FileAesKey": file_aes_key,
                "FileNo": file_no,
                "Wxid": wxid,
            },
        )

    async def download_voice(
        self,
        *,
        wxid: str,
        from_user_name: str,
        msg_id: int,
        bufid: str,
        length: int,
    ) -> Dict[str, Any]:
        return await self.post_json(
            "/Tools/DownloadVoice",
            {
                "Bufid": bufid,
                "FromUserName": from_user_name,
                "Length": int(length),
                "MsgId": int(msg_id),
                "Wxid": wxid,
            },
        )

    async def download_video(
        self,
        *,
        wxid: str,
        msg_id: int,
        data_len: int,
        compress_type: int = 0,
        section_start_pos: int = 0,
        section_data_len: int = 65536,
        to_wxid: str | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "CompressType": int(compress_type),
            "DataLen": int(data_len),
            "MsgId": int(msg_id),
            "Section": {
                "DataLen": int(section_data_len),
                "StartPos": int(section_start_pos),
            },
            "Wxid": wxid,
        }
        # 文档提示“视频不需要 ToWxid”，但部分实现可能仍接受。
        if isinstance(to_wxid, str) and to_wxid:
            payload["ToWxid"] = to_wxid
        return await self.post_json("/Tools/DownloadVideo", payload)

    async def get_chatroom_member_detail(
        self,
        *,
        qid: str,
        wxid: str,
    ) -> Dict[str, Any]:
        """获取群成员详情。

        API doc: /Group/GetChatRoomMemberDetail
        payload: {"QID": "<chatroom@chatroom>", "Wxid": "<bot_wxid>"}
        """
        return await self.post_json(
            "/Group/GetChatRoomMemberDetail",
            {
                "QID": qid,
                "Wxid": wxid,
            },
        )
