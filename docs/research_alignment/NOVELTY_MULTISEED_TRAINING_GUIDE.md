# Pipeline và đợt huấn luyện đối chứng novelty nhiều seed

Ngày chuẩn bị: 27/10/2026. Thư mục duy nhất: `D:\CAO HOC\IDS System`.

## 1. Mục tiêu và giới hạn kết luận

Đo khả năng gán nhãn **UNKNOWN (-1)** cho tấn công thuộc lớp đã bị loại hoàn toàn khỏi việc fit scaler, AE, Stage 1, Stage 2 và novelty detector. Không yêu cầu, và không có cơ sở để hệ thống trả đúng tên lớp chưa được học. Nhãn gốc của lớp held-out chỉ dùng để kiểm tra loại trừ và chấm điểm cuối cùng.

Ứng viên: **balanced_l2_k1** trên AE latent. Đối chứng giữ nguyên **MCP** (`1 - max probability`) và **Mahalanobis** (khoảng cách bình phương nhỏ nhất đến trung tâm lớp với hiệp phương sai pooled Ledoit–Wolf). Cả ba dùng đúng cùng upstream, mẫu test và gate của từng trial.

Ứng viên kNN này được đề xuất sau khi đã xem kết quả test `knn_v1`. Đợt mới khóa giả thuyết và kiểm tra độ ổn định theo seed, **không phải xác nhận độc lập trên test mới**. Tên script `confirmatory` không được dùng để tuyên bố test độc lập hoặc chứng minh phát hiện zero-day ngoài thực tế.

## 2. Thiết kế được khóa

| Thành phần | Quy định |
|---|---|
| Dữ liệu | CICIDS2017 local daily CSV; release/provenance upstream chưa xác minh |
| Chuẩn bị gốc | Dùng lại immutable arrays của `round2_20261027_fp32_s42`, có reproduction hash từ lượt rebuild raw trước |
| Kiểm tra mới | Audit lại raw CSV, so manifest; kiểm checksum arrays/schema/split trước từng bước |
| Target | Giữ nguyên 27 nhãn, kể cả Attempted; không gộp target theo kết quả |
| Split | Giữ split stratified random đã lưu; không tự chia lại |
| Held-out | 9 = DoS Hulk; 25 = Portscan; 26 = DDoS, mỗi trial loại một lớp riêng |
| Seed fit | 42, 43, 44 → 9 chuỗi mô hình độc lập về quá trình fit, cùng split |
| Novelty candidate | k=1, chuẩn hóa từng vector L2 với epsilon 1e-10, reference balanced tối đa 50.000 known-train attack, không oversampling |
| Seed reference | Bằng seed của trial, thay đổi cả fit upstream và mẫu reference; chưa cô lập riêng hai nguồn biến thiên |
| Gate chính | Ngưỡng thấp nhất ≤0,5 với benign FPR known-validation ≤0,001 |
| Gate phụ | Cố định 0,5 để kiểm tra tác động recall gate |
| Ngưỡng novelty | Quantile 95% score known-validation attack; `score >= threshold` → nghi ngờ unknown |
| Chọn cấu hình | Không chọn lại mô hình, k, chuẩn hóa, ngân sách FPR hay ngưỡng bằng held-out test |

Support held-out trong split hiện tại:

| Lớp | Train bị loại | Validation bị loại | Test unknown |
|---|---:|---:|---:|
| DoS Hulk (9) | 110.928 | 23.770 | 23.770 |
| Portscan (25) | 111.346 | 23.860 | 23.860 |
| DDoS (26) | 66.600 | 14.272 | 14.272 |

Số mẫu held-out ở train/validation chỉ thể hiện các hàng **không được dùng** để fit hoặc chọn ngưỡng, không phải dữ liệu huấn luyện zero-day. Không ghép ba bài toán LOACO thành một mô hình đã đồng thời học ba lớp unknown.

## 3. Pipeline thực thi

1. **Môi trường và audit:** kiểm CUDA, chạy unit/integration tests trên fixture; audit raw bằng `00_audit_dataset.py`, đối chiếu byte/hash với manifest lịch sử. Các arrays chuẩn bị gốc được kiểm toàn vẹn và giữ nguyên, không rebuild lại toàn bộ CSV trong đợt này. Đây là huấn luyện lại toàn bộ **mô hình**, không phải một lần thu thập dữ liệu mới.
2. **Preprocessing từng trial:** fit StandardScaler mới bằng known-train (benign + known attacks), loại held-out. Recompute transform toàn bộ bằng scaler đã fit, không cập nhật state với validation/test. So từng phần tử float32 với bản chuẩn hóa known-train cùng held-out đã lưu; chỉ khi giống hoàn toàn mới hard-link tệp immutable. Không tái sử dụng AE/XGBoost cũ.
3. **AE mới:** 84 → 64 → 32 → 16 → 32 → 64 → 84, MSE, AdamW; tối đa 100 epoch, early stopping patience 12 theo known-validation. AE học cả benign và known attacks, không phải benign-only anomaly detector. Batch train 8.192, encode 16.384; kiến trúc và hyperparameters gốc giữ nguyên trong JSON trial.
4. **Stage 1 mới:** XGBoost latent binary, class imbalance weighting; `hist`, CUDA. Nested 5-fold OOF: scaler/AE/classifier trong từng outer fold không fit hoặc early-stop bằng outer holdout. Trong outer-training: 80% fit, 10% stop, 10% Platt calibration. OOF được calibrate từng fold; final Platt fit raw OOF chỉ áp dụng final validation/test, không áp dụng lại lên OOF train.
5. **Stage 2 mới:** XGBoost `latent_only`, multi:softprob, balanced sample weights, chỉ known-train attacks; early-stop known-validation attacks. Không thêm P_attack làm meta-feature ở đợt này. P_attack vẫn cần cho gate và hợp đồng pipeline; nested OOF được giữ để duy trì protocol, dù không còn là input Stage 2.
6. **Khóa recall gate:** chỉ known-validation gồm benign + known attacks; không dùng held-out validation/test. Không đảm bảo một FPR budget cho known-validation sẽ bảo toàn toàn bộ unknown thực tế.
7. **Novelty đối chứng chung:** fit Mahalanobis trên toàn bộ known-train attack latent; fit kNN index trên balanced known-train reference; MCP dùng xác suất Stage 2. Tính cả ba score validation, lưu `locked_validation_thresholds.json`, kiểm tra reload mô hình tái tạo score; sau đó mới query test. Không để hàng validation/test trong index/covariance.
8. **Đánh giá:** một reference không novelty tại recall gate để đo lỗi cascade; ba detector × hai gate. Mẫu chỉ được gán unknown nếu đã qua Stage 1 và score novelty đạt ngưỡng. Đánh giá score-only riêng, không tráo với tỷ lệ hệ thống cuối cùng.
9. **Tổng hợp:** toàn bộ 9 trial, mean/std/min/max theo held-out × method × gate, paired delta kNN trừ từng baseline trên cùng seed. Giữ cả trường hợp kNN không tốt hơn, không chọn winner riêng theo từng held-out.

Quy tắc đầu ra cuối:

```text
p_attack < gate_threshold            -> BENIGN (0)
p_attack >= gate và score < threshold -> argmax known class của Stage 2
p_attack >= gate và score >= threshold -> UNKNOWN (-1)
```

Không có nhánh cứu mẫu bị chặn ở gate. Muốn thêm bypass/rescue benign gate là **một phương pháp khác**, cần protocol và đối chứng riêng, không sửa trong lúc đang chạy.

## 4. GPU, CPU và dung lượng

AE và các XGBoost dùng CUDA tuần tự trên RTX 3050 Laptop 4 GiB. AMP float16 cho train AE; encode latent giữ FP32 để tránh overflow đã gặp trước đây. Không nâng CUDA/package giữa đợt. Không khởi chạy job GPU khác đồng thời.

Mahalanobis dùng CPU BLAS FP64; kNN dùng exact `scipy.spatial.cKDTree`, CPU đa luồng, không approximate NN. Giữ backend này để đối chiếu đúng với baseline trước; không có bằng chứng mọi bước nhỏ/16 chiều đều nhanh hơn nếu chuyển lên GPU. CUDA warning DMatrix do input NumPy CPU không tự nó là lỗi kết quả.

Hard-link chỉ tiết kiệm bản sao vật lý của `features_scaled.npy`, không chia sẻ tham số mô hình. Mỗi scaler vẫn fit mới và kiểm transform toàn bộ trước khi liên kết. Không chỉnh sửa trực tiếp tệp `.npy` đã liên kết; không xóa/move nguồn lịch sử vì ancestry contract vẫn tham chiếu đường dẫn nguồn. Windows Explorer có thể đếm dung lượng logic nhiều lần; kiểm dung lượng thực bằng `Get-PSDrive D`.

Runner ước tính 0,42 GiB artifacts/trial ngoài scaled array được chia sẻ, một fold cache ~0,78 GiB, dự phòng 1,5 GiB. Với 9 trial yêu cầu khoảng **6,06 GiB trống lúc bắt đầu**. Đây là ước tính, không bảo đảm dung lượng; runner kiểm lại trước mỗi bước và dừng nếu dưới 1,5 GiB. Không tự xóa run cũ, không tự giảm seed/budget hoặc tiếp tục một run lỗi.

## 5. Lệnh chạy và theo dõi từ VS Code

PowerShell tại thư mục project:

```powershell
Set-Location 'D:\CAO HOC\IDS System'
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\16_run_confirmatory_study.py --study-id novelty_r3_20261027 --plan
if ($LASTEXITCODE -ne 0) { throw 'Preflight thất bại' }
# CHỈ chạy lệnh dưới nếu chưa có runner cùng study đang chạy.
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\16_run_confirmatory_study.py --study-id novelty_r3_20261027 --run
if ($LASTEXITCODE -ne 0) { throw 'Đọc status và log; không chạy lại cùng study ID' }
```

`--plan` chỉ kiểm và in kế hoạch, không fit, không ghi artifacts. `--run` từ chối mọi target đã tồn tại; không hỗ trợ resume. Nếu agent đã khởi chạy `novelty_r3_20261027`, **không chạy lại lệnh `--run` trên IDE**.

```powershell
$Study = 'D:\CAO HOC\IDS System\results\novelty_confirmation\novelty_r3_20261027'
$State = Get-Content -LiteralPath "$Study\status.json" -Raw | ConvertFrom-Json
$State | Select-Object status, pid, current_step
$State.steps | Select-Object name, status, returncode, seconds
Get-Content -LiteralPath $State.steps[-1].log -Tail 30
Get-Process -Id $State.pid -ErrorAction SilentlyContinue
Get-PSDrive D
nvidia-smi
```

Tránh sleep/hibernate khi chạy; không sửa `src/`, `scripts/`, `tests/`, dữ liệu, config đã khóa. Runner dừng nếu checksum thay đổi. Nếu thiếu dung lượng, OOM, lỗi hợp đồng hoặc tiến trình biến mất: giữ nguyên artifacts/log và điều tra; thay đổi cấu hình chỉ ở study ID mới sau quyết định nghiên cứu.

## 6. Vị trí bằng chứng và tham số được lưu

| Nội dung | Vị trí trong project |
|---|---|
| Protocol khóa, checksum nguồn/data/config | `results/novelty_confirmation/<study>/protocol_lock.json` |
| Trạng thái, PID, command đầy đủ, exit code/thời gian từng bước | `.../<study>/status.json`, `logs/*.log` |
| Audit dữ liệu và môi trường mới | `.../<study>/raw_audit/`, `environment.json` |
| Config từng held-out/seed | `configs/<study>_h<ID>_s<SEED>.json` |
| Scaler fit mới, fit indices, xác nhận shared storage | `data/processed/round2_20261027_fp32_s42/experiments/<run>/preprocessing/` |
| AE checkpoint, optimizer, kiến trúc/history | `models/autoencoder/<run>/best.pt`; results và metadata cùng run |
| Stage 1 final/fold classifier, fold AE/scaler, Platt, indices | `models/stage1/<run>/xgboost_latent/` |
| Stage 2 classifier/class ids/probabilities | `models/stage2/<run>/latent_only/`, `results/stage2/<run>/latent_only/` |
| Mahalanobis/kNN joblib; covariance/means/shrinkage/index | `models/novelty/<run>/heldout_<ID>/latent_only/` |
| Known-train/reference/validation indices và parameter manifest | Cùng thư mục novelty model: `*.npy`, `parameters.json` |
| MCP/Mahalanobis/kNN score, ngưỡng khóa trước query test | `results/novelty/<run>/heldout_<ID>/latent_only/` |
| Ngưỡng riêng mỗi detector | `artifacts/thresholds/<run>/heldout_<ID>/latent_only/<method>.json` |
| Gate đã chọn | `.../<study>/gate_h<ID>_s<SEED>.json` |
| Metric cascade, confusion matrix/per-class và dự đoán nén | `results/pipeline/<run>_<method>_<gate>/metrics.json`, `predictions.npz`, `contract.json` |
| So sánh đầy đủ; bảng từng trial; mean/std và paired deltas | `.../<study>/comparison.json`, `summary.csv`, `summary.json`, `RESEARCH_REPORT.md` |
| False unknown theo từng known class | `.../<study>/*_class_rejection.json` |

MCP không có tham số novelty phải fit riêng: lưu Stage 2 classifier, class IDs và ngưỡng MCP để tái hiện. Mahalanobis và kNN có file model riêng. Tất cả được giữ; không thay/xóa kết quả các đợt `recall_gate_v1_20261027`, `mahalanobis_v1`, `knn_v1`.

## 7. Điều kiện đọc kết quả và viết luận văn

Chỉ kết luận đợt hoàn tất nếu `status=completed`, đủ **120 subprocess steps** với cấu hình mặc định, mọi `returncode=0`, đủ 9 trial × 3 detector × 2 gate = 54 dòng trong `summary.csv`, cùng 9 evaluation reference không novelty. Kiểm mọi support tương ứng 23.770 / 23.860 / 14.272 và gate/population matched.

Các đại lượng cần báo cáo đồng thời:

- **Unknown recall cuối = unknown_detected / unknown_support**, precision, F1 sau Stage 1; không lấy score-only recall làm tỷ lệ toàn hệ thống.
- Unknown bị gate chặn; unknown qua gate nhưng bị nhận thành known; known attack bị gate nhận thành benign; known bị novelty từ chối sai; benign bị nhận unknown.
- Stage 1 binary recall/FPR; Stage 2 known-only macro-F1/per-class; E2E macro-F1; known false rejection toàn cục **và từng lớp kèm support**, đặc biệt lớp hiếm.
- Mean/std/min/max theo seed cùng từng held-out; không gộp các seed thành số lượng mẫu độc lập. Bootstrap accuracy hiện tại là row bootstrap trên split này, không phản ánh độ độc lập giữa flows/nguồn và không thay thế uncertainty của unknown recall.
- Mục tiêu 5% known-validation rejection không đảm bảo đúng 5% từng lớp hoặc trên test; báo thực tế và ties, không sửa ngưỡng bằng test để ép tỷ lệ.

Một kết luận hợp lệ nếu dữ liệu ủng hộ: “Trên ba bài toán LOACO của bản CICIDS2017 cục bộ, pipeline với novelty kNN cho ... theo seed, với ... false rejection; chưa xác nhận tính tổng quát ngoài split này.” Không tuyên bố phát hiện đúng tên zero-day, không coi điểm số cao là tính mới nghiên cứu, không ghi “leakage-free” khi còn feature-vector overlap/provenance và shared validation.

**Bước khoa học kế tiếp:** khóa phương pháp chung rồi đánh giá split độc lập theo nhóm feature-vector/flow hoặc thời gian với đủ support; kiểm provenance/Attempted; phân tách tập early stopping và threshold calibration nếu thiết kế được; xác nhận trên hai dataset khác bằng chuẩn hóa schema/đơn vị có kiểm chứng, không dùng test ngoài để chọn lại phương pháp. Các việc này chưa được thực hiện trong đợt này.
