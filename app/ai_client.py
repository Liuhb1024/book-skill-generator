import time

from openai import OpenAI

from app.config import settings


_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _client


def call_ai(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 1.0,
    response_format: str | dict | None = "json_object",
    max_tokens: int = 4096,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
) -> tuple[str, int, int]:
    request_format = response_format
    if isinstance(response_format, str):
        request_format = {"type": response_format}

    kwargs = {
        "model": model or settings.CHAPTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
    }
    if request_format is not None:
        kwargs["response_format"] = request_format

    last_error: Exception | None = None
    for delay in (1, 2, 4):
        try:
            response = get_client().chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            usage = response.usage
            return content, usage.prompt_tokens, usage.completion_tokens
        except Exception as exc:
            last_error = exc
            time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError("AI call failed without an exception")


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None = None,
) -> float:
    pricing = settings.MODEL_PRICING.get(model or settings.CHAPTER_MODEL)
    if pricing is None:
        return 0.0

    input_cost = prompt_tokens / 1_000_000 * pricing["input"]
    output_cost = completion_tokens / 1_000_000 * pricing["output"]
    return round(input_cost + output_cost, 6)
