# Credential Rotation

This document outlines the procedure for rotating sensitive credentials used by the application, specifically the Telegram `StringSession`.

## Telegram StringSession

The Telegram collector uses a `StringSession` to authenticate as a user account. This session string represents an active login session and provides full access to the account. 

### When to Rotate
- If the session string is accidentally exposed (e.g., committed to version control).
- If the connected Telegram account is compromised.
- If you manually terminate the session from your Telegram app settings (Settings > Devices > Terminate Session).

### Rotation Procedure
1. **Terminate Old Session**:
   - Open the Telegram app on your phone or desktop.
   - Go to **Settings** > **Devices** (or **Active Sessions**).
   - Find the session associated with the collector (usually named after the Telethon library) and tap **Terminate**.
2. **Generate New Session**:
   - Run the included generation script from the project root:
     ```bash
     pip install telethon
     python scripts/generate_telegram_session.py
     ```
   - Follow the prompts, enter your `API_ID` and `API_HASH`, and complete the login flow (phone number + code).
3. **Update Configuration**:
   - Copy the newly generated string output by the script.
   - Open your `.env` file (e.g., `backend/.env`).
   - Replace the old value of `TELEGRAM_SESSION_STRING` with the new string:
     ```env
     TELEGRAM_SESSION_STRING=1Bjwxyz...
     ```
4. **Restart Services**:
   - Restart the Celery worker and beat scheduler to pick up the new configuration:
     ```bash
     docker compose restart worker-ingest beat
     ```
