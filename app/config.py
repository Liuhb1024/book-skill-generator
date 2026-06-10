import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_LITE_MODEL: str = os.getenv("DEEPSEEK_LITE_MODEL", "deepseek-chat")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./outputs")
    MAX_FILE_SIZE_MB: int = 50
    MAX_CONCURRENT_CHAPTERS: int = 10
    CHAPTER_RETRY_COUNT: int = 2


settings = Settings()
