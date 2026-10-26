# Độ tin cậy thực nghiệm sau căn chỉnh

Ngày 26/10/2026. Phân biệt **logic đã kiểm chứng**, **artifact lịch sử đã replay**, và **thực nghiệm sửa protocol chưa chạy**.

## 1. Data và split

[VERIFIED FROM AUDIT] Audit ngày 24/10 ghi 2.096.804 hàng × 84 features sau cleaning; train/validation/test tương ứng 1.467.762/314.521/314.521; 27 nhãn gồm BENIGN. Audit đã xác nhận 2.253 validation và 2.213 test vectors trùng 84 features với train. Lượt này không tính lại overlap hoặc SHA256 toàn raw CSV; không đổi các mảng này.

[VERIFIED FROM IMPLEMENTATION] Preparation mới giữ nguyên policy nhưng dành ID 0 cho BENIGN, từ chối schema trùng, nhãn rỗng hoặc numeric invalid, và ngăn annotation/IP/time làm feature. `01b` dùng fixed split hiện có; scaler LOACO loại heldout trước fit. Check-only giữ ID 26 xác nhận 1.401.162 fit rows, bằng 1.467.762−66.600; chưa fit scaler trên toàn dữ liệu thật trong lượt này.

[TECHNICAL INTERPRETATION] Xử lý leakage ở scaler/OOF không làm split độc lập. Hash toàn 89 cột khác hash 84 predictors; trùng vector không tự chứng minh trùng session, cũng chưa định lượng mức metric inflation. Nếu đổi grouping/target, phải đặt protocol mới và không diễn giải như benchmark tương đương. Test đã xem không trở lại “unseen” chỉ bằng seed/run-id khác.

## 2. Phạm vi dữ liệu của từng thao tác ở revised_v1

| Thao tác | Fit | Chọn checkpoint/threshold | Chỉ transform/predict |
|---|---|---|---|
| Scaler common | Phase 2 train, bỏ heldout LOACO | Không | Toàn bộ hàng kể cả test/unknown |
| AE common | Cùng known train | Known external validation reconstruction | Toàn bộ hàng theo row order |
| Outer-fold scaler/AE | Inner-fit thuộc outer-training | AE: inner-stop | Inner-calibration và outer-holdout; có encode toàn bộ nhưng không fit |
| Outer-fold Stage 1 | Inner-fit | Inner-stop | Inner-calibration và outer-holdout |
| Fold calibrator | Score+label inner-calibration | Không tuning test | Outer-holdout |
| Final Stage 1 | Toàn known train | Known external validation | Validation/test |
| Final calibrator | Raw OOF train và label | Không | Final validation/test; không tái áp vào OOF |
| Stage 2 | Known attacks train, z hoặc [z,p OOF] | Known attacks validation | Mọi test flow; gate áp khi compose |
| Novelty OCSVM/IF | Known attacks train có sample cap | Quantile 95 của known-attack validation | Mọi test flow |
| MCP novelty | Không model fit riêng | Quantile 95 của known-attack validation | Mọi test flow |

[REQUIRES FURTHER VERIFICATION] Bảng phản ánh source và tests, không khẳng định full model mới đã chạy. Shared AE đã xem X train là hợp lệ cho Stage 2 common representation; không được gọi chính z này là fold-local OOF. Final calibration sử dụng score distribution của fold models, nên Brier/reliability trên validation vẫn cần kiểm tra.

## 3. Contract và lineage

[VERIFIED FROM IMPLEMENTATION] Manifest kiểm hash raw feature array, row_hashes, labels/binary/splits, feature_names/label_mapping/split_config; outputs/parents/parent sidecars và run/heldout/kind/status. Manifest lưu thêm bản chụp config, phiên bản packages và checksum source lúc tạo artifact; không tự đối chiếu toàn bộ config/source hiện tại với snapshot của mọi tầng. Script 04 kiểm latent và p nguồn; 05 kiểm known-validation/test indices; 06 kiểm all-test order, class set và probability ranges, rồi compose ngay cả check-only. p ở heldout train/validation có NaN theo thiết kế; chỉ reject NaN tại indices được phép tiêu thụ.

[TECHNICAL INTERPRETATION] Manifest là bằng chứng integrity/ancestry của local run, không chứng nhận nguồn upstream hoặc tính độc lập thống kê. Chưa có signature, distributed lock hoặc migration giữa absolute paths. Không tự ghi manifest cho old models rồi gọi đó là training evidence. Run dở dang để lại status `running`, không được coi là completed và không resume ngầm.

## 4. Evaluation và kiểm tra số học

[VERIFIED FROM EXPERIMENTAL ARTIFACTS] Replay read-only 4 pipeline cũ bằng composition mới: predictions khớp từng hàng và cả 4 aggregate keys cũ khớp trong tolerance 1e−12. Không chạy model forward thật từ checkpoints lịch sử, không tính lại bootstrap và không ghi metrics mới vào results.

| Legacy pipeline | Benign qua gate | Attack bị chặn | Attack qua gate nhưng final sai | Tổng lỗi |
|---|---:|---:|---:|---:|
| eval_main_latent_only |41|61|1377|1479|
| eval_main_pattack_xgb |41|61|1381|1483|
| eval_main_pattack_mlp |41|61|4629|4731|
| loaco_26 |77|463|13824|14364|

Pipeline `eval_main_pattack_mlp` vẫn dùng **gate XGB latent**. Không lấy FP của standalone Stage 1 MLP latent để gán vào pipeline này.

[VERIFIED FROM EXPERIMENTAL ARTIFACTS] LOACO 26 MCP final replay: phát hiện unknown 3.528/14.272; recall 0,2471973094, precision 0,5322069694, F1 0,3375915028; 372 unknown bị gate chặn, 14 benign thành unknown. Đây là tính lại từ **artifact cũ**, không phải kết quả strict LOACO mới. Score-only recall 0,260650 trong audit có population khác.

[VERIFIED FROM IMPLEMENTATION] Báo cáo mới giữ accuracy/balanced accuracy/macro-F1/weighted-F1, thêm per-class P/R/F1/support và confusion matrices. Binary có FPR/FNR/Brier; key `pr_auc` là alias AP, không phải trapezoidal PR-AUC. Unknown final tính mọi traffic; score-only chỉ true attacks. `composition_seconds_only_NOT_model_inference` không phải latency model hay throughput IDS.

## 5. External compatibility được kiểm tra local

| Bộ dữ liệu | Phạm vi đã đọc trong lượt này | Kết quả adapter | Hạn chế |
|---|---|---|---|
| CSE-CIC-IDS2018 | Header cả 9 CSV và prefix 1.000 dòng/file | 9.000 input, 71 invalid, 8.929 valid; 78 native features, 30 tên trùng primary | Không suy ra full distribution; file đuôi `.csv.757702C0`, 4.054.925.350 bytes, chưa xác nhận completeness, không dùng |
| CIC-UNSW-NB15 | Full Data.csv + Lable.csv | 447.915 input, 0 invalid; 76 features; 358.332 benign/89.583 attack | Row count/order positional khớp nhưng chưa xác minh provenance/extractor |

[VERIFIED FROM LOCAL DATA] UNSW Readme mapping: 0 Benign, 1 Analysis, 2 Backdoor, 3 DoS, 4 Exploits, 5 Fuzzers, 6 Generic, 7 Reconnaissance, 8 Shellcode, 9 Worms. Counts lần lượt: 358332, 385, 452, 4467, 30951, 29613, 4632, 16735, 2102, 246. Không ánh xạ các ID này sang CICIDS2017 bằng giá trị số.

[VERIFIED FROM LOCAL DATA] UNSW thiếu 8 tên predictor primary: Src Port, Dst Port, Protocol, Fwd RST Flags, Bwd RST Flags, ICMP Code, ICMP Type, Total TCP Flow Time. CSE còn có nhiều tên viết tắt; không suy ra thiếu feature về ngữ nghĩa chỉ từ thiếu tên exact. Các cột Fwd RST/ports/flow timing vẫn giữ theo thesis; chưa có ablation chứng minh shortcut.

[REQUIRES FURTHER VERIFICATION] Cross-dataset và intra-dataset training đều chưa chạy. `approved_shared_features` từ chối mapping chưa phê duyệt, thiếu cột hoặc map nhiều canonical cùng nguồn. Không zero-fill cho đủ 84 chiều; không retrain target rồi gọi zero-shot transfer.

## 6. Thí nghiệm bắt buộc chạy lại/hoàn tất

1. Main Stage 1 bốn model/representation nếu dùng kết quả corrective OOF/calibration; AE common mới nếu cần đầy đủ lineage/seed. Stage 2 meta-feature phải refit trên p mới; MLP cần rerun do loss aggregation sửa.
2. Toàn bộ chain LOACO mỗi heldout: scaler→AE→Stage 1/calibration→Stage 2→novelty→final. Không chỉ chạy lại script 06 trên model cũ để gọi strict.
3. Latent-only vs+p với cùng classifier và budget; thêm MLP latent-only nếu giữ kết luận về MLP meta-feature. NoAE/flat baseline và port/flow ablation sau chốt protocol.
4. Multi-seed, eligible multi-heldout và uncertainty theo đơn vị độc lập; không dựa một split hoặc IID accuracy bootstrap để nói significance.
5. Reliability/calibration và gate trade-off trên validation; cross-dataset/schema/ontology và raw-to-model reload/latency nếu giữ các claim đó.

[TECHNICAL INTERPRETATION] Code hiện tốt hơn về correctness nhưng bộ số liệu lịch sử vẫn exploratory. Không có bằng chứng định lượng về hướng/mức thay đổi metric sau các sửa đổi.
