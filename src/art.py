import os

from openai import AsyncOpenAI

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY"))

async def draw(model: str, prompt: str) -> str:
    response = await openai_client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1792x1024",
        quality="auto",
        n=1,
    )
    return response.data[0].url


