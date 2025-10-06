from __future__ import annotations

import json

import pytest

from chiron.mcp.llm_contracts import (
    ContractAssertionError,
    ContractScenario,
    DeterministicLLMClient,
    LLMContractRunner,
    default_llm_client,
    default_scenarios,
)


class StubClient:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def generate(self, prompt: str) -> str:
        return self.payload


def test_runner_validates_expected_keys(monkeypatch):
    scenario = ContractScenario(
        prompt="Use health tool", expected_keys={"status", "version"}
    )
    payload = json.dumps({"tool": "chiron_health_check", "arguments": {}})
    client = StubClient(payload)
    runner = LLMContractRunner(client)

    execution = runner.run(scenario)
    assert execution.tool == "chiron_health_check"
    assert "status" in execution.response


def test_runner_raises_for_missing_keys():
    scenario = ContractScenario(prompt="Bad", expected_keys={"status", "packages"})
    payload = json.dumps({"tool": "chiron_build_wheelhouse", "arguments": {"dry_run": True}})
    client = StubClient(payload)
    runner = LLMContractRunner(client)

    with pytest.raises(ContractAssertionError):
        runner.run(scenario)


def test_default_client_covers_default_scenarios():
    client = default_llm_client()
    runner = LLMContractRunner(client)
    results = runner.run_all(default_scenarios())
    assert len(results) == 2
    assert all(result.response for result in results)


def test_deterministic_client_requires_configured_prompt():
    client = DeterministicLLMClient({"known": "{}"})
    with pytest.raises(KeyError):
        client.generate("unknown")
