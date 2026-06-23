import os
from app.core.config import Settings

# test with what the user had initially
os.environ["TELEGRAM_CHANNELS"] = '\'["durov"]\''
try:
    settings = Settings()
    print("TELEGRAM_CHANNELS:", settings.telegram_channels)
except Exception as e:
    print("Error 1:", e)

os.environ["TELEGRAM_CHANNELS"] = '["durov"]'
try:
    settings = Settings()
    print("TELEGRAM_CHANNELS:", settings.telegram_channels)
except Exception as e:
    print("Error 2:", e)

os.environ["TELEGRAM_CHANNELS"] = 'durov'
try:
    settings = Settings()
    print("TELEGRAM_CHANNELS:", settings.telegram_channels)
except Exception as e:
    print("Error 3:", repr(e))
