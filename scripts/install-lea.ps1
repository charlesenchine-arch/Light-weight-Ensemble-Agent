# Backward-compatible entry point for source-checkout users.
& (Join-Path (Split-Path -Parent $PSScriptRoot) "install.ps1") @args
