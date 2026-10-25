# 06 — Lộ trình cải thiện ưu tiên correctness

Audit-only, 24/10/2026. Đây là đề xuất cho lần triển khai được ủy quyền tiếp theo; không có sửa code, nhãn, config hoặc training nào được thực hiện trong audit.
Root: D:\CAO HOC\IDS System. Bằng chứng E01–E18 ở [docs/research_audit/01_project_status.md](<D:/CAO HOC/IDS System/docs/research_audit/01_project_status.md>); chi tiết lỗi ở [docs/research_audit/02_pipeline_correctness.md](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).

## 1. Quy tắc ưu tiên

P0: phải giải quyết trước khi coi evaluation cuối có độ tin cậy khoa học. P1: cần cho bộ bằng chứng luận văn cuối. P2: cải thiện kỹ thuật quan trọng nhưng có thể giới hạn phạm vi. P3: mở rộng nếu thời gian/đóng góp yêu cầu.

Công sức là ước lượng tương đối (nhỏ/vừa/lớn), không phải dự báo ngày công hay GPU time. Những việc cần train ghi rõ là đề xuất, chưa chạy.

## 2. Issue register

| ID | Vấn đề và loại bằng chứng | Evidence | Hệ quả | Hành động đề xuất | P | Công sức |
|---|---|---|---|---|---|---|
| A01 | Provenance/target semantics chưa chốt | E01/E04; schema,Attempted; báo cáo02 §1 | Có thể đánh giá nhầm bài toán; khó so paper | Xác minh archive/version; giữ raw label, chốt target policy riêng | P0 | Vừa |
| A02 | Exact input overlap đã xác nhận | E02/E05;2.253 val/2.213 test | Evaluation không độc lập hoàn toàn | Group theo feature/canonical flow, split mới; audit overlap | P0 | Vừa |
| A03 | Strict LOACO scaler chứa unknown | E02:147,E06:34;66.600 DDoS train | Không đạt unseen-class preprocessing | Scaler known-only riêng từng heldout; rerun toàn upstream | P0 | Vừa/lớn |
| A04 | Outer OOF fold dùng early stopping | E07:86–122 | Meta-feature phụ thuộc own holdout labels | Inner validation hoặc rounds đã chốt không nhìn outer fold | P1 | Vừa/lớn |
| A05 | Self-calibration OOF và representation chung | E07:124,E09 | OOF independence chưa đúng nghĩa strict | Cross-fit calibrator; xác định fold-local representation contract | P1 | Lớn |
| A06 | open_set_metrics không phải final | E11:119,E12:49 | Dễ báo recall/F1 quá cao so hệ thống | Tách score-only và final unknown metrics, gồm benign | P1 | Nhỏ |
| A07 | Check-only thiếu nội dung/lineage validation | E10:64,E11:59,E15 | Trộn run sai vẫn có thể qua check | Row/schema/label hashes; shape/range/finite/class checks; fail-closed | P1 | Vừa |
| A08 | Thiếu single-stage/no-AE/MLP control | EXP03 inventory | Chưa cô lập hiệu ứng kiến trúc/representation | Thiết kế ablation tối thiểu, matched budget | P1 | Lớn |
| A09 | Nhãn hiếm support1–5; finalF1 = 0 | EXP03 §5.1 | Aggregate accuracy che bỏ sót | Per-class P/R/F1/support/CI; policy hiếm minh bạch | P1 | Vừa |
| A10 | Selection lock chưa có chứng cứ | E07/E10 tự sinh test;guide | Không chứng minh test chưa ảnh hưởng lựa chọn | Freeze protocol trước confirmatory test; selection log | P1 | Vừa |
| A11 | Chỉ một heldout DDoS | E13;loaco_26 | Không khái quát unknown classes | Multi-heldout phù hợp support, macro aggregate theo class | P1 nếu giữ claim open-set | Lớn |
| A12 | Một seed, CI IID accuracy | E11:36 | Thiếu uncertainty và dependence control | Multi-seed + paired/cluster CI cho metric chính | P1 | Lớn |
| A13 | Metadata thiếu ancestry/version hashes | E15;models/artifacts | Khó tái lập và phát hiện stale files | Immutable run manifest; configs/env/commit/input hashes | P1 | Vừa |
| A14 | MLP weighted loss aggregation | src/stage2.py:118 | Early stopping phụ thuộc batch partition | Tổng weighted numerator/denominator; regression test | P2 | Nhỏ |
| A15 | Stage 2 XGB checkpoint theo merror | model_config;stage2.py:49 | Không cùng tiêu chí macro-F1 | Chọn metric/selection procedure trước run mới | P2 | Nhỏ |
| A16 | Seed không bảo đảm bitwise; TF32/benchmark bật | E15/runtime,model_config | Variation chưa đo | Log deterministic flags và nhiều seed; không bắt buộc tắt tối ưu nếu báo đúng | P2 | Nhỏ/vừa |
| A17 | Thời gian/VRAM chưa đo | history elapsed0;Timer unused | Không bảo vệ efficiency claim | Benchmark toàn pipeline có warmup/synchronize | P2 | Vừa |
| A18 | Chưa clean-process inference replay | E11 chỉ replay scores | Chưa kiểm tra artifact đủ để triển khai | Load frozen models từ manifest và so golden predictions | P2; P1 nếu claim system deploy | Vừa |
| A19 | Ports/time-related lab shortcuts | E04;feature_names | Domain overfitting có thể xảy ra | Feature-group ablation và group/time stress test | P1/P2 theo claim | Vừa/lớn |
| A20 | Guide/README stale | E16;XGB version/checklist | Tiếp tục workflow sai, dễ quên context | Cập nhật sau protocol, phân biệt planned/verified/deprecated | P1 | Nhỏ |
| A21 | Cross-dataset chưa có | Không artifact thứ hai | Chưa chứng minh domain generalization | Compatibility audit trước transfer evaluation | P3; bắt buộc nếu giữ claim | Lớn |
| A22 | Model/score paths có thể ghi đè | E10:84,E13:98,E15 | Mất lịch sử hoặc lẫn variant | Unique run-id, refuse overwrite, atomic save/checksum | P1 | Vừa |

A01 không phải kết luận đã chắc chắn dùng sai archive; vấn đề đã xác nhận là thiếu justification nguồn/target. A19 là potential risk, chưa đo mức ảnh hưởng. P0 không đồng nghĩa xóa mọi giá trị engineering hoặc mọi metric cũ: giữ chúng là exploratory, không dùng làm xác nhận cuối.

## 3. Phase 1 — Correctness and Verification

Điều kiện vào: không train thêm trên protocol cũ để tối ưu score. Tất cả nhiệm vụ dưới cần quyền triển khai riêng, audit hiện tại chỉ đề xuất.

| Task | Vì sao | File/khu vực ảnh hưởng | Bằng chứng đầu ra | Acceptance criteria | P / tối thiểu |
|---|---|---|---|---|---|
| 1.1 Chốt provenance và target policy | A01 | [configs/base.json](<D:/CAO HOC/IDS System/configs/base.json>),[src/labels.py](<D:/CAO HOC/IDS System/src/labels.py>),[artifacts/metadata](<D:/CAO HOC/IDS System/artifacts/metadata>) | Dataset card,raw/target map có version,nguồn tải/hash | Mọi nhãn có semantics; raw bất biến; target policy được thống nhất; không invent nguồn | P0 / Có |
| 1.2 Split v2 theo group, audit duplicates | A02,A19 | [scripts/01_prepare_data.py](<D:/CAO HOC/IDS System/scripts/01_prepare_data.py>),[src/split_data.py](<D:/CAO HOC/IDS System/src/split_data.py>) | Split IDs/hash,group definitions,overlap report,distribution | Không exact-input group cross-split; group/time stress protocol mô tả rõ; class coverage/ngoại lệ ghi trước | P0 / Có |
| 1.3 Scaler theo protocol/heldout | A03 | [src/preprocessing.py](<D:/CAO HOC/IDS System/src/preprocessing.py>),[scripts/02_train_autoencoder.py](<D:/CAO HOC/IDS System/scripts/02_train_autoencoder.py>),[src/model_data.py](<D:/CAO HOC/IDS System/src/model_data.py>) | Fit-row hash/heldout IDs/scaler state riêng | Không heldout trong scaler fit; không val/test fit; test transform không đổi state | P0 / Có khi làm LOACO |
| 1.4 OOF độc lập và calibration | A04,A05 | [scripts/03_train_stage1.py](<D:/CAO HOC/IDS System/scripts/03_train_stage1.py>),[src/calibration.py](<D:/CAO HOC/IDS System/src/calibration.py>) | Outer/inner fold indices; model-fit/calibration IDs | Mỗi OOF hàng ngoài fit/early-stop/calibration tạo feature của chính nó; representation contract được ghi | P1 / Có khi dùng meta-feature |
| 1.5 Artifact validation fail-closed | A07,A13,A22 | [src/model_data.py](<D:/CAO HOC/IDS System/src/model_data.py>),[src/evaluation.py](<D:/CAO HOC/IDS System/src/evaluation.py>),[scripts/05_train_novelty.py](<D:/CAO HOC/IDS System/scripts/05_train_novelty.py>),[scripts/06_evaluate_pipeline.py](<D:/CAO HOC/IDS System/scripts/06_evaluate_pipeline.py>) | Manifest+negative tests | Sai row/order/schema/run/heldout/class columns/NaN/range bị từ chối; expected omitted LOACO rows xử lý có điều kiện | P1 / Có |
| 1.6 Chuẩn hóa metric và selection | A06,A10,A14,A15 | [src/metrics.py](<D:/CAO HOC/IDS System/src/metrics.py>),[src/stage2.py](<D:/CAO HOC/IDS System/src/stage2.py>),[scripts/06_evaluate_pipeline.py](<D:/CAO HOC/IDS System/scripts/06_evaluate_pipeline.py>) | Score-only/final report; batch-invariance tests; frozen selection log | Hand-calculated fixtures khớp; final unknown gồm benign và gate; primary metric/threshold policy khóa trước test | P1/P2 / Có cho metric |
| 1.7 Kiểm thử nhỏ không full train | Tránh phí GPU khi contract chưa đạt | [tests](<D:/CAO HOC/IDS System/tests>) | Test report,small synthetic integration replay | Positive/negative cases pass; không cần full CICIDS train để bắt lineage/NaN/split bugs | P1 / Có |

Definition of done Phase1: source change được review; test suite mở rộng; một manifest chứng minh fit/validation/test/unknown isolation; label/split protocol đã được chốt. Thay metadata bool bằng ancestry evidence, không sửa flag cho “qua check”.

## 4. Phase 2 — Closed-Set Experimental Completion

Giữ compute hợp lý: chạy tuần tự trên GPU local, smoke tests trước full dataset, không chạy concurrent GPU jobs. Batch/AMP hiện tại là điểm khởi đầu, không lời hứa optimal. Không đặt thêm hyperparameter search quá lớn trước khi biết bottleneck.

| Task | Vì sao | File/khu vực ảnh hưởng | Bằng chứng đầu ra | Acceptance criteria | P / tối thiểu |
|---|---|---|---|---|---|
| 2.1 Rerun controls trên protocol v2 | A08 | scripts03/04;models/results mới | XGB/MLP scaled/latent Stage 1,raw-vs-latent Stage 2 | Cùng split,target,selection budget; run-id mới, không overwrite | P1 / Có |
| 2.2 Single-stage vs cascade | Kiểm tra lý do kiến trúc | Module baseline mới nếu được duyệt;src/evaluation.py | Single-stage multiclass gồm BENIGN và cascade | Cùng data/features/tuning scope; report detect/per-class/final,cost | P1 / Có |
| 2.3 Ablation P_attack hoàn chỉnh | Cô lập meta-feature | scripts03/04,src/stage2.py | latent vs latent+p của XGB và MLP | OOF sạch; cùng classifier; bao gồm no-meta controls; không đổi model vì test | P1 / Có nếu giữ meta-feature claim |
| 2.4 Calibration/gate study validation | Trade-off false alarms | src/calibration.py,config.evaluation | Reliability/Brier/ECE,threshold sweep | Chọn trước FPR budget/primary metric; khóa threshold trước test | P1 / Có |
| 2.5 Minority và uncertainty | A09,A12 | src/metrics.py,results báo cáo mới | Per-class support/P/R/F1,paired CI,multi-seed | Ít nhất3 seed cho cấu hình cuối nếu khả thi; phân biệt train-seed/split-seed; CI đúng đơn vị độc lập | P1 / Có |
| 2.6 Confirmatory test sau khóa | A10 | Workflow/results manifests | Protocol lock timestamp/hash + final report | Chỉ evaluate sau chốt; test cũ gọi exploratory; không lén tune rồi tái gọi independent test | P1 / Có |

Lưu ý về test đã xem: đổi seed, split hoặc run-id trên cùng dữ liệu đã được dùng để ra quyết định không tự tạo test độc lập mới. Nếu không có phần dữ liệu/session thực sự chưa dùng cho lựa chọn, phải công bố tính exploratory/adaptive của benchmark; có thể bổ sung grouped/nested evaluation theo protocol đóng băng, nhưng không gọi đó là dữ liệu hoàn toàn chưa từng thấy. Dữ liệu độc lập mới là bằng chứng mạnh hơn khi khả thi.

Nếu dữ liệu nhỏ/nhãn hiếm không đủ group để vừa closed-set vừa độc lập: báo infeasibility, đổi scope có justification; không nhân bản mẫu giữa split để giữ đủ classes. Có thể tách nhóm nhãn cực hiếm thành phân tích hạn chế, nhưng không xóa chỉ vì F1 thấp.

## 5. Phase 3 — Open-Set / LOACO Validation

| Task | Vì sao | File/khu vực ảnh hưởng | Bằng chứng đầu ra | Acceptance criteria | P / tối thiểu |
|---|---|---|---|---|---|
| 3.1 Strict heldout ancestry | A03 | scripts01–05;scalers/models/manifest | Per-heldout fit IDs và hashes mọi tầng | Lớp heldout không xuất hiện ở bất kỳ fit/early-stop/calibration/threshold step nào | P0 / Có nếu claim unknown |
| 3.2 Multi-heldout suite | A11 | script05,protocol config mới | Per-class + macro across heldout | Chọn eligibility trước test; tối thiểu≥3 lớp đủ support khác family nếu khả thi; full eligible set tốt hơn; rare classes báo riêng | P1 / Có nếu claim unknown |
| 3.3 So sánh3 novelty methods | Score ranking vs operating point | src/novelty.py,scripts05/06 | Isolated và final metrics mọi method | Giữ known-rejection budget; report unknown precision/recall/F1,known accuracy,benign→unknown,gate FN | P1 / Có |
| 3.4 Chọn method không nhìn unknown test | Tránh lựa chọn hậu nghiệm | Protocol/selection manifest | Validation strategy có pseudo-unknown từ train families nếu cần | Không dùng heldout target test để chọn score/threshold/hyperparams; nếu không đủ thì report toàn bộ exploratory | P1 / Có |
| 3.5 Threshold/robustness study | Operating point stability | Evaluation/reporting | Curves/CI trên protocol cho phép | Threshold chosen trên known-validation; sensitivity không được biến thành tối ưu test ngầm | P1 / Có |

Không cần chứng minh “zero-day thực tế” để hoàn thành một nghiên cứu LOACO, nhưng phải gọi đúng “mô phỏng unseen attack class trong benchmark”. Nếu luận văn chỉ chốt closed-set, Phase3 có thể là future work với phạm vi được người hướng dẫn chấp thuận; không giữ claim unknown mà bỏ bằng chứng này.

## 6. Phase 4 — Extended Validation

| Task | Vì sao | File/khu vực ảnh hưởng | Bằng chứng đầu ra | Acceptance criteria | P / tối thiểu |
|---|---|---|---|---|---|
| 4.1 Feasibility audit dataset thứ hai | Tránh transfer không cùng semantics | Loader/schema/labels tương lai;chưa có module hiện tại | Compatibility matrix cho CSE-CIC-IDS2018 hoặc CIC-UNSW-NB15 | Xác minh phiên bản,nguồn,units,flow extractor,label ontology; không chỉ giao tên cột | P3 / Không nếu scope hẹp |
| 4.2 Source→target transfer | Domain generalization | Mã thí nghiệm mới được duyệt | Within-source control + target results | Không fit scaler/tune bằng target test; nêu unknown mapping và missing features | P3 / Có nếu tuyên bố cross-dataset |
| 4.3 Reload và tài nguyên | A17,A18 | Runtime/inference helpers;manifest | Golden replay,latency/throughput/peak memory | Clean process nạp frozen artifacts; predictions khớp tolerance; warmup,synchronize,batch,hardware/version ghi rõ | P2 / Có nếu claim triển khai/efficiency |
| 4.4 Feature/group stress tests | A19 | Feature policy/split/data_loader | Port-free/feature-group ablation,temporal/group test | Cùng selection budget; ghi thay đổi class coverage; không gọi shifted task là closed-set tương đương | P2 / Nên có |

Không tải dataset hoặc cài package trong audit. Cross-dataset có thể tốn nhiều công sức do khác flow extractor/label taxonomy; ưu tiên hoàn tất Phases1–3 trước.

## 7. Phase 5 — Thesis Evidence Consolidation

| Task | Vì sao | File/khu vực ảnh hưởng | Bằng chứng đầu ra | Acceptance criteria | P / tối thiểu |
|---|---|---|---|---|---|
| 5.1 Run registry và bảng tự sinh | Chống chọn số thủ công/hallucination | docs/results/artifacts | Mapping claim→run→metric→source/code commit | Mỗi số truy ra artifact; validation/test/oracle/final phân biệt; không mix protocol versions | P1 / Có |
| 5.2 Literature matrix | Chốt novelty và baseline | [Tài liệu tham khảo](<D:/CAO HOC/IDS System/Tài liệu tham khảo>),docs | Trích dẫn được đọc thực,sources/DOI kiểm chứng | Không gán nội dung từ tên file; đối chiếu split/dataset versions; không gọi tích hợp là mới tự động | P1 / Có |
| 5.3 Cập nhật hướng dẫn/context | A20 | [README.md](<D:/CAO HOC/IDS System/README.md>),[docs/TRAINING_GUIDE.md](<D:/CAO HOC/IDS System/docs/TRAINING_GUIDE.md>) | Lệnh chạy đúng interpreter,acceptance,known caveats | Không còn hứa “no leakage” vô điều kiện; failed/old runs đánh dấu; version khớp | P1 / Có |
| 5.4 Bảng hình và limitations | Dễ bảo vệ | docs,results/tables,results/figures | Confusion matrix,per-class,gate trade-off,LOACO table nếu có | Figure/table cùng frozen run; ghi support,CI,units; không cherry-pick | P1 / Có |
| 5.5 Reproducibility rehearsal | Kiểm tra đủ artifact | scripts/tests/models/manifest | Checklist + clean reload logs | Có thể tái tính metrics; người khác hiểu điều kiện; training reproduction phạm vi/hardware ghi rõ | P1/P2 / Có |

## 8. Bộ tối thiểu trước khi nộp

Bắt buộc cho luận văn closed-set có thể bảo vệ về kỹ thuật:

1. Dataset provenance/target policy và split độc lập được giải trình; không còn known exact-feature overlap ngoài chính sách đã công bố.
2. Model selection/OOF/calibration phù hợp claim; không dùng test để quyết định.
3. Single-stage/no-AE/meta-feature controls tương ứng câu hỏi đã giữ lại, không cần mọi thuật toán có thể nghĩ ra.
4. Final cascade metrics, per-class support và uncertainty; thừa nhận lớp hiếm/negative findings.
5. Frozen run registry, versioned config/environment, source/label/split hashes; tái tính metric độc lập.
6. Literature comparison và phát biểu đóng góp không vượt bằng chứng.

Bổ sung bắt buộc nếu giữ open-set/zero-day simulation trong kết luận chính: strict known-only preprocessing, nhiều heldout classes, final unknown metrics có gate/benign, selection không sử dụng target unknown test.

Cross-dataset và production deployment không bắt buộc cho mọi luận văn Thạc sĩ; chỉ bắt buộc nếu được giữ như claim hoặc yêu cầu đề cương. Không đổi scope ngầm: cần thống nhất với người hướng dẫn.

## 9. Năm việc nên làm tiếp theo

1. Chốt dataset version và label policy, đặc biệt Attempted.
2. Xây split/provenance v2 và scaler đúng từng protocol/heldout.
3. Sửa OOF/calibration, artifact checks và metric final unknown.
4. Chạy bộ baseline/ablation có kiểm soát, nhiều seed; strict multi-heldout nếu giữ mục tiêu unknown.
5. Khóa evidence registry, cập nhật tài liệu và literature matrix, chuẩn bị bộ bảng/hình bảo vệ.

Không tiếp tục tối ưu score trên main/loaco_26 hiện có. Giữ nguyên kết quả làm lịch sử exploratory và so sánh sự khác biệt khi protocol được sửa.
