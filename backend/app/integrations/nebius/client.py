import httpx

from app.core.config import get_settings


class NebiusNotConfigured(RuntimeError):
    pass


class NebiusClient:
    def __init__(self):
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.nebius_api_key)

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        selected_model = model or self.settings.nemotron_model
        if not self.configured or not selected_model:
            raise NebiusNotConfigured("NEBIUS_API_KEY and a model are required")
        payload = {"model": selected_model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.settings.nebius_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.nebius_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
