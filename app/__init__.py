"""Agent ICE — Intent-to-Action Security Controller.

Top-level package. The application is split into clearly separated layers:

    app.agent      — planner / agent behavior (untrusted decision maker)
    app.ice        — trusted security decision + enforcement
    app.llm        — local Ollama/Qwen integration (contextual evidence only)
    app.tools      — safe mock tool implementations
    app.security   — low-level deterministic validators
    app.storage    — SQLite persistence via SQLAlchemy
    app.telemetry  — structured logging and security events
    app.api        — HTTP routes (thin; delegate to services)
"""

__version__ = "0.1.0"