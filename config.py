import os
from dotenv import load_dotenv

load_dotenv()

class Config:

    # saucedemo.com
    BASE_URL = "https://www.saucedemo.com"

    # Test users
    STANDARD_USER = "standard_user"
    LOCKED_USER = "locked_out_user"
    PROBLEM_USER = "problem_user"
    PERFORMANCE_USER = "performance_glitch_user"

    # Password (same for all saucedemo users)
    PASSWORD = "secret_sauce"

    # Timeouts (milliseconds)
    DEFAULT_TIMEOUT = 30000
    SHORT_TIMEOUT = 5000

    # automationexercise.com

    AE_BASE_URL = "https://automationexercise.com"
    AE_EMAIL = os.getenv("AE_EMAIL", "")
    AE_PASSWORD = os.getenv("AE_PASSWORD", "")