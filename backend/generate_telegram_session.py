import asyncio
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

if not API_ID or not API_HASH or API_ID == "dummy" or API_HASH == "dummy":
    print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set properly in your .env file.")
    print("Please update them and run this script again.")
    exit(1)

async def main():
    print("Starting Telegram Client...")
    print("When prompted, enter your phone number (with country code, e.g., +1234567890)")
    print("Then enter the login code you receive in your Telegram app.\n")
    
    # We use an empty StringSession to start fresh
    client = TelegramClient(StringSession(), int(API_ID), API_HASH)
    
    await client.start()
    
    print("\n" + "="*50)
    print("SUCCESS! You are now logged in.")
    print("Here is your new TELEGRAM_SESSION_STRING:\n")
    print(client.session.save())
    print("\n" + "="*50)
    print("\nCopy the string above and update TELEGRAM_SESSION_STRING in both your backend/.env and root .env files.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
