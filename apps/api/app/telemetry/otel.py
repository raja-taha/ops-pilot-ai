from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("otel")


def setup_otel(app) -> None:
    settings = get_settings()
    if not settings.otel_enabled:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        try:
            exporter = OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception as exc:
            logger.warning("otlp_exporter_unavailable", error=str(exc))

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("otel_enabled", service=settings.otel_service_name)
    except Exception as exc:
        logger.warning("otel_setup_failed", error=str(exc))
