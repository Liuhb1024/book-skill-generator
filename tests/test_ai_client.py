from types import SimpleNamespace

import app.ai_client as ai_client


class FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30),
        )


class FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeCompletions())


def test_call_ai_returns_content_and_tokens(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(ai_client, "get_client", lambda: fake_client)

    content, prompt_tokens, completion_tokens = ai_client.call_ai(
        "You are a JSON API.",
        "Return ok.",
        model="deepseek-v4-flash",
        temperature=0.1,
        response_format="json_object",
        max_tokens=512,
        frequency_penalty=0.5,
        presence_penalty=0.3,
    )

    assert content == '{"ok": true}'
    assert prompt_tokens == 120
    assert completion_tokens == 30
    assert fake_client.chat.completions.kwargs["model"] == "deepseek-v4-flash"
    assert fake_client.chat.completions.kwargs["temperature"] == 0.1
    assert fake_client.chat.completions.kwargs["max_tokens"] == 512
    assert fake_client.chat.completions.kwargs["response_format"] == {"type": "json_object"}
    assert fake_client.chat.completions.kwargs["frequency_penalty"] == 0.5
    assert fake_client.chat.completions.kwargs["presence_penalty"] == 0.3
    assert fake_client.chat.completions.kwargs["messages"] == [
        {"role": "system", "content": "You are a JSON API."},
        {"role": "user", "content": "Return ok."},
    ]


def test_estimate_cost_uses_model_pricing():
    cost = ai_client.estimate_cost(1_000_000, 500_000, model="deepseek-v4-flash")

    assert cost == 1.9
