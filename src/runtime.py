from __future__ import annotations

import os
import random
from typing import Any

import numpy as np


def set_reproducible_seed(seed: int) -> None:
    """Cố định các seed có thể kiểm soát; CUDA vẫn có thể sai khác nhỏ giữa các lần chạy."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    import torch

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def configure_torch_runtime(hardware: dict[str, Any]):
    """Kiểm tra CUDA và áp dụng cấu hình tối ưu cho RTX 3050 Laptop 4 GB."""
    import torch

    requested = str(hardware["device"])
    wants_cuda = requested.startswith("cuda")
    cuda_available = torch.cuda.is_available()
    if wants_cuda and not cuda_available and hardware.get("require_cuda", True):
        raise RuntimeError(
            "Cấu hình yêu cầu CUDA nhưng torch.cuda.is_available() = False. "
            "Hãy chạy scripts/setup_windows_cuda.ps1 và scripts/verify_environment.py."
        )
    device = torch.device(requested if wants_cuda and cuda_available else "cpu")

    if device.type == "cuda":
        torch.cuda.set_device(device)
        torch.backends.cuda.matmul.allow_tf32 = bool(hardware.get("allow_tf32", True))
        torch.backends.cudnn.allow_tf32 = bool(hardware.get("allow_tf32", True))
        torch.backends.cudnn.benchmark = bool(hardware.get("cudnn_benchmark", True))
        torch.use_deterministic_algorithms(bool(hardware.get("deterministic_algorithms", False)))
        # "high" cho phép TF32 trên Ampere; nhanh hơn FP32 đầy đủ nhưng vẫn phù hợp mô hình tabular.
        torch.set_float32_matmul_precision("high")
    return device


def amp_settings(hardware: dict[str, Any], device) -> tuple[bool, Any]:
    import torch

    enabled = bool(hardware.get("mixed_precision", True)) and device.type == "cuda"
    dtype_name = str(hardware.get("amp_dtype", "float16"))
    dtype = torch.float16 if dtype_name == "float16" else torch.bfloat16
    return enabled, dtype


def cuda_diagnostics() -> dict[str, Any]:
    import torch

    report: dict[str, Any] = {
        "torch_version": torch.__version__,
        "torch_cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        report.update(
            {
                "gpu_name": props.name,
                "compute_capability": f"{props.major}.{props.minor}",
                "vram_mib": round(props.total_memory / 1024**2),
                "cudnn_version": torch.backends.cudnn.version(),
            }
        )
    return report


def clear_cuda_cache() -> None:
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def oom_guidance(batch_size: int) -> str:
    return (
        "GPU hết bộ nhớ. Không đổi dữ liệu hoặc split. Hãy giảm batch_size trong "
        f"configs/model_config.json từ {batch_size} xuống {max(256, batch_size // 2)}, "
        "sau đó tạo experiment id mới để kết quả vẫn truy vết được."
    )

