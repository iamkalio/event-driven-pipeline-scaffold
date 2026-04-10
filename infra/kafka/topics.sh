#!/usr/bin/env bash
set -euo pipefail

KAFKA_BIN=${KAFKA_BIN:-/opt/bitnami/kafka/bin/kafka-topics.sh}
BOOTSTRAP=${BOOTSTRAP:-kafka:9092}

"$KAFKA_BIN" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic runtime-events --partitions 24 --replication-factor 1
"$KAFKA_BIN" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic threat-events --partitions 12 --replication-factor 1
"$KAFKA_BIN" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic runtime-events-dlq --partitions 6 --replication-factor 1
