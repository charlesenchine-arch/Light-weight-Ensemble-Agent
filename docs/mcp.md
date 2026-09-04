# MCP tool servers

LEA can expose selected tools from local stdio Model Context Protocol (MCP)
servers to planning, coding, fixing, or review stages. MCP support is optional so
the base install stays small.

## Install the optional client

From a source checkout:

```bash
pip install -e ".[mcp]"
```

With pipx and the GitHub repository:

```bash
pipx install "lea-agent[mcp] @ git+https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent.git"
```

If LEA is already installed with pipx, add the optional dependency in place:

```bash
pipx inject lea-agent "mcp>=2.1,<3"
```

## Configure and trust a server

Add a stdio server to the project's `agentflow.yaml`. Tool names must be selected
explicitly; an empty list exposes nothing.

```yaml
mcp_servers:
  project-tools:
    command: python
    args: [tools/project_mcp.py]
    cwd: .
    tools: [lookup_component, search_runbook]
    stages: [plan, code, review]
    timeout_seconds: 30
    env:
      DOCS_TOKEN: "${DOCS_TOKEN}"
```

Inspect the exact command, environment-variable names, selected tools, and stages,
then approve it:

```bash
lea mcp list
lea mcp trust project-tools
```

The approval is stored outside the repository in `~/.agentflow/mcp-trust.json` and
is tied to the resolved workspace plus the complete server configuration. Editing
the command, arguments, environment map, tool allowlist, or stages invalidates the
approval. Re-approve the new configuration deliberately, or revoke it with:

```bash
lea mcp revoke project-tools
```

Exposed tools are namespaced, for example
`mcp__project-tools__lookup_component`, so they cannot silently replace LEA's
built-in file or shell tools. MCP schemas are included in the same conservative
preflight input-token estimate as built-in schemas. Results are capped before they
enter the conversation and older tool results use LEA's normal history compaction.

## Threat model and boundaries

An MCP server is a local executable, not a passive configuration file. Only trust
software you would be willing to run directly.

- Repository configuration alone cannot start a server. The matching command must
  also have an approval in the user-level trust store.
- The child receives the MCP SDK's minimal environment plus only values named in
  `env`. A value in the exact form `${NAME}` is read from that environment variable
  after trust is granted. LEA never writes the resolved secret to the trust store.
- Arguments named like paths, files, directories, roots, commands, or shell scripts
  pass through LEA's workspace and dangerous-command checks before a tool call.
- That argument inspection is defense in depth, not a process sandbox. A malicious
  server can ignore its declared arguments, access its own ambient permissions, or
  make network requests. Run untrusted servers in an operating-system sandbox or
  container and give them narrow credentials.
- Interrupting a turn cancels the active SDK request and closes the stdio transport,
  which shuts down the child process. Timeouts are bounded per server.
- Discovery or invocation failures become tool warnings/errors. They do not add a
  cost event or mutate the session ledger.

The first implementation intentionally supports stdio only. Streamable HTTP needs
an additional trust design for origins, authentication, redirects, and TLS and is
therefore not silently treated as equivalent to a local process.

Protocol implementation uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).
