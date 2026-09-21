param(
    [ValidateSet('single','evaluate')][string]$Mode = 'evaluate',
    [int]$Seeds = 30,
    [int]$Powered = 8,
    [int]$Connected = 8,
    [double]$BackgroundScale = 1,
    [int]$BackgroundTasksPerSlot = 1,
    [switch]$Offline
)
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Push-Location $project
try {
    # Explicit EXAMPLE assumptions, not hardware measurements or paper parameters.
    $mainClass = if ($Mode -eq 'single') { 'uav.PaperSimulation' } else { 'uav.PaperDatasetEvaluation' }
    $mavenArgs = @('compile','exec:java',"-Dexec.mainClass=$mainClass",'-Dexec.classpathScope=compile',
        '-Dpaper.workload=datasets',"-Dpaper.seeds=$Seeds", "-Dpaper.powered=$Powered", "-Dpaper.connected=$Connected",
        '-Drescuenet.images=datasets/raw/rescuenet/validation/val-org-img',
        '-Drescuenet.masks=datasets/raw/rescuenet/validation/val-label-img',
        '-Dalibaba.csv=datasets/raw/alibaba2018/batch_task.csv',
        '-Dpaper.imageLimit=449','-Dpaper.alibabaLimit=1000','-Dpaper.alibabaScanLimit=100000',
        '-Dpaper.uavMips=2000','-Dpaper.imageMiPerMegapixel=833.3333333333334','-Dpaper.cpuPowerW=20',
        '-Dalibaba.assumedMips=1000','-Dalibaba.durationScale=1',
        "-Dpaper.backgroundScale=$($BackgroundScale.ToString([Globalization.CultureInfo]::InvariantCulture))",
        "-Dpaper.backgroundTasksPerSlot=$BackgroundTasksPerSlot")
    if ($Offline) { $mavenArgs = @('-o') + $mavenArgs }
    & mvn @mavenArgs
    if ($LASTEXITCODE -ne 0) { throw "Maven exited with code $LASTEXITCODE" }
} finally { Pop-Location }
