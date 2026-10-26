# Ma trận đối chiếu nghiên cứu – triển khai

Khởi tạo trước khi sửa source: 2026-10-26T05:23:01+07:00 (mốc kiểm tra đồng hồ). Root duy nhất: `D:\CAO HOC\IDS System`. Snapshot đầu vào: `8e96ddd0aeff5605496eb884a2a81ab8d9ee64d4`. Không thay đổi luận văn, dữ liệu gốc, nhãn, split hoặc kết quả lịch sử.

## Nguồn và thứ tự ưu tiên

1. Bản luận văn `C:\Users\Admin\Downloads\main (3).pdf`, 107 trang; SHA256 đã đối chiếu: `49fa2b10bcb3ac7cd861288dc5127718f5e614d2d4925b3db17934fe876fb1b4`. Bản trích tại `docs/thesis_review_2026-10-25/evidence/thesis_extracted.txt`. Trang dưới đây là trang PDF, không phải số trang in.
2. `docs/thesis_review_2026-10-25/REVIEW_LUAN_VAN.md`, README và input_audit.json. Đây là review kỹ thuật có sẵn, **không phải biên bản phê duyệt của người hướng dẫn**. Không tìm thấy quyết định phê duyệt mới trong nguồn đã khảo sát.
3. Tám báo cáo `docs/research_audit/01...08`; mã Axx dưới đây thuộc bảng vấn đề của báo cáo 06, snapshot 24/10/2026. Không coi snapshot cũ là trạng thái hiện tại khi đã có bằng chứng mới.
4. Code/config/tests và artifact local hiện tại. Baseline kiểm thử trước sửa: `python -B -m unittest discover -s tests -v`: 16/16 PASS (0,220 giây), không training.

## Ma trận lập trước triển khai

| Yêu cầu | Bằng chứng luận văn | Bằng chứng review/audit | Triển khai đầu vào | Sai lệch/phân loại | Hành động được giới hạn |
|---|---|---|---|---|---|
| IDS offline hai tầng | §3.1, §3.4, §3.7, PDF51–61 | Review phân biệt component/final | Gate rồi attack-only classifier, novelty tùy chọn | Không có mâu thuẫn kiến trúc | Giữ XGB/MLP, dense AE và ba score; không thêm thuật toán |
| Target 27 nhãn raw, giữ Attempted | §3.2.2 PDF53–54 | H07; A01 | preserve; binary mọi non-BENIGN | UNRESOLVED METHODOLOGICAL DECISION: provenance/ý nghĩa target | Giữ nhãn; đổi policy là REQUIRES RESEARCHER APPROVAL |
| Split random theo lớp 70/15/15 | §3.2.2 PDF53–54 | H07; A02 | Full-row dedup; còn trùng 84-feature qua split theo audit | EXPERIMENTAL VALIDITY RISK | Không đổi split ngầm; group/time split là REQUIRES RESEARCHER APPROVAL |
| Tên/schema/order/ID nhất quán | §3.2, §3.7 | A07 | BENIGN ID theo thứ tự gặp; checks yếu | IMPLEMENTATION DEFECT | Cố định BENIGN=0 cho preparation mới; validate schema/shape/labels/split và identity |
| Chỉ train fit scaler | §3.2.1, §3.3 | H05; A03 | Main đúng; LOACO dùng scaler global train | IMPLEMENTATION DEFECT | Scaler riêng theo run, fit known train; giữ raw/split/legacy scaled bất biến |
| Dense AE 84→64→32→16, MSE | §3.3 PDF54–55 | A16–18 | Đúng kiến trúc joint; thời gian 0 placeholder | DOCUMENTATION MISMATCH | Giữ kiến trúc; ghi thời gian thực/seed/checkpoint và lineage; không gọi greedy SAE |
| XGB/MLP × scaled/latent | §3.4.1 PDF55–56 | A08 | Đã có bốn main kết quả | MISSING EVIDENCE: chưa multi-seed/budget | Giữ baseline; không tuyên bố model thắng tổng quát |
| Gate theo operating point | §3.4.1 PDF56 ghi cố định 0,5 | A10; prompt yêu cầu validation-selected | Code dùng 0,5 | UNRESOLVED METHODOLOGICAL DECISION | Giữ 0,5 đúng thesis, ghi rõ không optimized; sweep/FPR budget cần REQUIRES RESEARCHER APPROVAL |
| OOF không phụ thuộc target của hàng cần dự đoán | §3.5 PDF57–58 thừa nhận hai phụ thuộc | H06; A04–05 | Outer holdout earlystop; calibrator fit/apply lại OOF | IMPLEMENTATION DEFECT | Protocol sửa có version: outer 5-fold, inner fit/stop/calibration disjoint; fold-local scaler/AE chỉ phục vụ scalar p; lưu indices; chưa chạy full fit |
| Một không gian latent chung cho Stage 2 | §3.5.2 PDF58–59 | A05 | z chung, p nối thật | EXPERIMENTAL VALIDITY RISK nếu ghép latent khác encoder | Không ghép z từ các encoder fold; chỉ ghép scalar OOF p với z chung |
| Stage 2 attack-only, weighted CE | §3.4.2 PDF56 | A14 | Mean weighted CE nhân batch size | IMPLEMENTATION DEFECT | Aggregate theo tổng class weights, regression test; checkpoint mới có thể đổi |
| Ablation meta-feature | Bảng3.1 PDF58 | M09; A08 | 3 biến thể, thiếu MLP latent-only | MISSING EVIDENCE | Thêm tùy chọn control MLP latent-only, không tự chạy; raw+latent/flat baseline chưa được duyệt, không thêm kiến trúc |
| Evaluation trên toàn test, predicted gate | §3.7 PDF61 | A06–07 | Composition đúng nhưng NaN fail-open; check-only không compose | IMPLEMENTATION DEFECT | Fail-closed, check trước return; per-class/confusion/FPR/FNR/error decomposition |
| Unknown score-only khác final | §3.6–3.7; chương4 | A06 | JSON open_set_metrics là score-only | DOCUMENTATION MISMATCH | Giữ alias lịch sử, thêm nhãn population và final unknown có benign/gate |
| Strict LOACO mọi bước fit | §3.2/3.6; giới hạn chương4 | H05; A03,A11 | Loại heldout ở models, chưa scaler | EXPERIMENTAL VALIDITY RISK | Known-only scaler + lineage xuyên tầng; tất cả LOACO cũ vẫn preliminary; multi-heldout chưa chạy |
| Tái lập/protect artifacts | §1.6, chương4 | A13,A22 | Paths overwrite; thiếu hashes | IMPLEMENTATION DEFECT | Refuse overwrite, run manifest/config/env/input hashes và sidecar identity; legacy chỉ replay có cảnh báo |
| External validation | Phạm vi/future work, chưa kết quả | A21 snapshot nói chưa có tích hợp | Hiện có 9 CSV CSE và file đuôi .757702C0; UNSW Data.csv/Lable.csv/Readme | MISSING EVIDENCE: completeness/feature semantics | Adapter audit/preprocess có schema explicit; không download, không gán ontology CIC2017 lên dataset khác |
| Giải thích Fwd RST/ports/flow timing | §3.2; limitations | A19 | Ports còn, IP đã loại | EXPERIMENTAL VALIDITY RISK, chưa đo shortcut | Kiểm feature exact names và mismatch; không drop theo phỏng đoán; ablation cần protocol riêng |
| Latency/generalization/novelty | Chương4 limitations, chương5 | A12,A17–18,A21 | Không có model-reload benchmark/cross-dataset results | MISSING EVIDENCE | Ghi NOT REPRODUCIBLE nếu thiếu entrypoint; không gọi score replay là model latency |

## Giải quyết xung đột và biên giới quyền

Luận văn mô tả trung thực phiên bản cũ, kể cả OOF/scaler sai. Sửa engineering không biến lịch sử đó thành thí nghiệm đúng: code mới mang protocol riêng, cần rerun và bổ sung phương pháp/kết quả sau khi có evidence. Inner partition là chi tiết corrective protocol phải công bố, không phải bằng chứng được supervisor phê duyệt. Không đổi seed/split/nhãn để làm đẹp metrics.

Thứ tự thực hiện: contracts/evaluation → preprocessing LOACO → nested OOF/calibration → weighted loss/reproducibility → adapters/tests → tài liệu. Các mục chưa triển khai hoặc chưa kiểm chứng thực thi phải được ghi rõ trong changelog và báo cáo cuối; bảng này là kế hoạch đối chiếu, không phải checklist đã hoàn thành.
