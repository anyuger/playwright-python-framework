class Config:
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