param(
    [ValidateRange(1,1000)][int]$Seeds=30,
    [ValidateRange(0,2147483647)][long]$FirstSeed=51000,
    [string]$Output='',
    [switch]$Offline
)
$ErrorActionPreference='Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $arguments=@('compile','exec:java','-Dexec.mainClass=uav.offloading.MobileServiceBenchmark',
        '-Dexec.classpathScope=compile',"-Dmobile.seeds=$Seeds","-Dmobile.firstSeed=$FirstSeed")
    if ($Output) {$arguments += "-Dmobile.output=$Output"}
    if ($Offline) {$arguments=@('-o')+$arguments}
    & mvn @arguments
    if ($LASTEXITCODE -ne 0) {throw "Mobile service benchmark failed: $LASTEXITCODE"}
} finally {Pop-Location}
