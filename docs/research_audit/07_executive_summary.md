# 07 — Tóm tắt điều hành

**Phạm vi:** D:\CAO HOC\IDS System · commit 895cc8b · audit 24/10/2026. Chỉ kiểm tra và tạo báo cáo; không train, sửa source/config/data hoặc ghi đè kết quả.

## Đánh giá tổng thể

Dự án là một prototype nghiên cứu offline đã chạy thực nghiệm, nhưng **chưa sẵn sàng dùng toàn bộ kết quả hiện tại làm bằng chứng cuối cùng cho luận văn có thể bảo vệ**. Cần sửa protocol và bổ sung đối chứng; không cần bắt đầu lại mọi công việc engineering.

Đã xác minh: dữ liệu 2.096.804 hàng/84 features; AE latent 16; XGBoost và MLP Stage 1; P_attack và calibration; ba biến thể Stage 2 main; ba novelty scores trong LOACO-26; bốn pipeline evaluation. 16 unit tests đạt. Các metric test tính lại và cả bốn final prediction arrays tái ghép đều khớp artifacts.

Main latent-only có accuracy = 0,995298 nhưng Macro-F1 = 0,840758; một số lớp hiếm có finalF1 = 0. Độ chính xác tổng thể không đủ đại diện chất lượng phát hiện mọi lớp.

## Rủi ro lớn nhất

- Nguồn/version dữ liệu và ngữ nghĩa 27 nhãn chưa được giải trình đầy đủ; Attempted cần chốt chính sách target.
- Có 2.213 test và 2.253 validation vectors trùng hoàn toàn bộ 84 features với train.
- Scaler LOACO đã fit cả 66.600 DDoS train dù DDoS là lớp “chưa biết”; strict LOACO chưa đạt.
- OOF holdout dùng để early stopping; calibrator áp lại trên chính các OOF target đã fit. Không thể bảo đảm meta-feature độc lập hoàn toàn.
- Unknown recall = 0,260650 đang báo là score-only; sau gate toàn pipeline còn 0,247197, F1 trên toàn test 0,337592.
- Thiếu full baselines, nhiều seed/heldout classes, runtime và cross-dataset evidence; check-only chưa kiểm đủ lineage/nội dung.

## Giá trị mạnh nhất hiện có

Pipeline modular có artifacts truy vết; ablation latent/P_attack thực sự chạy; phân tích error propagation chỉ ra khoảng cách giữa classifier riêng và hệ thống cuối. Đây là nền tảng engineering và phân tích phù hợp để phát triển luận văn. Chưa có independent literature review xác nhận novelty; không gọi việc ghép các thuật toán là đóng góp mới đã chứng minh.

## Năm hành động tiếp theo

1. Xác minh dataset release và thống nhất target/Attempted policy, giữ raw bất biến.
2. Tạo split/provenance mới và scaler đúng từng protocol/heldout.
3. Sửa OOF/calibration, validation contracts và tách isolated/final unknown metrics.
4. Chạy baseline/ablation có kiểm soát, uncertainty; strict multi-heldout nếu giữ claim unknown.
5. Khóa run registry, cập nhật tài liệu, literature matrix và bộ bằng chứng bảo vệ.

## Trao đổi với người hướng dẫn

Chốt ba quyết định: target semantics; phạm vi closed-set hay thêm open-set; bộ đối chứng tối thiểu và quy tắc chọn model trước test. Giữ main/loaco_26 như exploratory; kết quả sửa protocol dùng run-id mới. Không khẳng định zero-day thực tế, real-time, superior hoặc cross-dataset khi chưa có bằng chứng.

**Điều kiện sẵn sàng:** correctness được kiểm chứng, đối chứng khớp câu hỏi nghiên cứu, metrics end-to-end/per-class có uncertainty và provenance tái lập. Nếu giữ open-set, cần known-only preprocessing xuyên suốt và nhiều heldout classes. Không dùng tỷ lệ hoàn thành chủ quan.

Chi tiết: [01 Hiện trạng](<D:/CAO HOC/IDS System/docs/research_audit/01_project_status.md>) · [02 Correctness](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>) · [03 Thí nghiệm](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>) · [04 Đóng góp](<D:/CAO HOC/IDS System/docs/research_audit/04_research_contributions.md>) · [05 Bảo vệ](<D:/CAO HOC/IDS System/docs/research_audit/05_thesis_technical_notes.md>) · [06 Lộ trình](<D:/CAO HOC/IDS System/docs/research_audit/06_improvement_roadmap.md>).
