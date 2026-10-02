<#
 PowerShell equivalent of the Makefile. Usage: .\scripts\dev.ps1 <up|down|logs|ps|build|test|lint|k8s-validate>
#>
param([Parameter(Position = 0)][string]$Task = "help")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Ensure-Env {
    if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host ".env created -- change POSTGRES_PASSWORD" }
}

switch ($Task) {
    "up"           { Ensure-Env; docker compose up --build -d; Write-Host "UI: http://localhost:8080 (FRONTEND_PORT in .env)" }
    "down"         { docker compose down }
    "logs"         { docker compose logs -f --tail=100 }
    "ps"           { docker compose ps }
    "build"        { docker compose build }
    "test"         { python -m pytest -q }
    "lint"         {
        python -m yamllint -c .yamllint.yml k8s docker-compose.yml docker-compose.override.example.yml
        python scripts/validate_k8s.py
        Push-Location frontend; npm run lint; Pop-Location
    }
    "k8s-validate" { python scripts/validate_k8s.py }
    default        { Write-Host "Usage: .\scripts\dev.ps1 <up|down|logs|ps|build|test|lint|k8s-validate>" }
}
if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { exit $LASTEXITCODE }
