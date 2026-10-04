from groq import AsyncGroq

from core.config import settings


_client = AsyncGroq(
    api_key=settings.groq_api_key,
)


async def generate_text(
    prompt: str,
    system_prompt: str = "You are a helpful AI assistant.",
    temperature: float = 0.2,
) -> str:
    """Generate text using the configured Groq model."""

    response = await _client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=temperature,
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return content.strip()
