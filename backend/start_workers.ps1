$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Users\deepanshu\Desktop\regintel-ai\.venv\Scripts\python.exe"

function Get-EnvValueFromFile {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    $match = Get-Content $Path | Where-Object { $_ -match "^$([regex]::Escape($Name))=(.*)$" } | Select-Object -First 1
    if (-not $match) {
        return $null
    }

    return ($match -replace "^$([regex]::Escape($Name))=", "").Trim()
}

function Start-AIWorker {
    param(
        [int]$Port,
        [string]$ApiKeyEnvName,
        [int]$MaxConcurrentRequests = 2
    )

    $apiKeyValue = [Environment]::GetEnvironmentVariable($ApiKeyEnvName, "Process")
    if (-not $apiKeyValue) {
        $apiKeyValue = [Environment]::GetEnvironmentVariable($ApiKeyEnvName, "User")
    }
    if (-not $apiKeyValue) {
        $apiKeyValue = [Environment]::GetEnvironmentVariable($ApiKeyEnvName, "Machine")
    }
    if (-not $apiKeyValue) {
        $apiKeyValue = Get-EnvValueFromFile -Path (Join-Path $root ".env") -Name $ApiKeyEnvName
    }

    if (-not $apiKeyValue) {
        throw "Missing environment variable: $ApiKeyEnvName"
    }

    $command = @(
        "Set-Location -LiteralPath '$root'",
        '`$env:AI_WORKER_MODE = ''1''',
        ('`$env:GROQ_API_KEY = ''{0}''' -f $apiKeyValue),
        ('`$env:MAX_CONCURRENT_REQUESTS = ''{0}''' -f $MaxConcurrentRequests),
        ('`$env:WORKER_PORT = ''{0}''' -f $Port),
        ('`$env:PORT = ''{0}''' -f $Port),
        ('"{0}" -m uvicorn app.worker_main:app --host 127.0.0.1 --port {1}' -f $python, $Port)
    ) -join "; "

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $command | Out-Null
    Write-Host "Started worker on port $Port using key $ApiKeyEnvName"
}

Start-AIWorker -Port 8001 -ApiKeyEnvName "GROQ_API_KEY_1" -MaxConcurrentRequests 2
Start-AIWorker -Port 8002 -ApiKeyEnvName "GROQ_API_KEY_2" -MaxConcurrentRequests 2
Start-AIWorker -Port 8003 -ApiKeyEnvName "GROQ_API_KEY_3" -MaxConcurrentRequests 2

Write-Host "All workers started."
