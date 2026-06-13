import os
import sys
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

def main():
    print("=== Telegram StringSession Generator ===")
    print("This script will help you generate a StringSession for the Telegram Collector.")
    print("You will need your API_ID and API_HASH from https://my.telegram.org")
    print()
    
    api_id = input("Enter your API_ID: ").strip()
    api_hash = input("Enter your API_HASH: ").strip()
    
    if not api_id or not api_hash:
        print("API_ID and API_HASH are required. Exiting.")
        sys.exit(1)
        
    try:
        api_id = int(api_id)
    except ValueError:
        print("API_ID must be an integer. Exiting.")
        sys.exit(1)
        
    print("\nConnecting to Telegram... (You will be prompted for your phone number and login code)")
    
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()
        print("\n=== SUCCESS ===")
        print("Your StringSession has been generated successfully!")
        print("\nPlease copy the string below and save it as TELEGRAM_SESSION_STRING in your .env file:\n")
        print(session_string)
        print("\nWARNING: Treat this string like a password! Anyone with this string can access your Telegram account.")

if __name__ == "__main__":
    main()
