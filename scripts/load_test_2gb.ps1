param(
  [string]$Image = "claims-pipeline-ui:newfolder",
  [string]$ContainerName = "claims-loadtest-2gb",
  [switch]$DisableLlmNarrative
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$OutputsHost = Join-Path $RepoRoot "outputs"
$DataHost = Join-Path $RepoRoot "data"
$PowerBiHost = Join-Path $RepoRoot "powerbi"
$ConfigsHost = Join-Path $RepoRoot "configs"

New-Item -ItemType Directory -Path $OutputsHost -Force | Out-Null
New-Item -ItemType Directory -Path $DataHost -Force | Out-Null
New-Item -ItemType Directory -Path $PowerBiHost -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PowerBiHost "data") -Force | Out-Null
New-Item -ItemType Directory -Path $ConfigsHost -Force | Out-Null

$runId = "loadtest_2gb_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$containerProcessedDir = "/app/data/processed/$runId"
$containerOutputsDir = "/app/outputs/$runId"
$containerPowerBiDir = "/app/powerbi/data/$runId"
$containerDbPath = "/app/outputs/$runId/claims_analytics.db"
$containerReportPath = "/app/outputs/$runId/Claims_Analysis_Report.pdf"

$narrativeArg = @()
if ($DisableLlmNarrative) {
  $narrativeArg = @("--no-llm-narrative")
}

try {
  docker rm -f $ContainerName 2>$null | Out-Null
} catch {
}

$cmd = @(
  "run",
  "--name", $ContainerName,
  "--memory", "2g",
  "--cpus", "1.5",
  "-v", "$($OutputsHost):/app/outputs",
  "-v", "$($DataHost):/app/data",
  "-v", "$($PowerBiHost):/app/powerbi",
  "-v", "$($ConfigsHost):/app/configs",
  $Image,
  "python", "src/main.py",
  "--base-dir", "/app",
  "--processed-dir", $containerProcessedDir,
  "--outputs-dir", $containerOutputsDir,
  "--db-path", $containerDbPath,
  "--powerbi-dir", $containerPowerBiDir,
  "--report-path", $containerReportPath
) + $narrativeArg

$start = Get-Date
docker @cmd
$exitCode = $LASTEXITCODE
$end = Get-Date

$memoryLimitBytes = [int64](docker inspect $ContainerName --format "{{.HostConfig.Memory}}")
$logs = docker logs $ContainerName 2>&1

$usagePath = Join-Path $OutputsHost "$runId\\usage_metrics.json"
if (-not (Test-Path $usagePath)) {
  throw "usage_metrics.json not found at $usagePath"
}
$usage = Get-Content $usagePath -Raw | ConvertFrom-Json

$summary = [ordered]@{
  run_id = $runId
  started_at_local = $start.ToString("s")
  finished_at_local = $end.ToString("s")
  duration_seconds_wall = [math]::Round(($end - $start).TotalSeconds, 3)
  docker_memory_limit_bytes = $memoryLimitBytes
  docker_memory_limit_gb = [math]::Round($memoryLimitBytes / 1GB, 3)
  container_exit_code = $exitCode
  api_calls_total = $usage.api_calls_total
  api_calls_by_kind = $usage.api_calls_by_kind
  api_errors_total = $usage.api_errors_total
  input_tokens = $usage.token_usage.input_tokens
  output_tokens = $usage.token_usage.output_tokens
  total_tokens = $usage.token_usage.total_tokens
  usage_metrics_path = $usagePath
}

$summaryPath = Join-Path $OutputsHost "$runId\\load_test_summary.json"
$summary | ConvertTo-Json -Depth 6 | Out-File -FilePath $summaryPath -Encoding utf8

$md = @"
# Load Test (2GB RAM) Summary

- Run ID: `$($summary.run_id)`
- Memory Limit: `$($summary.docker_memory_limit_gb) GB`
- Exit Code: `$($summary.container_exit_code)`
- Duration (wall): `$($summary.duration_seconds_wall) sec`

## LLM/API Usage

- API Calls (total): `$($summary.api_calls_total)`
- API Errors: `$($summary.api_errors_total)`
- Input Tokens: `$($summary.input_tokens)`
- Output Tokens: `$($summary.output_tokens)`
- Total Tokens: `$($summary.total_tokens)`

## Files

- Usage metrics: `$($summary.usage_metrics_path)`
- Summary JSON: `$summaryPath`
@"

$mdPath = Join-Path $OutputsHost "$runId\\load_test_summary.md"
$md | Out-File -FilePath $mdPath -Encoding utf8

docker rm -f $ContainerName | Out-Null

Write-Host "Load test complete."
Write-Host "Run ID: $runId"
Write-Host "Summary: $summaryPath"
Write-Host "Markdown: $mdPath"
