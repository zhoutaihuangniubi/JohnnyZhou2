import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


def load_config() -> dict:
    with open(BASE_DIR / "config.yaml") as f:
        config = yaml.safe_load(f)
    # Resolve env var references in the config
    config["_env"] = {
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "NEWSAPI_KEY": os.getenv("NEWSAPI_KEY"),
        "NYTIMES_API_KEY": os.getenv("NYTIMES_API_KEY"),
        "BUZZSPROUT_API_TOKEN": os.getenv("BUZZSPROUT_API_TOKEN"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "FISH_AUDIO_API_KEY": os.getenv("FISH_AUDIO_API_KEY"),
        "HTTP_PROXY": os.getenv("HTTP_PROXY"),
    }
    return config
