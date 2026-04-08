from __future__ import annotations
"""llm_client 模块测试 — TokenPool 轮转、GLMClient 降级、配额感知"""

import time
from unittest.mock import MagicMock, patch

import pytest

from lingflow_plus.llm_client import (
    GLMClient,
    KeySlot,
    LLMResponse,
    TokenPool,
    _is_quota_error,
    _next_reset_time,
    ask,
    call_glm,
)


# ---------------------------------------------------------------------------
# KeySlot 单元测试
# ---------------------------------------------------------------------------


class TestKeySlot:
    def test_available_by_default(self):
        slot = KeySlot(name="test", key="k", base_url="http://x", model="m")
        assert slot.is_available is True
        assert slot.exhausted is False

    def test_mark_exhausted(self):
        slot = KeySlot(name="test", key="k", base_url="http://x", model="m")
        slot.mark_exhausted(time.time() + 3600)
        assert slot.is_available is False
        assert slot.exhausted is True

    def test_auto_recover_after_reset(self):
        slot = KeySlot(name="test", key="k", base_url="http://x", model="m")
        slot.mark_exhausted(time.time() - 1)
        assert slot.is_available is True
        assert slot.exhausted is False

    def test_call_count_tracking(self):
        slot = KeySlot(name="test", key="k", base_url="http://x", model="m")
        assert slot.call_count == 0
        assert slot.total_tokens == 0


# ---------------------------------------------------------------------------
# TokenPool 单元测试
# ---------------------------------------------------------------------------


class TestTokenPool:
    def _make_pool(self, n=3):
        keys = {}
        names = ["GLM_CODING_PLAN_KEY", "GLM_47_CC_KEY", "GLM_API_KEY", "DEEPSEEK_API_KEY"]
        for i in range(min(n, len(names))):
            keys[names[i]] = f"key-{i}"
        return TokenPool(keys=keys)

    def test_loads_keys(self):
        pool = self._make_pool(3)
        assert pool.size == 3
        assert pool.available_count == 3

    def test_acquire_returns_slot(self):
        pool = self._make_pool(2)
        slot = pool.acquire()
        assert slot is not None
        assert slot.key == "key-0"

    def test_acquire_skips_exhausted(self):
        pool = self._make_pool(3)
        s0 = pool._slots[0]
        s0.mark_exhausted(time.time() + 3600)
        slot = pool.acquire()
        assert slot is not None
        assert slot.name != s0.name

    def test_acquire_returns_none_if_all_exhausted(self):
        pool = self._make_pool(2)
        for s in pool._slots:
            s.mark_exhausted(time.time() + 3600)
        assert pool.acquire() is None

    def test_report_exhausted(self):
        pool = self._make_pool(3)
        slot = pool._slots[0]
        pool.report_exhausted(slot)
        assert not slot.is_available

    def test_report_success(self):
        pool = self._make_pool(1)
        slot = pool._slots[0]
        pool.report_success(slot, tokens=100)
        assert slot.call_count == 1
        assert slot.total_tokens == 100

    def test_get_status(self):
        pool = self._make_pool(2)
        status = pool.get_status()
        assert status["total"] == 2
        assert status["available"] == 2
        assert len(status["slots"]) == 2

    @patch.object(TokenPool, "_load_from_store", return_value={})
    def test_empty_keys_warning(self, mock_store):
        pool = TokenPool(keys={})
        assert pool.size == 0
        assert pool.acquire() is None

    def test_rotation_order(self):
        pool = self._make_pool(4)
        names = []
        for _ in range(4):
            slot = pool.acquire()
            names.append(slot.name)
            pool.report_exhausted(slot)
        assert names == ["GLM_CODING_PLAN_KEY", "GLM_47_CC_KEY", "GLM_API_KEY", "DEEPSEEK_API_KEY"]


# ---------------------------------------------------------------------------
# GLMClient Mock 测试 — mock openai.OpenAI (lazy import)
# ---------------------------------------------------------------------------


class TestGLMClient:
    def _mock_openai_response(self, content="hello", model="glm-4.7", tokens=50):
        usage = MagicMock()
        usage.total_tokens = tokens
        choice = MagicMock()
        choice.message.content = content
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        return resp

    def _make_client(self, n_keys=2):
        keys = {}
        names = ["GLM_CODING_PLAN_KEY", "GLM_47_CC_KEY", "GLM_API_KEY", "DEEPSEEK_API_KEY"]
        for i in range(min(n_keys, len(names))):
            keys[names[i]] = f"key-{i}"
        pool = TokenPool(keys=keys)
        return GLMClient(pool=pool)

    @patch("openai.OpenAI")
    def test_chat_success(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._mock_openai_response("你好世界")

        client = self._make_client(1)
        resp = client.chat("hello")
        assert isinstance(resp, LLMResponse)
        assert resp.content == "你好世界"
        assert resp.tokens == 50

    @patch("openai.OpenAI")
    def test_chat_with_system_prompt(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._mock_openai_response()

        client = self._make_client(1)
        resp = client.chat("hello", system_prompt="be concise")
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    @patch("openai.OpenAI")
    def test_call_uses_pool_key(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._mock_openai_response()

        client = self._make_client(1)
        resp = client.call([{"role": "user", "content": "hi"}])
        assert resp.key_name == "GLM_CODING_PLAN_KEY"

    @patch("openai.OpenAI")
    def test_rotation_on_quota_error(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        err = Exception("Error code: 1113, 额度不足")
        mock_client.chat.completions.create.side_effect = [
            err,
            self._mock_openai_response("fallback ok"),
        ]

        client = self._make_client(2)
        resp = client.chat("test")
        assert resp.content == "fallback ok"
        assert resp.key_name == "GLM_47_CC_KEY"

    @patch("openai.OpenAI")
    def test_rotation_on_429(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = [
            Exception("429 Rate limit exceeded"),
            self._mock_openai_response("ok"),
        ]

        client = self._make_client(2)
        resp = client.chat("test")
        assert resp.content == "ok"

    @patch("openai.OpenAI")
    def test_rotation_on_balance_error(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = [
            Exception("余额不足"),
            self._mock_openai_response("ok"),
        ]

        client = self._make_client(2)
        resp = client.chat("test")
        assert resp.content == "ok"

    @patch("openai.OpenAI")
    def test_all_keys_exhausted_raises(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = Exception("1113 exhausted")

        client = self._make_client(2)
        with pytest.raises(RuntimeError, match="所有 API Key 均不可用"):
            client.chat("test")

    @patch("openai.OpenAI")
    def test_non_quota_error_raises_immediately(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = ValueError("bad request")

        client = self._make_client(2)
        with pytest.raises(ValueError, match="bad request"):
            client.chat("test")

    @patch("openai.OpenAI")
    def test_model_override(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._mock_openai_response()

        client = self._make_client(1)
        resp = client.chat("hi", model="glm-4-flash")
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "glm-4-flash"

    @patch("openai.OpenAI")
    def test_quota_manager_integration(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._mock_openai_response(tokens=200)

        qm = MagicMock()
        client = self._make_client(1)
        client.set_quota_manager(qm)
        client.chat("test", project="proj-a")
        qm.consume.assert_called_once_with("proj-a", 200)

    @patch("openai.OpenAI")
    def test_get_status(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._mock_openai_response(tokens=42)

        client = self._make_client(1)
        client.chat("test")
        status = client.get_status()
        assert status["pool"]["total"] == 1
        assert len(status["usage"]) == 1


# ---------------------------------------------------------------------------
# _is_quota_error 单元测试
# ---------------------------------------------------------------------------


class TestIsQuotaError:
    def test_1113(self):
        assert _is_quota_error(Exception("Error code: 1113")) is True

    def test_balance_insufficient(self):
        assert _is_quota_error(Exception("余额不足")) is True

    def test_429(self):
        assert _is_quota_error(Exception("429 Too Many Requests")) is True

    def test_rate_limit(self):
        assert _is_quota_error(Exception("rate_limit exceeded")) is True

    def test_other_error(self):
        assert _is_quota_error(Exception("timeout")) is False

    def test_auth_error(self):
        assert _is_quota_error(Exception("401 Unauthorized")) is False


# ---------------------------------------------------------------------------
# LLMResponse 测试
# ---------------------------------------------------------------------------


class TestLLMResponse:
    def test_str_returns_content(self):
        r = LLMResponse(content="hello", model="glm-4.7", key_name="K", tokens=10)
        assert str(r) == "hello"

    def test_defaults(self):
        r = LLMResponse(content="x")
        assert r.model == ""
        assert r.tokens == 0
        assert r.raw is None


# ---------------------------------------------------------------------------
# 便捷函数测试
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    @patch("lingflow_plus.llm_client._get_default_client")
    def test_call_glm(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.call.return_value = LLMResponse(content="ok")

        resp = call_glm([{"role": "user", "content": "hi"}])
        assert resp.content == "ok"
        mock_client.call.assert_called_once()

    @patch("lingflow_plus.llm_client._get_default_client")
    def test_call_glm_with_system_prompt(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.call.return_value = LLMResponse(content="ok")

        resp = call_glm([{"role": "user", "content": "hi"}], system_prompt="be helpful")
        call_args = mock_client.call.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"

    @patch("lingflow_plus.llm_client._get_default_client")
    def test_ask(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.return_value = LLMResponse(content="42")

        result = ask("what is 6*7?")
        assert result == "42"
        mock_client.chat.assert_called_once_with("what is 6*7?", model=None)


# ---------------------------------------------------------------------------
# Live API 测试 (标记为 live，默认跳过)
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestLiveAPI:
    def test_real_glm_call(self):
        client = GLMClient(timeout=30)
        resp = client.chat("1+1等于几？只回答数字", model="glm-4-flash")
        assert resp.content.strip()
        assert resp.tokens > 0
        assert resp.model

    def test_real_ask(self):
        result = ask("hi")
        assert isinstance(result, str)
        assert len(result) > 0
