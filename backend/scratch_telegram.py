import asyncio
from app.services.telegram import TelegramCollector

async def main():
    collector = TelegramCollector()
    items, errors = await collector.process_channels()
    print("Items:", len(items))
    print("Errors:", errors)

if __name__ == "__main__":
    asyncio.run(main())
