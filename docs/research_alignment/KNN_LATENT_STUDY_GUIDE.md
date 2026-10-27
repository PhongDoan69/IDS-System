# kNN distance trên latent — protocol thí nghiệm thủ công

## Mục tiêu và nguyên tắc

Chỉ đổi novelty; reuse đúng các chain LOACO `recall_gate_v1_20261027_h9_s42`,
`h25_s42`, `h26_s42`. Không retrain AE/XGBoost, không dùng model main đã học
held-out. `14_run_mahalanobis_comparison.py` chỉ được import để dùng hàm kiểm
upstream; không fit Mahalanobis khi chạy script kNN.

Nguồn ý tưởng: Sun et al., ICML 2022, *Out-of-Distribution Detection with Deep
Nearest Neighbors*, https://proceedings.mlr.press/v162/sun22d.html.
Code tác giả: https://github.com/deeplearning-wisc/knn-ood (L2, kth squared L2).
Đây là adaptation dùng AE latent 16 chiều; không tái lập kết quả ImageNet/CIFAR.

## Grid được khai báo trước

- k = 1, 10, 50.
- Latent gốc (`none`) so với L2 theo từng hàng (`l2`, epsilon 1e-10).
- Reference `natural`: lấy ngẫu nhiên không hoàn lại từ known-train attacks.
- Reference `balanced`: quota gần cân bằng lớp, lớp ít lấy hết rồi chia phần
  thiếu cho các lớp còn lại; không nhân bản/oversample. Lưu số hàng từng lớp.
- Hai policy cùng kích thước min(50.000, số known-train), cùng seed42; không
  so full natural database với balanced database nhỏ hơn.
- Primary đã chốt: **natural_l2_k50**, gate recall cũ. Không tự chọn biến thể
  test cao nhất. Các biến thể khác là ablation, không phải chứng cứ độc lập.

Database chỉ nhận known TRAIN attack. Không benign, validation, test hoặc lớp
held-out. Còn có thể trùng vector feature giữa các split; không xóa hàng ngầm.
L2 là phép biến đổi từng hàng, không có thống kê fit từ validation/test.

## Lệnh VS Code / PowerShell

```powershell
cd "D:\CAO HOC\IDS System"
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\15_run_knn_distance_study.py --study-id knn_v1 --check-only
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\15_run_knn_distance_study.py --study-id knn_v1 --run
```

Check-only: kiểm đầy đủ lineage/hash/split/heldout/gate, không tạo index, không
ghi artifact. Hashing nhiều file lớn có thể im lặng một lúc. Không train song
song với runner khác; giữ nguyên source/config khi chạy. Không overwrite/resume.

Mặc định 36 cấu hình novelty và 39 lượt đánh giá pipeline (36 kNN + 3 MCP).
Chỉ dùng recall gate; thêm `--gates fixed recall` nếu muốn đối chứng cả gate0,5.
Có thể chạy một heldout trước bằng `--held-out-labels 9` với study-id riêng.
`--batch-size 1024 --workers -1` kiểm soát RAM/CPU; không thay protocol khoa học.
Không thay k/reference-size sau khi xem test rồi tuyên bố đó là cấu hình độc lập.

## Tính toán và leakage

SciPy cKDTree exact (`eps=0`), squared Euclidean, CPU FP64. Không cần Faiss,
không cài CUDA wheel hay đổi môi trường. GPU hiện không được dùng cho kNN
trong script này; benchmark tốc độ chưa được xác nhận. Exact search ở16D và
database50k có thể chậm; query theo batch, progress mỗi khoảng30 giây. Cả ba
k được query trong cùng lần tìm kiếm cho mỗi batch, không query lại từng k.

Mỗi index: fit reference -> query known validation -> chốt ngưỡng phân vị95%
cho TẤT CẢ k -> mới query test. Score lớn là nghi unknown. Giữ toán tử >= như
MCP; ties có thể làm actual validation rejection khác5%, script cảnh báo và
ghi rõ, không sửa theo test. Gate/Stage2 probabilities giữ nguyên khi đổi score.

## Artifacts

`results/knn_studies/<study-id>/` chứa protocol_lock.json, status.json,
events.log, logs evaluator và command/exit code; comparison.json, summary.csv,
COMPARISON.md báo TẤT CẢ biến thể, không xếp hạng chọn winner.

Mỗi heldout lưu known_train_indices.npy, validation_indices.npy và reference
indices theo policy. Mỗi geometry lưu knn_index.joblib (reference đã transform
và exact tree), parameters.json (policy/seed/counts/zero rows), các ngưỡng chốt
trước test. Mỗi k lưu threshold, FP64 scores, test indices và lineage contract.
Kiểm index sau reload trên16 validation rows, không dùng test để kiểm fit.

`known_class_rejection_recall.json` cạnh mỗi k và
`mcp_known_class_rejection_recall.json` tại heldout giúp phát hiện lớp known
nhỏ bị reject nhiều dù global rejection khoảng5%. Pipeline metrics/predictions
đầy đủ nằm tại `results/pipeline/<study-id>_h<ID>_<variant>_<gate>/`.

## Đọc kết quả

So sánh primary với MCP trước, sau đó xem riêng ảnh hưởng k/L2/policy cùng
reference size. Cần unknown precision/recall/F1 cuối cascade, known FRR từng
lớp, benign->unknown, macro-F1 và gate-blocked unknown; không chỉ AUROC.
Nếu chọn winner từ test ablation, chỉ ghi là exploratory; cần một đánh giá
mới độc lập trước khi chốt phương pháp. Vẫn còn một seed, split cố định,
historical tests đã xem, validation dùng upstream stopping và provenance chưa
xác minh. L2 có thể mất thông tin độ lớn; balanced cap không bảo đảm tốt hơn.
