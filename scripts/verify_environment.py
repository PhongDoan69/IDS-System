from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.model_config import load_model_config
from src.console import configure_utf8_console


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kiểm tra môi trường CPU/GPU, không huấn luyện mô hình.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "model_config.json"))
    parser.add_argument("--skip-cuda-smoke", action="store_true")
    return parser.parse_args()


def main() -> None:
    configure_utf8_console()
    args = parse_args()
    config = load_model_config(args.config)
    import numpy
    import pandas
    import sklearn
    import torch
    import xgboost

    from src.runtime import cuda_diagnostics

    xgboost_build = xgboost.build_info()
    report = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scikit_learn": sklearn.__version__,
        "xgboost": xgboost.__version__,
        "xgboost_cuda_enabled": xgboost_build.get("USE_CUDA"),
        **cuda_diagnostics(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if config["hardware"]["require_cuda"] and not report["cuda_available"]:
        raise SystemExit("LỖI: cấu hình yêu cầu CUDA nhưng PyTorch không nhận GPU.")
    if config["hardware"]["require_cuda"] and not report["xgboost_cuda_enabled"]:
        raise SystemExit("LỖI: wheel XGBoost hiện tại không được build với CUDA.")
    expected_runtime = config["hardware"]["pytorch_cuda_wheel"].removeprefix("cu")
    expected_runtime = f"{int(expected_runtime) // 10}.{int(expected_runtime) % 10}"
    if report["torch_cuda_runtime"] != expected_runtime:
        raise SystemExit(
            f"LỖI: PyTorch CUDA runtime={report['torch_cuda_runtime']}, cần {expected_runtime}."
        )
    if report.get("gpu_name") != config["hardware"]["expected_gpu"]:
        print("CẢNH BÁO: GPU thực tế khác cấu hình; hãy giảm batch_size nếu VRAM thấp hơn.")
    if not args.skip_cuda_smoke and torch.cuda.is_available():
        # Đây chỉ là phép cộng tensor 4 phần tử để xác nhận wheel/driver, không phải chạy model.
        value = (torch.ones(4, device="cuda") + 1).cpu().tolist()
        print(f"CUDA smoke test: OK ({value})")


if __name__ == "__main__":
    main()

