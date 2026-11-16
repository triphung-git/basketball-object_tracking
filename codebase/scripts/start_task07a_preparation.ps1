param([string]$RunId = ('restart-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
$ErrorActionPreference = 'Stop'
if ($RunId -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Invalid run identifier' }
$task07Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$task07Job = Join-Path $task07Root 'outputs/task07a-finetune-20261108/job'
$task07Status = Join-Path $task07Job 'status.json'
if (Test-Path -LiteralPath $task07Status) {
    $task07Previous = Get-Content -LiteralPath $task07Status -Raw | ConvertFrom-Json
    if ($task07Previous.pid) {
        $task07Existing = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $task07Previous.pid)
        if ($task07Existing -and $task07Existing.Name -eq 'python.exe' -and $task07Existing.CommandLine -like '*prepare_task07a_ready.py*') {
            Write-Output ('Preparation already running: PID ' + $task07Previous.pid)
            return
        }
    }
}
$task07Run = Join-Path $task07Job $RunId
if (Test-Path -LiteralPath $task07Run) { throw 'Run directory already exists; choose a new RunId' }
New-Item -ItemType Directory -Path $task07Run | Out-Null
$task07Python = Join-Path $task07Root '.venv/Scripts/python.exe'
$task07Script = Join-Path $task07Root 'scripts/prepare_task07a_ready.py'
$task07Arguments = @('-u',('"' + $task07Script + '"'),'--run-dir',('"' + $task07Run + '"'),'--manage-downloads')
$task07Process = Start-Process -FilePath $task07Python -ArgumentList $task07Arguments -WindowStyle Hidden -RedirectStandardOutput (Join-Path $task07Run 'supervisor.stdout.log') -RedirectStandardError (Join-Path $task07Run 'supervisor.stderr.log') -PassThru
Write-Output ('Started preparation launcher PID ' + $task07Process.Id)
Write-Output ('Status: ' + $task07Status)
