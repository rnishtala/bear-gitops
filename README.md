# Bear GitOps 🐻

A demo payment service for AutoSRE incident management demonstrations.

## Overview

This is a simple payment processing service that demonstrates:
- GitOps configuration management
- Configurable latency/error injection
- CI/CD with automatic deployment
- Integration with AutoSRE for incident remediation

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Payment API    │──────│   Config File   │──────│   AutoSRE       │
│  (FastAPI)      │      │   (YAML)        │      │   Remediation   │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

## Configuration

The service reads from `config/payment-service.yaml`:

```yaml
service:
  name: payment-service
  timeout_ms: 100           # Target response time
  max_retries: 3
  
database:
  connection_pool_size: 10  # Increase for high traffic
  query_timeout_ms: 50
  
features:
  rate_limiting: true
  circuit_breaker: true
```

## Known Issues

⚠️ **Current Config Issue**: The `connection_pool_size` is set too low, causing 
connection contention and high latency under load. AutoSRE can detect and fix this!

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python -m uvicorn app.main:app --reload --port 8001
```

## Deployment

Merging to `main` triggers automatic deployment via GitHub Actions.

## Demo Scenario

1. Service experiences high latency due to config error
2. AutoSRE detects the issue via Jaeger traces
3. AI triage identifies root cause: connection pool exhaustion
4. Remediation agent creates PR to fix config
5. After approval and merge, CI/CD deploys the fix
6. Latency returns to normal
