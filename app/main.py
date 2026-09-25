import os
import random
import time

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

app = FastAPI(
    title="Observability Demo API",
    description="FastAPI workload instrumented with OpenTelemetry and Prometheus.",
    version="1.0.0",
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
    return {
        "service": SERVICE_NAME,
        "message": "Platform Engineering Observability Demo",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
    }


@app.get("/work")
def work():
    with tracer.start_as_current_span("perform-demo-work") as span:
        duration = random.uniform(0.1, 0.5)

        span.set_attribute("work.type", "demo")
        span.set_attribute("work.duration_seconds", duration)

        time.sleep(duration)

        with tracer.start_as_current_span("database-simulation"):
            time.sleep(random.uniform(0.05, 0.15))

        return {
            "status": "completed",
            "duration_seconds": round(duration, 3),
        }


@app.get("/slow")
def slow():
    with tracer.start_as_current_span("slow-operation") as span:
        duration = 2.0

        span.set_attribute("operation.slow", True)
        span.set_attribute("operation.duration_seconds", duration)

        time.sleep(duration)

        return {
            "status": "completed",
            "message": "Slow request generated for observability testing.",
            "duration_seconds": duration,
        }


@app.get("/error")
def error():
    with tracer.start_as_current_span("intentional-error") as span:
        span.set_attribute("error.intentional", True)

        raise HTTPException(
            status_code=500,
            detail="Intentional failure generated for observability testing.",
        )