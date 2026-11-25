"""JSON logs on stdout, which Cloud Logging parses into severity + structured fields."""
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"severity": record.levelname, "message": record.getMessage(), "logger": record.name}
        for key in ("run_id", "entity", "connector", "rows", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            # Message + stack trace + this @type lets Cloud Error Reporting (free) group
            # failures and email you about new ones.
            payload["message"] = f"{payload['message']}\n{self.formatException(record.exc_info)}"
            payload["@type"] = "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent"
        elif record.levelno >= logging.ERROR:
            payload["@type"] = "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent"
        return json.dumps(payload, default=str)


def configure() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    return logging.getLogger("lunanele-google-bi")
