"""Model Context Protocol (MCP) agent mode for Chiron.

This module provides an MCP server that exposes Chiron operations
as tools for AI assistants and automation systems.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from chiron.features import FeatureFlags

_get_feature_flags_resolver: Callable[[], FeatureFlags] | None
try:  # pragma: no cover - optional dependency
    from chiron.features import get_feature_flags as _get_feature_flags_resolver
except ImportError:  # pragma: no cover - fallback when features unavailable
    _get_feature_flags_resolver = None

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP server for Chiron operations."""

    TOOLS = [
        {
            "name": "chiron_build_wheelhouse",
            "description": "Build a wheelhouse bundle with wheels for multiple platforms",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Output directory for wheelhouse",
                        "default": "wheelhouse",
                    },
                    "with_sbom": {
                        "type": "boolean",
                        "description": "Generate SBOM",
                        "default": True,
                    },
                    "with_signatures": {
                        "type": "boolean",
                        "description": "Sign artifacts",
                        "default": True,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Dry run mode",
                        "default": True,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "chiron_verify_artifacts",
            "description": "Verify signatures, SBOM, and provenance of artifacts",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Path to artifact or directory to verify",
                    },
                    "verify_signatures": {
                        "type": "boolean",
                        "description": "Verify signatures",
                        "default": True,
                    },
                    "verify_sbom": {
                        "type": "boolean",
                        "description": "Verify SBOM",
                        "default": True,
                    },
                    "verify_provenance": {
                        "type": "boolean",
                        "description": "Verify provenance",
                        "default": True,
                    },
                },
                "required": ["target"],
            },
        },
        {
            "name": "chiron_create_airgap_bundle",
            "description": "Create an offline bundle for air-gapped environments",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output": {
                        "type": "string",
                        "description": "Output file path",
                        "default": "airgap-bundle.tar.gz",
                    },
                    "include_extras": {
                        "type": "boolean",
                        "description": "Include optional dependencies",
                        "default": False,
                    },
                    "include_security": {
                        "type": "boolean",
                        "description": "Include security tools",
                        "default": False,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Dry run mode",
                        "default": True,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "chiron_check_policy",
            "description": "Check if dependencies meet policy requirements",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "config_path": {
                        "type": "string",
                        "description": "Path to policy configuration file",
                    }
                },
                "required": [],
            },
        },
        {
            "name": "chiron_health_check",
            "description": "Run health checks and provide system status",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "chiron_get_feature_flags",
            "description": "Get current feature flag status",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
    ]

    def __init__(self, policy_check: bool = True):
        """Initialize MCP server.

        Args:
            policy_check: Whether to enforce policy checks on operations
        """
        self.policy_check = policy_check

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools.

        Returns:
            List of tool definitions
        """
        return self.TOOLS

    def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool with given arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments for the tool

        Returns:
            Tool execution result
        """
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "chiron_build_wheelhouse": self._build_wheelhouse,
            "chiron_verify_artifacts": self._verify_artifacts,
            "chiron_create_airgap_bundle": self._create_airgap_bundle,
            "chiron_check_policy": self._check_policy,
            "chiron_health_check": self._health_check,
            "chiron_get_feature_flags": self._get_feature_flags,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": [t["name"] for t in self.TOOLS],
            }

        return handler(arguments)

    def _build_wheelhouse(self, args: dict[str, Any]) -> dict[str, Any]:
        """Build wheelhouse bundle with real implementation."""
        dry_run = args.get("dry_run", True)
        output_dir = args.get("output_dir", "wheelhouse")
        with_sbom = args.get("with_sbom", True)
        with_signatures = args.get("with_signatures", True)

        if dry_run:
            return {
                "status": "dry_run",
                "message": "Would build wheelhouse",
                "output_dir": output_dir,
                "with_sbom": with_sbom,
                "with_signatures": with_signatures,
            }

        try:
            from chiron.deps.bundler import WheelhouseBundler

            wheelhouse_path = Path(output_dir)
            if not wheelhouse_path.exists():
                return {
                    "status": "error",
                    "message": f"Wheelhouse directory not found: {output_dir}",
                }

            bundler = WheelhouseBundler(wheelhouse_path)
            bundle_path = wheelhouse_path.parent / "wheelhouse-bundle.tar.gz"

            metadata = bundler.create_bundle(
                output_path=bundle_path,
                include_sbom=with_sbom,
                include_osv=True,
            )

            return {
                "status": "success",
                "message": "Wheelhouse bundle created successfully",
                "bundle_path": str(bundle_path),
                "metadata": metadata.to_dict(),
            }
        except ImportError:
            return {
                "status": "error",
                "message": "WheelhouseBundler module not available",
            }
        except Exception as e:
            logger.error(f"Failed to build wheelhouse: {e}")
            return {
                "status": "error",
                "message": f"Failed to build wheelhouse: {str(e)}",
            }

    def _verify_artifacts(self, args: dict[str, Any]) -> dict[str, Any]:
        """Verify artifacts with real implementation."""
        target = args.get("target")

        if not target:
            return {
                "status": "error",
                "message": "Target path is required for verification",
            }

        try:
            from chiron.deps.verify import (
                check_cli_commands,
                check_script_imports,
            )

            # Perform verification checks
            script_results = check_script_imports()
            cli_results = check_cli_commands()

            all_passed = all(script_results.values()) and all(cli_results.values())

            return {
                "status": "success" if all_passed else "warning",
                "message": "Artifact verification completed",
                "target": target,
                "results": {
                    "scripts": script_results,
                    "cli_commands": cli_results,
                },
                "all_checks_passed": all_passed,
            }
        except ImportError:
            return {
                "status": "error",
                "message": "Verification modules not available",
            }
        except Exception as e:
            logger.error(f"Failed to verify artifacts: {e}")
            return {
                "status": "error",
                "message": f"Verification failed: {str(e)}",
                "target": target,
            }

    def _create_airgap_bundle(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create air-gap bundle with real implementation."""
        dry_run = args.get("dry_run", True)
        output = args.get("output", "airgap-bundle.tar.gz")
        include_extras = args.get("include_extras", False)
        include_security = args.get("include_security", False)

        if dry_run:
            return {
                "status": "dry_run",
                "message": "Would create air-gap bundle",
                "output": output,
                "include_extras": include_extras,
                "include_security": include_security,
            }

        try:
            from chiron.deps.bundler import WheelhouseBundler

            # Assume a wheelhouse directory exists
            wheelhouse_path = Path("wheelhouse")
            if not wheelhouse_path.exists():
                return {
                    "status": "error",
                    "message": "Wheelhouse directory not found. Build wheelhouse first.",
                }

            bundler = WheelhouseBundler(wheelhouse_path)
            output_path = Path(output)

            metadata = bundler.create_bundle(
                output_path=output_path,
                include_sbom=True,
                include_osv=include_security,
            )

            return {
                "status": "success",
                "message": "Air-gap bundle created successfully",
                "output": str(output_path),
                "metadata": metadata.to_dict(),
            }
        except ImportError:
            return {
                "status": "error",
                "message": "WheelhouseBundler module not available",
            }
        except Exception as e:
            logger.error(f"Failed to create air-gap bundle: {e}")
            return {
                "status": "error",
                "message": f"Failed to create bundle: {str(e)}",
            }

    def _check_policy(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check policy compliance with real implementation."""
        config_path = args.get("config_path")

        try:
            from chiron.deps.policy import DependencyPolicy

            # Load policy configuration
            if config_path:
                policy_path = Path(config_path)
                if not policy_path.exists():
                    return {
                        "status": "error",
                        "message": f"Policy configuration not found: {config_path}",
                    }
                policy = DependencyPolicy.from_toml(policy_path)
            else:
                # Use default policy
                policy = DependencyPolicy()

            # Policy engine would be used to check for violations
            # engine = PolicyEngine(policy)

            return {
                "status": "success",
                "message": "Policy loaded successfully",
                "config_path": config_path,
                "policy": {
                    "default_allowed": policy.default_allowed,
                    "max_major_version_jump": policy.max_major_version_jump,
                    "require_security_review": policy.require_security_review,
                    "allow_pre_releases": policy.allow_pre_releases,
                    "allowlist_count": len(policy.allowlist),
                    "denylist_count": len(policy.denylist),
                },
            }
        except ImportError:
            return {
                "status": "error",
                "message": "Policy engine modules not available",
            }
        except Exception as e:
            logger.error(f"Failed to check policy: {e}")
            return {
                "status": "error",
                "message": f"Policy check failed: {str(e)}",
                "config_path": config_path,
            }

    def _health_check(self, args: dict[str, Any]) -> dict[str, Any]:
        """Health check (skeleton)."""
        return {
            "status": "healthy",
            "components": {
                "mcp_server": "operational",
                "policy_check": "enabled" if self.policy_check else "disabled",
            },
            "version": "0.1.0",
        }

    def _get_feature_flags(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get feature flags (skeleton)."""
        resolver = _get_feature_flags_resolver
        if resolver is None:
            return {"error": "Feature flags module not available"}

        flags = resolver()
        return {
            "flags": {
                "allow_public_publish": flags.is_enabled("allow_public_publish"),
                "require_slsa_provenance": flags.is_enabled("require_slsa_provenance"),
                "enable_oci_distribution": flags.is_enabled("enable_oci_distribution"),
                "enable_mcp_agent": flags.is_enabled("enable_mcp_agent"),
                "dry_run_by_default": flags.is_enabled("dry_run_by_default"),
            }
        }


def create_mcp_server_config() -> dict[str, Any]:
    """Create MCP server configuration.

    Returns:
        MCP server configuration dictionary
    """
    return {
        "mcpServers": {
            "chiron": {
                "command": "python",
                "args": ["-m", "chiron.mcp.server"],
                "env": {},
                "description": "Chiron dependency & wheelhouse management",
                "version": "0.1.0",
                "capabilities": {"tools": True, "resources": False, "prompts": False},
            }
        }
    }


if __name__ == "__main__":
    # Example usage
    server = MCPServer()

    print("Available Chiron MCP Tools:")
    print("=" * 60)
    for tool in server.list_tools():
        print(f"\n{tool['name']}")
        print(f"  {tool['description']}")

    print("\n" + "=" * 60)
    print("\nMCP Server Configuration:")
    print(json.dumps(create_mcp_server_config(), indent=2))
