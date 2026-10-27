# Mahalanobis — tái sử dụng upstream LOACO, so sánh với MCP

## Phạm vi

Chỉ fit bộ novelty Mahalanobis mới; KHÔNG train lại scaler, AE, Stage 1 hay
Stage 2. Dùng đúng latent/P_attack/class probabilities của ba source run
`recall_gate_v1_20261027_h9_s42`, `h25_s42`, `h26_s42`. Không thay bằng
artifact main closed-set vì main đã học lớp held-out.

Đây là baseline thích nghi từ Mahalanobis theo lớp, không tuyên bố tái lập
nguyên trạng OIDMD. Thuật toán: trung bình latent riêng từng known-attack
class; residual sau trừ trung bình lớp; covariance dùng chung Ledoit–Wolf
shrinkage fit trên toàn known TRAIN attack. Không fit covariance riêng cho
lớp hiếm. Score = khoảng cách Mahalanobis bình phương nhỏ nhất đến mọi lớp.
Điểm càng lớn càng nghi unknown; nhãn known vẫn do Stage 2 XGBoost quyết định.

## Chạy trong VS Code

```powershell
cd "D:\CAO HOC\IDS System"
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\14_run_mahalanobis_comparison.py --study-id mahalanobis_v1 --check-only
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\14_run_mahalanobis_comparison.py --study-id mahalanobis_v1 --run
```

`--check-only`: verify hash/ancestry/schema/split/heldout/gate, không fit hoặc
ghi output. Hash các array lớn có thể mất thời gian, không phải treo GPU.
`--run`: fit novelty cho cả 3 heldout và replay MCP đối chứng trên cùng input.
Không chép dataset, không cài package, không sửa checkpoint cũ. CPU FP64/BLAS
và batch score chủ động được dùng cho covariance 16 chiều; không cần CUDA để
fit lại các mạng lớn. Cần tối thiểu 512 MiB trống; giữ lock chung với GPU jobs
để tránh thao tác song song lên artifacts. Nếu lỗi, giữ nguyên output và dùng
study-id mới sau khi chẩn đoán; không resume/overwrite.

Có thể chạy một heldout bằng `--held-out-labels 9`; batch size là thông số
vận hành, không chọn dựa trên test. Source-study mặc định có seed42 trong tên
run; script này không phải adapter tổng quát cho source study tên khác cấu trúc.

## Kiểm soát leakage và so sánh công bằng

1. Fit means/covariance chỉ trên known train attacks; loại benign và heldout.
2. Chốt ngưỡng bằng phân vị 95% known validation attack score như MCP (ngân
   sách rejection 5%). Không chọn covariance/hyperparameter từ test.
3. Sau khi fit/ngưỡng khóa mới score test. Lưu FP64, không ép float32 làm đổi tie.
4. Đánh giá cả gate0,5 và recall gate cũ. Với mỗi gate, MCP/Mahalanobis dùng
   cùng P_attack/Stage2 probabilities và test indices; kiểm tra Stage1 metrics
   giống hệt. Không đổi gate khi đổi novelty.
5. Báo actual known false rejection vì quantile/ties không bảo đảm chính xác5%
   ở validation và không bảo đảm5% ở test.

## Kết quả và tham số

`results/mahalanobis_studies/<study-id>/`:

- protocol_lock.json: source/input hashes, scope, tham số và giới hạn.
- heldout_<ID>/mahalanobis.joblib: class IDs, means, covariance, precision,
  Cholesky, class counts, Ledoit–Wolf shrinkage; kiểm tra score sau reload.
- fit_indices.npy, validation_indices.npy, fit.json: bằng chứng scope fit.
- mahalanobis_threshold.json: ngưỡng, budget và nguồn known validation.
- novelty/: validation/test scores, test indices và lineage contract.
- logs/: command evaluator, stdout/stderr; status.json: progress/exit codes.
- comparison.json và COMPARISON.md: MCP vs Mahalanobis, fixed/recall gates.

Các metric/predictions đầy đủ lưu riêng dưới `results/pipeline/<study-id>_...`.
Lựa chọn phương pháp chỉ sau review khoa học, không tự thay pipeline chuẩn
nếu một test score cao hơn. So sánh chính: recall-gate unknown recall/precision/
F1, benign→unknown, known false rejection, gate-blocked unknown và per-class
support; score-only AUROC/AP là bổ sung, không thay metric cuối cascade.

## Giới hạn

Validation cũ còn dùng upstream cho early stopping; không có calibration split
mới. Một seed, split cố định/trùng vector, test đã được xem và provenance chưa
xác minh vẫn còn. Covariance pooled ưu thế lớp đông; lớp hiếm có mean bất ổn.
Không có bảo đảm hình học AE phân tách unknown. Nếu score không tốt, báo kết
quả âm; không chỉnh method theo heldout test rồi gọi là đánh giá độc lập.
