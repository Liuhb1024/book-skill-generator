import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.dmxapi.com/v1")
    SKELETON_MODEL: str = os.getenv("SKELETON_MODEL", "deepseek-v4-pro-guan")
    CHAPTER_MODEL: str = os.getenv("CHAPTER_MODEL", "deepseek-v4-flash")
    INTEGRATE_MODEL: str = os.getenv("INTEGRATE_MODEL", "deepseek-v4-flash")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./outputs")
    MAX_FILE_SIZE_MB: int = 50
    MAX_CONCURRENT_CHAPTERS: int = 10
    CHAPTER_RETRY_COUNT: int = 2
    MODEL_PRICING: dict = {
        "deepseek-v4-pro-guan": {"input": 3.0, "output": 6.0},
        "deepseek-v4-flash": {"input": 0.95, "output": 1.9},
    }


settings = Settings()
