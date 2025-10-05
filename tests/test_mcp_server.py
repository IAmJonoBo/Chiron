"""Tests for MCP server module."""

import json
from unittest.mock import Mock, patch

import pytest

from chiron.mcp.server import MCPServer, create_mcp_server_config


class TestMCPServer:
    """Test cases for MCPServer class."""

    def test_initialization_default(self):
        """Test MCPServer initialization with defaults."""
        server = MCPServer()

        assert server.policy_check is True

    def test_initialization_with_policy_disabled(self):
        """Test MCPServer initialization with policy check disabled."""
        server = MCPServer(policy_check=False)

        assert server.policy_check is False

    def test_list_tools(self):
        """Test listing available tools."""
        server = MCPServer()
        tools = server.list_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0

        # Check that all tools have required fields
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_list_tools_returns_correct_count(self):
        """Test that list_tools returns all defined tools."""
        server = MCPServer()
        tools = server.list_tools()

        # Should have at least the core tools
        tool_names = [tool["name"] for tool in tools]
        assert "chiron_build_wheelhouse" in tool_names
        assert "chiron_verify_artifacts" in tool_names
        assert "chiron_create_airgap_bundle" in tool_names
        assert "chiron_check_policy" in tool_names
        assert "chiron_health_check" in tool_names
        assert "chiron_get_feature_flags" in tool_names

    def test_tool_schemas_valid(self):
        """Test that all tool schemas are valid."""
        server = MCPServer()
        tools = server.list_tools()

        for tool in tools:
            schema = tool["inputSchema"]
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema
            assert isinstance(schema["required"], list)

    def test_execute_tool_build_wheelhouse_dry_run(self):
        """Test executing build_wheelhouse in dry run mode."""
        server = MCPServer()
        result = server.execute_tool("chiron_build_wheelhouse", {"dry_run": True})

        assert result["status"] == "dry_run"
        assert "message" in result
        assert "output_dir" in result

    def test_execute_tool_build_wheelhouse_with_args(self):
        """Test executing build_wheelhouse with custom arguments."""
        server = MCPServer()
        args = {
            "output_dir": "custom_wheelhouse",
            "with_sbom": False,
            "with_signatures": False,
            "dry_run": True,
        }
        result = server.execute_tool("chiron_build_wheelhouse", args)

        assert result["status"] == "dry_run"
        assert result["output_dir"] == "custom_wheelhouse"
        assert result["with_sbom"] is False
        assert result["with_signatures"] is False

    def test_execute_tool_build_wheelhouse_not_dry_run(self):
        """Test executing build_wheelhouse in non-dry-run mode."""
        server = MCPServer()
        result = server.execute_tool("chiron_build_wheelhouse", {"dry_run": False})

        assert result["status"] == "not_implemented"
        assert "message" in result

    def test_execute_tool_verify_artifacts(self):
        """Test executing verify_artifacts tool."""
        server = MCPServer()
        result = server.execute_tool(
            "chiron_verify_artifacts", {"target": "/path/to/artifacts"}
        )

        assert result["status"] == "not_implemented"
        assert result["target"] == "/path/to/artifacts"

    def test_execute_tool_create_airgap_bundle_dry_run(self):
        """Test executing create_airgap_bundle in dry run mode."""
        server = MCPServer()
        args = {
            "output": "custom-bundle.tar.gz",
            "include_extras": True,
            "include_security": True,
            "dry_run": True,
        }
        result = server.execute_tool("chiron_create_airgap_bundle", args)

        assert result["status"] == "dry_run"
        assert result["output"] == "custom-bundle.tar.gz"
        assert result["include_extras"] is True
        assert result["include_security"] is True

    def test_execute_tool_create_airgap_bundle_not_dry_run(self):
        """Test executing create_airgap_bundle in non-dry-run mode."""
        server = MCPServer()
        result = server.execute_tool("chiron_create_airgap_bundle", {"dry_run": False})

        assert result["status"] == "not_implemented"

    def test_execute_tool_check_policy(self):
        """Test executing check_policy tool."""
        server = MCPServer()
        result = server.execute_tool(
            "chiron_check_policy", {"config_path": "/path/to/config.yaml"}
        )

        assert result["status"] == "not_implemented"
        assert result["config_path"] == "/path/to/config.yaml"

    def test_execute_tool_health_check(self):
        """Test executing health_check tool."""
        server = MCPServer()
        result = server.execute_tool("chiron_health_check", {})

        assert result["status"] == "healthy"
        assert "components" in result
        assert "mcp_server" in result["components"]
        assert result["components"]["mcp_server"] == "operational"
        assert "version" in result

    def test_execute_tool_health_check_policy_enabled(self):
        """Test health check shows policy check status."""
        server = MCPServer(policy_check=True)
        result = server.execute_tool("chiron_health_check", {})

        assert result["components"]["policy_check"] == "enabled"

    def test_execute_tool_health_check_policy_disabled(self):
        """Test health check shows policy check disabled."""
        server = MCPServer(policy_check=False)
        result = server.execute_tool("chiron_health_check", {})

        assert result["components"]["policy_check"] == "disabled"

    def test_execute_tool_get_feature_flags_with_module(self):
        """Test executing get_feature_flags tool with features module."""
        server = MCPServer()

        with patch("chiron.mcp.server._get_feature_flags_resolver") as mock_resolver:
            mock_feature_manager = Mock()
            mock_feature_manager.is_enabled = Mock(return_value=True)
            mock_resolver.return_value = mock_feature_manager

            result = server.execute_tool("chiron_get_feature_flags", {})

            assert "flags" in result
            assert isinstance(result["flags"], dict)

    def test_execute_tool_get_feature_flags_without_module(self):
        """Test executing get_feature_flags tool without features module."""
        server = MCPServer()

        with patch("chiron.mcp.server._get_feature_flags_resolver", None):
            result = server.execute_tool("chiron_get_feature_flags", {})

            assert "error" in result
            assert "not available" in result["error"]

    def test_execute_tool_unknown(self):
        """Test executing unknown tool."""
        server = MCPServer()
        result = server.execute_tool("unknown_tool", {})

        assert "error" in result
        assert "available_tools" in result
        assert isinstance(result["available_tools"], list)

    def test_build_wheelhouse_defaults(self):
        """Test _build_wheelhouse with default arguments."""
        server = MCPServer()
        result = server._build_wheelhouse({})

        assert result["status"] == "dry_run"
        assert result["output_dir"] == "wheelhouse"
        assert result["with_sbom"] is True
        assert result["with_signatures"] is True

    def test_verify_artifacts_skeleton(self):
        """Test _verify_artifacts skeleton implementation."""
        server = MCPServer()
        result = server._verify_artifacts({"target": "/test/path"})

        assert result["status"] == "not_implemented"
        assert result["target"] == "/test/path"

    def test_create_airgap_bundle_defaults(self):
        """Test _create_airgap_bundle with default arguments."""
        server = MCPServer()
        result = server._create_airgap_bundle({})

        assert result["status"] == "dry_run"
        assert result["output"] == "airgap-bundle.tar.gz"
        assert result["include_extras"] is False
        assert result["include_security"] is False

    def test_check_policy_skeleton(self):
        """Test _check_policy skeleton implementation."""
        server = MCPServer()
        result = server._check_policy({})

        assert result["status"] == "not_implemented"

    def test_health_check_structure(self):
        """Test _health_check response structure."""
        server = MCPServer()
        result = server._health_check({})

        assert result["status"] == "healthy"
        assert "components" in result
        assert "version" in result
        assert result["version"] == "0.1.0"


class TestCreateMCPServerConfig:
    """Test cases for create_mcp_server_config function."""

    def test_create_config(self):
        """Test creating MCP server configuration."""
        config = create_mcp_server_config()

        assert "mcpServers" in config
        assert "chiron" in config["mcpServers"]

    def test_config_structure(self):
        """Test MCP server configuration structure."""
        config = create_mcp_server_config()
        chiron_config = config["mcpServers"]["chiron"]

        assert "command" in chiron_config
        assert "args" in chiron_config
        assert "env" in chiron_config
        assert "description" in chiron_config
        assert "version" in chiron_config
        assert "capabilities" in chiron_config

    def test_config_command(self):
        """Test MCP server command configuration."""
        config = create_mcp_server_config()
        chiron_config = config["mcpServers"]["chiron"]

        assert chiron_config["command"] == "python"
        assert chiron_config["args"] == ["-m", "chiron.mcp.server"]

    def test_config_capabilities(self):
        """Test MCP server capabilities."""
        config = create_mcp_server_config()
        capabilities = config["mcpServers"]["chiron"]["capabilities"]

        assert capabilities["tools"] is True
        assert capabilities["resources"] is False
        assert capabilities["prompts"] is False

    def test_config_serializable(self):
        """Test that config can be serialized to JSON."""
        config = create_mcp_server_config()

        # Should not raise exception
        json_str = json.dumps(config)
        assert isinstance(json_str, str)

        # Should be deserializable
        parsed = json.loads(json_str)
        assert parsed == config


class TestMCPServerTools:
    """Test cases for individual MCP tools."""

    def test_build_wheelhouse_tool_schema(self):
        """Test build_wheelhouse tool schema."""
        server = MCPServer()
        tools = server.list_tools()

        tool = next(t for t in tools if t["name"] == "chiron_build_wheelhouse")
        schema = tool["inputSchema"]
        properties = schema["properties"]

        assert "output_dir" in properties
        assert "with_sbom" in properties
        assert "with_signatures" in properties
        assert "dry_run" in properties

        # Check defaults
        assert properties["output_dir"]["default"] == "wheelhouse"
        assert properties["with_sbom"]["default"] is True
        assert properties["with_signatures"]["default"] is True
        assert properties["dry_run"]["default"] is True

    def test_verify_artifacts_tool_schema(self):
        """Test verify_artifacts tool schema."""
        server = MCPServer()
        tools = server.list_tools()

        tool = next(t for t in tools if t["name"] == "chiron_verify_artifacts")
        schema = tool["inputSchema"]

        assert "target" in schema["properties"]
        assert "target" in schema["required"]

    def test_create_airgap_bundle_tool_schema(self):
        """Test create_airgap_bundle tool schema."""
        server = MCPServer()
        tools = server.list_tools()

        tool = next(t for t in tools if t["name"] == "chiron_create_airgap_bundle")
        schema = tool["inputSchema"]
        properties = schema["properties"]

        assert "output" in properties
        assert "include_extras" in properties
        assert "include_security" in properties
        assert "dry_run" in properties

    def test_check_policy_tool_schema(self):
        """Test check_policy tool schema."""
        server = MCPServer()
        tools = server.list_tools()

        tool = next(t for t in tools if t["name"] == "chiron_check_policy")
        schema = tool["inputSchema"]

        assert "config_path" in schema["properties"]
        assert len(schema["required"]) == 0  # config_path is optional

    def test_health_check_tool_schema(self):
        """Test health_check tool schema."""
        server = MCPServer()
        tools = server.list_tools()

        tool = next(t for t in tools if t["name"] == "chiron_health_check")
        schema = tool["inputSchema"]

        assert len(schema["properties"]) == 0
        assert len(schema["required"]) == 0

    def test_get_feature_flags_tool_schema(self):
        """Test get_feature_flags tool schema."""
        server = MCPServer()
        tools = server.list_tools()

        tool = next(t for t in tools if t["name"] == "chiron_get_feature_flags")
        schema = tool["inputSchema"]

        assert len(schema["properties"]) == 0
        assert len(schema["required"]) == 0


class TestMCPServerIntegration:
    """Integration tests for MCP server."""

    def test_full_workflow(self):
        """Test complete workflow from initialization to tool execution."""
        # Initialize server
        server = MCPServer(policy_check=True)

        # List tools
        tools = server.list_tools()
        assert len(tools) > 0

        # Execute health check
        health_result = server.execute_tool("chiron_health_check", {})
        assert health_result["status"] == "healthy"

        # Execute build in dry run
        build_result = server.execute_tool("chiron_build_wheelhouse", {"dry_run": True})
        assert build_result["status"] == "dry_run"

        # Execute airgap bundle in dry run
        bundle_result = server.execute_tool(
            "chiron_create_airgap_bundle",
            {"output": "test-bundle.tar.gz", "dry_run": True},
        )
        assert bundle_result["status"] == "dry_run"

    def test_multiple_tool_executions(self):
        """Test executing multiple tools in sequence."""
        server = MCPServer()

        # Execute several tools
        results = []
        results.append(server.execute_tool("chiron_health_check", {}))
        results.append(
            server.execute_tool("chiron_build_wheelhouse", {"dry_run": True})
        )
        results.append(
            server.execute_tool("chiron_create_airgap_bundle", {"dry_run": True})
        )

        # All should succeed
        assert all("status" in r for r in results)
        assert results[0]["status"] == "healthy"
        assert results[1]["status"] == "dry_run"
        assert results[2]["status"] == "dry_run"

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        server = MCPServer()

        # Unknown tool
        result = server.execute_tool("nonexistent_tool", {})
        assert "error" in result

        # Invalid arguments (missing required field)
        result = server.execute_tool("chiron_verify_artifacts", {})
        # Should still execute but with None target
        assert result["status"] == "not_implemented"

    def test_config_generation_and_usage(self):
        """Test that generated config matches server capabilities."""
        server = MCPServer()
        config = create_mcp_server_config()

        # Config should reference the server module
        assert "chiron.mcp.server" in str(config)

        # Capabilities should match what server provides
        capabilities = config["mcpServers"]["chiron"]["capabilities"]
        assert capabilities["tools"] is True

        # Should have tools
        tools = server.list_tools()
        assert len(tools) > 0


class TestMCPServerEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_arguments(self):
        """Test tools with empty argument dictionaries."""
        server = MCPServer()

        # All tools should handle empty args
        result = server.execute_tool("chiron_build_wheelhouse", {})
        assert "status" in result

        result = server.execute_tool("chiron_health_check", {})
        assert "status" in result

    def test_extra_arguments(self):
        """Test tools with extra/unexpected arguments."""
        server = MCPServer()

        args = {
            "output_dir": "test",
            "unexpected_arg": "value",
            "another_extra": 123,
            "dry_run": True,
        }

        # Should not fail with extra arguments
        result = server.execute_tool("chiron_build_wheelhouse", args)
        assert result["status"] == "dry_run"

    def test_none_arguments(self):
        """Test tools with None values."""
        server = MCPServer()

        args = {"output_dir": None, "dry_run": True}

        # Should handle None values
        result = server.execute_tool("chiron_build_wheelhouse", args)
        assert "status" in result

    def test_policy_check_flag_effect(self):
        """Test that policy_check flag affects behavior correctly."""
        server_with_policy = MCPServer(policy_check=True)
        server_without_policy = MCPServer(policy_check=False)

        result_with = server_with_policy.execute_tool("chiron_health_check", {})
        result_without = server_without_policy.execute_tool("chiron_health_check", {})

        assert result_with["components"]["policy_check"] == "enabled"
        assert result_without["components"]["policy_check"] == "disabled"

    def test_tool_list_immutability(self):
        """Test that tools list is not modified by execution."""
        server = MCPServer()

        original_tools = server.list_tools()
        original_count = len(original_tools)

        # Execute some tools
        server.execute_tool("chiron_health_check", {})
        server.execute_tool("chiron_build_wheelhouse", {"dry_run": True})

        # Tools list should remain unchanged
        current_tools = server.list_tools()
        assert len(current_tools) == original_count
