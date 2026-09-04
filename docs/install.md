# Install LEA

The recommended installers put LEA in an isolated `uv` tool environment. They do
not require administrator access and do not install packages into the active Python
environment.

## macOS and Linux

Inspect the script first if desired:

```bash
curl -LsSf https://raw.githubusercontent.com/charlesenchine-arch/Light-weight-Ensemble-Agent/main/install.sh | less
```

Install:

```bash
curl -LsSf https://raw.githubusercontent.com/charlesenchine-arch/Light-weight-Ensemble-Agent/main/install.sh | sh
```

Include optional MCP support:

```bash
curl -LsSf https://raw.githubusercontent.com/charlesenchine-arch/Light-weight-Ensemble-Agent/main/install.sh | LEA_WITH_MCP=1 sh
```

## Windows PowerShell

Inspect the script first:

```powershell
irm https://raw.githubusercontent.com/charlesenchine-arch/Light-weight-Ensemble-Agent/main/install.ps1 | more
```

Install:

```powershell
irm https://raw.githubusercontent.com/charlesenchine-arch/Light-weight-Ensemble-Agent/main/install.ps1 | iex
```

Include optional MCP support:

```powershell
$env:LEA_WITH_MCP = "1"
irm https://raw.githubusercontent.com/charlesenchine-arch/Light-weight-Ensemble-Agent/main/install.ps1 | iex
```

## What the installer does

1. Finds `uv`, or downloads its official installer from `https://astral.sh`.
2. Downloads the pinned LEA v0.3.0 wheel from this repository's GitHub Release.
3. Verifies the wheel against the SHA-256 digest embedded in both installer scripts.
4. Uses `uv tool install` with an isolated Python 3.12 environment.
5. Prints the executable directory if it is not already on `PATH`.

The scripts never use `sudo`, never modify a project, and refuse to install a wheel
whose digest differs. The installer script itself comes from the default branch, so
review it before execution in security-sensitive environments. For a fully pinned
flow, download an installer from a reviewed commit and invoke it locally.

## Existing Python tool managers

If `uv` or pipx is already configured, no bootstrap script is needed:

```bash
uv tool install git+https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent.git@v0.3.0
# or
pipx install git+https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent.git@v0.3.0
```

After installation:

```bash
cd your-project
lea init
lea
```

Remove the isolated installation with `uv tool uninstall lea-agent`, or use
`pipx uninstall lea-agent` if it was installed with pipx.

