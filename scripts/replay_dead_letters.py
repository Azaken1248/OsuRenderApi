import asyncio
import os
import asyncpg
from dotenv import load_dotenv


async def replay_dead_letters():
    load_dotenv()
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://osurender:osurender@localhost:5432/osurender",
    )
    # Convert sqlalchemy URL to asyncpg DSN
    dsn = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        print("Scanning for dead letters (FAILED outbox events)...")
        records = await conn.fetch(
            "SELECT id, event_type, last_error FROM outbox_events WHERE status = 'FAILED'"
        )
        if not records:
            print("No dead letters found.")
            return

        print(f"Found {len(records)} dead letters.")
        for record in records:
            print(
                f"  - Event {record['id']} ({record['event_type']}): {record['last_error']}"
            )

        confirm = input(f"Replay {len(records)} failed events? (y/N): ")
        if confirm.lower() == "y":
            res = await conn.execute(
                "UPDATE outbox_events SET status = 'PENDING', retry_count = 0, last_error = NULL WHERE status = 'FAILED'"
            )
            print(f"Success: {res}")
        else:
            print("Aborted.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(replay_dead_letters())
