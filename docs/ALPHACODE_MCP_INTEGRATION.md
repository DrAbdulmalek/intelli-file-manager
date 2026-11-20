# AlphaCode Local Integration — MCP Bridge

**Status:** local bridge implemented on the feature branch; connection to the installed AlphaCode client is not yet verified. This document does not assume a particular AlphaCode launcher or settings-file location.

## Architecture

AlphaCode is the local MCP client. IntelliFile starts a local MCP server as a child process using standard input/output (stdio). The transport uses newline-delimited JSON-RPC messages and does not open a TCP/HTTP listener.

```
AlphaCode (local agent / MCP client)
       |
       | MCP stdio — JSON-RPC, local process only
       v
src/integrations/alphacode_mcp_server.py
       |
       +-- shared Path Policy: iter_entries_reported()
       +-- explicitly allowlisted roots only
       +-- metadata-only inventory
       +-- dry-run plan validation
```

The bridge has no network client, no cloud fallback, and no API that reads file contents or mutates user files.

## Exposed tools

| Tool | Behavior | Side effects |
|---|---|---|
| `intellifile.status` | Reports bridge version, root configuration count, and capability limits | None |
| `intellifile.inventory` | Lists metadata for eligible files under an explicitly allowlisted root | Read-only metadata access |
| `intellifile.validate_plan` | Checks relative source/destination paths, collisions, allowlist containment, and symlink components | Validates only; does not reserve or change paths |

Inventory returns relative paths, sizes, modification timestamps, and extensions. It does not open file contents or compute hashes. It excludes hidden paths, credential-related directories/files, likely medical paths, symlinks, unsupported filesystem objects, and mount-point crossings. The inventory is not an atomic snapshot. A hard cap of 10,000 traversed entries and a depth limit of 32 prevent an unbounded scan; the response marks incomplete scans and truncation explicitly.

The plan validator is **not** an execution authorization. Destination validation can become stale immediately after the response; it does not reserve the destination. Every proposed operation still requires human review.

## Safety boundary — deliberately disabled

This bridge does not expose:
- file-content reads, OCR, RAG ingestion, or upload;
- move, copy, rename, overwrite, delete, or undo;
- shell execution or arbitrary subprocess execution;
- arbitrary path access outside `INTELLIFILE_AGENT_ROOTS`;
- cloud services or remote telemetry.

The bridge remains read-only until SafeMover and the end-to-end sensitivity barrier pass independent adversarial review. Do not add mutation tools as a convenience wrapper around `os.rename`, `shutil.move`, or shell commands.

## Configure an AlphaCode MCP client

AlphaCode must provide an MCP client capable of launching a stdio server. Add the following server entry to AlphaCode's MCP configuration. Replace the example absolute paths with paths on the local device; do not commit the real configuration file.

```json
{
  "mcpServers": {
    "intellifile": {
      "command": "/absolute/path/to/python",
      "args": [
        "/absolute/path/to/intelli-file-manager/src/integrations/alphacode_mcp_server.py"
      ],
      "env": {
        "INTELLIFILE_AGENT_ROOTS": "/absolute/path/to/approved/folder"
      }
    }
  }
}
```

On Linux, multiple allowed roots are separated by the platform path separator (`:`). Each root must already exist and be a directory. No root is enabled when the environment variable is absent or empty. The bridge refuses a requested scan root outside the configured roots and refuses symlinked scan roots.

Use the Python interpreter from the environment in which IntelliFile dependencies are installed. The MCP bridge itself uses only the Python standard library and IntelliFile's Path Policy module.

After saving the client configuration, restart AlphaCode and check that it discovers the `intellifile` server. Call `intellifile.status` first; then run a small inventory against a synthetic test directory. Do not point it at a real user directory until the synthetic test succeeds.

### Compatibility note

The bridge implements the MCP stdio lifecycle for protocol version `2025-11-25`. A newer MCP client may first probe for the newer stateless lifecycle and then fall back to the legacy initialization handshake. Actual interoperability depends on the MCP client embedded in the installed AlphaCode build and must be verified on the device.

If the installed AlphaCode application does not support MCP stdio servers, this server alone cannot make the application connect. In that case, AlphaCode needs a local adapter that speaks this MCP client protocol; do not substitute a network listener or cloud relay.

## Local tests

From the IntelliFile repository root:

```bash
python -m pytest tests/unit/test_alphacode_mcp.py tests/unit/test_path_policy.py
```

The tests use temporary synthetic directories. They cover allowlist enforcement, hidden/sensitive path exclusion, symlinks, depth/entry limits, dry-run-only plan validation, MCP initialization, and stdio framing.

## Operational privacy

- Keep the MCP configuration local and private.
- Do not place personal paths, user names, tokens, patient data, or operational logs in Git.
- The bridge writes protocol frames to stdout only; any diagnostics belong on stderr.
- No operational or engineering logs are uploaded by this integration.
