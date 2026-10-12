param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$runtimePath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $runtimePath)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Install Python 3.10 or later, then run this launcher again." }
    & $runtimePath -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Check your connection and retry." }
}
& $runtimePath -c "import app, ultralytics"
if ($LASTEXITCODE -ne 0) {
    & $runtimePath -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}
& $runtimePath run_ui.py --port $Port
