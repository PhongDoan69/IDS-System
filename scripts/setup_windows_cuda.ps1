param(
    [string]$PythonVersion = "",
    [string]$TorchVersion = "2.13.0",
    [string]$TorchIndex = "https://download.pytorch.org/whl/cu130"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# CUDA Toolkit/nvcc is optional. The PyTorch cu130 wheel includes the required CUDA runtime.
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher (py.exe) was not found. Install 64-bit Python 3.10, 3.11, or 3.12 first."
}

if ($PythonVersion) {
    $PythonCandidates = @($PythonVersion)
} else {
    $PythonCandidates = @("3.12", "3.11", "3.10")
}

$SelectedPythonVersion = $null
$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
foreach ($Candidate in $PythonCandidates) {
    & py "-$Candidate" -c "import sys; raise SystemExit(0 if sys.maxsize > 2**32 else 1)" *> $null
    if ($LASTEXITCODE -eq 0) {
        $SelectedPythonVersion = $Candidate
        break
    }
}
$ErrorActionPreference = $PreviousErrorActionPreference

if (-not $SelectedPythonVersion) {
    if ($PythonVersion) {
        throw "64-bit Python $PythonVersion is not installed or is not registered with py.exe. Run 'py -0p' to list installed versions."
    }
    throw "No supported 64-bit Python was found. Install Python 3.10, 3.11, or 3.12, then run this script again."
}

Write-Host "Using Python $SelectedPythonVersion"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & py "-$SelectedPythonVersion" -m venv (Join-Path $ProjectRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create .venv with Python $SelectedPythonVersion."
    }
}

function Invoke-CheckedVenvPython {
    param(
        [string]$Step,
        [string[]]$CommandArgs
    )

    & $VenvPython @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE. Review the pip/Python error above."
    }
}

Invoke-CheckedVenvPython "Virtual environment check" @(
    "-c", "import sys; print('Virtual environment:', sys.executable)"
)
Invoke-CheckedVenvPython "pip/setuptools/wheel upgrade" @(
    "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"
)
Invoke-CheckedVenvPython "Project dependency installation" @(
    "-m", "pip", "install", "-r", (Join-Path $ProjectRoot "requirements.txt")
)

# Use the official PyTorch index to select the CUDA 13.0 wheel for Windows.
Invoke-CheckedVenvPython "PyTorch CUDA installation" @(
    "-m", "pip", "install", "torch==$TorchVersion", "--index-url", $TorchIndex
)

Invoke-CheckedVenvPython "Environment verification" @(
    (Join-Path $PSScriptRoot "verify_environment.py"),
    "--config",
    (Join-Path $ProjectRoot "configs\model_config.json")
)

Write-Host "Environment setup complete. Select this VS Code interpreter: $VenvPython"
