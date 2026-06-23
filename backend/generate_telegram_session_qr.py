import asyncio
import os
import qrcode
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

if not API_ID or not API_HASH or API_ID == "dummy" or API_HASH == "dummy":
    print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set properly in your .env file.")
    exit(1)

async def main():
    print("Starting Telegram Client with QR Code Login...")
    client = TelegramClient(StringSession(), int(API_ID), API_HASH)
    await client.connect()
    
    qr_login = await client.qr_login()
    print("\nPlease scan the following QR code using your Telegram app:")
    print("Go to Settings -> Devices -> Link Desktop Device\n")
    
    qr = qrcode.QRCode()
    qr.add_data(qr_login.url)
    qr.print_ascii()
    
    try:
        await qr_login.wait()
    except Exception as e:
        print(f"Login failed or timed out: {e}")
        return

    print("\n" + "="*50)
    print("SUCCESS! You are now logged in.")
    print("Here is your new TELEGRAM_SESSION_STRING:\n")
    print(client.session.save())
    print("\n" + "="*50)
    print("\nCopy the string above and update TELEGRAM_SESSION_STRING in both your backend/.env and root .env files.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
