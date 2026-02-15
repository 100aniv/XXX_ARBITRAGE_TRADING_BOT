param(
    [string]$ComposeFile = "infra/docker-compose.yml",
    [string]$ProjectName = "arbitrage",
    [int]$RedisDb = 0,
    [int]$HealthcheckTimeoutSec = 90,
    [int]$EnsureSchema = 1,
    [int]$ApplySchemaIfMissing = 0,
    [string]$SchemaSqlPath = "db/schema/v2_schema.sql"
)

$ErrorActionPreference = "Stop"
try {
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue) {
        $global:PSNativeCommandUseErrorActionPreference = $false
    }
} catch {
}

function New-Timestamp {
    return (Get-Date -Format "yyyyMMdd_HHmmss")
}

function Write-Line {
    param([string]$Message)
    Write-Host $Message
    if ($script:EvidenceFile) {
        Add-Content -Path $script:EvidenceFile -Value $Message
    }
}

function Invoke-NativeLogged {
    param(
        [scriptblock]$Command,
        [string]$OutFile
    )

    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $Command 2>&1
        if ($OutFile) {
            $out | Set-Content -Path $OutFile
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
}

function Wait-ContainerHealthy {
    param(
        [string]$ContainerName,
        [int]$TimeoutSec
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $status = (& docker inspect -f "{{.State.Health.Status}}" $ContainerName 2>$null)
            if ($status -eq "healthy") {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 2
    }

    return $false
}

function Get-MissingV2Tables {
    $sql = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('v2_orders','v2_fills','v2_trades') ORDER BY table_name;"
    $rawPath = Join-Path $evidenceDir "postgres_schema_check_raw.txt"
    $exit = Invoke-NativeLogged -Command { docker exec arbitrage-postgres psql -U arbitrage -d arbitrage -t -A -c $sql } -OutFile $rawPath
    if ($exit -ne 0) {
        return @("v2_orders", "v2_fills", "v2_trades")
    }

    $out = @()
    if (Test-Path -Path $rawPath) {
        $out = Get-Content -Path $rawPath
    }

    $existing = @()
    foreach ($line in $out) {
        $t = ($line -as [string]).Trim()
        if ($t) { $existing += $t }
    }

    $required = @("v2_orders", "v2_fills", "v2_trades")
    $missing = @()
    foreach ($t in $required) {
        if (-not ($existing -contains $t)) { $missing += $t }
    }
    return $missing
}

function Invoke-V2SchemaApply {
    param([string]$SchemaPath)

    if (-not (Test-Path -Path $SchemaPath)) {
        Write-Line "FAIL: schema sql file not found: $SchemaPath"
        exit 1
    }

    Write-Line "db_schema_apply=starting"
    $applyPath = Join-Path $evidenceDir "postgres_schema_apply.txt"
    $containerSchemaPath = "/tmp/v2_schema.sql"
    $cpExit = Invoke-NativeLogged -Command { docker cp $SchemaPath "arbitrage-postgres:$containerSchemaPath" } -OutFile (Join-Path $evidenceDir "docker_cp_schema.txt")
    if ($cpExit -ne 0) {
        Write-Line "FAIL: schema copy into container failed"
        exit 1
    }
    $applyExit = Invoke-NativeLogged -Command { docker exec arbitrage-postgres psql -U arbitrage -d arbitrage -f $containerSchemaPath } -OutFile $applyPath
    if ($applyExit -ne 0) {
        Write-Line "FAIL: schema apply failed"
        exit 1
    }
    Write-Line "db_schema_apply=done"
}

$ts = New-Timestamp
$evidenceDir = Join-Path -Path "logs/evidence" -ChildPath ("STEP0_BOOTSTRAP_RUNTIME_ENV_" + $ts)
New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null
$script:EvidenceFile = Join-Path -Path $evidenceDir -ChildPath "bootstrap_runtime_env.txt"

Write-Line "timestamp=$ts"
Write-Line "compose_file=$ComposeFile"

if (-not (Test-Path -Path $ComposeFile)) {
    Write-Line "FAIL: compose file not found: $ComposeFile"
    exit 1
}

Write-Line "docker_compose_up=starting"
$composeUpPath = Join-Path $evidenceDir "docker_compose_up.txt"
$composeUpExit = Invoke-NativeLogged -Command { docker compose -p $ProjectName -f $ComposeFile up -d postgres redis } -OutFile $composeUpPath

if ($composeUpExit -ne 0) {
    Write-Line "WARN: docker compose up failed (exit=$composeUpExit). Attempting docker start for existing containers..."
    $startPath = Join-Path $evidenceDir "docker_start_existing.txt"
    $startExit = Invoke-NativeLogged -Command { docker start arbitrage-postgres arbitrage-redis } -OutFile $startPath
    if ($startExit -ne 0) {
        Write-Line "FAIL: docker start existing containers failed"
        exit 1
    }
}

Write-Line "docker_compose_ps=starting"
$composePsPath = Join-Path $evidenceDir "docker_compose_ps.txt"
$composePsExit = Invoke-NativeLogged -Command { docker compose -p $ProjectName -f $ComposeFile ps } -OutFile $composePsPath
if ($composePsExit -ne 0) {
    Write-Line "FAIL: docker compose ps failed"
    exit 1
}

$pgOk = Wait-ContainerHealthy -ContainerName "arbitrage-postgres" -TimeoutSec $HealthcheckTimeoutSec
$redisOk = Wait-ContainerHealthy -ContainerName "arbitrage-redis" -TimeoutSec $HealthcheckTimeoutSec

if (-not $pgOk) {
    Write-Line "FAIL: postgres healthcheck not healthy within ${HealthcheckTimeoutSec}s"
    exit 1
}

if (-not $redisOk) {
    Write-Line "FAIL: redis healthcheck not healthy within ${HealthcheckTimeoutSec}s"
    exit 1
}

if ($EnsureSchema -ne 0) {
    Write-Line "db_schema_check=starting"
    $missing = Get-MissingV2Tables
    if ($missing.Count -gt 0) {
        Write-Line ("WARN: missing tables: " + ($missing -join ","))
        if ($ApplySchemaIfMissing -ne 0) {
            Invoke-V2SchemaApply -SchemaPath $SchemaSqlPath
            $missing2 = Get-MissingV2Tables
            if ($missing2.Count -gt 0) {
                Write-Line ("FAIL: schema still missing tables after apply: " + ($missing2 -join ","))
                exit 1
            }
        } else {
            Write-Line "FAIL: DB schema missing (strict mode requires v2_orders/v2_fills/v2_trades)"
            exit 1
        }
    }
    Write-Line "db_schema_check=ok"
}

$env:POSTGRES_CONNECTION_STRING = "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
$env:REDIS_URL = "redis://localhost:6380/$RedisDb"
$env:BOOTSTRAP_FLAG = "1"

Write-Line "POSTGRES_CONNECTION_STRING=SET"
Write-Line "REDIS_URL=SET"
Write-Line "BOOTSTRAP_FLAG=SET"
Write-Line "OK"

exit 0
