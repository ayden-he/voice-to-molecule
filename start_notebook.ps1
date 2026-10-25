$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not $env:GEMINI_API_KEY) {
    $secureKey = Read-Host 'Enter Gemini API key (input is hidden)' -AsSecureString
    $env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
}
if (-not $env:GEMINI_API_KEY) {
    Write-Error 'No API key was entered; voice server was not started.'
    exit 1
}

Write-Host 'Starting the GitHub voice backend on http://127.0.0.1:8001'
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'voice_server.py')
