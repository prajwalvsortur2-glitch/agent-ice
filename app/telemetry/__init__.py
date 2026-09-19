"""Structured telemetry for Agent ICE.

Emits structured JSON logs internally. Also exposes an optional
OpenTelemetry-style hook (`app.telemetry.otel`) so a future deployment can
attach a real exporter without touching application code.
"""