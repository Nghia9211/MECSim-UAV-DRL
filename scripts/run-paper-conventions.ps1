param([int]$Seeds=30,[string]$Output="target/paper-convention-new",[switch]$Offline)
$ErrorActionPreference='Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if ($Seeds -lt 1 -or $Seeds -gt 1000) { throw 'Seeds must be in 1..1000' }
    if (Test-Path -LiteralPath $Output) { throw 'Choose a new Output directory' }
    $arguments=@('test','compile','exec:java','-Dexec.mainClass=uav.PaperConventionBenchmark',
        '-Dexec.classpathScope=compile',"-Daudit.seeds=$Seeds","-Daudit.output=$Output")
    if ($Offline) { $arguments=@('-o')+$arguments }
    & mvn @arguments
    if ($LASTEXITCODE -ne 0) { throw "Java validation/benchmark failed: $LASTEXITCODE" }
    $auditPython=Join-Path (Get-Location) '.venv-drl/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $auditPython)) { $auditPython='python' }
    & $auditPython scripts/verify-paper-conventions.py $Output
    if ($LASTEXITCODE -ne 0) { throw "Independent audit failed: $LASTEXITCODE" }
    & $auditPython scripts/test-paper-convention-verifier.py $Output
    if ($LASTEXITCODE -ne 0) { throw "Verifier tests failed: $LASTEXITCODE" }
} finally { Pop-Location }
