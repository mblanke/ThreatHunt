param(
    [switch]$Build,
    [switch]$BackendOnly,
    [int]$HealthTimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$msg) {
    Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}

function Wait-Http200([string]$url, [int]$timeoutSeconds) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSeconds) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Step 'Starting containers'
$composeArgs = if ($BackendOnly) { 'up -d backend' } else { 'up -d' }
if ($Build) { $composeArgs = $composeArgs.Replace('up -d', 'up -d --build') }

# Use cmd wrapper to safely allow merged output while preserving exit code semantics.
cmd /c "docker compose $composeArgs 2>&1"
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Step 'Container status'
docker compose ps

Write-Step 'Health checks'
$backendOk = Wait-Http200 -url 'http://localhost:8000/health' -timeoutSeconds $HealthTimeoutSeconds
$frontendOk = if ($BackendOnly) { $true } else { Wait-Http200 -url 'http://localhost:3000/' -timeoutSeconds $HealthTimeoutSeconds }

if (-not $backendOk) {
    Write-Error 'Backend health check failed: http://localhost:8000/health did not return HTTP 200 in time.'
    exit 1
}
if (-not $frontendOk) {
    Write-Error 'Frontend health check failed: http://localhost:3000/ did not return HTTP 200 in time.'
    exit 1
}

Write-Step 'All good'
Write-Host 'Backend:  http://localhost:8000/health (OK)' -ForegroundColor Green
if (-not $BackendOnly) {
    Write-Host 'Frontend: http://localhost:3000/ (OK)' -ForegroundColor Green
}
exit 0

