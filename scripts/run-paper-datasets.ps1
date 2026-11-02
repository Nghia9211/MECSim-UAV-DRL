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
    # Dataset paths and EXAMPLE compute assumptions live in scenarios.json (dataset_defaults);
    # 'evaluate' runs the dataset_evaluation suite. Only explicitly given options override them.
    $mainClass = if ($Mode -eq 'single') { 'uav.PaperSimulation' } else { 'uav.PaperDatasetEvaluation' }
    $mavenArgs = @('compile','exec:java',"-Dexec.mainClass=$mainClass",'-Dexec.classpathScope=compile')
    if ($Mode -eq 'single') { $mavenArgs += '-Dpaper.workload=mixed' }
    $invariant = [Globalization.CultureInfo]::InvariantCulture
    $overrides = [ordered]@{
        Seeds = 'paper.seeds'; Powered = 'paper.powered'; Connected = 'paper.connected'
        BackgroundScale = 'paper.backgroundScale'; BackgroundTasksPerSlot = 'paper.backgroundTasksPerSlot'
    }
    foreach ($name in $overrides.Keys) {
        if ($PSBoundParameters.ContainsKey($name)) {
            $value = (Get-Variable -Name $name -ValueOnly).ToString($invariant)
            $mavenArgs += "-D$($overrides[$name])=$value"
        }
    }
    if ($Offline) { $mavenArgs = @('-o') + $mavenArgs }
    & mvn @mavenArgs
    if ($LASTEXITCODE -ne 0) { throw "Maven exited with code $LASTEXITCODE" }
} finally { Pop-Location }
