param([switch]$ExecutableOnly)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    $BuildPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $BuildPython)) { throw "Crie a .venv conforme o README." }
    & $BuildPython -c "import PyInstaller, tkinter, PIL, pymupdf, requests, rarfile; tkinter.Tcl()"
    if ($LASTEXITCODE -ne 0) { throw 'Instale as dependencias: .\.venv\Scripts\python.exe -m pip install -e ".[build]"' }
    & $BuildPython -m PyInstaller --noconfirm --clean installer\PANEL.spec
    if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar executavel." }
    if ($ExecutableOnly) { Write-Host "Executavel: dist\PANEL\PANEL.exe"; return }
    $Compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    $CompilerPath = if ($Compiler) { $Compiler.Source } else {
        @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
            Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $CompilerPath -or -not (Test-Path -LiteralPath $CompilerPath)) { throw "Executavel pronto. Instale Inno Setup 6 para gerar o instalador." }
    & $CompilerPath installer\Panel.iss
    if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar instalador." }
    Write-Host "Instalador: dist\installer\PANEL-Setup-1.7.1.exe"
} finally { Pop-Location }
