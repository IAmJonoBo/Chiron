"""LLM-assisted contract testing for the Chiron MCP server."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from chiron.mcp.server import MCPServer


class LLMClient(Protocol):
    """Protocol for lightweight LLM clients."""

    def generate(self, prompt: str) -> str:  # pragma: no cover - interface
        """Return a string response for the provided prompt."""


@dataclass(slots=True)
class ContractScenario:
    """Scenario executed via LLM guidance."""

    prompt: str
    expected_keys: set[str]
    description: str = ""


@dataclass(slots=True)
class ContractExecution:
    """Execution result for a contract scenario."""

    scenario: ContractScenario
    tool: str
    arguments: dict[str, Any]
    response: dict[str, Any]


class ContractAssertionError(RuntimeError):
    """Raised when contract validation fails."""


class DeterministicLLMClient:
    """Simple client returning predetermined responses."""

    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses

    def generate(self, prompt: str) -> str:
        try:
            return self._responses[prompt]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"No deterministic response configured for prompt: {prompt}") from exc


class LLMContractRunner:
    """Run contract scenarios using an LLM client to propose tool invocations."""

    def __init__(self, client: LLMClient, server: MCPServer | None = None) -> None:
        self.client = client
        self.server = server or MCPServer()

    def run(self, scenario: ContractScenario) -> ContractExecution:
        payload = self.client.generate(scenario.prompt)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ContractAssertionError(f"LLM response is not valid JSON: {payload}") from exc

        tool = data.get("tool")
        if not tool:
            raise ContractAssertionError("LLM response must include a tool field")

        arguments = data.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ContractAssertionError("LLM arguments must be a JSON object")

        response = self.server.execute_tool(tool, arguments)
        missing = scenario.expected_keys - response.keys()
        if missing:
            raise ContractAssertionError(
                f"Missing expected keys in response for {tool}: {', '.join(sorted(missing))}"
            )

        return ContractExecution(
            scenario=scenario,
            tool=tool,
            arguments=arguments,
            response=response,
        )

    def run_all(self, scenarios: Iterable[ContractScenario]) -> list[ContractExecution]:
        return [self.run(scenario) for scenario in scenarios]


def default_scenarios() -> list[ContractScenario]:
    """Default scenarios covering key MCP tools."""

    return [
        ContractScenario(
            prompt=(
                "Select the health check tool and invoke it with no arguments, "
                "returning a JSON object including status and version."
            ),
            expected_keys={"status", "version", "components"},
            description="Validate service health metadata",
        ),
        ContractScenario(
            prompt=(
                "Invoke the wheelhouse builder tool in dry-run mode and return a JSON "
                "object describing the status and message fields."
            ),
            expected_keys={"status", "message", "version"},
            description="Verify wheelhouse orchestration contract",
        ),
    ]


def default_llm_client() -> DeterministicLLMClient:
    """Return a deterministic client suitable for tests and CI."""

    responses = {
        default_scenarios()[0].prompt: json.dumps({
            "tool": "chiron_health_check",
            "arguments": {},
        }),
        default_scenarios()[1].prompt: json.dumps({
            "tool": "chiron_build_wheelhouse",
            "arguments": {"dry_run": True},
        }),
    }
    return DeterministicLLMClient(responses)


def run_default_contracts(client: LLMClient | None = None) -> list[ContractExecution]:
    """Execute the default contract scenarios."""

    runner = LLMContractRunner(client or default_llm_client())
    return runner.run_all(default_scenarios())


__all__ = [
    "ContractScenario",
    "ContractExecution",
    "LLMContractRunner",
    "DeterministicLLMClient",
    "ContractAssertionError",
    "default_scenarios",
    "default_llm_client",
    "run_default_contracts",
]
