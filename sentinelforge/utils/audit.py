import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from sentinelforge.utils.logging import get_logger, request_id_ctx

logger = get_logger("sentinelforge.audit")


class AuditEvent(BaseModel):
    """Structured audit trail record for sandbox and agent actions."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str
    severity: str = "INFO"
    request_id: Optional[str] = None
    target_path: Optional[str] = None
    command: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True


class AuditLogger:
    """Manages appending and querying audit trail records."""

    def __init__(self, audit_log_path: Optional[Path] = None):
        self.audit_log_path = audit_log_path or Path(".sentinelforge/audit.jsonl")
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._in_memory_events: List[AuditEvent] = []

    def record_event(
        self,
        event_type: str,
        severity: str = "INFO",
        target_path: Optional[str] = None,
        command: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> AuditEvent:
        """Records an audit event to file and memory."""
        req_id = request_id_ctx.get()
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            request_id=req_id,
            target_path=target_path,
            command=command,
            details=details or {},
            success=success,
        )

        self._in_memory_events.append(event)

        log_fn = logger.warning if severity in ("WARNING", "SECURITY_ALERT") else logger.info
        log_fn(
            f"Audit [{event_type}] success={success}",
            extra={"extra": event.model_dump()},
        )

        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit event to file: {e}")

        return event

    def get_recent_events(self, limit: int = 50) -> List[AuditEvent]:
        """Returns the most recent audit events."""
        return self._in_memory_events[-limit:]


audit_logger = AuditLogger()

