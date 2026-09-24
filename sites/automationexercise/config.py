import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    # automationexercise.com
    BASE_URL = "https://automationexercise.com"

    # Credentials come from .env locally and GitHub secrets in CI
    EMAIL = os.getenv("AE_EMAIL", "")
    PASSWORD = os.getenv("AE_PASSWORD", "")
