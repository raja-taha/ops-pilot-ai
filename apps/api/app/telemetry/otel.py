from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("otel")


def setup_otel(app) -> None:
    """Enable tracing only when useful locally.

    Default local mode: off (no OTLP collector noise).
    Set OTEL_ENABLED=true and optionally OTEL_EXPORT_OTLP=true when a collector
    is running on OTEL_EXPORTER_OTLP_ENDPOINT.
    """
    settings = get_settings()
    if not settings.otel_enabled:
        logger.info("otel_disabled")
        return
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)

        if settings.app_env == "development":
            # Quiet console exporter — avoid dumping full exception spans
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        else:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        if settings.otel_export_otlp:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(
                endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces"
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "otel_otlp_enabled",
                endpoint=settings.otel_exporter_otlp_endpoint,
            )

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("otel_enabled", service=settings.otel_service_name)
    except Exception as exc:
        logger.warning("otel_setup_failed", error=str(exc))
