# Uses the previously built local image; never installs tools or calls AWS.
[CmdletBinding()]
param([string]$Image = 'echomind-infra-validation:local')

$ErrorActionPreference = 'Stop'
$containerArgs = @(
    'run', '--rm', '--pull', 'never', '--platform', 'linux/amd64', '--network', 'none',
    '--read-only', '--tmpfs', '/tmp', '--env', 'PYTHONDONTWRITEBYTECODE=1'
)

# Mount only validation inputs, excluding private parameters and credentials.
foreach ($name in @('stack.yaml', 'security.guard', 'check_infra.py', 'check_guard.py', 'estimate_cost.py')) {
    $sourcePath = Join-Path $PSScriptRoot $name
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Missing validation input: $name"
    }
    $containerArgs += @('--mount', "type=bind,source=$sourcePath,target=/work/$name,readonly")
}

function Invoke-Validation {
    param([string[]]$CheckCommand)
    & docker @containerArgs $Image @CheckCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Validation failed: $($CheckCommand -join ' ') (exit $LASTEXITCODE)"
    }
}

Invoke-Validation @('cfn-lint', '--version')
Invoke-Validation @('cfn-guard', '--version')
Invoke-Validation @('cfn-lint', '-t', 'stack.yaml', '-r', 'us-east-1', '--format', 'json')
Invoke-Validation @('python', 'check_guard.py')
Invoke-Validation @('python', 'check_infra.py', '-v')
Write-Output 'All local infrastructure checks passed. No AWS resources were created.'
