"""Shared domain models used across ingestion, processing, and API layers."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, IPvAnyAddress


class SourceType(StrEnum):
    """Supported event source types."""

    EBPF = 'ebpf'
    SDK_AGENT = 'sdk_agent'
    AI_HOOKS = 'ai_hooks'
    THREAT_FEEDS = 'threat_feeds'
    KERNEL = 'kernel'
    USER = 'user'


class HostMetadata(BaseModel):
    """Host metadata attached during enrichment."""

    id: UUID
    hostname: str
    cloud_provider: str | None = None
    region: str | None = None
    registered_at: datetime


class RawEvent(BaseModel):
    """Normalized event stored in Kafka and PostgreSQL."""

    event_id: str
    host_id: UUID
    source_type: str
    event_type: str
    process_id: str
    captured_at: datetime
    received_at: datetime
    library_name: str | None = None
    function_name: str | None = None
    syscall_type: str | None = None
    network_dest: IPvAnyAddress | None = None
    severity: int = Field(default=0, ge=0, le=10)
    raw_payload: dict[str, object]


class JoinedEvent(BaseModel):
    """Correlated kernel and user events."""

    event_id: str
    host_id: UUID
    process_id: str
    kernel: RawEvent | None = None
    user: RawEvent | None = None


class VulnerabilityMatch(BaseModel):
    """Vulnerability context attached to an enriched event."""

    cve_id: str
    severity: int
    epss_score: float
    actively_exploited: bool
    published_at: datetime | None = None


class EnrichedEvent(BaseModel):
    """Joined event with host and vulnerability context."""

    event_id: str
    host_id: UUID
    process_id: str
    source_type: str
    captured_at: datetime
    library_name: str | None = None
    function_name: str | None = None
    syscall_type: str | None = None
    network_dest: str | None = None
    severity: int = Field(ge=0, le=10)
    host: HostMetadata | None = None
    vulnerabilities: list[VulnerabilityMatch] = Field(default_factory=list)
    context: dict[str, object] = Field(default_factory=dict)


class ThreatAssessment(BaseModel):
    """Threat engine output used by alerting."""

    should_alert: bool
    severity: int
    score: float
    reason: str
    channels: list[str] = Field(default_factory=list)


class DLQEvent(BaseModel):
    """Dead-letter payload for failed processing attempts."""

    topic: str
    key: str
    consumer_group: str
    error: str
    failed_at: datetime
    event: RawEvent


class EventQuery(BaseModel):
    """Dashboard query parameters for runtime events."""

    severity: int = Field(default=0, ge=0, le=10)
    resolved: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    from_ts: datetime | None = None
    to_ts: datetime | None = None
