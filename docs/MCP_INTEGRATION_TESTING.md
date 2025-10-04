# MCP Integration Testing Guide

This guide provides detailed instructions for testing Chiron's MCP (Model Context Protocol) server with actual MCP clients.

## Overview

Chiron implements an MCP server that exposes dependency management and wheelhouse operations as tools for AI assistants. This guide covers:

1. Setting up MCP clients
2. Configuring Chiron MCP server
3. Testing individual tools
4. Validating integration

---

## Prerequisites

- Chiron installed: `pip install chiron` or `pip install -e .`
- An MCP-compatible client (Claude Desktop, VS Code, etc.)
- Python 3.12+

---

## 1. MCP Client Setup

### Claude Desktop

1. **Install Claude Desktop** (if not already installed)
   - Download from https://claude.ai/download

2. **Locate config file**:
   ```bash
   # macOS
   ~/Library/Application\ Support/Claude/claude_desktop_config.json
   
   # Windows
   %APPDATA%\Claude\claude_desktop_config.json
   
   # Linux
   ~/.config/Claude/claude_desktop_config.json
   ```

3. **Add Chiron MCP server**:
   ```json
   {
     "mcpServers": {
       "chiron": {
         "command": "python",
         "args": ["-m", "chiron.mcp.server"],
         "env": {},
         "description": "Chiron dependency & wheelhouse management",
         "version": "0.1.0",
         "capabilities": {
           "tools": true,
           "resources": false,
           "prompts": false
         }
       }
     }
   }
   ```

4. **Restart Claude Desktop**

### VS Code with Copilot

1. **Install MCP extension** (when available)

2. **Configure in `.vscode/mcp-servers.json`**:
   ```json
   {
     "servers": {
       "chiron": {
         "command": "python -m chiron.mcp.server",
         "type": "stdio"
       }
     }
   }
   ```

### Custom MCP Client

For custom clients using the MCP protocol:

```python
import subprocess
import json

# Start MCP server
process = subprocess.Popen(
    ["python", "-m", "chiron.mcp.server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Send tool list request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}
process.stdin.write(json.dumps(request) + "\n")
process.stdin.flush()

# Read response
response = process.stdout.readline()
print(response)
```

---

## 2. Testing Individual Tools

### Test 1: Health Check

**Prompt for AI assistant**:
```
Use the chiron_health_check tool to check if Chiron is operational.
```

**Expected Response**:
```json
{
  "status": "healthy",
  "components": {
    "mcp_server": "operational",
    "policy_check": "enabled"
  },
  "version": "0.1.0"
}
```

**Validation**:
- [ ] Tool executes without errors
- [ ] Status is "healthy"
- [ ] Version is correct
- [ ] Components are listed

### Test 2: List Feature Flags

**Prompt for AI assistant**:
```
Use the chiron_get_feature_flags tool to show current feature flag status.
```

**Expected Response**:
```json
{
  "flags": {
    "allow_public_publish": false,
    "require_slsa_provenance": true,
    "enable_oci_distribution": false,
    "enable_mcp_agent": true,
    "dry_run_by_default": true
  }
}
```

**Validation**:
- [ ] Tool executes without errors
- [ ] Returns dictionary of flags
- [ ] Flags have boolean values

### Test 3: Build Wheelhouse (Dry Run)

**Prompt for AI assistant**:
```
Use the chiron_build_wheelhouse tool to build a wheelhouse in dry-run mode.
Output to "test_wheelhouse" directory with SBOM and signatures enabled.
```

**Expected Response**:
```json
{
  "status": "dry_run",
  "message": "Would build wheelhouse",
  "output_dir": "test_wheelhouse",
  "with_sbom": true,
  "with_signatures": true
}
```

**Validation**:
- [ ] Tool executes without errors
- [ ] Status is "dry_run"
- [ ] Parameters are echoed correctly
- [ ] Message is informative

### Test 4: Create Air-gap Bundle (Dry Run)

**Prompt for AI assistant**:
```
Use the chiron_create_airgap_bundle tool to create an air-gap bundle.
Include extras and security tools, output to "test-bundle.tar.gz", dry-run mode.
```

**Expected Response**:
```json
{
  "status": "dry_run",
  "message": "Would create air-gap bundle",
  "output": "test-bundle.tar.gz",
  "include_extras": true,
  "include_security": true
}
```

**Validation**:
- [ ] Tool executes without errors
- [ ] Status is "dry_run"
- [ ] Parameters are echoed correctly

### Test 5: Verify Artifacts

**Prompt for AI assistant**:
```
Use the chiron_verify_artifacts tool to verify artifacts at "/path/to/wheelhouse".
```

**Expected Response**:
```json
{
  "status": "not_implemented",
  "message": "Artifact verification requires full implementation",
  "target": "/path/to/wheelhouse"
}
```

**Validation**:
- [ ] Tool executes without errors
- [ ] Returns not_implemented status
- [ ] Target path is echoed

### Test 6: Check Policy

**Prompt for AI assistant**:
```
Use the chiron_check_policy tool with config at "/path/to/policy.yaml".
```

**Expected Response**:
```json
{
  "status": "not_implemented",
  "message": "Policy checking requires full implementation",
  "config_path": "/path/to/policy.yaml"
}
```

**Validation**:
- [ ] Tool executes without errors
- [ ] Returns not_implemented status
- [ ] Config path is echoed

---

## 3. Integration Test Scenarios

### Scenario 1: Full Workflow Simulation

**Test Steps**:
1. Check health status
2. Get feature flags
3. Build wheelhouse (dry-run)
4. Verify artifacts (dry-run)
5. Create air-gap bundle (dry-run)

**AI Assistant Prompt**:
```
Execute a complete Chiron workflow:
1. Check the health of Chiron
2. Show me the current feature flags
3. Build a wheelhouse with SBOM and signatures
4. Verify the wheelhouse artifacts
5. Create an air-gap bundle with extras

Use dry-run mode where applicable.
```

**Validation**:
- [ ] All tools execute in sequence
- [ ] No errors occur
- [ ] Responses are coherent
- [ ] Context is maintained between steps

### Scenario 2: Error Handling

**Test Steps**:
1. Call invalid tool name
2. Call tool with missing required parameter
3. Call tool with invalid parameter type

**AI Assistant Prompt**:
```
Test error handling:
1. Try to use a tool called "chiron_invalid_tool"
2. Try to verify artifacts without providing a target path
3. Try to build wheelhouse with output_dir set to a number instead of string
```

**Validation**:
- [ ] Invalid tool returns error with available tools
- [ ] Missing parameter handled gracefully
- [ ] Invalid types handled appropriately

### Scenario 3: Parameter Variations

**Test Steps**:
Test tools with various parameter combinations

**AI Assistant Prompt**:
```
Test Chiron tools with different parameters:
1. Build wheelhouse without SBOM
2. Build wheelhouse without signatures
3. Create air-gap bundle without extras
4. Create air-gap bundle with custom output name
```

**Validation**:
- [ ] All parameter combinations work
- [ ] Defaults are applied correctly
- [ ] Custom values are respected

---

## 4. Automated Testing

### Python Test Script

Create `test_mcp_integration.py`:

```python
"""Integration tests for MCP server."""

import json
import subprocess
from pathlib import Path


def test_mcp_server_startup():
    """Test that MCP server starts successfully."""
    result = subprocess.run(
        ["python", "-m", "chiron.mcp.server"],
        capture_output=True,
        text=True,
        timeout=5
    )
    assert result.returncode == 0 or "Available Chiron MCP Tools" in result.stdout


def test_mcp_tools_available():
    """Test that tools are listed in output."""
    result = subprocess.run(
        ["python", "-m", "chiron.mcp.server"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    output = result.stdout
    assert "chiron_build_wheelhouse" in output
    assert "chiron_verify_artifacts" in output
    assert "chiron_health_check" in output


def test_mcp_config_generation():
    """Test that config can be generated."""
    result = subprocess.run(
        ["python", "-m", "chiron.mcp.server"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Config should be in output
    assert "mcpServers" in result.stdout


if __name__ == "__main__":
    test_mcp_server_startup()
    test_mcp_tools_available()
    test_mcp_config_generation()
    print("✅ All MCP integration tests passed!")
```

Run with:
```bash
python test_mcp_integration.py
```

---

## 5. Troubleshooting

### Issue: MCP Server Not Found

**Symptoms**: Client shows "command not found" or similar

**Solutions**:
1. Verify Python is in PATH: `which python`
2. Verify Chiron is installed: `python -c "import chiron.mcp.server"`
3. Use full path to Python: `/usr/bin/python3 -m chiron.mcp.server`

### Issue: Tools Not Appearing

**Symptoms**: Client shows no Chiron tools

**Solutions**:
1. Check client configuration is correct
2. Restart client application
3. Check client logs for errors
4. Test server directly: `python -m chiron.mcp.server`

### Issue: Tool Execution Fails

**Symptoms**: Tools return errors

**Solutions**:
1. Check error message for details
2. Verify parameters match schema
3. Check Chiron logs if available
4. Test with simpler parameters first

---

## 6. Client-Specific Notes

### Claude Desktop

- Config location varies by OS
- Requires restart after config changes
- Shows tools in conversation panel
- Good error reporting

### VS Code

- Requires MCP extension (when available)
- Config in workspace settings
- Integrated with Copilot chat
- May need VS Code restart

### Custom Clients

- Use stdio protocol
- JSON-RPC 2.0 format
- Handle async responses
- Implement proper error handling

---

## 7. Reporting Issues

When reporting MCP integration issues, include:

1. **Client Information**:
   - Client name and version
   - Operating system
   - Python version

2. **Configuration**:
   - MCP server config (redact sensitive data)
   - Chiron version: `python -c "import chiron; print(chiron.__version__)"`

3. **Error Details**:
   - Full error message
   - Steps to reproduce
   - Expected vs actual behavior

4. **Logs**:
   - Client logs (if available)
   - Server output: `python -m chiron.mcp.server 2>&1 | tee mcp.log`

---

## 8. Next Steps

After completing integration testing:

1. **Document findings**: Note any issues or incompatibilities
2. **Report bugs**: Open issues for any problems found
3. **Suggest improvements**: Propose enhancements
4. **Share configurations**: Contribute working configs for other clients

---

## Conclusion

This guide provides a comprehensive approach to testing Chiron's MCP integration. The skeleton implementation is suitable for testing tool discovery and parameter handling, but actual operations require full implementation.

For production use, implement the actual tool functionality (see `GAP_ANALYSIS.md`).
