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
    # API 请求队列化配置（sync 接口不受影响）
    request_delay_min: float = 0.0
    request_delay_max: float = 0.0
    
    def __post_init__(self):
        # API 请求队列（不包括 sync）
        self._request_queue: asyncio.Queue = asyncio.Queue()
        self._queue_worker_started = False
        self._request_counter = 0

    def _url(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        p = path if path.startswith("/") else f"/{path}"
        return f"{base}{p}"

    def _post_json_sync(self, url: str, payload: Dict[str, Any], api_name: str = "API") -> Dict[str, Any]:
        import time
        start_time = time.time()
        
        # 记录请求开始
        payload_str = json.dumps(payload, ensure_ascii=False)
        logger.debug(f"[wxhttp] → {api_name} 请求: {payload_str[:200]}..." if len(payload_str) > 200 else f"[wxhttp] → {api_name} 请求: {payload_str}")
        
        data = payload_str.encode("utf-8")
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
            elapsed = time.time() - start_time
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            logger.error(f"[wxhttp] ✗ {api_name} HTTP错误 {e.code} (耗时 {elapsed:.2f}s): {body[:200]}")
            raise RuntimeError(f"HTTP {e.code} calling {url}: {body}") from e
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[wxhttp] ✗ {api_name} 请求失败 (耗时 {elapsed:.2f}s): {e}")
            raise RuntimeError(f"Failed calling {url}: {e}") from e

        try:
            result = json.loads(raw)
            elapsed = time.time() - start_time
            
            # 记录响应结果
            code = result.get("Code", "N/A")
            success = result.get("Success", False)
            msg = result.get("Message", "")
            status = "✓" if (success or code in (0, 200)) else "⚠"
            logger.info(f"[wxhttp] {status} {api_name} ← Code={code} {msg} (耗时 {elapsed:.2f}s)")
            
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[wxhttp] ✗ {api_name} JSON解析失败 (耗时 {elapsed:.2f}s): {raw[:200]}")
            raise RuntimeError(f"Invalid JSON from {url}: {raw[:500]}") from e

    async def _queue_worker(self):
        """后台队列工作线程，处理所有非 sync 的 API 请求"""
        import random
        logger.info(f"[wxhttp] 请求队列工作线程启动（延时: {self.request_delay_min}-{self.request_delay_max}s）")
        
        while True:
            try:
                url, payload, api_name, future = await self._request_queue.get()
                
                # 随机延时（模拟真人操作）
                if self.request_delay_max > 0:
                    delay = random.uniform(self.request_delay_min, self.request_delay_max)
                    logger.debug(f"[wxhttp] 队列延时 {delay:.2f}s 后发送 {api_name}")
                    await asyncio.sleep(delay)
                
                # 执行请求
                try:
                    result = await asyncio.to_thread(self._post_json_sync, url, payload, api_name)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self._request_queue.task_done()
            except Exception as e:
                logger.exception(f"[wxhttp] 队列工作线程异常: {e}")
    
    async def _ensure_queue_worker(self):
        """确保队列工作线程已启动"""
        if not self._queue_worker_started:
            self._queue_worker_started = True
            asyncio.create_task(self._queue_worker())
    
    async def _request_via_queue(self, path: str, payload: Dict[str, Any], api_name: str) -> Dict[str, Any]:
        """通过队列发送请求（带延时控制）"""
        await self._ensure_queue_worker()
        
        url = self._url(path)
        future = asyncio.Future()
        await self._request_queue.put((url, payload, api_name, future))
        
        return await future
    
    async def post_json(self, path: str, payload: Dict[str, Any], api_name: str = "API", bypass_queue: bool = False) -> Dict[str, Any]:
        """发送 JSON POST 请求
        
        Args:
            path: API 路径
            payload: 请求参数
            api_name: API 名称（用于日志）
            bypass_queue: 是否绕过队列（sync 接口使用）
        """
        if bypass_queue:
            # sync 接口不走队列，直接调用
            url = self._url(path)
            return await asyncio.to_thread(self._post_json_sync, url, payload, api_name)
        else:
            # 其他接口走队列
            return await self._request_via_queue(path, payload, api_name)

    async def sync(self, *, wxid: str, scene: int = 0, synckey: str = "") -> Dict[str, Any]:
        return await self.post_json(
            "/Msg/Sync",
            {
                "Scene": scene,
                "Synckey": synckey,
                "Wxid": wxid,
            },
            api_name="Msg/Sync",
            bypass_queue=True,  # sync 接口不走队列
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
        return await self.post_json(
            "/Msg/SendTxt",
            {
                "At": at,
                "Content": content,
                "ToWxid": to_wxid,
                "Type": type_,
                "Wxid": wxid,
            },
            api_name="Msg/SendTxt",
        )

    async def upload_img(
        self,
        *,
        wxid: str,
        to_wxid: str,
        base64_data: str,
    ) -> Dict[str, Any]:
        return await self.post_json(
            "/Msg/UploadImg",
            {
                "Base64": base64_data,
                "ToWxid": to_wxid,
                "Wxid": wxid,
            },
            api_name="Msg/UploadImg",
        )

    async def send_voice(
        self,
        *,
        wxid: str,
        to_wxid: str,
        base64_data: str,
        type_: int = 4,
        voice_time_ms: int = 1000,
    ) -> Dict[str, Any]:
        return await self.post_json(
            "/Msg/SendVoice",
            {
                "Base64": base64_data,
                "ToWxid": to_wxid,
                "Type": int(type_),
                "VoiceTime": int(voice_time_ms),
                "Wxid": wxid,
            },
            api_name="Msg/SendVoice",
        )

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
            api_name="Tools/DownloadImg",
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
            api_name="Tools/CdnDownloadImage",
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
            api_name="Tools/DownloadVoice",
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
        return await self.post_json("/Tools/DownloadVideo", payload, api_name="Tools/DownloadVideo")

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
            api_name="Group/GetChatRoomMemberDetail",
        )
