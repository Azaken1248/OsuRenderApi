import logging
import json
import sys
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
job_id_var: ContextVar[str] = ContextVar("job_id", default="")
event_id_var: ContextVar[str] = ContextVar("event_id", default="")
worker_id_var: ContextVar[str] = ContextVar("worker_id", default="")
component_var: ContextVar[str] = ContextVar("component", default="unknown")


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": component_var.get(""),
            "request_id": request_id_var.get(""),
            "job_id": job_id_var.get(""),
            "event_id": event_id_var.get(""),
            "worker_id": worker_id_var.get(""),
        }
        log_entry = {k: v for k, v in log_entry.items() if v}
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging(component: str, level: int = logging.INFO):
    component_var.set(component)
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").propagate = False


def generate_request_id() -> str:
    return str(uuid.uuid4())[:8]
