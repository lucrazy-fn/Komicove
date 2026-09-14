param([switch]$Release)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not $env:JAVA_HOME) {
        $StudioJava = 'C:\Program Files\Android\Android Studio\jbr'
        $PortableJava = Join-Path $PSScriptRoot '..\..\.android-tools\jdk'
        if (Test-Path -LiteralPath $StudioJava) { $env:JAVA_HOME = $StudioJava }
        elseif (Test-Path -LiteralPath $PortableJava) { $env:JAVA_HOME = (Get-ChildItem -LiteralPath $PortableJava -Directory | Select-Object -First 1).FullName }
        else { throw 'Instale JDK 17 ou Android Studio e configure JAVA_HOME.' }
    }
    $Task = if ($Release) { 'assembleRelease' } else { 'assembleDebug' }
    & .\gradlew.bat --no-daemon ":app:$Task"
    if ($LASTEXITCODE -ne 0) { throw 'A compilacao falhou. Confira o erro acima.' }
    if ($Release) { Write-Host 'APK release sem assinatura: app\build\outputs\apk\release. Assine com sua chave permanente antes de distribuir.' }
    else { Write-Host 'APK de teste: app\build\outputs\apk\debug\app-debug.apk' }
} finally { Pop-Location }
