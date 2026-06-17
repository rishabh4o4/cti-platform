import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.tasks.reddit import collect_reddit_data
from app.tasks.x import collect_x_data
from app.tasks.telegram import collect_telegram_data

if __name__ == "__main__":
    print("Triggering Reddit data collection...")
    collect_reddit_data.delay()
    print("Triggering X data collection...")
    collect_x_data.delay()
    print("Triggering Telegram data collection...")
    collect_telegram_data.delay()
    print("Tasks sent to celery!")
