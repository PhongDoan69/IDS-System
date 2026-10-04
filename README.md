# IDS System - CICIDS2017 Research Pipeline

Pipeline thực nghiệm cho luận văn thạc sĩ về hệ thống phát hiện xâm nhập kết hợp mô
hình máy học. Phase 2 đã hoàn tất làm sạch, bảo toàn 27 nhãn, loại rò rỉ đặc trưng,
chia train/validation/test cố định và scale chỉ trên train.

Phần mã Phase 3-6 hiện đã sẵn sàng để người dùng chủ động chạy trong Visual Studio
Code. Mã không tự huấn luyện khi import và mọi script đều có chế độ `--check-only`.

## Cấu trúc mô hình

1. Autoencoder học latent 16 chiều từ 84 đặc trưng đã scale.
2. Stage 1 so sánh XGBoost/MLP cho BENIGN vs ATTACK và sinh `P_attack` OOF.
3. Stage 2 so sánh latent-only với latent + `P_attack` cho phân loại đa lớp tấn công.
4. Novelty detection dùng LOACO, max probability, One-Class SVM và Isolation Forest.
5. Đánh giá end-to-end sinh BENIGN, lớp tấn công đã biết hoặc UNKNOWN_ATTACK.

## Bắt đầu

Máy cần Python 3.12 64-bit. Từ terminal VS Code:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows_cuda.ps1
.\.venv\Scripts\python.exe scripts\verify_environment.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\02_train_autoencoder.py --check-only
```

Quy trình, lệnh chạy đầy đủ, LOACO và lưu ý GPU nằm tại
[`docs/TRAINING_GUIDE.md`](docs/TRAINING_GUIDE.md).

## Nguyên tắc chống leakage

- Exact duplicate được loại trước khi split.
- Scaler chỉ fit trên train; validation/test dùng scaler đã đóng băng.
- Stage 1 dùng 5-fold OOF cho xác suất train đưa sang Stage 2.
- Calibration chỉ fit bằng OOF train.
- Early stopping và threshold chỉ dùng validation.
- Test không tham gia fit, calibration, chọn epoch hoặc chọn ngưỡng.
- Với LOACO, lớp held-out phải bị loại khỏi train/validation của AE, Stage 1 và Stage 2.

Raw CSV trong `CICIDS2017/` không bị sửa đổi. Model, latent và các artifact lớn được
Git ignore theo mặc định.
