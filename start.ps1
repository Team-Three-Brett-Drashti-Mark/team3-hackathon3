# start.ps1 — Start the Pathwise backend + frontend in one command.
# Run from the project root: .\start.ps1
#
# If you get an execution-policy error, run once as admin:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:BackendProcess  = $null
$script:FrontendProcess = $null

function Stop-Servers {
    Write-Host ""
    Write-Host "Shutting down..."
    foreach ($proc in @($script:BackendProcess, $script:FrontendProcess)) {
        if ($proc -and !$proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Done. Goodbye!"
}

# ---------------------------------------------------------------------------
# Clear ports 8000 and 5173
# ---------------------------------------------------------------------------
Write-Host "Clearing ports 8000 and 5173..."
foreach ($port in @(8000, 5173)) {
    $owningPids = (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue).OwningProcess |
                  Sort-Object -Unique
    foreach ($pid in $owningPids) {
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1

# ---------------------------------------------------------------------------
# Start backend — use the venv's uvicorn directly so no activation needed
# ---------------------------------------------------------------------------
$uvicorn = Join-Path $ProjectRoot "venv\Scripts\uvicorn.exe"
Write-Host "Starting backend (FastAPI) on http://localhost:8000 ..."
$script:BackendProcess = Start-Process -NoNewWindow -PassThru `
    -FilePath $uvicorn `
    -ArgumentList "app.api:app", "--port", "8000" `
    -WorkingDirectory $ProjectRoot

# Wait until the backend is actually accepting connections
Write-Host -NoNewline "Waiting for backend"
for ($i = 0; $i -lt 20; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 1
        Write-Host " ready!"
        break
    } catch {
        Write-Host -NoNewline "."
        Start-Sleep -Milliseconds 500
    }
}

# ---------------------------------------------------------------------------
# Start frontend
# ---------------------------------------------------------------------------
Write-Host "Starting frontend (Vite) on http://localhost:5173 ..."
$script:FrontendProcess = Start-Process -NoNewWindow -PassThru `
    -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm", "run", "dev" `
    -WorkingDirectory (Join-Path $ProjectRoot "frontend")

# ---------------------------------------------------------------------------
# Keep running until Ctrl+C
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================"
Write-Host "  Pathwise is running!"
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Backend:  http://localhost:8000"
Write-Host "  Press Ctrl+C to stop both servers."
Write-Host "============================================"
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($script:BackendProcess.HasExited) {
            Write-Host "Backend exited unexpectedly (code $($script:BackendProcess.ExitCode))."
            break
        }
        if ($script:FrontendProcess.HasExited) {
            Write-Host "Frontend exited unexpectedly (code $($script:FrontendProcess.ExitCode))."
            break
        }
    }
} finally {
    Stop-Servers
}
