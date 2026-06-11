import asyncio
import json
import logging
import random
import uuid
import asyncpg

from src.core.config import get_settings
from src.db.models import OutboxStatus

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("osurender.dispatcher")

class OutboxDispatcher:
    def __init__(self):
        self.settings = get_settings()
        self.pool = None
        self.conn = None
        # Create a background task for polling
        self._poll_task = None
        self._sweeper_task = None

    async def connect(self):
        # We need a dedicated connection for LISTEN
        self.conn = await asyncpg.connect(self.settings.database_url.replace("postgresql+asyncpg", "postgresql"))
        await self.conn.add_listener("new_outbox_event", self.handle_notification)
        logger.info("Connected to PostgreSQL and listening for 'new_outbox_event'")
        
        # We also need a pool for executing queries concurrently if needed
        self.pool = await asyncpg.create_pool(self.settings.database_url.replace("postgresql+asyncpg", "postgresql"))

    async def handle_notification(self, connection, pid, channel, payload):
        logger.debug(f"Received notification on {channel} with payload {payload}")
        # When a notification arrives, we schedule a drain asynchronously
        asyncio.create_task(self.drain_outbox())

    async def drain_outbox(self):
        """
        Atomically claim and process a batch of outbox events using SKIP LOCKED.
        """
        if not self.pool:
            return

        query = """
        WITH claimed AS (
            SELECT id FROM outbox_events 
            WHERE status = 'PENDING' 
            ORDER BY created_at 
            LIMIT 100 
            FOR UPDATE SKIP LOCKED
        )
        UPDATE outbox_events 
        SET status = 'PROCESSING', processing_started_at = NOW() 
        WHERE id IN (SELECT id FROM claimed) 
        RETURNING *;
        """
        try:
            async with self.pool.acquire() as connection:
                records = await connection.fetch(query)
                
                if not records:
                    return
                
                logger.info(f"Claimed {len(records)} events for processing")
                
                # Import here to avoid circular imports during startup
                from src.workers.render_worker import process_render_job
                
                for record in records:
                    event_id = record['id']
                    payload_str = record['payload']
                    retry_count = record['retry_count']
                    
                    try:
                        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                        job_id = payload.get("job_id")
                        
                        if job_id:
                            # Try to dispatch to celery (non-blocking)
                            await asyncio.to_thread(process_render_job.delay, job_id)
                            
                            # Mark as PROCESSED
                            await connection.execute(
                                "UPDATE outbox_events SET status = 'PROCESSED', processed_at = NOW() WHERE id = $1", 
                                event_id
                            )
                            logger.info(f"Dispatched job {job_id} successfully")
                    except Exception as e:
                        logger.error(f"Failed to dispatch event {event_id}: {e}", exc_info=True)
                        new_retry = retry_count + 1
                        if new_retry > 3:
                            await connection.execute(
                                "UPDATE outbox_events SET status = 'FAILED', last_error = $1 WHERE id = $2", 
                                str(e), event_id
                            )
                            logger.error(f"Event {event_id} failed after {new_retry} retries")
                        else:
                            await connection.execute(
                                "UPDATE outbox_events SET status = 'PENDING', retry_count = $1, last_error = $2 WHERE id = $3", 
                                new_retry, str(e), event_id
                            )
                            
        except Exception as e:
            logger.error(f"Error draining outbox: {e}", exc_info=True)

    async def safety_poll(self):
        """
        Polls the outbox every 60 seconds just in case notifications are lost.
        """
        while True:
            try:
                await asyncio.sleep(60)
                logger.debug("Running safety poll")
                await self.drain_outbox()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in safety poll: {e}")
                
    async def stuck_processing_sweeper(self):
        """
        Recovers events that got stuck in PROCESSING due to a crash.
        """
        while True:
            try:
                await asyncio.sleep(300) # Every 5 minutes
                if not self.pool:
                    continue
                
                logger.debug("Running stuck processing sweeper")
                query = """
                UPDATE outbox_events 
                SET status = 'PENDING'
                WHERE status = 'PROCESSING' 
                AND processing_started_at < NOW() - INTERVAL '5 minutes'
                RETURNING id;
                """
                async with self.pool.acquire() as connection:
                    records = await connection.fetch(query)
                    if records:
                        logger.warning(f"Recovered {len(records)} stuck outbox events to PENDING")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stuck processing sweeper: {e}")

    async def run(self):
        while True:
            try:
                await self.connect()
                
                # Start background tasks
                self._poll_task = asyncio.create_task(self.safety_poll())
                self._sweeper_task = asyncio.create_task(self.stuck_processing_sweeper())
                
                # Drain once on startup to catch anything pending
                await self.drain_outbox()
                
                # Wait for the connection to close or throw an error
                while self.conn and not self.conn.is_closed():
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Dispatcher connection lost: {e}")
            finally:
                if self._poll_task:
                    self._poll_task.cancel()
                if self._sweeper_task:
                    self._sweeper_task.cancel()
                    
                if self.pool:
                    await self.pool.close()
                    
            # Reconnect jitter
            jitter = random.uniform(3, 10)
            logger.info(f"Reconnecting dispatcher in {jitter:.2f} seconds...")
            await asyncio.sleep(jitter)

if __name__ == "__main__":
    dispatcher = OutboxDispatcher()
    try:
        asyncio.run(dispatcher.run())
    except KeyboardInterrupt:
        logger.info("Dispatcher shutting down")
