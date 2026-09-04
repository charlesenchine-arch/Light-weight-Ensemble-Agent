param(
    [switch]$WithMcp
)

$ErrorActionPreference = "Stop"
$LeaRelease = "v0.3.0"
$LeaWheel = "lea_agent-0.3.0-py3-none-any.whl"
$LeaWheelSha256 = "3CBB85B6E7545C2129C30C681EA69E28B75A25591366438658A370FD779FD7C9"
$LeaWheelUrl = "https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent/releases/download/$LeaRelease/$LeaWheel"
$UvInstallUrl = "https://astral.sh/uv/install.ps1"

if ($env:LEA_WITH_MCP -eq "1") {
    $WithMcp = $true
}

if ($env:LEA_INSTALL_DRY_RUN -eq "1") {
    Write-Host "LEA installer dry run"
    Write-Host "wheel: $LeaWheelUrl"
    Write-Host "sha256: $LeaWheelSha256"
    $McpPart = if ($WithMcp) { " --with mcp>=2.1,<3" } else { "" }
    Write-Host "install: uv tool install --python 3.12 --force$McpPart $LeaWheel"
    return
}

function Find-Uv {
    $Command = Get-Command uv -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }
    foreach ($Candidate in @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe")
    )) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            return $Candidate
        }
    }
    return $null
}

$TempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("lea-install-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $TempDirectory | Out-Null
try {
    $Uv = Find-Uv
    if (-not $Uv) {
        Write-Host "uv not found; installing it from $UvInstallUrl"
        $UvInstaller = Join-Path $TempDirectory "install-uv.ps1"
        Invoke-WebRequest -UseBasicParsing -Uri $UvInstallUrl -OutFile $UvInstaller
        $Shell = (Get-Process -Id $PID).Path
        & $Shell -NoProfile -ExecutionPolicy Bypass -File $UvInstaller
        if ($LASTEXITCODE -ne 0) {
            throw "uv installer exited with code $LASTEXITCODE"
        }
        $Uv = Find-Uv
        if (-not $Uv) {
            throw "uv was installed but could not be located."
        }
    }

    $WheelPath = Join-Path $TempDirectory $LeaWheel
    Write-Host "Downloading LEA $LeaRelease"
    Invoke-WebRequest -UseBasicParsing -Uri $LeaWheelUrl -OutFile $WheelPath
    $ActualHash = (Get-FileHash -LiteralPath $WheelPath -Algorithm SHA256).Hash
    if ($ActualHash -ne $LeaWheelSha256) {
        throw "LEA wheel checksum mismatch; refusing to install."
    }

    $Arguments = @("tool", "install", "--python", "3.12", "--force")
    if ($WithMcp) {
        $Arguments += @("--with", "mcp>=2.1,<3")
    }
    $Arguments += $WheelPath
    & $Uv @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "uv tool install exited with code $LASTEXITCODE"
    }

    $ToolBin = (& $Uv tool dir --bin).Trim()
    Write-Host "LEA $LeaRelease installed and verified."
    $LeaCommand = Join-Path $ToolBin "lea.exe"
    if (Test-Path -LiteralPath $LeaCommand -PathType Leaf) {
        & $LeaCommand version
    }
    if (($env:Path -split ";") -notcontains $ToolBin) {
        Write-Host "Add $ToolBin to PATH, then open a new terminal."
    }
    Write-Host "Next: cd to a project and run 'lea init', then 'lea'."
}
finally {
    if (Test-Path -LiteralPath $TempDirectory) {
        Remove-Item -LiteralPath $TempDirectory -Recurse -Force
    }
}
