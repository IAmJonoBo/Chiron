# Chiron Observability Sandbox

This Docker Compose setup provides a complete local observability stack for Chiron development and testing.

## Components

- **OpenTelemetry Collector**: Receives traces, metrics, and logs from Chiron
- **Jaeger**: Trace visualization and analysis
- **Grafana Tempo**: Alternative trace backend
- **Prometheus**: Metrics storage and querying
- **Grafana**: Unified dashboard for metrics, traces, and logs
- **Loki**: Log aggregation and querying
- **Chiron Service**: The Chiron FastAPI service instrumented with OpenTelemetry

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- At least 4GB of free RAM

### Start the Stack

```bash
docker-compose -f docker-compose.observability.yml up -d
```

### Access UIs

- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger UI**: http://localhost:16686
- **Prometheus**: http://localhost:9090
- **Chiron Service**: http://localhost:8000
- **Chiron API Docs**: http://localhost:8000/docs

### Generate Test Traffic

```bash
# Send some requests to generate traces
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/status
curl http://localhost:8000/docs
```

### View Traces

1. Open Jaeger UI: http://localhost:16686
2. Select "chiron" service
3. Click "Find Traces"
4. Explore the traces and spans

### View Metrics

1. Open Grafana: http://localhost:3000
2. Navigate to "Explore"
3. Select "Prometheus" as data source
4. Query for Chiron metrics

### View Logs

1. Open Grafana: http://localhost:3000
2. Navigate to "Explore"
3. Select "Loki" as data source
4. Query logs with `{service_name="chiron"}`

## Configuration

### OpenTelemetry Collector

The collector configuration is in `otel-collector-config.yaml`. It:
- Receives OTLP data on ports 4317 (gRPC) and 4318 (HTTP)
- Exports traces to Jaeger and Tempo
- Exports metrics to Prometheus
- Exports logs to Loki

### Prometheus

Scrapes metrics from:
- OpenTelemetry Collector
- Chiron service
- Jaeger
- Tempo
- Loki

Configuration in `prometheus.yml`.

### Grafana

Pre-configured data sources:
- Prometheus (metrics)
- Jaeger (traces)
- Tempo (traces)
- Loki (logs)

Provisioning configuration in `grafana-provisioning/`.

## Chiron Integration

The Chiron service is configured with OpenTelemetry environment variables:

```yaml
environment:
  - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
  - OTEL_SERVICE_NAME=chiron
  - OTEL_RESOURCE_ATTRIBUTES=deployment.environment=local,service.version=0.1.0
```

This enables automatic instrumentation of:
- HTTP requests (FastAPI)
- Database queries
- External API calls
- Custom spans and metrics

## Development Workflow

1. **Start the stack**: `docker-compose -f docker-compose.observability.yml up -d`
2. **Make code changes** to Chiron
3. **Rebuild Chiron service**: `docker-compose -f docker-compose.observability.yml build chiron-service`
4. **Restart Chiron**: `docker-compose -f docker-compose.observability.yml restart chiron-service`
5. **View telemetry** in Grafana/Jaeger
6. **Stop the stack**: `docker-compose -f docker-compose.observability.yml down`

## Troubleshooting

### Check Service Health

```bash
# Check all services
docker-compose -f docker-compose.observability.yml ps

# Check logs
docker-compose -f docker-compose.observability.yml logs -f chiron-service
docker-compose -f docker-compose.observability.yml logs -f otel-collector
```

### Verify OpenTelemetry Collector

```bash
# Check health
curl http://localhost:13133/

# Check metrics
curl http://localhost:8888/metrics
```

### Reset Data

To start fresh:

```bash
docker-compose -f docker-compose.observability.yml down -v
docker-compose -f docker-compose.observability.yml up -d
```

## Production Considerations

This setup is for **local development only**. For production:

1. Use managed services or properly configured self-hosted solutions
2. Enable authentication and TLS
3. Configure retention policies
4. Set up proper resource limits
5. Use persistent storage
6. Configure alerting
7. Follow security best practices

## Further Reading

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Tempo Documentation](https://grafana.com/docs/tempo/)
- [Grafana Loki Documentation](https://grafana.com/docs/loki/)
