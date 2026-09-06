import re
import time
import uuid

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars


CORRELATION_ID_HEADER = "X-Correlation-ID"
_CORRELATION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

_SHARED_PROCESSORS = [
    merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]


def configure_structlog():
    structlog.configure(
        processors=_SHARED_PROCESSORS
        + [
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def build_processor_formatter():
    configure_structlog()
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )


def _correlation_id(request):
    candidate = request.headers.get(CORRELATION_ID_HEADER, "")
    if _CORRELATION_ID_RE.fullmatch(candidate):
        return candidate
    return str(uuid.uuid4())


class RequestObservabilityMiddleware:
    """Attach a safe correlation ID and emit one structured event per request."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = structlog.get_logger("vorneq.request")

    def __call__(self, request):
        clear_contextvars()
        correlation_id = _correlation_id(request)
        request.correlation_id = correlation_id
        bind_contextvars(correlation_id=correlation_id)
        started = time.monotonic()

        try:
            response = self.get_response(request)
        except Exception:
            self.logger.exception(
                "request.exception",
                method=request.method,
                path=request.path,
            )
            clear_contextvars()
            raise

        duration_ms = round((time.monotonic() - started) * 1000, 2)
        response[CORRELATION_ID_HEADER] = correlation_id

        event = {
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        if response.status_code >= 500:
            self.logger.error("request.completed", **event)
        elif response.status_code >= 400:
            self.logger.warning("request.completed", **event)
        else:
            self.logger.info("request.completed", **event)

        clear_contextvars()
        return response
