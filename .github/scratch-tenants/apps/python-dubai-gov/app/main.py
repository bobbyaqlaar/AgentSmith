"""A scratch tenant on the dubai-gov compliance profile."""

from fastapi import FastAPI
from opentelemetry import trace

app = FastAPI()
tracer = trace.get_tracer("scratch.dubai-gov")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    with tracer.start_as_current_span("healthz"):
        return {"status": "ok"}
