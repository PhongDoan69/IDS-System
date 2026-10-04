param(
    [string]$PythonVersion = "3.12",
    [string]$TorchVersion = "2.13.0",
    [string]$TorchIndex = "https://download.pytorch.org/whl/cu130"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# CUDA Toolkit/nvcc không bắt buộc. Wheel PyTorch cu130 mang theo CUDA runtime cần thiết.
# Driver 610.62 của máy hỗ trợ CUDA tối đa 13.3 và tương thích ngược với runtime 13.0.
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Không tìm thấy Python Launcher (py.exe). Hãy cài Python $PythonVersion 64-bit trước."
}

& py "-$PythonVersion" --version
if ($LASTEXITCODE -ne 0) {
    throw "Python $PythonVersion chưa được cài hoặc chưa đăng ký với py launcher."
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & py "-$PythonVersion" -m venv (Join-Path $ProjectRoot ".venv")
}

& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

# Dùng index chính thức của PyTorch để chắc chắn lấy wheel CUDA 13.0 cho Windows.
& $VenvPython -m pip install "torch==$TorchVersion" --index-url $TorchIndex

& $VenvPython (Join-Path $PSScriptRoot "verify_environment.py") --config (Join-Path $ProjectRoot "configs\model_config.json")

Write-Host "Hoàn tất môi trường. Trong VS Code chọn interpreter: $VenvPython"

