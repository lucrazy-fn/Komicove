param([switch]$Release)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $PortableJava = Join-Path $PSScriptRoot '..\..\.android-tools\jdk'
    $LocalJdk = Get-ChildItem -LiteralPath $PortableJava -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'jdk-17*' } | Select-Object -First 1
    if ($LocalJdk) { $env:JAVA_HOME = $LocalJdk.FullName }
    if (-not $env:JAVA_HOME) {
        $StudioJava = 'C:\Program Files\Android\Android Studio\jbr'
        $PortableJava = Join-Path $PSScriptRoot '..\..\.android-tools\jdk'
        if (Test-Path -LiteralPath $StudioJava) { $env:JAVA_HOME = $StudioJava }
        elseif (Test-Path -LiteralPath $PortableJava) { $env:JAVA_HOME = (Get-ChildItem -LiteralPath $PortableJava -Directory | Select-Object -First 1).FullName }
        else { throw 'Instale JDK 17 ou Android Studio e configure JAVA_HOME.' }
    }
    $JavaRelease = Join-Path $env:JAVA_HOME 'release'
    if (-not (Test-Path $JavaRelease) -or -not (Select-String -Path $JavaRelease -Pattern '^JAVA_VERSION="17\.' -Quiet)) { throw 'Configure JAVA_HOME para um JDK 17. Java 8 e Java 25 nao sao compativeis com este build.' }
    $Task = if ($Release) { 'assembleRelease' } else { 'copyNamedDebugApk' }
    & .\gradlew.bat --no-daemon ":app:$Task"
    if ($LASTEXITCODE -ne 0) { throw 'A compilacao falhou. Confira o erro acima.' }
    if ($Release) { Write-Host 'APK release sem assinatura: app\build\outputs\apk\release. Assine com sua chave permanente antes de distribuir.' }
    else { Write-Host 'APK de teste renomeado: build\outputs\named (original: app\build\outputs\apk\debug\app-debug.apk)' }
} finally { Pop-Location }
