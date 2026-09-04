from agentflow.catalog import MODELS, models_for_provider
from agentflow.config import ENV_KEYS, api_key, available_providers
from agentflow.providers.openai_compat import base_url_for
from agentflow.router import PREFERENCES


def test_cn_vendors_are_wired():
    assert "moonshot" in ENV_KEYS
    assert "qwen" in ENV_KEYS
    assert ENV_KEYS["moonshot"] == ("MOONSHOT_API_KEY", "KIMI_API_KEY")
    assert ENV_KEYS["qwen"] == ("DASHSCOPE_API_KEY", "QWEN_API_KEY")
    assert {m.id for m in models_for_provider("moonshot")} >= {
        "kimi-k3",
        "kimi-k2.7-code",
        "kimi-k2.7-code-highspeed",
    }
    assert {m.id for m in models_for_provider("qwen")} >= {
        "qwen3.8-max",
        "qwen3-coder-plus",
        "qwen3.7-flash",
    }


def test_preference_ids_exist_in_catalog():
    missing = []
    for role, by_mode in PREFERENCES.items():
        for mode, ids in by_mode.items():
            for mid in ids:
                if mid not in MODELS:
                    missing.append(f"{role}/{mode}/{mid}")
    assert missing == []


def test_qwen_api_key_alias(monkeypatch):
    for name in (
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "MOONSHOT_API_KEY",
        "KIMI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("QWEN_API_KEY", "sk-test-qwen")
    monkeypatch.setenv("KIMI_API_KEY", "sk-test-kimi")
    assert api_key("qwen") == "sk-test-qwen"
    assert api_key("moonshot") == "sk-test-kimi"
    flags = available_providers()
    assert flags["qwen"] is True
    assert flags["moonshot"] is True


def test_dashscope_region_urls(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_BASE_URL", raising=False)
    monkeypatch.delenv("QWEN_BASE_URL", raising=False)
    monkeypatch.delenv("MOONSHOT_BASE_URL", raising=False)
    monkeypatch.setenv("DASHSCOPE_REGION", "cn")
    assert base_url_for("qwen") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    monkeypatch.setenv("DASHSCOPE_REGION", "intl")
    assert base_url_for("qwen") == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.invalid/v1")
    assert base_url_for("qwen") == "https://example.invalid/v1"
    assert base_url_for("moonshot") == "https://api.moonshot.cn/v1"
    monkeypatch.setenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
    assert base_url_for("moonshot") == "https://api.moonshot.ai/v1"
