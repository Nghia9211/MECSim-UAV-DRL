param(
    [ValidateRange(1,1000)][int]$Seeds=30,
    [ValidateRange(0,2147483647)][long]$FirstSeed=41000,
    [ValidateRange(0,0.99)][double]$EstimateError=0,
    [string]$Output='',
    [switch]$Offline
)
$ErrorActionPreference='Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not $Output) {$Output="target/offloading-$(Get-Date -Format yyyyMMdd-HHmmss)-$PID"}
    $noise=$EstimateError.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    $arguments=@('compile','exec:java','-Dexec.mainClass=uav.offloading.OffloadingBenchmark',
        '-Dexec.classpathScope=compile',"-Doffloading.seeds=$Seeds","-Doffloading.firstSeed=$FirstSeed","-Doffloading.estimateError=$noise")
    if ($Output) {$arguments += "-Doffloading.output=$Output"}
    if ($Offline) {$arguments=@('-o')+$arguments}
    & mvn @arguments
    if ($LASTEXITCODE -ne 0) {throw "Offloading benchmark failed: $LASTEXITCODE"}
    & python scripts/verify-uav-offloading.py $Output
    if ($LASTEXITCODE -ne 0) {throw 'Offloading verification/metrics failed'}
} finally {Pop-Location}
