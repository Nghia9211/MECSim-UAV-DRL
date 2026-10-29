param(
    [Parameter(Mandatory=$true)][string]$Directory,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedCommit,
    [ValidatePattern('^target/[A-Za-z0-9][A-Za-z0-9_.-]*$')][string]$RemoteOutput='target/dqn-24-125-retrain-20261030-v1',
    [ValidatePattern('^target/[A-Za-z0-9][A-Za-z0-9_.-]*$')][string]$RemoteControl='target/dqn-24-125-control-20261030-v1',
    [ValidateRange(10,60)][int]$PollSeconds=45,
    [ValidateRange(1,48)][int]$MaxWaitHours=12,
    [switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
$Directory=[IO.Path]::GetFullPath($Directory)
$repo='/mnt/disk1/nghialt2/MECSim-UAV-DRL'
$sshExe="$env:WINDIR/System32/OpenSSH/ssh.exe"
$scpExe="$env:WINDIR/System32/OpenSSH/scp.exe"

function Read-JsonFile([string]$Path) { Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json }
function Require([bool]$Condition,[string]$Message) { if (-not $Condition) {throw $Message} }

function Validate-Campaign {
    Require ((Get-Content -LiteralPath "$Directory/control/exit-code" -Raw).Trim() -eq '0') 'Remote job did not exit 0'
    Require ((Get-Content -LiteralPath "$Directory/control/commit" -Raw).Trim() -eq $ExpectedCommit) 'Unexpected job commit'
    Require ((Get-Content -LiteralPath "$Directory/control/job.log" -Raw).Contains('DQN_24_125_COMPLETE_AND_VERIFIED')) 'Missing completion marker'
    $manifest=Read-JsonFile "$Directory/manifest.json"
    $verification=Read-JsonFile "$Directory/verification.json"
    $smoke=Read-JsonFile "$Directory/smoke/manifest.json"
    $smokeVerification=Read-JsonFile "$Directory/smoke/verification.json"
    Require ($manifest.status -eq 'COMPLETE' -and $manifest.smoke -eq $false) 'Full campaign incomplete'
    Require ($manifest.commit -eq $ExpectedCommit -and $smoke.commit -eq $ExpectedCommit) 'Unexpected campaign source'
    Require ($verification.status -eq 'PASS' -and $verification.source_unchanged -eq $true) 'Full campaign verification failed'
    Require ($smoke.status -eq 'COMPLETE' -and $smoke.smoke -eq $true -and $smokeVerification.status -eq 'PASS') 'Smoke incomplete/unverified'
    Require ($verification.traces -eq 1440 -and $smokeVerification.traces -eq 32) 'Missing evaluation traces'
    Require ($manifest.plan.steps -eq 1000000 -and $manifest.plan.test_episodes -eq 30) 'Unexpected training/evaluation budget'
    Require ((@($manifest.plan.modes | Sort-Object) -join ',') -eq 'extended125,paper24') 'Unexpected state modes'
    Require ((@($manifest.plan.learning_seeds | Sort-Object) -join ',') -eq '0,1,2') 'Missing learning seeds'
    Require ($manifest.plan.properties.'paper.deliveryConvention' -eq 'LEGACY') 'Expected paper REFERENCE setting'
    $protocolHash=(Get-FileHash -LiteralPath "$Directory/control/protocol.json" -Algorithm SHA256).Hash.ToLowerInvariant()
    Require ($protocolHash -eq $manifest.protocol_sha256 -and $protocolHash -eq $smoke.protocol_sha256) 'Protocol snapshot mismatch'
    Require (@($verification.checkpoints).Count -eq 12) 'Expected best/final for six models'
    $seen=New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($proof in $verification.checkpoints) {
        Require ($proof.run -match '^(paper24|extended125)/seed-([012])$') 'Unsafe/unknown checkpoint run'
        $mode=$Matches[1];$learningSeed=[int]$Matches[2]
        Require ($proof.checkpoint -in @('best','final')) 'Unknown checkpoint type'
        Require ($seen.Add($proof.run+'::'+$proof.checkpoint)) 'Duplicate checkpoint'
        $name=if ($proof.checkpoint -eq 'best') {'best_model.zip'} else {'final_model.zip'}
        $modelHash=(Get-FileHash -LiteralPath "$Directory/$($proof.run)/$name" -Algorithm SHA256).Hash.ToLowerInvariant()
        Require ($modelHash -eq $proof.sha256) 'Downloaded checkpoint hash mismatch'
        Require ($proof.steps -gt 0 -and $proof.steps -le 1000000) 'Invalid checkpoint step count'
        if ($proof.checkpoint -eq 'final') {Require ($proof.steps -eq 1000000) 'Final checkpoint is undertrained'}
        $cfg=Read-JsonFile "$Directory/$($proof.run)/config.json"
        Require ($cfg.actual_steps -eq 1000000 -and $cfg.gradient_updates -eq 249975) 'Incomplete optimization budget'
        Require ($cfg.seed -eq $learningSeed -and $cfg.environment.observation_mode -eq $mode) 'Model/state label mismatch'
    }
    [pscustomobject]@{status='PASS';models=6;checkpoints=12;steps_per_model=1000000;evaluation_traces=1440;commit=$ExpectedCommit}
}

if ($ValidateOnly) {
    Validate-Campaign | ConvertTo-Json
    exit 0
}

New-Item -ItemType Directory -Force $Directory | Out-Null
function Log([string]$Message) {
    $line=(Get-Date -Format o)+' '+$Message
    Add-Content -LiteralPath "$Directory/watcher.log" -Value $line -Encoding UTF8
}
function Copy-Remote([string]$Relative,[string]$Local) {
    New-Item -ItemType Directory -Force ([IO.Path]::GetDirectoryName($Local)) | Out-Null
    for ($attempt=0;$attempt -lt 3;$attempt++) {
        try {
            & $scpExe -q -o BatchMode=yes -o ConnectTimeout=10 "aiotlab_92:$repo/$Relative" $Local 2>$null
            if ($LASTEXITCODE -eq 0) {return}
        } catch {Log "Download retry: $Relative"}
        Start-Sleep -Seconds 5
    }
    throw "Could not download $Relative"
}

try {
    Log "Waiting for $RemoteControl; expected commit $ExpectedCommit"
    $deadline=(Get-Date).AddHours($MaxWaitHours)
    while ($true) {
        if ((Get-Date) -gt $deadline) {throw 'Timed out waiting for training'}
        $status='RUNNING'
        try {
            $result=& $sshExe -o BatchMode=yes -o ConnectTimeout=10 aiotlab_92 "if test -f $repo/$RemoteControl/exit-code; then cat $repo/$RemoteControl/exit-code; else echo RUNNING; fi" 2>$null
            if ($LASTEXITCODE -eq 0) {$status=(@($result) -join "`n").Trim()}
        } catch {Log 'SSH unavailable; retrying'}
        if ($status -eq '0') {break}
        if ($status -match '^\d+$') {throw "Remote training failed with exit $status"}
        Start-Sleep -Seconds $PollSeconds
    }
    Log 'Remote exit 0; downloading audited results and checkpoints'
    foreach ($file in @('exit-code','commit','job.log','started','finished','protocol.json')) {
        Copy-Remote "$RemoteControl/$file" "$Directory/control/$file"
    }
    foreach ($file in @('manifest.json','verification.json','REPORT.md','summary.csv')) {
        Copy-Remote "$RemoteOutput/$file" "$Directory/$file"
        Copy-Remote "${RemoteOutput}-smoke/$file" "$Directory/smoke/$file"
    }
    foreach ($mode in @('paper24','extended125')) {foreach ($seed in @(0,1,2)) {
        foreach ($file in @('config.json','validation.csv','best_model.zip','final_model.zip')) {
            Copy-Remote "$RemoteOutput/$mode/seed-$seed/$file" "$Directory/$mode/seed-$seed/$file"
        }
    }}
    $receipt=Validate-Campaign
    $receipt | ConvertTo-Json | Set-Content -LiteralPath "$Directory/completion-checked.json" -Encoding UTF8
    @'
# DQN 24D / 125D completed

Six paper REFERENCE models, 1m steps/model. Full replay/checkpoint audits PASS.
These models choose the next device in PaperSimulation; they are separate from mobile contact-wait/offloading. Mobile task DVR, J/on-time image and task latency are not defined in this paper environment; see REPORT.md for paper lifetime results.

Checkpoints and reports were downloaded and their hashes checked. Shutdown is manual: run Tat_may_sau_train.cmd. It requests shutdown without forcing applications closed.
'@ | Set-Content -LiteralPath "$Directory/READ_ME.md" -Encoding UTF8
    @'
@echo off
"%SystemRoot%\System32\shutdown.exe" /s /t 0
'@ | Set-Content -LiteralPath "$Directory/Tat_may_sau_train.cmd" -Encoding ASCII
    Log 'PASS: reports/models saved; manual shutdown command created'
} catch {
    Log ('FAILED: '+$_.Exception.Message)
    @{status='FAILED';error=$_.Exception.Message;at=(Get-Date -Format o)} | ConvertTo-Json |
        Set-Content -LiteralPath "$Directory/watcher-failed.json" -Encoding UTF8
    exit 1
}
