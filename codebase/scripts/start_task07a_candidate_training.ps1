$outputDir = "codebase/outputs/task07a-candidate-20261109"
$logFile = "codebase/outputs/task07a-candidate-training.log"
$errFile = "codebase/outputs/task07a-candidate-training.err.log"
$python = "codebase/.venv-train/Scripts/python.exe"
$script = "codebase/scripts/train_task07a_candidate.py"
$dataset = "codebase/data/finetune/task07a/mixed-20261108"

Write-Output "Starting task07a candidate training on RTX 2050..."
$proc = Start-Process -FilePath $python -ArgumentList @($script, "--dataset", $dataset, "--output", $outputDir, "--epochs", "30", "--batch", "2", "--execute") -RedirectStandardOutput $logFile -RedirectStandardError $errFile -NoNewWindow -PassThru
Start-Sleep -Seconds 5
Get-Process -Id $proc.Id -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, WorkingSet64
