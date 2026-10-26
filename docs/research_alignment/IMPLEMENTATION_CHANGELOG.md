# Nhật ký thay đổi triển khai

## CHANGE-001 — Chốt nguồn và ma trận trước khi sửa code

- Thời gian tham chiếu: 2026-10-26T05:23:01+07:00, đọc từ đồng hồ hệ thống trước khi tạo hồ sơ.
- Finding: audit A01–A22; review H05–H07; thesis §3.2–3.7.
- Evidence: PDF hash khớp input_audit; source hiện tại vẫn có OOF earlystop/self-calibration và global LOACO scaler; baseline 16 tests PASS.
- Files: `docs/research_alignment/01_alignment_matrix.md`, file nhật ký này.
- Trước: chưa có ma trận ưu tiên giữa luận văn/review/audit và quyền thay đổi.
- Thay đổi: ghi nguồn, phân loại sai lệch, sửa được phép và quyết định cần người nghiên cứu.
- Lý do khoa học: không hợp thức hóa protocol lịch sử hoặc suy diễn phê duyệt từ tài liệu review.
- Kiểm chứng đã chạy: `.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v` → 16 tests, OK, 0,220 s; `Get-FileHash` PDF → khớp SHA256 trong ma trận.
- So sánh: chưa thay đổi source, model hoặc metrics.
- Rủi ro còn lại: target/split/gate policy chưa có phê duyệt mới; mọi corrective training còn chưa chạy.

Các thay đổi tiếp theo sẽ được ghi khi đã thực hiện; không ghi đề xuất thành kết quả.

## CHANGE-002 — Contracts fail-closed và bảo vệ artifact

- Thời điểm ghi nhận/kiểm chứng: 2026-10-26T05:32:02.1943170+07:00; bổ sung kiểm tra ancestry lúc 2026-10-26T05:37:35.8640467+07:00. Đây là mốc đồng hồ đã đọc, không phải timestamp giả cho từng dòng code.
- Finding/evidence: A07,A13,A22; audit02 §4.2; probe NaN trước sửa trả BENIGN.
- Files: `src/contracts.py`, `src/artifact_contracts.py`, `src/model_data.py`, `src/model_config.py`, `src/data_loader.py`, `src/preprocessing.py`, `scripts/00_audit_dataset.py`, `scripts/01_prepare_data.py`.
- Trước: kiểm chủ yếu length; cho phép NaN/range/schema lỗi; thiếu ancestry; paths có thể overwrite; ID BENIGN phụ thuộc file order.
- Đã sửa: validators shape/finite/range/class-set/order; kiểm binary ↔ label/split; schema không có tên trùng; BENIGN=0 khi preparation mới; ngăn annotation/IP/time trở lại predictors; run-id không sanitize âm thầm; từ chối output đã tồn tại. Manifest lưu SHA256 dataset raw-array/rows/split/labels/schema và input/output/model/source, bản chụp config cùng phiên bản packages; kiểm đệ quy các parent sidecars. Config/package versions được lưu dạng giá trị, không phải checksum từng package.
- Lý do khoa học: một file cùng kích thước không chứng minh đúng experiment; lỗi đầu vào không được biến thành benign.
- Kiểm chứng: baseline suite sau nhóm sửa: 16/16 PASS (0,102 s); AST 37 source/script PASS; replay main check-only PASS; bộ mở rộng sau đó kiểm tamper/heldout/schema/order và overwrite.
- Tác động so sánh: không thay prediction hợp lệ; key metric mở rộng không xóa key cũ. Legacy không có manifest phải dùng cờ replay tường minh, không được đưa vào training mới.
- Rủi ro: hash local không chứng minh upstream provenance, session independence hoặc ý nghĩa nhãn. Manifest dùng absolute paths, di chuyển máy cần migration có kiểm chứng; không sửa JSON tùy tiện cho qua check. Chạy duy nhất một job, chưa có distributed locking.

## CHANGE-003 — Metric cuối, weighted loss, seed và runtime history

- Thời điểm ghi nhận/kiểm chứng: 2026-10-26T05:32:02.1943170+07:00; regression mở rộng kiểm lại sau đó.
- Finding/evidence: A06,A09,A14,A16,A17; review M05–M06; source weighted CE mean nhân batch count và elapsed_seconds=0.
- Files: `src/metrics.py`, `src/evaluation.py`, `src/stage2.py`, `src/training_utils.py`, `src/autoencoder.py`, `src/novelty.py`, `scripts/06_evaluate_pipeline.py`.
- Đã sửa: FPR/FNR/Brier/AP alias, undefined AUROC, full per-class và confusion matrix; score-only/final unknown tách riêng, kể cả benign→unknown và unknown bị gate chặn; error decomposition; check-only chạy composition thật trong RAM. Weighted CE tổng theo target weights, giữ gradient batch loss như cũ. AE shuffle nhận seed cấu hình; history đo wall time đến epoch; early-stop/novelty threshold từ chối nonfinite.
- Lý do khoa học: đúng population và mẫu số; checkpoint MLP không lệ thuộc cách gộp batch do lỗi aggregation; không nhầm score replay với model latency.
- Kiểm chứng: hand-calculated metric fixture; weighted CE CPU forward ở batch 1/2/3/5 khớp loss toàn bộ tới 6 chữ số; AE forward shape84→16→84. Các tests này thuộc suite PASS 35 sau tích hợp.
- Tác động: Stage 2 MLP cần rerun vì checkpoint/scheduler có thể đổi; AE seed correction có thể đổi trajectory. Không suy ra metric tăng/giảm. Các metric lịch sử được giữ nguyên trên đĩa.
- Rủi ro: timing chưa gồm full inference/encode pipeline; bootstrap cũ vẫn IID accuracy, chưa CI macro-F1/cluster/multi-seed; gate 0,5 vẫn cố định theo thesis.

## CHANGE-004 — Preprocessing known-only và nested OOF revised_v1

- Thời điểm ghi nhận/kiểm chứng: 2026-10-26T05:37:35.8640467+07:00.
- Finding/evidence: H05–H06; A03–A05; thesis §3.2.1/§3.5.1 thừa nhận lỗi lịch sử.
- Files: `src/research_protocol.py`, `src/stage1_protocol.py`, `src/calibration.py`, `scripts/01b_prepare_protocol.py`, `scripts/02_train_autoencoder.py`, `scripts/03_train_stage1.py`.
- Trước: scaler toàn train có unknown LOACO; outer holdout chọn epoch; calibrator fit/apply cùng OOF; encoder/scaler chung trong OOF.
- Đã sửa: preprocessing riêng từng run, fit indices known-only; outer 5-fold và inner 80/10/10 (fit/stop/calibration); scaler/AE fold-local; chỉ scalar p ghép lại. Calibrator từng fold không dùng outer-holdout. Final calibrator fit raw OOF train và chỉ áp lên final val/test; final classifier vẫn dùng train và external validation early stopping. Lưu fit/stop/calibration/holdout indices, scaler/encoder/classifier/calibrator mỗi fold. Cache scaled/latent tạm được đóng memmap rồi dọn; artifacts học được được giữ.
- Lý do khoa học: loại phụ thuộc own-label qua checkpoint/calibration và exposure X ở preprocessing sinh OOF p. Không ghép tọa độ latent khác encoder vào Stage 2.
- Kiểm chứng: `scripts/01b_prepare_protocol.py --run-id aligned_check_only_20261026 --held-out-label-id 26 --check-only` → fit scope 1.401.162, không ghi scaler; synthetic scaler mean chỉ known train; nested orchestration 5 folds + final bằng classifier mock PASS. Test integration tiếp theo đi qua cả nhánh latent và các scripts02–06.
- Tác động: BREAKING cho training CLI: cần `--protocol revised_v1` và preprocessing/lineage mới. Các run main/loaco_26 cũ không được tái dùng cho corrective training. Inner fit nhỏ hơn legacy; thêm 5 AE cho Stage 1 latent, tăng compute; chưa đo GPU time.
- Rủi ro: full GPU training chưa chạy; distribution fold/final score có thể khác nên calibration không được mặc định tốt. Stage 2 z chung vẫn fit train (được phép cho Stage 2), không phải latent OOF. Giữ split cũ nên overlap/generalization chưa được giải quyết.

## CHANGE-005 — Stage 2/novelty lineage và adapter external

- Thời điểm ghi nhận/kiểm chứng: 2026-10-26T05:37:35.8640467+07:00.
- Finding/evidence: A07,A08,A21,A22; review M09; external CSV đã xuất hiện sau audit 24/10.
- Files: `scripts/04_train_stage2.py`, `scripts/05_train_novelty.py`, `scripts/06_evaluate_pipeline.py`, `src/external_data.py`, `scripts/07_inspect_external.py`, `scripts/check_cse_cic_2018.py`, `scripts/inspect_cic_unsw.py`, `configs/external_shared_features.template.json`.
- Đã sửa: require upstream hashes/heldout/run; Stage 2 thêm control `latent_only_mlp` tùy chọn, không đổi ba experiment lịch sử trong config; novelty path chứa variant Stage 2; precision score detector không ép float32 trước lưu; threshold và scores ràng buộc ancestry. Hai adapter native schema giữ raw labels/row offsets, đồng bộ drop invalid X/y, đọc đúng header Label của Lable.csv; common-feature mapping mặc định chưa approved và fail-closed.
- Kiểm chứng thực tế: 12 entrypoints `--help` PASS; external CSE đọc prefix1.000 mỗi9 CSV:9.000 rows,71 invalid,8.929 valid,78native predictors,30 tên trùng primary; **không phải phân phối toàn dataset**. UNSW full scan447.915 rows,0 invalid,76 features,76 tên trùng; benign358.332/attack89.583; X/y cùng số hàng. Không tự dùng/đổi tên file CSE đuôi `.csv.757702C0`.
- Tác động: chưa có model hoặc metric external; không thể ghép trực tiếp 78/76 features vào encoder 84. Novelty output mới thêm thư mục variant, guide lịch sử không dùng được cho protocol mới.
- Rủi ro: exact-name overlap không xác minh units/extractor; ontology đa lớp khác; chưa xác minh nguồn tải/completeness CSE. Native adapter chưa phải full external training hoặc zero-shot inference.

## CHANGE-006 — Regression và integration tests, lỗi tìm được khi kiểm chứng

- Thời điểm nhóm kiểm thử khởi động đối chiếu: 2026-10-26T05:37:35.8640467+07:00; kết quả dưới đây lấy từ lệnh đã chạy sau mốc này.
- Files: `tests/test_research_alignment.py`; bổ sung lifecycle/console ở `src/model_data.py`, `src/stage1_protocol.py`, reader close ở `src/external_data.py`.
- Đã thêm: 19 test cases ngoài16 test cũ; negative input/ancestry, known-only scaler, inner scopes, real-script integration02→03→04→05→06 với model mock; actual scaler/calibrator/metrics/contracts trên fixture; CPU forward weighted CE và AE, không train XGBoost/MLP/AE thật.
- Lệnh: `.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v`.
- Kết quả: **35/35 PASS, 6,546 s** ở lần có integration. Lần đầu sandbox chặn atomic replace (`WinError5`); chạy lại ngoài sandbox phát hiện console cp1252, rồi mock-held memmap khóa file Windows. Đã bổ sung UTF-8, explicit memmap close và reset mock; reader mismatch được đóng rõ ràng. Không che các lần test lỗi thành PASS.
- Environment: `scripts/verify_environment.py --skip-cuda-smoke` PASS; Python3.10.7, torch2.13.0+cu130/runtime13.0, XGBoost3.2.0 CUDA-enabled, RTX3050Laptop4096MiB. Đây là máy hiện tại, không gán ngược cho môi trường training lịch sử. Không benchmark GPU.
- Tác động: tests không sinh benchmark result hoặc sửa datasets/models/results cũ; fixture trong TemporaryDirectory được dọn khi test thành công.
- Rủi ro: mocks kiểm orchestration, không xác nhận khả năng hội tụ/VRAM/performance của full training. Cảnh báo sklearn khi fixture có predicted class không có trong truth là dự kiến, không bị giấu.

## CHANGE-007 — Hoàn thiện kiểm tra schema và chống ghi đè run dở dang

- Thời điểm kiểm chứng cuối: 2026-10-26T06:00:34.8803342+07:00, lấy trực tiếp từ đồng hồ sau lệnh regression.
- Finding/evidence: A07, A13, A22; pandas có thể đổi tên header trùng trước khi kiểm schema; file chính có thể mất trong khi sidecar hoặc history còn tồn tại.
- Files: `src/data_loader.py`, `src/preprocessing.py`, `src/autoencoder.py`, `src/contracts.py`, `scripts/01_prepare_data.py`, `scripts/02_train_autoencoder.py`, `tests/test_research_alignment.py`.
- Trước: chưa chặn header CSV gốc trùng trước pandas; thiếu kiểm chiều ở partial_fit và finite latent trước hoàn tất; guard chưa bao phủ sidecar đơn lẻ, tất cả output preparation và history AE đơn lẻ.
- Đã sửa: đọc/kiểm header gốc; kiểm chiều scaler và giá trị latent; guard mọi output preparation, thư mục results AE và sidecar còn sót. Không xóa hoặc tự resume run dở dang.
- Lý do khoa học: schema không được bị sửa ngầm; output lỗi phải dừng; không thay dữ liệu hoặc bằng chứng lịch sử khi đường dẫn chỉ còn một phần artifacts.
- Kiểm chứng: thêm regression header trùng và orphan sidecar. Mốc sau kiểm header: **36/36 PASS, 6,916 s**. Sau guard sidecar: lệnh `python -X utf8 -B -m unittest discover -s tests -v` đạt **37/37 PASS, 6,820 s**. Sau guard history AE, lệnh `.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -q` đạt **37/37 PASS, 6,906 s**. Tổng cộng 21 test cases mới so với baseline 16.
- So sánh: valid input không đổi target/split hoặc kiến trúc; input lỗi/đường dẫn cũ nay bị từ chối sớm. Chưa phát sinh kết quả training thật mới.
- Rủi ro: đây là guard tại entrypoint, không phải distributed lock; không chạy hai job cùng run-id. Chưa kiểm toàn chuỗi trên GPU với dữ liệu đầy đủ.

## CHANGE-008 — Hồ sơ tái lập, replay lịch sử và kiểm tra bảo toàn

- Mốc kiểm tra tài liệu/inventory: 2026-10-26T05:59:45.9667836+07:00; chốt bổ sung theo mốc regression 06:00:34 ở CHANGE-007. Đây là mốc quan sát, không gán giờ giả cho từng thao tác soạn thảo.
- Finding/evidence: A06, A08, A10–A13, A17–A22 và review H05–H07/M05–M06/M09; thiếu phân biệt lịch sử, code mới và bằng chứng chưa chạy.
- Files: sáu file `docs/research_alignment/01_alignment_matrix.md`, `02_methodology_alignment_summary.md`, `03_experiment_validity_report.md`, `04_research_technical_notes.md`, `IMPLEMENTATION_CHANGELOG.md`, `PIPELINE_REPRODUCTION_GUIDE.md`; thêm banner hướng dẫn tại `README.md` và `docs/TRAINING_GUIDE.md`.
- Đã thực hiện: lập ma trận trước source edits; tách quyết định cần duyệt; hướng dẫn PowerShell theo thứ tự phụ thuộc, input/output/acceptance và lỗi thường gặp; giữ hướng dẫn cũ như lịch sử. Cập nhật số tests theo bằng chứng; phân biệt checksum source/input với config snapshot và package versions, không gọi đó là cơ chế khóa toàn bộ source/config.
- Lý do khoa học: không dùng sửa code để hợp thức hóa kết quả cũ; không biến lệnh hướng dẫn thành nhật ký đã chạy; không gọi replay scores là model inference benchmark.
- Kiểm chứng tài liệu: Python `ast.parse` trên 45 file source/scripts/tests PASS; PowerShell Parser trên 17 block lệnh trong guide PASS; sáu liên kết Markdown nội bộ của sáu deliverables tồn tại; `git diff --check` PASS. 12 CLI entrypoints `--help` đã PASS trong lượt này. Cài đặt máy sạch và full training chưa chạy.
- Replay read-only: dùng Python gọi `compose_pipeline_predictions`, `multiclass_metrics` và `pipeline_diagnostics` trên arrays/probabilities lịch sử, so với `test_predictions.csv.gz` và `metrics.json`. Bốn run `eval_main_latent_only`, `eval_main_pattack_xgb`, `eval_main_pattack_mlp`, `loaco_26` khớp từng prediction và bốn aggregate metric cũ trong tolerance 1e-12. Không load checkpoint để chạy forward, không tính lại bootstrap, không ghi report vào results. Các phép tính phát sinh được ghi trong báo cáo validity, có nhãn artifact lịch sử.
- Kiểm chứng bảo toàn: `Get-ChildItem -File -Recurse` cho `CICIDS2017`, `data/processed`, `data/external`, `models`, `results`, `artifacts`; so chuỗi sorted `FullName|Length|LastWriteTimeUtc.Ticks` trước/sau. Cả hai có **172 file**, cùng inventory SHA256 `e167e2021a0cd1443a594d74f6e7e398d4db9b8a76d49dab899a0203d8eac0c6`. Đây là checksum danh mục/path/size/mtime, **không phải hash lại toàn bộ nội dung 172 file**. Không chạy lệnh ghi vào các artifacts đó.
- Phạm vi thay đổi: 22 file tracked được sửa và 15 file mới (gồm sáu báo cáo); thư mục review 25/10 vốn đã untracked được giữ nguyên. Không sửa tám báo cáo audit, bản PDF, requirements hoặc config kiến trúc chính; không tạo commit.
- Tác động: CLI training revised_v1 không dùng lệnh legacy không có protocol; cần run ID và artifacts mới. Giữ gate 0,5 theo thesis, chưa có threshold sweep/selection registry. Dataset/target/split và external ontology vẫn cần quyết định của nhà nghiên cứu.
- Rủi ro còn lại: metadata integrity không giải quyết feature-vector overlap, provenance/Attempted, test đã xem, rare support, một seed/heldout, thiếu đối chứng, reliability/CI và model-reload latency. Các mục NOT REPRODUCIBLE được chỉ rõ ở guide. Chỉ kết luận đã cải thiện correctness và khả năng kiểm tra; chưa kết luận tăng metric hoặc đạt độ tin cậy khoa học cuối cùng.
