import json
import logging
import os
import random
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator


SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "demo-api")
OTLP_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://otel-collector:4317",
)

LOG_PATH = os.getenv(
    "APP_LOG_PATH",
    "/var/log/demo-api/app.log",
)


# ---------------------------------------------------------
# OpenTelemetry tracing
# ---------------------------------------------------------

resource = Resource.create(
    {
        "service.name": SERVICE_NAME,
        "service.version": "1.0.0",
        "deployment.environment": "local",
    }
)

trace_provider = TracerProvider(resource=resource)

otlp_exporter = OTLPSpanExporter(
    endpoint=OTLP_ENDPOINT,
    insecure=True,
)

trace_provider.add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)

trace.set_tracer_provider(trace_provider)

tracer = trace.get_tracer(__name__)


# ---------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------

os.makedirs(
    os.path.dirname(LOG_PATH),
    exist_ok=True,
)

logger = logging.getLogger(SERVICE_NAME)
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    formatter = logging.Formatter("%(message)s")

    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def current_trace_context():
    span = trace.get_current_span()
    context = span.get_span_context()

    if not context.is_valid:
        return None, None

    trace_id = format(context.trace_id, "032x")
    span_id = format(context.span_id, "016x")

    return trace_id, span_id


def log_event(level: str, message: str, **fields):
    trace_id, span_id = current_trace_context()

    payload = {
        "timestamp": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "level": level.upper(),
        "service": SERVICE_NAME,
        "message": message,
        "trace_id": trace_id,
        "span_id": span_id,
        **fields,
    }

    log_method = getattr(
        logger,
        level.lower(),
        logger.info,
    )

    log_method(
        json.dumps(
            payload,
            separators=(",", ":"),
        )
    )


# ---------------------------------------------------------
# FastAPI
# ---------------------------------------------------------

app = FastAPI(
    title="Observability Demo API",
    description="FastAPI workload instrumented with OpenTelemetry, Prometheus, and structured logging.",
    version="1.1.0",
)

FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="/metrics",
)

Instrumentator().instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
)


@app.get("/")
def root():
    log_event(
        "info",
        "root endpoint requested",
        route="/",
        status_code=200,
    )

    return {
        "service": SERVICE_NAME,
        "message": "Platform Engineering Observability Demo",
    }


@app.get("/health")
def health():
    log_event(
        "info",
        "health check completed",
        route="/health",
        status_code=200,
    )

    return {
        "status": "ok",
        "service": SERVICE_NAME,
    }


@app.get("/work")
def work():
    with tracer.start_as_current_span(
        "perform-demo-work"
    ) as span:
        duration = random.uniform(
            0.1,
            0.5,
        )

        span.set_attribute(
            "work.type",
            "demo",
        )

        span.set_attribute(
            "work.duration_seconds",
            duration,
        )

        time.sleep(duration)

        with tracer.start_as_current_span(
            "database-simulation"
        ):
            database_duration = random.uniform(
                0.05,
                0.15,
            )

            time.sleep(database_duration)

        total_duration = (
            duration
            + database_duration
        )

        log_event(
            "info",
            "work completed",
            route="/work",
            status_code=200,
            work_duration_seconds=round(
                duration,
                3,
            ),
            database_duration_seconds=round(
                database_duration,
                3,
            ),
            total_duration_seconds=round(
                total_duration,
                3,
            ),
        )

        return {
            "status": "completed",
            "duration_seconds": round(
                total_duration,
                3,
            ),
        }


@app.get("/slow")
def slow():
    with tracer.start_as_current_span(
        "slow-operation"
    ) as span:
        duration = 2.0

        span.set_attribute(
            "operation.slow",
            True,
        )

        span.set_attribute(
            "operation.duration_seconds",
            duration,
        )

        time.sleep(duration)

        log_event(
            "warning",
            "slow request completed",
            route="/slow",
            status_code=200,
            duration_seconds=duration,
        )

        return {
            "status": "completed",
            "message": "Slow request generated for observability testing.",
            "duration_seconds": duration,
        }


@app.get("/error")
def error():
    with tracer.start_as_current_span(
        "intentional-error"
    ) as span:
        span.set_attribute(
            "error.intentional",
            True,
        )

        log_event(
            "error",
            "intentional application failure",
            route="/error",
            status_code=500,
            error_type="observability_test",
        )

        raise HTTPException(
            status_code=500,
            detail="Intentional failure generated for observability testing.",
        )