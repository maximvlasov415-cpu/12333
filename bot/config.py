import os

from dotenv import load_dotenv

load_dotenv()


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

TRIGGER_CHANCE = _float_env("TRIGGER_CHANCE", 0.04)
COOLDOWN_SECONDS = _int_env("COOLDOWN_SECONDS", 600)
MAX_TOKENS = _int_env("MAX_TOKENS", 60)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Заполните .env по примеру .env.example")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY не задан. Заполните .env по примеру .env.example")
