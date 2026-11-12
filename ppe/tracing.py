"""Optional manual spans; full payloads require explicit content opt-in."""

import os
from contextlib import contextmanager, suppress
from urllib.request import urlopen

from ppe.config import Settings


def tracing_settings(settings: Settings) -> Settings | None:
    if not settings.tracing_enabled:
        return None
    try:
        if not settings.tracking_uri.startswith(("http://", "https://")):
            return None
        with urlopen(
            settings.tracking_uri.rstrip("/") + "/health", timeout=0.6
        ) as response:
            if response.status != 200:
                return None
        os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "2")
        os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "0")
        os.environ.setdefault("MLFLOW_ENABLE_TELEMETRY", "false")
        import mlflow

        mlflow.set_tracking_uri(settings.tracking_uri)
        mlflow.set_experiment(settings.experiment)
        return settings
    except Exception:
        return None


def annotate(span, **attributes):
    if span is not None:
        with suppress(Exception):
            span.set_attributes(attributes)


def trace_error(span, error_code=None):
    """Mark failure without recording exception messages or stack traces."""
    if error_code is not None:
        annotate(span, error_code=error_code)
    if span is not None:
        with suppress(Exception):
            span.set_status("ERROR")


def trace_output(settings, span, output):
    if span is not None and settings and settings.trace_content:
        with suppress(Exception):
            span.set_outputs(
                output.model_dump(mode="json")
                if hasattr(output, "model_dump")
                else output
            )


@contextmanager
def trace_span(settings, name, kind, inputs=None, **attributes):
    context, span = None, None
    if settings:
        try:
            import mlflow

            context = mlflow.start_span(name=name, span_type=kind)
            span = context.__enter__()
            annotate(span, **attributes)
            if settings.trace_content:
                span.set_inputs(inputs)
        except Exception:
            if span is None:
                context = None
    try:
        yield span
    except Exception as exc:
        trace_error(span, error_code=type(exc).__name__)
        raise
    finally:
        if context is not None:
            with suppress(Exception):
                context.__exit__(None, None, None)  # No exception payloads in traces.
