import httpx

from .spec import ChatSpec, GatewayError


class OpenAICompatAdapter:
    def __init__(self, name, base_url, api_key, model):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    async def complete(self, spec: ChatSpec) -> str:
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

            return data["choices"][0]["message"]["content"]

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

    async def complete(self, spec: ChatSpec) -> str:
        if not self.responses:
            return ""

        if len(self.responses) > 1:
            return self.responses.pop(0)

        return self.responses[0]


FAKE_RESPONSES = [
    '{"action": "message_payments_team", "reason": "Payment needs review", "wake_after_minutes": 120}',
    '{"action": "refund_customer"}',
]