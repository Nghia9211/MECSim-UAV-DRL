param([switch]$Offline)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $arguments = @('compile','exec:java','-Dexec.mainClass=uav.PaperGymBridge',
        '-Dexec.classpathScope=compile','-Dexec.args=--classpath')
    if ($Offline) { $arguments = @('-o') + $arguments }
    & mvn @arguments
    if ($LASTEXITCODE -ne 0) { throw "Java build failed: $LASTEXITCODE" }
} finally { Pop-Location }
