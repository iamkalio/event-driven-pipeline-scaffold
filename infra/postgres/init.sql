CREATE TABLE IF NOT EXISTS hosts (
    id UUID PRIMARY KEY,
    hostname TEXT NOT NULL,
    cloud_provider TEXT,
    region TEXT,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runtime_event_registry (
    id UUID PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_events (
    id UUID NOT NULL REFERENCES runtime_event_registry(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    host_id UUID NOT NULL REFERENCES hosts(id),
    source_type TEXT NOT NULL,
    library_name TEXT,
    function_name TEXT,
    syscall_type TEXT,
    network_dest INET,
    severity INT NOT NULL,
    raw_payload JSONB NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ
) PARTITION BY RANGE (captured_at);

DO $$
DECLARE
    start_date DATE := date_trunc('month', CURRENT_DATE)::date;
    end_date DATE := (date_trunc('month', CURRENT_DATE) + INTERVAL '1 month')::date;
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS runtime_events_current PARTITION OF runtime_events FOR VALUES FROM (%L) TO (%L)',
        start_date,
        end_date
    );
END $$;

CREATE TABLE IF NOT EXISTS vulnerabilities (
    id UUID PRIMARY KEY,
    cve_id TEXT UNIQUE NOT NULL,
    severity INT NOT NULL,
    epss_score DOUBLE PRECISION NOT NULL,
    actively_exploited BOOLEAN NOT NULL DEFAULT FALSE,
    published_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS event_vulnerabilities (
    event_id UUID NOT NULL REFERENCES runtime_event_registry(id) ON DELETE CASCADE,
    vuln_id UUID NOT NULL REFERENCES vulnerabilities(id) ON DELETE CASCADE,
    match_reason TEXT NOT NULL,
    matched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, vuln_id)
);

CREATE TABLE IF NOT EXISTS libraries (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    language TEXT NOT NULL,
    licence TEXT NOT NULL,
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS event_libraries (
    event_id UUID NOT NULL REFERENCES runtime_event_registry(id) ON DELETE CASCADE,
    library_id UUID NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
    access_type TEXT NOT NULL,
    PRIMARY KEY (event_id, library_id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES runtime_event_registry(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    dedup_hash TEXT UNIQUE NOT NULL,
    fired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumer_group TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_enrichment (
    id UUID PRIMARY KEY,
    event_id TEXT NOT NULL,
    host_id UUID NOT NULL,
    process_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    arrived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempt_count INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_runtime_events_open_high
    ON runtime_events (severity, captured_at DESC)
    WHERE severity >= 4 AND resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_event_vulnerabilities_vuln_id
    ON event_vulnerabilities (vuln_id);

CREATE INDEX IF NOT EXISTS idx_event_libraries_library_id
    ON event_libraries (library_id);

CREATE INDEX IF NOT EXISTS idx_alerts_dedup_hash
    ON alerts (dedup_hash);
