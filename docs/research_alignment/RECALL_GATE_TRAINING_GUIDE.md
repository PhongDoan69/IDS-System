# Huấn luyện protocol recall_gate_v1

Mục tiêu: gán UNKNOWN cho attack chưa học, không suy ra tên lớp mới. Stage 1
không được loại bỏ nhiều attack trước novelty. Đây là protocol mới, không sửa
kết quả lịch sử và không bảo đảm recall unknown sẽ tăng trên mọi lớp.

## Cố định và thay đổi

- Giữ AE latent16, nested OOF 5 fold, Platt calibration, XGBoost latent nhị phân,
  XGBoost latent_only đa lớp và maximum-probability novelty.
- Giữ ngưỡng novelty theo 5% known-validation rejection.
- Thêm gate chọn trên benign + known-attack validation, loại heldout hoàn toàn.
  Chọn ngưỡng thấp nhất không vượt benign FPR 0,1% và không cao hơn 0,5.
  Đây là ngân sách vận hành khai báo trước, KHÔNG chọn từ heldout test.
- Nếu baseline đã vượt ngân sách FPR, dừng để người nghiên cứu quyết định;
  không tự tăng ngưỡng và hy sinh recall.
- Đánh giá gate cố định 0,5 và gate mới trên CÙNG checkpoint để cô lập hiệu ứng.

## Thực hiện trong PowerShell / VS Code

```powershell
cd "D:\CAO HOC\IDS System"
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\13_run_recall_gate_study.py --study-id recall_gate_v1_20261027 --plan
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\13_run_recall_gate_study.py --study-id recall_gate_v1_20261027 --run
```

Mặc định heldout 9/25/26; mỗi class phải có >=500 mẫu test. Cần khoảng 5,15 GiB
trống (ước lượng) cho ba chain, vẫn kiểm tra 2 GiB trước mỗi bước. Không xóa
artifacts cũ tự động. Không chạy song song. Run lỗi không resume/ghi đè;
đọc log trước khi quyết định ID mới. Khi hashing/checksum im lặng, runner vẫn
in RUNNING mỗi 60 giây; không Ctrl+C chỉ vì GPU tạm rảnh.

Thứ tự: environment -> scaler known-train -> AE -> Stage1 nested OOF -> Stage2
-> gate selection known-validation -> novelty -> fixed-gate test -> recall-gate
test. Không dùng chỉ số test cuối để chọn gate, profile hay novelty threshold.

## CUDA và tham số được lưu

AE train sử dụng CUDA/AMP theo cấu hình; encode toàn bộ bằng FP32 để tránh
overflow FP16. XGBoost train dùng cuda:0/hist. Không cài lại CUDA hoặc thay wheel
đang hoạt động; verify_environment ghi phiên bản thực trong log. CSV, hash,
chia split, Platt và metrics vẫn CPU/I/O; chuyển chúng sang GPU chưa có bằng
chứng lợi ích. CPU NumPy prediction của XGBoost vẫn có thể fallback DMatrix;
không tuyên bố đã tối ưu latency hay GPU utilization toàn pipeline.

Mỗi run lưu `configs/<run>.json`, scaler và fit indices trong
`<processed>/experiments/<run>/preprocessing`, AE `best.pt`, Stage1 fold/final
XGBoost + Platt trong `models/stage1/<run>`, Stage2 `final.json` trong
`models/stage2/<run>/latent_only`. Gate trong study `gate_h<ID>.json`; novelty
threshold trong `artifacts/thresholds/<run>`. Không chỉ lưu hyperparameters:
checkpoint, class order, schema, scaler và calibrator đều cần cho tái lập.

Study `results/recall_gate_studies/<study-id>` chứa protocol/source hashes,
packages.json, status.json, logs của TỪNG subprocess cùng command/exit code,
comparison.json. Logs AE gồm epoch/train/validation MSE; Stage1 gồm OOF fold
và tree metrics; Stage2 gồm tree metrics. Đây không phải benchmark inference.

## Dataset khác

Trước hết dùng adapter đã kiểm tra schema, đơn vị, ontology, benign=0 và split.
Chuẩn bị `features_raw.npy`, labels, split IDs, row hashes, metadata và config
theo contract của dự án. Không ép 84 cột bằng cách thêm số 0 hoặc đổi tên cột
mà chưa kiểm tra ý nghĩa. Runner không phải raw CSV adapter.

```powershell
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\13_run_recall_gate_study.py --study-id DATASET_recall_v1 --config configs\DATASET_MODEL.json --processed-dir data\processed\DATASET --held-out-labels ID1 ID2 --plan
```

Thay ID1/ID2 bằng số từ metadata dataset, kiểm tra support; sau khi plan hợp lệ
mới dùng --run. Mọi stage retrain trên dataset đích: đây là kiểm tra cùng phương
pháp sau retrain, KHÔNG phải zero-shot transfer từ CICIDS2017.

## Diễn giải kết quả

So sánh unknown gate recall, final unknown precision/recall/F1, benign FPR,
known false rejection và per-class support. Hạ gate có thể tăng benign->UNKNOWN;
không chỉ nhìn recall. Các test cũ đã xem nên kết quả vẫn exploratory. Một seed,
split ngẫu nhiên/vector overlap và provenance chưa xác minh vẫn là giới hạn;
ngưỡng chọn từ known validation không bảo đảm nhận diện mọi unknown attack.
