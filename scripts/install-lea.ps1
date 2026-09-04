# Install `lea` onto the user PATH, same idea as `grok`.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing venv at $python. Run: python -m venv .venv; .\.venv\Scripts\pip install -e ."
}

$bin = Join-Path $env:USERPROFILE ".lea\bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null

$cmdPath = Join-Path $bin "lea.cmd"
@(
    "@echo off"
    "set LEA_HOME=$repo"
    "`"$python`" -m agentflow %*"
) | Set-Content -Path $cmdPath -Encoding ASCII

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
if ($userPath -notlike "*$bin*") {
    $joined = if ($userPath.Trim().Length -eq 0) { $bin } else { $userPath.TrimEnd(";") + ";" + $bin }
    [Environment]::SetEnvironmentVariable("Path", $joined, "User")
}

$env:Path = $bin + ";" + $env:Path
Write-Host "Installed $cmdPath"
Write-Host "Open a new PowerShell, then type: lea"
