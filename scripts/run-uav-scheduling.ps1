param(
    [ValidateRange(2,1000)][int]$Seeds=30,
    [long]$FirstSeed=0,
    [string]$Output='',
    [switch]$Offline
)
$ErrorActionPreference='Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $arguments=@('compile','exec:java','-Dexec.mainClass=uav.scheduling.SchedulingBenchmark',
        '-Dexec.classpathScope=compile',"-Dscheduling.seeds=$Seeds","-Dscheduling.firstSeed=$FirstSeed")
    if ($Output) {$arguments += "-Dscheduling.output=$Output"}
    if ($Offline) {$arguments=@('-o')+$arguments}
    & mvn @arguments
    if ($LASTEXITCODE -ne 0) {throw "Scheduling benchmark failed: $LASTEXITCODE"}
} finally {Pop-Location}
