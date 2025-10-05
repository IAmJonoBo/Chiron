# Grafana Dashboard Deployment Guide

This guide provides step-by-step instructions for deploying Chiron's Grafana dashboard to production.

## Overview

Chiron includes a pre-configured Grafana dashboard for monitoring:

- Build success rates and durations
- Security scan results
- SBOM generation status
- Artifact metrics
- Feature flag status
- Policy violations

**Dashboard Location**: `src/chiron/dashboards/grafana-dashboard.json`

---

## Prerequisites

- Grafana instance (v9.0+)
- Metrics data source configured (e.g., Prometheus, Tempo, or other compatible source)
- Chiron metrics being exported (see Metrics Setup below)
- Admin access to Grafana

---

## 1. Metrics Setup

### Configure OpenTelemetry Exporter

**In your application code**:

```python
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource

# Create resource
resource = Resource.create({"service.name": "chiron"})

# Create metrics exporter (Prometheus format compatible)
reader = PrometheusMetricReader()

# Create meter provider
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

# Now metrics will be available at http://localhost:8000/metrics
```

**Or configure via environment variables**:

```bash
export OTEL_EXPORTER_PROMETHEUS_PORT=8000
export OTEL_EXPORTER_PROMETHEUS_HOST=0.0.0.0
export OTEL_SERVICE_NAME=chiron
```

### Add Metrics Scrape Configuration

**For Prometheus-compatible backends, configure scraping in `prometheus.yml`**:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "chiron"
    static_configs:
      - targets: ["localhost:8000"]
        labels:
          environment: "production"
          service: "chiron"

    # Or use service discovery
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - chiron

    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: chiron
```

### Verify Metrics Collection

```bash
# Check metrics scraping targets
curl http://metrics-backend:9090/api/v1/targets

# Query a Chiron metric
curl http://metrics-backend:9090/api/v1/query?query=chiron_build_total
```

---

## 2. Dashboard Installation

### Method 1: Grafana UI

1. **Log in to Grafana**
   - Navigate to your Grafana instance
   - Log in with admin credentials

2. **Import Dashboard**
   - Click "+" → "Import" in left sidebar
   - Click "Upload JSON file"
   - Select `src/chiron/dashboards/grafana-dashboard.json`
   - Or paste JSON content directly

3. **Configure Data Source**
   - Select your metrics data source (Prometheus-compatible)
   - Click "Import"

4. **Verify Dashboard**
   - Dashboard should appear with panels
   - Check that data is loading

### Method 2: Grafana API

```bash
# Set variables
GRAFANA_URL="http://grafana:3000"
GRAFANA_API_KEY="your-api-key"
DASHBOARD_FILE="src/chiron/dashboards/grafana-dashboard.json"

# Import dashboard
curl -X POST \
  -H "Authorization: Bearer ${GRAFANA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @${DASHBOARD_FILE} \
  "${GRAFANA_URL}/api/dashboards/db"
```

### Method 3: Terraform

```hcl
resource "grafana_dashboard" "chiron" {
  config_json = file("${path.module}/src/chiron/dashboards/grafana-dashboard.json")

  folder      = grafana_folder.chiron.id
  overwrite   = true
}

resource "grafana_folder" "chiron" {
  title = "Chiron Monitoring"
}
```

### Method 4: Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: chiron-dashboard
  namespace: monitoring
  labels:
    grafana_dashboard: "1"
data:
  chiron-dashboard.json: |
    # Paste contents of grafana-dashboard.json here
---
# Dashboard will be automatically imported by Grafana sidecar
```

---

## 3. Dashboard Configuration

### Update Data Source

If your metrics data source has a different name:

1. Open dashboard settings (gear icon)
2. Click "JSON Model" tab
3. Find and replace data source references:
   ```json
   {
     "datasource": {
       "type": "prometheus",
       "uid": "YOUR_DATASOURCE_UID"
     }
   }
   ```

### Configure Variables

The dashboard includes several variables:

**Environment**:

```promql
label_values(chiron_build_total, environment)
```

**Platform**:

```promql
label_values(chiron_build_total{environment="$environment"}, platform)
```

**Time Range**: Use dashboard time picker (top right)

### Customize Thresholds

Adjust alert thresholds for your environment:

**Build Success Rate Panel**:

- Green: ≥98%
- Yellow: 95-98%
- Red: <95%

**To modify**:

1. Edit panel
2. Go to "Thresholds" section
3. Adjust values
4. Save dashboard

---

## 4. Panel Descriptions

### 1. Build Success Rate

**Query**: `rate(chiron_build_success_total[5m]) / rate(chiron_build_total[5m])`
**Description**: Percentage of successful builds
**Alert If**: <95%

### 2. Build Duration (p95)

**Query**: `histogram_quantile(0.95, rate(chiron_build_duration_bucket[5m]))`
**Description**: 95th percentile build time
**Alert If**: >600s (10 minutes)

### 3. Vulnerability Scan Results

**Query**: `sum by (severity) (chiron_vulnerabilities_total)`
**Description**: Security vulnerabilities by severity
**Alert If**: critical > 0

### 4. SBOM Generation Status

**Query**: `rate(chiron_sbom_generated_total[5m]) / rate(chiron_build_total[5m])`
**Description**: SBOM generation success rate
**Alert If**: <99%

### 5. Signature Verification Status

**Query**: `rate(chiron_signatures_verified_total[5m]) / rate(chiron_signatures_total[5m])`
**Description**: Signature verification success rate
**Alert If**: <99%

### 6. Wheelhouse Bundle Size

**Query**: `chiron_wheelhouse_size_bytes`
**Description**: Size of wheelhouse bundles over time
**Alert If**: Sudden large increases

### 7. Release Pipeline Stages

**Query**: `sum by (stage) (chiron_pipeline_stage_duration_sum)`
**Description**: Time spent in each pipeline stage
**Alert If**: Any stage >30 minutes

### 8. Active Feature Flags

**Query**: `chiron_feature_flag_enabled`
**Description**: Current feature flag status
**Alert If**: Unexpected changes

### 9. Policy Gate Violations

**Query**: `rate(chiron_policy_violations_total[5m])`
**Description**: Policy violations by type
**Alert If**: critical_policy > 0

---

## 5. Alerting Setup

### Create Alert Rules

**In Grafana**:

1. **High Build Failure Rate**

```yaml
alert: HighBuildFailureRate
expr: |
  rate(chiron_build_total[5m]) - rate(chiron_build_success_total[5m]) > 0.05
for: 10m
labels:
  severity: warning
annotations:
  summary: "High build failure rate detected"
  description: "Build failure rate is above 5% for 10 minutes"
```

2. **Critical Vulnerabilities**

```yaml
alert: CriticalVulnerabilities
expr: |
  chiron_vulnerabilities_total{severity="critical"} > 0
for: 1m
labels:
  severity: critical
annotations:
  summary: "Critical vulnerabilities detected"
  description: "{{ $value }} critical vulnerabilities found"
```

3. **SBOM Generation Failure**

```yaml
alert: SBOMGenerationFailure
expr: |
  rate(chiron_sbom_generated_total[5m]) / rate(chiron_build_total[5m]) < 0.99
for: 15m
labels:
  severity: warning
annotations:
  summary: "SBOM generation success rate below 99%"
```

### Configure Notifications

**In Grafana → Alerting → Contact Points**:

Add notification channels:

- Email
- Slack
- PagerDuty
- Webhook

Example Slack notification:

```json
{
  "channel": "#chiron-alerts",
  "text": "Alert: {{ .CommonAnnotations.summary }}",
  "attachments": [
    {
      "title": "{{ .GroupLabels.alertname }}",
      "text": "{{ .CommonAnnotations.description }}",
      "color": "{{ if eq .Status \"firing\" }}danger{{ else }}good{{ end }}"
    }
  ]
}
```

---

## 6. Production Deployment Checklist

### Pre-Deployment

- [ ] Metrics backend is scraping Chiron metrics
- [ ] Verify metrics in metrics backend: `/graph` or equivalent
- [ ] Test queries in metrics backend
- [ ] Grafana data source configured
- [ ] Dashboard JSON file validated

### Deployment

- [ ] Import dashboard to Grafana
- [ ] Configure data source
- [ ] Set appropriate time ranges
- [ ] Configure variables
- [ ] Adjust thresholds for your environment
- [ ] Test all panels load data

### Post-Deployment

- [ ] Verify all panels show data
- [ ] Test dashboard variables work
- [ ] Configure alert rules
- [ ] Set up notification channels
- [ ] Test alerts fire correctly
- [ ] Document dashboard URL
- [ ] Share with team

### Ongoing Maintenance

- [ ] Review and adjust thresholds monthly
- [ ] Update queries as metrics evolve
- [ ] Add new panels for new features
- [ ] Keep dashboard in version control
- [ ] Document any customizations

---

## 7. Troubleshooting

### No Data in Panels

**Check**:

1. Metrics backend is scraping Chiron: `http://metrics-backend:9090/targets`
2. Metrics exist: `curl http://localhost:8000/metrics | grep chiron`
3. Time range includes data
4. Data source is correct
5. Queries are valid

**Solution**:

```bash
# Verify metrics endpoint
curl http://localhost:8000/metrics

# Test metrics query
curl "http://metrics-backend:9090/api/v1/query?query=chiron_build_total"
```

### Incorrect Data Source

**Symptoms**: "Data source not found" error

**Solution**:

1. Go to dashboard settings → JSON Model
2. Replace data source UID:
   ```bash
   # Get your data source UID
   curl -H "Authorization: Bearer ${API_KEY}" \
     http://grafana:3000/api/datasources | jq '.[] | select(.type=="prometheus") | .uid'
   ```

### Panels Show "N/A"

**Check**:

- Query returns no results
- Labels don't match
- Time range is appropriate

**Solution**:
Test query in your metrics backend first, then update Grafana panel.

### High Cardinality Issues

**Symptoms**: Slow queries, high memory usage

**Solution**:

1. Review label usage
2. Add recording rules:
   ```yaml
   groups:
     - name: chiron
       interval: 30s
       rules:
         - record: chiron:build_success_rate:5m
           expr: rate(chiron_build_success_total[5m]) / rate(chiron_build_total[5m])
   ```

---

## 8. Advanced Configuration

### Multi-Environment Setup

Create separate dashboard folders:

- Production
- Staging
- Development

Use variables to switch between environments:

```json
{
  "templating": {
    "list": [
      {
        "name": "environment",
        "type": "query",
        "query": "label_values(chiron_build_total, environment)",
        "current": {
          "value": "production"
        }
      }
    ]
  }
}
```

### Custom Panels

Add organization-specific metrics:

```json
{
  "panels": [
    {
      "title": "Custom Metric",
      "targets": [
        {
          "expr": "your_custom_metric{environment=\"$environment\"}"
        }
      ]
    }
  ]
}
```

### Dashboard as Code

Manage dashboards in version control:

```bash
# Export dashboard
curl -H "Authorization: Bearer ${API_KEY}" \
  "http://grafana:3000/api/dashboards/uid/${DASHBOARD_UID}" \
  | jq '.dashboard' > dashboard.json

# Import dashboard
curl -X POST \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d @dashboard.json \
  "http://grafana:3000/api/dashboards/db"
```

---

## 9. Best Practices

### Dashboard Design

- Keep panels focused on single metrics
- Use consistent colors across dashboard
- Add descriptions to complex queries
- Group related panels together
- Use appropriate visualization types

### Performance

- Use recording rules for complex queries
- Set appropriate scrape intervals (15-30s)
- Limit time ranges for large datasets
- Use downsampling for long retention

### Security

- Use read-only API keys for viewing
- Restrict dashboard editing access
- Audit dashboard changes
- Protect sensitive metrics

### Documentation

- Document custom modifications
- Keep query explanations up to date
- Note threshold rationale
- Document alert escalation procedures

---

## 10. Next Steps

After deployment:

1. **Monitor dashboard usage**: Check which panels are most valuable
2. **Collect feedback**: Ask team what metrics they need
3. **Iterate**: Add panels for new features
4. **Automate**: Set up dashboard provisioning
5. **Scale**: Add dashboards for other components

---

## Support

For issues or questions:

- Check Grafana docs: https://grafana.com/docs/
- Check OpenTelemetry docs: https://opentelemetry.io/docs/
- Open issue: https://github.com/IAmJonoBo/Chiron/issues
- Review `GAP_ANALYSIS.md` for known limitations

---

## Conclusion

This guide provides comprehensive instructions for deploying Chiron's Grafana dashboard. The dashboard provides visibility into build processes, security scanning, and operational metrics essential for production monitoring.

Remember to customize thresholds and alerts for your specific environment and scale.
