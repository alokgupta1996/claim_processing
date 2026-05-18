param(
  [string]$Image = "claims-pipeline-ui:newfolder",
  [string]$AppContainer = "claims-api-2gb",
  [int]$Users = 20,
  [int]$SpawnRate = 5,
  [string]$RunTime = "90s",
  [int]$PipelineRuns = 1,
  [string]$RunMode = "pdf_only",
  [int]$MaxFilesPerRequest = 3,
  [switch]$DisableLlmNarrative
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ScriptsDir = Join-Path $RepoRoot "scripts"
$OutputsHost = Join-Path $RepoRoot "outputs"
$DataHost = Join-Path $RepoRoot "data"
$PowerBiHost = Join-Path $RepoRoot "powerbi"
$ConfigsHost = Join-Path $RepoRoot "configs"
$ApiPort = 8502

New-Item -ItemType Directory -Path $OutputsHost -Force | Out-Null
New-Item -ItemType Directory -Path $DataHost -Force | Out-Null
New-Item -ItemType Directory -Path $PowerBiHost -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PowerBiHost "data") -Force | Out-Null
New-Item -ItemType Directory -Path $ConfigsHost -Force | Out-Null

$llmEnvNames = @(
  "AZURE_OPENAI_API_KEY",
  "AZURE_OPENAI_ENDPOINT",
  "AZURE_OPENAI_DEPLOYMENT",
  "AZURE_OPENAI_API_VERSION",
  "OPENAI_API_KEY"
)
$dockerEnvArgs = @()
$presentLlmEnv = @()
foreach ($envName in $llmEnvNames) {
  $envVal = [Environment]::GetEnvironmentVariable($envName)
  if (-not [string]::IsNullOrWhiteSpace($envVal)) {
    $dockerEnvArgs += @("-e", "$envName=$envVal")
    $presentLlmEnv += $envName
  }
}

$runId = "locust_2gb_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$runOutputDir = Join-Path $OutputsHost $runId
New-Item -ItemType Directory -Path $runOutputDir -Force | Out-Null

$locustBase = Join-Path $runOutputDir "locust"
$containerLocustBase = "/mnt/out/locust"

try { docker rm -f $AppContainer 2>$null | Out-Null } catch {}

# Start app under 2GB memory cap.
$appRunCmd = @(
  "run", "-d",
  "--name", $AppContainer,
  "--memory", "2g",
  "--cpus", "1.5",
  "-p", "$ApiPort`:$ApiPort",
  "-v", "$($OutputsHost):/app/outputs",
  "-v", "$($DataHost):/app/data",
  "-v", "$($PowerBiHost):/app/powerbi",
  "-v", "$($ConfigsHost):/app/configs"
) + $dockerEnvArgs + @(
  $Image,
  "python", "-m", "uvicorn", "api.app:app",
  "--host", "0.0.0.0",
  "--port", "$ApiPort"
)
docker @appRunCmd | Out-Null

# Wait for health.
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
  try {
    $status = (Invoke-WebRequest -Uri "http://localhost:$ApiPort/api/health" -UseBasicParsing -TimeoutSec 3).StatusCode
    if ($status -eq 200) {
      $ready = $true
      break
    }
  } catch {}
  Start-Sleep -Seconds 2
}
if (-not $ready) {
  throw "API app did not become healthy on port $ApiPort."
}

# Capture existing API output folders before load.
$existingApiRunNames = @{}
Get-ChildItem $OutputsHost -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like "api_*" } |
  ForEach-Object { $existingApiRunNames[$_.Name] = $true }

# Run locust headless against the API upload endpoint.
$locustUseLlm = if ($DisableLlmNarrative) { "false" } else { "true" }
docker run --rm `
  -v "$($ScriptsDir):/mnt/locust" `
  -v "$($runOutputDir):/mnt/out" `
  -v "$($RepoRoot):/mnt/input" `
  -e LOCUST_INPUT_DIR=/mnt/input `
  -e LOCUST_UPLOAD_ENDPOINT=/api/upload-and-run `
  -e LOCUST_RUN_MODE=$RunMode `
  -e LOCUST_USE_LLM_NARRATIVE=$locustUseLlm `
  -e LOCUST_MAX_FILES_PER_REQUEST=$MaxFilesPerRequest `
  locustio/locust `
  -f /mnt/locust/locustfile.py `
  --headless `
  -u $Users `
  -r $SpawnRate `
  --run-time $RunTime `
  --host http://host.docker.internal:$ApiPort `
  --csv "$containerLocustBase" | Out-Null

# Capture newly created API output folders from Locust uploads and aggregate usage.
$newApiRunDirs = Get-ChildItem $OutputsHost -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like "api_*" -and -not $existingApiRunNames.ContainsKey($_.Name) }
$apiUploadUsage = [ordered]@{
  run_count = 0
  api_calls_total = 0
  chat_completions = 0
  embeddings = 0
  api_errors_total = 0
  input_tokens = 0
  output_tokens = 0
  total_tokens = 0
}
foreach ($dir in $newApiRunDirs) {
  $usageFile = Join-Path $dir.FullName "usage_metrics.json"
  if (-not (Test-Path $usageFile)) { continue }
  try {
    $u = Get-Content $usageFile -Raw | ConvertFrom-Json
    $apiUploadUsage.run_count += 1
    $apiUploadUsage.api_calls_total += [int]$u.api_calls_total
    $apiUploadUsage.chat_completions += [int]$u.api_calls_by_kind.chat_completions
    $apiUploadUsage.embeddings += [int]$u.api_calls_by_kind.embeddings
    $apiUploadUsage.api_errors_total += [int]$u.api_errors_total
    $apiUploadUsage.input_tokens += [int]$u.token_usage.input_tokens
    $apiUploadUsage.output_tokens += [int]$u.token_usage.output_tokens
    $apiUploadUsage.total_tokens += [int]$u.token_usage.total_tokens
  } catch {}
}

# Run one pipeline execution under 2GB for token/API usage capture.
$containerProcessedDir = "/app/data/processed/$runId"
$containerOutputsDir = "/app/outputs/$runId"
$containerPowerBiDir = "/app/powerbi/data/$runId"
$containerDbPath = "/app/outputs/$runId/claims_analytics.db"
$containerReportPath = "/app/outputs/$runId/Claims_Analysis_Report.pdf"

$narrativeArg = @()
if ($DisableLlmNarrative) {
  $narrativeArg = @("--no-llm-narrative")
}

for ($i = 1; $i -le $PipelineRuns; $i++) {
  $iterRunId = "$runId`_p$($i)"
  $iterProcessedDir = "/app/data/processed/$iterRunId"
  $iterOutputsDir = "/app/outputs/$iterRunId"
  $iterPowerBiDir = "/app/powerbi/data/$iterRunId"
  $iterDbPath = "/app/outputs/$iterRunId/claims_analytics.db"
  $iterReportPath = "/app/outputs/$iterRunId/Claims_Analysis_Report.pdf"

  $pipelineCmd = @(
    "run", "--rm",
    "--memory", "2g",
    "--cpus", "1.5",
    "-v", "$($OutputsHost):/app/outputs",
    "-v", "$($DataHost):/app/data",
    "-v", "$($PowerBiHost):/app/powerbi",
    "-v", "$($ConfigsHost):/app/configs"
  ) + $dockerEnvArgs + @(
    $Image,
    "python", "src/main.py",
    "--base-dir", "/app",
    "--processed-dir", $iterProcessedDir,
    "--outputs-dir", $iterOutputsDir,
    "--db-path", $iterDbPath,
    "--powerbi-dir", $iterPowerBiDir,
    "--report-path", $iterReportPath,
    "--run-mode", $RunMode
  ) + $narrativeArg
  docker @pipelineCmd | Out-Null
}

$usagePath = Join-Path $OutputsHost "$runId`_p$PipelineRuns\\usage_metrics.json"
if (-not (Test-Path $usagePath)) {
  throw "usage_metrics.json not found at $usagePath"
}
$usage = Get-Content $usagePath -Raw | ConvertFrom-Json

$locustStatsPath = Join-Path $runOutputDir "locust_stats.csv"
if (-not (Test-Path $locustStatsPath)) {
  throw "Locust stats not found at $locustStatsPath"
}
$statsRows = Import-Csv $locustStatsPath
$agg = $statsRows | Where-Object { $_.Name -eq "Aggregated" } | Select-Object -First 1

function Parse-IntSafe($value) {
  $n = 0
  if ([int]::TryParse([string]$value, [ref]$n)) { return $n }
  return 0
}

function Parse-DoubleSafe($value) {
  $n = 0.0
  if ([double]::TryParse([string]$value, [ref]$n)) { return $n }
  return 0.0
}

$memoryLimitBytes = [int64](docker inspect $AppContainer --format "{{.HostConfig.Memory}}")

$summary = [ordered]@{
  run_id = $runId
  docker_memory_limit_bytes = $memoryLimitBytes
  docker_memory_limit_gb = [math]::Round($memoryLimitBytes / 1GB, 3)
  locust = [ordered]@{
    users = $Users
    spawn_rate = $SpawnRate
    run_time = $RunTime
    api_port = $ApiPort
    run_mode = $RunMode
    max_files_per_request = $MaxFilesPerRequest
    total_requests = Parse-IntSafe($agg."Request Count")
    total_failures = Parse-IntSafe($agg."Failure Count")
    median_ms = Parse-DoubleSafe($agg."Median Response Time")
    p95_ms = Parse-DoubleSafe($agg."95%")
    avg_ms = Parse-DoubleSafe($agg."Average Response Time")
    rps = Parse-DoubleSafe($agg."Requests/s")
  }
  llm_usage = [ordered]@{
    llm_env_vars_present = $presentLlmEnv
    llm_env_vars_count = $presentLlmEnv.Count
    api_calls_total = [int]$usage.api_calls_total
    api_calls_by_kind = $usage.api_calls_by_kind
    api_errors_total = [int]$usage.api_errors_total
    input_tokens = [int]$usage.token_usage.input_tokens
    output_tokens = [int]$usage.token_usage.output_tokens
    total_tokens = [int]$usage.token_usage.total_tokens
    usage_metrics_path = $usagePath
    api_upload_usage = $apiUploadUsage
  }
}

$summaryPath = Join-Path $runOutputDir "load_test_summary.json"
$summary | ConvertTo-Json -Depth 8 | Out-File -FilePath $summaryPath -Encoding utf8

$mdPath = Join-Path $runOutputDir "load_test_summary.md"
$md = @"
# Locust Load Test (2GB RAM) Summary

- Run ID: $($summary.run_id)
- Memory Limit: $($summary.docker_memory_limit_gb) GB
- Pipeline Runs: $PipelineRuns

## HTTP Load (Locust)
- Users: $($summary.locust.users)
- Spawn Rate: $($summary.locust.spawn_rate)/sec
- Run Time: $($summary.locust.run_time)
- API Port: $($summary.locust.api_port)
- Run Mode: $($summary.locust.run_mode)
- Max Files/Request: $($summary.locust.max_files_per_request)
- Total Requests: $($summary.locust.total_requests)
- Total Failures: $($summary.locust.total_failures)
- Avg Response: $($summary.locust.avg_ms) ms
- Median Response: $($summary.locust.median_ms) ms
- P95 Response: $($summary.locust.p95_ms) ms
- Throughput: $($summary.locust.rps) req/s

## LLM/API Usage
- LLM env vars present: $($summary.llm_usage.llm_env_vars_count)
- Pipeline API Calls (total): $($summary.llm_usage.api_calls_total)
- Pipeline API Errors: $($summary.llm_usage.api_errors_total)
- Pipeline Input Tokens: $($summary.llm_usage.input_tokens)
- Pipeline Output Tokens: $($summary.llm_usage.output_tokens)
- Pipeline Total Tokens: $($summary.llm_usage.total_tokens)
- Upload Runs Captured: $($summary.llm_usage.api_upload_usage.run_count)
- Upload API Calls (total): $($summary.llm_usage.api_upload_usage.api_calls_total)
- Upload API Errors: $($summary.llm_usage.api_upload_usage.api_errors_total)
- Upload Input Tokens: $($summary.llm_usage.api_upload_usage.input_tokens)
- Upload Output Tokens: $($summary.llm_usage.api_upload_usage.output_tokens)
- Upload Total Tokens: $($summary.llm_usage.api_upload_usage.total_tokens)

## Output Files
- JSON summary: $summaryPath
- Usage metrics: $($summary.llm_usage.usage_metrics_path)
- Locust raw stats: $locustStatsPath
"@
$md | Out-File -FilePath $mdPath -Encoding utf8

docker rm -f $AppContainer | Out-Null

Write-Host "Locust load test complete."
Write-Host "Summary: $summaryPath"
Write-Host "Markdown: $mdPath"
