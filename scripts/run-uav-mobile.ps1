param(
    [ValidateRange(1,1000)][int]$Seeds=30,
    [ValidateRange(0,2147483647)][long]$FirstSeed=51000,
    [string]$Output='',
    [string]$Protocol='PureEdgeSim/uav/offloading/mobile-protocol.json',
    [ValidateRange(0,0.99)][double]$EstimateError=0,
    [switch]$Offline
)
$ErrorActionPreference='Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not $Output) {$Output="target/mobile-$(Get-Date -Format yyyyMMdd-HHmmss)-$PID"}
    $noise=$EstimateError.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    $arguments=@('compile','exec:java','-Dexec.mainClass=uav.offloading.MobileServiceBenchmark',
        '-Dexec.classpathScope=compile',"-Dmobile.seeds=$Seeds","-Dmobile.protocol=$Protocol")
    if ($PSBoundParameters.ContainsKey('FirstSeed')) {$arguments += "-Dmobile.firstSeed=$FirstSeed"}
    if ($PSBoundParameters.ContainsKey('EstimateError')) {$arguments += "-Dmobile.estimateError=$noise"}
    if ($Output) {$arguments += "-Dmobile.output=$Output"}
    if ($Offline) {$arguments=@('-o')+$arguments}
    & mvn @arguments
    if ($LASTEXITCODE -ne 0) {throw "Mobile service benchmark failed: $LASTEXITCODE"}
    & python scripts/verify-uav-mobile.py $Output
    if ($LASTEXITCODE -ne 0) {throw 'Mobile verification/metrics failed'}
} finally {Pop-Location}
