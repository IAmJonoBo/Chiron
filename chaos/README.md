# Chaos Testing for Chiron

This directory contains chaos engineering experiments for validating Chiron's resilience and reliability.

## Overview

Chaos testing helps validate system behavior under adverse conditions:
- Service failures
- Network issues
- Resource constraints
- High load
- Dependency failures

## Prerequisites

Install chaos testing dependencies:

```bash
uv pip install chaostoolkit chaostoolkit-http requests
```

## Running Experiments

### Service Availability Under Load

Test that the service remains available under HTTP load:

```bash
# Start the Chiron service first
docker-compose -f docker-compose.observability.yml up -d chiron-service

# Run the experiment
chaos run chaos/experiments/service-availability.json
```

## Experiment Structure

Each experiment JSON file contains:

1. **Steady-State Hypothesis**: Defines normal system behavior
2. **Method**: Actions to inject chaos
3. **Rollbacks**: Actions to restore system state (optional)

## Custom Probes and Actions

### Probes (in `probes.py`)

- `check_response_time`: Verify response time is within threshold
- `check_service_health`: Verify service health endpoint

### Actions (in `actions.py`)

- `generate_http_load`: Send concurrent HTTP requests

## Creating New Experiments

1. Create a new JSON file in `chaos/experiments/`
2. Define the steady-state hypothesis
3. Add chaos actions to the method
4. Optionally add rollback actions
5. Test the experiment locally
6. Document the experiment in this README

## Best Practices

1. **Start Small**: Begin with simple experiments
2. **Monitor**: Watch metrics and logs during experiments
3. **Document**: Record findings and improvements
4. **Automate**: Integrate experiments into CI/CD
5. **Gradual Complexity**: Increase chaos intensity over time

## Integration with CI/CD

Chaos experiments can be run in CI:

```yaml
# .github/workflows/chaos-tests.yml
- name: Run chaos tests
  run: |
    docker-compose -f docker-compose.observability.yml up -d
    chaos run chaos/experiments/service-availability.json
```

## Further Reading

- [Chaos Toolkit Documentation](https://chaostoolkit.org/)
- [Principles of Chaos Engineering](https://principlesofchaos.org/)
- [Chaos Engineering Book](https://www.oreilly.com/library/view/chaos-engineering/9781491988459/)
