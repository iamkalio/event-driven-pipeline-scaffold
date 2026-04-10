"""Prometheus metrics definitions for ingestion and processing."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class MetricsService:
    """Owns Prometheus metrics without relying on module globals."""

    def __init__(self) -> None:
        """Create a fresh collector registry and metrics.

        Args:
            None.

        Returns:
            None.
        """
        self.registry = CollectorRegistry(auto_describe=True)
        self.events_ingested_total = Counter(
            'events_ingested_total',
            'Total ingested events.',
            ['source_type'],
            registry=self.registry,
        )
        self.events_processed_total = Counter(
            'events_processed_total',
            'Total processed events by status.',
            ['status'],
            registry=self.registry,
        )
        self.enrichment_latency_seconds = Histogram(
            'enrichment_latency_seconds',
            'Latency for enrichment operations.',
            registry=self.registry,
        )
        self.dlq_depth = Gauge(
            'dlq_depth',
            'Current depth of the DLQ.',
            registry=self.registry,
        )
        self.alert_fired_total = Counter(
            'alert_fired_total',
            'Total alerts fired by channel.',
            ['channel'],
            registry=self.registry,
        )
        self.consumer_lag = Gauge(
            'consumer_lag',
            'Consumer lag by topic and partition.',
            ['topic', 'partition'],
            registry=self.registry,
        )

    def mark_ingested(self, source_type: str) -> None:
        """Increment the ingestion counter.

        Args:
            source_type: Event source label.

        Returns:
            None.
        """
        self.events_ingested_total.labels(source_type=source_type).inc()

    def mark_processed(self, status: str) -> None:
        """Increment the processing counter.

        Args:
            status: Processing outcome label.

        Returns:
            None.
        """
        self.events_processed_total.labels(status=status).inc()

    def mark_alert(self, channel: str) -> None:
        """Increment the alert counter.

        Args:
            channel: Delivery channel label.

        Returns:
            None.
        """
        self.alert_fired_total.labels(channel=channel).inc()

    def set_consumer_lag(self, topic: str, partition: int, lag: int) -> None:
        """Update the consumer lag gauge.

        Args:
            topic: Kafka topic name.
            partition: Kafka partition number.
            lag: Current lag value.

        Returns:
            None.
        """
        self.consumer_lag.labels(topic=topic, partition=str(partition)).set(lag)

    def set_dlq_depth(self, depth: int) -> None:
        """Update the DLQ depth gauge.

        Args:
            depth: Number of queued DLQ records.

        Returns:
            None.
        """
        self.dlq_depth.set(depth)
