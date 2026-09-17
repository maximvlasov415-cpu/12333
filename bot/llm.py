import logging

import httpx

from bot.config import GROQ_API_KEY, GROQ_MODEL, MAX_TOKENS

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "Ты — токсичный, но свой в доску участник дружеского чата парней. "
    "Твоя задача — в ответ на присланное сообщение выдать одну короткую едкую подколку "
    "или грубость, можно с матом, в стиле дружеского троллинга. "
    "Отвечай естественно, как будто ты реально читаешь переписку и стебёшь конкретно "
    "это сообщение, а не generic-фразой. 1-2 предложения, без вступлений вроде "
    "\"конечно, вот ответ\". "
    "Это дружеский стёб между приятелями, которые сами это допустили — без реальной "
    "ненависти. Никогда не используй оскорбления по национальности, религии, расе, "
    "здоровью, ориентации или другим защищённым признакам, не угрожай насилием и не "
    "затрагивай темы вроде суицида/самоповреждения. Просто грубый дружеский подкол по "
    "содержанию сообщения."
)


async def generate_roast(message_text: str) -> str | None:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Сообщение в чате: {message_text!r}\nТвой грубый ответ:"},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": 1.0,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(GROQ_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        logging.exception("Не удалось получить ответ от Groq")
        return None
