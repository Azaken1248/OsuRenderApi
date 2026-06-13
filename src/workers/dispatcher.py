import asyncio
import json
import logging
import random
import uuid
import asyncpg

from src.core.config import get_settings
from src.db.models import OutboxStatus
import src.core.metrics

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("osurender.dispatcher")


class OutboxDispatcher:
    def __init__(self):
        self.settings = get_settings()
        self.pool = None
        self.conn = None

        self._poll_task = None
        self._sweeper_task = None
        self._drain_loop_task = None
        self._drain_event = asyncio.Event()

    async def connect(self):

        self.conn = await asyncpg.connect(
            self.settings.database_url.replace("postgresql+asyncpg", "postgresql")
        )
        await self.conn.add_listener("new_outbox_event", self.handle_notification)
        logger.info("Connected to PostgreSQL and listening for 'new_outbox_event'")

        self.pool = await asyncpg.create_pool(
            self.settings.database_url.replace("postgresql+asyncpg", "postgresql")
        )

    async def handle_notification(self, connection, pid, channel, payload):
        logger.debug(f"Received notification on {channel} with payload {payload}")

        self._drain_event.set()

    async def drain_loop(self):
        """
        Persistent background task that processes events sequentially when notified.
        """
        while True:
            try:
                await self._drain_event.wait()
                self._drain_event.clear()

                while True:
                    processed = await self.drain_outbox()
                    if not processed:
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in drain loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def drain_outbox(self):
        """
        Atomically claim and process a batch of outbox events using SKIP LOCKED.
        """
        if not self.pool:
            return 0

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
                    return 0

                logger.info(f"Claimed {len(records)} events for processing")

                from src.workers.render_worker import process_render_job

                for record in records:
                    event_id = record["id"]
                    payload_str = record["payload"]
                    retry_count = record["retry_count"]

                    try:
                        payload = (
                            json.loads(payload_str)
                            if isinstance(payload_str, str)
                            else payload_str
                        )
                        job_id = payload.get("job_id")

                        if job_id:

                            await asyncio.to_thread(process_render_job.delay, job_id)

                            await connection.execute(
                                "UPDATE outbox_events SET status = 'PROCESSED', processed_at = NOW() WHERE id = $1",
                                event_id,
                            )
                            from src.core.metrics import outbox_dispatch_total

                            outbox_dispatch_total.inc()
                            logger.info(f"Dispatched job {job_id} successfully")
                    except Exception as e:
                        logger.error(
                            f"Failed to dispatch event {event_id}: {e}", exc_info=True
                        )
                        new_retry = retry_count + 1
                        if new_retry > 3:
                            await connection.execute(
                                "UPDATE outbox_events SET status = 'FAILED', last_error = $1 WHERE id = $2",
                                str(e),
                                event_id,
                            )
                            logger.error(
                                f"Event {event_id} failed after {new_retry} retries"
                            )
                        else:
                            await connection.execute(
                                "UPDATE outbox_events SET status = 'PENDING', retry_count = $1, last_error = $2 WHERE id = $3",
                                new_retry,
                                str(e),
                                event_id,
                            )
                return len(records)

        except Exception as e:
            logger.error(f"Error draining outbox: {e}", exc_info=True)
            return 0

    async def safety_poll(self):
        """
        Polls the outbox every 60 seconds just in case notifications are lost.
        """
        while True:
            try:
                await asyncio.sleep(60)
                logger.debug("Running safety poll")
                self._drain_event.set()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in safety poll: {e}")

    async def sweep_stuck_events(self):
        if not self.pool:
            return 0

        logger.debug("Running stuck processing sweeper")
        query = """
        WITH stuck AS (
            SELECT id, retry_count FROM outbox_events 
            WHERE status = 'PROCESSING' 
            AND processing_started_at < NOW() - INTERVAL '5 minutes'
        )
        UPDATE outbox_events 
        SET 
            status = CASE WHEN retry_count >= 3 THEN 'FAILED' ELSE 'PENDING' END::outbox_status,
            retry_count = CASE WHEN retry_count >= 3 THEN retry_count ELSE retry_count + 1 END,
            last_error = CASE WHEN retry_count >= 3 THEN 'Stuck in PROCESSING state too many times' ELSE last_error END
        WHERE id IN (SELECT id FROM stuck)
        RETURNING id;
        """
        try:
            async with self.pool.acquire() as connection:
                records = await connection.fetch(query)
                if records:
                    from src.core.metrics import stuck_processing_events_total

                    stuck_processing_events_total.inc(len(records))
                    logger.warning(
                        f"Swept {len(records)} stuck outbox events (reverted to PENDING or marked FAILED)"
                    )
                return len(records)
        except Exception as e:
            logger.error(f"Error in stuck processing sweeper: {e}")
            return 0

    async def stuck_processing_sweeper(self):
        """
        Recovers events that got stuck in PROCESSING due to a crash.
        """
        while True:
            try:
                await asyncio.sleep(300)
                await self.sweep_stuck_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stuck processing sweeper: {e}")

    async def sweep_old_events(self):
        if not self.pool:
            return 0
        logger.debug("Running data lifecycle sweeper")
        query = """
        DELETE FROM outbox_events 
        WHERE status = 'PROCESSED' 
        AND processed_at < NOW() - INTERVAL '7 days';
        """
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query)
        except Exception as e:
            logger.error(f"Failed to sweep old events: {e}")

    async def data_lifecycle_sweeper(self):
        while True:
            try:
                await asyncio.sleep(3600)
                await self.sweep_old_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in data lifecycle sweeper: {e}")

    async def run(self):
        reconnect_reason = "startup"
        while True:
            try:
                await self.connect()

                self._poll_task = asyncio.create_task(self.safety_poll())
                self._sweeper_task = asyncio.create_task(
                    self.stuck_processing_sweeper()
                )
                self._lifecycle_task = asyncio.create_task(
                    self.data_lifecycle_sweeper()
                )
                self._drain_loop_task = asyncio.create_task(self.drain_loop())

                self._drain_event.set()

                while self.conn and not self.conn.is_closed():
                    try:
                        await self.conn.execute("SELECT 1")
                    except Exception as e:
                        logger.warning(f"Heartbeat failed: {e}")
                        reconnect_reason = "listener"
                        break
                    await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"Dispatcher connection lost: {e}")
                reconnect_reason = "postgres"
            finally:
                if self._poll_task:
                    self._poll_task.cancel()
                if self._sweeper_task:
                    self._sweeper_task.cancel()
                if hasattr(self, "_lifecycle_task") and self._lifecycle_task:
                    self._lifecycle_task.cancel()
                if self._drain_loop_task:
                    self._drain_loop_task.cancel()

                if self.pool:
                    await self.pool.close()

            from src.core.metrics import listener_reconnects_total

            listener_reconnects_total.labels(reason=reconnect_reason).inc()
            jitter = random.uniform(3, 10)
            logger.info(f"Reconnecting dispatcher in {jitter:.2f} seconds...")
            await asyncio.sleep(jitter)
            reconnect_reason = "unknown"


if __name__ == "__main__":
    import os
    from prometheus_client import start_http_server

    start_http_server(8728)

    dispatcher = OutboxDispatcher()
    try:
        asyncio.run(dispatcher.run())
    except KeyboardInterrupt:
        logger.info("Dispatcher shutting down")
