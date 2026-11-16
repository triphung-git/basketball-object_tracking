param(
    [string]$OutputDir = "codebase/outputs/task07-finetune-recovery-20261113/candidate-training",
    [int]$Epochs = 30,
    [int]$Batch = 2,
    [int]$Patience = 10
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path

$env:PYTHONPATH = "$repoRoot\codebase\src;$repoRoot\codebase\scripts"
$env:PYTHONIOENCODING = "utf-8"

$python = (Resolve-Path "$repoRoot\codebase\.venv-train\Scripts\python.exe").Path
$script = (Resolve-Path "$repoRoot\codebase\scripts\train_task07a_candidate.py").Path
$dataset = (Resolve-Path "$repoRoot\codebase\data\finetune\task07a\mixed-20261108").Path

$resolvedOutputDir = Join-Path $repoRoot $OutputDir
if (-not (Test-Path $resolvedOutputDir)) {
    New-Item -ItemType Directory -Path $resolvedOutputDir -Force | Out-Null
}

$logFile = Join-Path $resolvedOutputDir "candidate_stdout.log"
$errFile = Join-Path $resolvedOutputDir "candidate_stderr.log"

Write-Output "Starting Task07 Recovery Candidate Fine-Tuning..."
Write-Output "Repo Root: $repoRoot"
Write-Output "Target: $resolvedOutputDir"
Write-Output "Dataset: $dataset"
Write-Output "Epochs: $Epochs, Batch: $Batch, Patience: $Patience"

# In PowerShell, pass single properly-quoted string to avoid space-splitting bugs with native Win32 processes
$argString = "-u `"$script`" --dataset `"$dataset`" --output `"$resolvedOutputDir`" --epochs $Epochs --batch $Batch --patience $Patience --name candidate --execute"

$proc = Start-Process -FilePath $python `
    -ArgumentList $argString `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errFile `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 5

$alive = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
if ($alive) {
    Write-Output "Candidate job successfully running in background with PID $($proc.Id)"
    Write-Output "Working Set: $([math]::Round($alive.WorkingSet64 / 1MB, 2)) MB"
    Write-Output "Stdout: $logFile"
    Write-Output "Stderr: $errFile"
} else {
    Write-Error "Process $($proc.Id) terminated prematurely. Check $errFile"
    if (Test-Path $errFile) {
        Get-Content $errFile
    }
}
