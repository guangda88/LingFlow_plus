from __future__ import annotations
"""GLM API 客户端 — Token 池轮转 + 模型降级 + 配额感知

灵字辈统一 LLM 调用模块，支持:
- 3 个 GLM Key + DeepSeek 后备的 Token 池自动轮转
- 模型降级链: glm-5.1 → glm-5-turbo → glm-5 → glm-4.7 → glm-4.7-flash → ... → deepseek-chat
- 配额耗尽自动检测 (429/1113/余额不足) 并切换
- 5 小时配额窗口感知
- 与 TokenQuotaManager 集成

用法:
    from lingflow_plus.llm_client import call_glm, GLMClient

    # 便捷函数
    resp = call_glm([{"role": "user", "content": "你好"}])

    # 客户端实例
    client = GLMClient()
    resp = client.chat("写一个快速排序")
"""

import importlib.util
import logging
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
_GLM_CODING_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com"

_RESET_ANCHOR_HOUR = 15
_RESET_ANCHOR_MIN = 57
_RESET_INTERVAL = 5 * 3600

GLM_CODING_PLAN_MODELS = [
    "glm-5.1",
    "glm-5-turbo",
    "glm-5",
    "glm-4.7",
    "glm-4.7-flash",
    "glm-4.6",
    "glm-4.6v",
    "glm-4.5",
    "glm-4.5-air",
    "glm-4.5v",
]

_PRIMARY_MODEL = "glm-5.1"
_FALLBACK_MODELS = [m for m in GLM_CODING_PLAN_MODELS if m != _PRIMARY_MODEL]
_DEEPSEEK_MODEL = "deepseek-chat"

_KEY_PRIORITY = [
    ("GLM_CODING_PLAN_KEY", _GLM_CODING_BASE_URL, _PRIMARY_MODEL),
    ("GLM_47_CC_KEY", _GLM_BASE_URL, "glm-4.7"),
    ("GLM_API_KEY", _GLM_BASE_URL, "glm-4.5-air"),
    ("DEEPSEEK_API_KEY", _DEEPSEEK_BASE_URL, _DEEPSEEK_MODEL),
]


@dataclass
class KeySlot:
    """Token 池中的一个 Key 槽位"""
    name: str
    key: str
    base_url: str
    model: str
    exhausted: bool = False
    reset_at: float = 0.0
    call_count: int = 0
    total_tokens: int = 0

    @property
    def is_available(self) -> bool:
        if not self.exhausted:
            return True
        if time.time() >= self.reset_at:
            self.exhausted = False
            self.reset_at = 0.0
            return True
        return False

    def mark_exhausted(self, reset_time: float) -> None:
        self.exhausted = True
        self.reset_at = reset_time


class TokenPool:
    """Token 池 — 多 Key 自动轮转

    按优先级加载 GLM_CODING_PLAN_KEY → GLM_47_CC_KEY → GLM_API_KEY → DEEPSEEK_API_KEY，
    配额耗尽时自动切换到下一个可用 Key。
    """

    def __init__(self, keys: Optional[Dict[str, str]] = None):
        self._slots: List[KeySlot] = []
        self._lock = threading.RLock()
        self._load_keys(keys)

    def _load_keys(self, keys: Optional[Dict[str, str]] = None) -> None:
        available = keys or self._load_from_store()
        for name, base_url, model in _KEY_PRIORITY:
            val = available.get(name)
            if val:
                self._slots.append(KeySlot(name=name, key=val, base_url=base_url, model=model))
        if not self._slots:
            logger.warning("TokenPool: 无可用 API Key")

    def _load_from_store(self) -> Dict[str, str]:
        try:
            spec = importlib.util.spec_from_file_location(
                "ling_key_store", Path.home() / ".ling_lib" / "ling_key_store.py"
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return {
                    "GLM_CODING_PLAN_KEY": mod.get_key("GLM_CODING_PLAN_KEY") or "",
                    "GLM_47_CC_KEY": mod.get_key("GLM_47_CC_KEY") or "",
                    "GLM_API_KEY": mod.get_key("GLM_API_KEY") or "",
                    "DEEPSEEK_API_KEY": mod.get_key("DEEPSEEK_API_KEY") or "",
                }
        except Exception as e:
            logger.debug(f"ling_key_store 加载失败: {e}")
        return {}

    def acquire(self) -> Optional[KeySlot]:
        """获取当前可用的 Key 槽位"""
        with self._lock:
            for slot in self._slots:
                if slot.is_available:
                    return slot
        return None

    def report_exhausted(self, slot: KeySlot) -> None:
        """报告某个 Key 配额耗尽"""
        with self._lock:
            slot.mark_exhausted(_next_reset_time())
            logger.warning(f"Key [{slot.name}] 配额耗尽，切换下一个")

    def report_success(self, slot: KeySlot, tokens: int = 0) -> None:
        """报告调用成功"""
        with self._lock:
            slot.call_count += 1
            slot.total_tokens += tokens

    @property
    def size(self) -> int:
        return len(self._slots)

    @property
    def available_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._slots if s.is_available)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            slots = []
            for s in self._slots:
                slots.append({
                    "name": s.name,
                    "available": s.is_available,
                    "model": s.model,
                    "calls": s.call_count,
                    "tokens": s.total_tokens,
                    "resets_in": max(0, int(s.reset_at - time.time())) if s.exhausted else 0,
                })
            return {"total": len(slots), "available": self.available_count, "slots": slots}


def _next_reset_time() -> float:
    now = datetime.now()
    anchor = now.replace(hour=_RESET_ANCHOR_HOUR, minute=_RESET_ANCHOR_MIN, second=0, microsecond=0)
    anchor_ts = anchor.timestamp()
    intervals_ago = int((now.timestamp() - anchor_ts) / _RESET_INTERVAL)
    last_reset = anchor_ts + intervals_ago * _RESET_INTERVAL
    if last_reset > now.timestamp():
        last_reset -= _RESET_INTERVAL
    return last_reset + _RESET_INTERVAL


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc)
    return any(t in msg for t in ("1113", "余额不足", "429", "rate_limit", "Rate limit"))


class GLMClient:
    """GLM API 客户端 — Token 池轮转 + 模型降级

    示例:
        client = GLMClient()
        result = client.chat("你好")
        print(result.content)
    """

    def __init__(
        self,
        pool: Optional[TokenPool] = None,
        max_retries: int = 3,
        timeout: int = 60,
        model: Optional[str] = None,
    ):
        self._pool = pool or TokenPool()
        self._max_retries = max_retries
        self._timeout = timeout
        self._default_model = model
        self._quota_manager: Optional[Any] = None
        self._usage_lock = threading.Lock()
        self._usage: Dict[str, Dict[str, int]] = {}

    def set_quota_manager(self, manager: Any) -> None:
        self._quota_manager = manager

    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        project: Optional[str] = None,
    ) -> "LLMResponse":
        """发送聊天请求

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            model: 指定模型 (覆盖默认)
            project: 项目名 (用于配额追踪)

        Returns:
            LLMResponse
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        return self.call(messages, model=model, project=project)

    def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        project: Optional[str] = None,
    ) -> "LLMResponse":
        """发送消息列表到 LLM

        Args:
            messages: OpenAI 格式消息列表
            model: 指定模型
            project: 项目名

        Returns:
            LLMResponse
        """
        from openai import OpenAI

        target_model = model or self._default_model
        attempts = 0
        tried_keys: set = set()

        while attempts < self._max_retries:
            slot = self._pool.acquire()
            if slot is None or slot.name in tried_keys:
                if slot is None:
                    break
                tried_keys.add(slot.name)
                continue

            use_model = target_model or slot.model
            try:
                client = OpenAI(
                    api_key=slot.key,
                    base_url=slot.base_url,
                    max_retries=0,
                    timeout=self._timeout,
                )
                resp = client.chat.completions.create(
                    model=use_model,
                    messages=messages,
                )
                tokens = getattr(getattr(resp, "usage", None), "total_tokens", 0) or 0
                self._pool.report_success(slot, tokens)
                self._track_usage(use_model, slot.name, tokens)
                if project and self._quota_manager:
                    self._quota_manager.consume(project, tokens)
                content = resp.choices[0].message.content if resp.choices else ""
                return LLMResponse(
                    content=content,
                    model=use_model,
                    key_name=slot.name,
                    tokens=tokens,
                    raw=resp,
                )
            except Exception as e:
                attempts += 1
                if _is_quota_error(e):
                    self._pool.report_exhausted(slot)
                    tried_keys.add(slot.name)
                    logger.info(f"[attempt {attempts}] Key {slot.name} 配额耗尽，轮转下一个")
                    continue
                logger.error(f"LLM 调用异常 (key={slot.name}, model={use_model}): {e}")
                raise

        raise RuntimeError(f"所有 API Key 均不可用 (尝试 {attempts} 次)")

    def _track_usage(self, model: str, key_name: str, tokens: int) -> None:
        with self._usage_lock:
            key = f"{key_name}/{model}"
            if key not in self._usage:
                self._usage[key] = {"calls": 0, "tokens": 0}
            self._usage[key]["calls"] += 1
            self._usage[key]["tokens"] += tokens

    def get_status(self) -> Dict[str, Any]:
        return {
            "pool": self._pool.get_status(),
            "usage": dict(self._usage),
        }


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str = ""
    key_name: str = ""
    tokens: int = 0
    raw: Any = None

    def __str__(self) -> str:
        return self.content


_default_client: Optional[GLMClient] = None
_client_lock = threading.Lock()


def _get_default_client() -> GLMClient:
    global _default_client
    if _default_client is None:
        with _client_lock:
            if _default_client is None:
                _default_client = GLMClient()
    return _default_client


def call_glm(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> LLMResponse:
    """便捷函数 — 调用 GLM API

    Args:
        messages: OpenAI 格式消息列表，或传入单个字符串
        model: 可选指定模型
        system_prompt: 可选系统提示词

    Returns:
        LLMResponse

    示例:
        resp = call_glm([{"role": "user", "content": "你好"}])
        print(resp.content)
    """
    client = _get_default_client()
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages
    return client.call(messages, model=model)


def ask(question: str, model: Optional[str] = None) -> str:
    """最简接口 — 问一个问题，返回文本

    Args:
        question: 问题文本
        model: 可选模型

    Returns:
        回答文本
    """
    client = _get_default_client()
    resp = client.chat(question, model=model)
    return resp.content
