import httpx

from .spec import ChatSpec, GatewayError


class OpenAICompatAdapter:
    def __init__(self, name, base_url, api_key, model):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    async def complete(self, spec: ChatSpec) -> tuple[str, dict]:
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": self.model,
            "messages": spec.messages,
            "max_tokens": spec.max_tokens,
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=body,
                )

            response.raise_for_status()

            data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            return content, {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            if status == 429 or status >= 500:
                raise GatewayError(
                    f"{self.name}: provider error {status}"
                ) from exc

            raise GatewayError(
                f"{self.name}: HTTP error {status}"
            ) from exc

        except httpx.TimeoutException as exc:
            raise GatewayError(
                f"{self.name}: request timed out"
            ) from exc

        except httpx.HTTPError as exc:
            raise GatewayError(
                f"{self.name}: HTTP request failed"
            ) from exc


class FakeAdapter:
    def __init__(self, responses: list[str], name="fake"):
        self.responses = responses
        self.name = name
        self.model = "fake"

    async def complete(self, spec: ChatSpec) -> tuple[str, dict]:
        if not self.responses:
            return "", {"prompt_tokens": 0, "completion_tokens": 0}

        content = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

        return content, {"prompt_tokens": 0, "completion_tokens": 0}


FAKE_RESPONSES = [
    '{"action": "message_payments_team", "reason": "Payment needs review", "wake_after_minutes": 120}',
    '{"action": "refund_customer"}',
]