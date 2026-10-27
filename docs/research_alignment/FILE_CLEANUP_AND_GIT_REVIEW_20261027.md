# Kiểm kê dọn thư mục và lọc file cho GitHub — chỉ đề xuất, chưa xóa

Ngày: 27/10/2026. Phạm vi duy nhất: `D:\CAO HOC\IDS System`.

**Không xóa/move/archive file, không sửa code/config/.gitignore, không stage/commit/push, không gc/prune hoặc thay Git refs trong lượt này.** Chỉ bổ sung báo cáo này và danh sách đề xuất commit. Các deletion đã thấy trong Git là trạng thái có sẵn từ lần dọn trước.

## 1. Phạm vi và cách đánh giá

- Quét metadata, tên/đường dẫn, kích thước và Git status của **38.994 tệp trước khi bổ sung hai tệp báo cáo**, kể cả `.venv` và `.git`; không có lỗi truy cập hoặc reparse point bị bỏ qua. Không đọc toàn bộ nội dung mỗi CSV/PDF; mức độ liên quan được xác định thêm từ code, config, tài liệu và artifact contracts.
- Tổng kích thước logic: **30,377 GiB**. Đếm mỗi hard-link file identity một lần: **24,385 GiB**. Đây là tổng file bytes, **không phải** số NTFS allocated blocks hoặc cam kết dung lượng thu hồi khi xóa một nhóm.
- Có **4 nhóm hard-link**, giảm số byte vật lý trùng theo file identity khoảng **5,992 GiB** so với cộng kích thước theo mọi pathname.
- Đọc **269 artifact contracts**: chưa thấy thiếu parent path theo kiểm tra tồn tại. Đồ thị ancestry của R3 bảo vệ **994 đường dẫn**; ngoài ra còn phải giữ các input/config/schema/split chung. Đây là kiểm dependency/path, không phải rehash toàn bộ 269 contracts trong lượt dọn này.
- Git branch: `codex/model-training-pipeline`, HEAD `5281c76680408b6131b45abb92a9370e4bf9f187`; so với remote-tracking ref đã có tại máy: ahead/behind **0/0**, không fetch để xác nhận trạng thái server mới nhất. Index chưa stage tệp nào.

### Dung lượng chính

| Nhóm | Số tệp | Dung lượng logic | Xử lý đề xuất |
|---|---:|---:|---|
| `data/` | 258 | 18,746 GiB | Dữ liệu/representation, giữ cục bộ, không commit; không xóa hàng loạt |
| `.venv/` | 34.822 | 3,265 GiB | Môi trường CUDA đang dùng, không commit; không xóa cả môi trường chỉ để dọn Git |
| `.git/` | 781 | 2,831 GiB | Có tmp và lịch sử dataset cũ; cần xử lý Git riêng, không xóa thủ công object store |
| `models/` | 1.181 | 2,722 GiB | Weights/fold models/novelty index; giữ bằng chứng, không commit |
| `results/` | 1.528 | 2,013 GiB | Kết quả/log/prediction, giữ cục bộ hoặc archive có kiểm chứng, không commit mới |
| `CICIDS2017/` | 5 | 0,755 GiB | Dữ liệu gốc, giữ nguyên, không commit |
| `Tài liệu tham khảo/` | 15 | 40,24 MiB | Liên quan luận văn; giữ PDF cục bộ, ưu tiên `.bib` cho Git |
| `docs/` | 48 | 1,79 MiB | Phần lớn trực tiếp phục vụ luận văn; không đáng xóa để tiết kiệm dung lượng |

`data/processed/` riêng có 15,922 GiB logic nhưng khoảng 9,930 GiB sau khử trùng hard-link; không coi chênh lệch này là dữ liệu có thể tiếp tục thu hồi.

## 2. Nhóm có thể dọn sau khi được xác nhận

### A. Cache/tệp thử nghiệm, không phải kết quả nghiên cứu chính

| Đường dẫn/nhóm chính xác | Dung lượng | Đánh giá và điều kiện |
|---|---:|---|
| `.pytest_cache/` | 1.311 byte | Cache kiểm thử; có thể sinh lại |
| `src/__pycache__/`, `scripts/__pycache__/`, `tests/__pycache__/` | Cùng `.pytest_cache`: 80 tệp, khoảng 0,34 MiB | Không cần commit hoặc lưu làm bằng chứng model |
| `.venv/**/__pycache__/` | Phần lớn cache còn lại | Có thể sinh lại khi import; không xóa thư viện/DLL/metadata package. Chỉ dọn khi không có Python dùng môi trường |
| Tổng cache Python/pytest toàn project | **10.699 tệp; 139,05 MiB** | Tiết kiệm nhỏ hơn nhiều so với model/data; không phải lý do xóa `.venv` |
| `data/interim/smoke/` | **18 tệp; 3,32 MiB** | Bộ 5.000 mẫu smoke, sinh lại bằng lệnh ghi trong `docs/PHASE_2_REPORT.md`; không là benchmark luận văn chính |
| `models/stage1/cicunsw_zero_day_v2_loaco_3/xgboost_latent/fold_2/feature_cache_oumwf5w5/latent.npy` | 19.595.200 byte | Cache còn sót của run lỗi, không phải latent hoàn tất được công nhận |
| Cùng thư mục: `scaled.npy` | 93.076.720 byte | Hai cache tổng **107,45 MiB**; không thấy được tham chiếu trong parent contracts/JSON đã rà, không có job train đang dùng tại thời điểm kiểm tra |
| Thư mục rỗng `CSE-CIC-IDS2018/` tại root | 0 byte | Không phải thư mục chứa 9 CSV thực tế; có thể bỏ placeholder nếu không còn dùng |
| Thư mục rỗng `data/processed/experiments/` | 0 byte | Placeholder layout legacy; không giải phóng đáng kể |

Không gom các thư mục rỗng `.git/*` hoặc `.venv/Include` vào danh sách xóa: đây là cấu trúc do Git/Python quản lý.

Không thấy tệp checkpoint `.tmp`, download `.part/.crdownload` còn sót trong phần project nghiên cứu ở lần quét này. Cache Hugging Face ở `data/external/CIC-UNSW-NB15/.cache/` chỉ có metadata nhỏ; nên giữ thông tin tải/provenance thay vì dọn để tiết kiệm vài trăm byte.

### B. Tệp tạm của Git — có thể xử lý nhưng không được xóa nhầm object thật

`git count-objects -v` nhận diện **14 garbage files**, tổng file bytes **925.623.437 byte ≈ 882,74 MiB**. Danh sách:

```text
.git/objects/23/tmp_obj_UNsQet
.git/objects/67/tmp_obj_1eTrLB
.git/objects/67/tmp_obj_27t5wn
.git/objects/67/tmp_obj_9gWL5Q
.git/objects/67/tmp_obj_cWSGdN
.git/objects/67/tmp_obj_fv2y94
.git/objects/67/tmp_obj_HH9zvS
.git/objects/67/tmp_obj_INIz9u
.git/objects/67/tmp_obj_jWZs90
.git/objects/67/tmp_obj_kaewKr
.git/objects/67/tmp_obj_oVzc49
.git/objects/67/tmp_obj_pnlAvu
.git/objects/67/tmp_obj_qSRIg3
.git/objects/67/tmp_obj_rfiwW9
```

`git fsck --full --no-reflogs --unreachable` kết thúc exit 0, liệt kê **279 unreachable blobs + 108 unreachable trees**. “Unreachable với `--no-reflogs`” không đồng nghĩa được phép xóa ngay: một số dữ liệu còn phục hồi qua reflog. Chưa gc/prune, chưa expire reflog, chưa xóa tmp hay object.

Đây là ứng viên dọn dung lượng rõ hơn việc xóa vài tài liệu Markdown. Chỉ xử lý sau khi xác nhận không còn Git process, có backup repository và được phê duyệt. **Không dùng xóa recursive `.git/objects` hay xóa toàn `.git`.**

## 3. Model/run cũ: có thể archive, không gọi là “không liên quan luận văn”

Hai baseline trước R3 đã được thay thế về vai trò phương pháp hiện hành nhưng vẫn có giá trị lịch sử/đối chứng:

| Bundle run | Số tệp liên quan hiện có | Kích thước logic | Dependency ngoài bundle theo contracts |
|---|---:|---:|---|
| `loaco_more_v2_20261027_h9_s42_baseline` | 82 | **1,005 GiB** | Chưa thấy; không là ancestry của R3 |
| `loaco_more_v2_20261027_h25_s42_baseline` | 82 | **0,974 GiB** | Chưa thấy; không là ancestry của R3 |
| `cicunsw_zero_day_v2_loaco_3` — run chưa hoàn tất | 29 | **223,42 MiB** | Chưa thấy; không là ancestry của R3 |

“Bundle” gồm các thư mục cùng run ID dưới `models/{autoencoder,stage1,stage2,novelty}/`, `results/{autoencoder,stage1,stage2,novelty}/`, `results/pipeline/<run>_*`, `artifacts/metadata/<phase>/`, `artifacts/thresholds/` và `data/processed/<dataset>/experiments/`. **Không** có nghĩa chỉ xóa thư mục model mà để contracts còn lại trỏ vào file đã mất.

Đề xuất:

- Hai baseline có thể chuyển sang cold archive đầy đủ khoảng **1,98 GiB**, nếu không còn nhu cầu replay trực tiếp; giữ config, selection, summary và tài liệu giải thích baseline được validation chọn. Cần archive mới + manifest/checksum; không giả định đã có trong backup cũ.
- Với CIC-UNSW LOACO lỗi, giữ status/log lỗi và quyết định có tiếp tục nghiên cứu run này không. Có thể archive phần model/cache chưa hoàn tất; **không ghi nhận nó là kết quả zero-day thành công**.
- Không xóa kết quả âm hoặc kém hơn như Mahalanobis/regularized chỉ vì điểm thấp: đây là đối chứng và thông tin chống chọn lọc kết quả.

### Prepared arrays trùng nhưng chưa phải “rác an toàn”

SHA-256 của sáu tệp sau trong `data/processed/` và `data/processed/round2_20261027_fp32_s42/` khớp từng cặp:

```text
features_raw.npy
features_scaled.npy
attack_label_ids.npy
binary_labels.npy
row_hashes.npy
split_ids.npy
```

Chỉ `features_raw.npy` + `features_scaled.npy` ở layout root đã chiếm **1,312 GiB**, là bản sao riêng chứ không hard-link với round2. Tuy nhiên `configs/model_config.json` mặc định vẫn trỏ tới `data/processed`; việc bỏ layout này có thể làm lệnh legacy/default không chạy. Vì vậy chỉ là **ứng viên hợp nhất layout/archiving có điều kiện**, không đưa vào danh sách xóa an toàn ngay. Chưa hash mọi file còn lại để tuyên bố toàn hai thư mục tương đương.

## 4. Những phần phải giữ để bảo toàn luận văn và tái hiện

### A. R3 và đối chứng novelty

- Toàn bộ 9 chain `novelty_r3_20261027_h{9,25,26}_s{42,43,44}`: AE, OOF fold models/scalers/calibrators/indices, final Stage 1, Stage 2, novelty models/scores/ngưỡng, predictions, contracts.
- `results/novelty_confirmation/novelty_r3_20261027/`: protocol lock, status, comparison, summary, class rejection, logs.
- `results/recall_gate_studies/recall_gate_v1_20261027/`, `results/mahalanobis_studies/mahalanobis_v1/`, `results/knn_studies/knn_v1/`: không commit trực tiếp nhưng phải giữ local/archive, là cơ sở MCP/Mahalanobis/kNN và lịch sử chọn giả thuyết.
- `data/processed/round2_20261027_fp32_s42/` cùng metadata/labels/splits/source IDs/row hashes; không xóa vì tên có ngày cũ.

**Cảnh báo quan trọng:** mỗi nhóm bốn đường dẫn dưới đây trỏ tới cùng một scaled file:

```text
data/processed/round2_20261027_fp32_s42/experiments/
  recall_gate_v1_20261027_h<ID>_s42/preprocessing/features_scaled.npy
  novelty_r3_20261027_h<ID>_s42/preprocessing/features_scaled.npy
  novelty_r3_20261027_h<ID>_s43/preprocessing/features_scaled.npy
  novelty_r3_20261027_h<ID>_s44/preprocessing/features_scaled.npy
# ID = 9, 25, 26
```

Mỗi nhóm có **2,625 GiB logic nhưng chỉ một file identity 0,656 GiB**. Xóa tên đường dẫn nguồn recall-gate không giải phóng 0,656 GiB trong khi ba hard-link R3 còn tồn tại, **nhưng lại phá ancestry vì contracts tham chiếu đúng source path**. Các scaler, fit indices và contract bên cạnh source này cũng phải giữ. Không sửa metadata để che đường dẫn bị xóa.

### B. Nguồn dữ liệu và bằng chứng phương pháp trước đó

- `CICIDS2017/*.csv`, `data/external/CSE-CIC-IDS2018/`, `data/external/CIC-UNSW-NB15/`: vẫn trực tiếp liên quan kiểm chứng luận văn; không xếp vào rác chỉ vì không commit. CSE đang có 9 CSV trong `data/external`, không phải thư mục rỗng cùng tên tại root.
- `round2_20261027_fp32_s42_main` và LOACO26 lịch sử: giữ bằng chứng ablation, precision fix và đối chiếu trước R3, kể cả khi model không phải lựa chọn cuối.
- `cicunsw_zero_day_v2_main`: giữ kết quả closed-set hiện có; study tổng thể failed ở LOACO không làm mất giá trị phần main đã hoàn tất.
- `.venv/`: môi trường đang cài CUDA không phải file source cần Git, nhưng không “không quan trọng”.
- `Tài liệu tham khảo/*.pdf`, `references_reviewed.bib`, review tài liệu và `.tex`: phục vụ luận văn; không xóa. PDF giữ cục bộ; chưa kiểm quyền phân phối nên không đưa bản PDF nhà xuất bản vào commit mới.

### C. Bản sao đã có ngoài project

Đường dẫn backup từ đợt dọn trước:

`C:\Users\Admin\IDS_cleanup_backups\20261027_retired_runs\retired_artifacts.zip`

File hiện tồn tại, **3.673.143.209 byte**, cùng `verified_manifest.json` và `deletion_receipt.json` ghi 70 targets/901 files đã được kiểm khi tạo backup. Lượt này chỉ kiểm tồn tại/receipt, **không đọc lại toàn ZIP để xác minh checksum mới**. Không xóa backup và không coi nó đã bao gồm các chain được giữ lại hoặc R3 tạo sau đó.

## 5. Tài liệu nào có thể lọc khỏi package Git gọn

Đây là **tùy chọn tổ chức/phạm vi public**, không phải kết luận tài liệu vô giá trị:

| Nhóm | File/thư mục cụ thể | Đề xuất |
|---|---|---|
| Bản sao tiêu chí biên soạn từ bên ngoài | `docs/thesis_review_2026-10-25/upstream/composer/SKILL.md`, `composer/references/section_guides.md`, `writing_standards.md`, `upstream/strategist/SKILL.md`, `strategist/references/quality_standards.md`, `upstream/LICENSE` | Không tham gia train; có thể giữ trong archive review riêng. Nếu giữ bản sao phải giữ LICENSE/attribution; không xóa LICENSE riêng lẻ |
| Dữ liệu trích xuất bản luận văn cũ | `docs/thesis_review_2026-10-25/evidence/thesis_extracted.txt`, `pdf_pages.json` | Cần cho kiểm toán review, không cần runtime IDS; giữ local/archive, cân nhắc public trước khi đưa vào package mã nguồn |
| Ảnh chụp trang review | Cùng `evidence/`: `page-015.png`, `page-044.png`, `page-094.png`, `page-102.png` | Bằng chứng editorial, không phải kết quả benchmark; package Git tối giản có thể không thêm mới |
| Bằng chứng sửa citation | Cùng `evidence/`: `references_original.bib`, `references_patch.diff`, `input_audit.json` | Vẫn liên quan nguồn trích dẫn; nên giữ archive, không bắt buộc đưa vào package runtime |
| Bản thảo review/đề xuất văn bản | `DOAN_CHINH_SUA_EN.md`, `KHUNG_REVIEW_IDS.md`, `REVIEW_LUAN_VAN.md`, `KIEM_TRA_TAI_LIEU_THAM_KHAO.md` | **Giữ** trong docs luận văn, phân biệt lịch sử với kết luận mới R3 |
| Báo cáo cũ | `docs/research_audit/`, `ROUND1_FINDINGS.md`, `ROUND1_EXECUTION_PLAN.md`, `PHASE_2_REPORT.md` | **Giữ** để truy vết tiến độ/validity. Không dùng lời khuyên/metric cũ thay số liệu R3 |

`prepare_evidence.py` đọc `evidence/pdf_pages.json` và ghi nhận các bản sao upstream: không chuyển/xóa nhóm này mà vẫn tuyên bố script review tái lập đầy đủ. Chưa xóa hoặc untrack file nào vốn đã tracked trong nhóm trên.

## 6. Danh sách nên giữ để commit source/config/docs

Tệp [COMMIT_ALLOWLIST_20261027.txt](<D:/CAO HOC/IDS System/docs/research_alignment/COMMIT_ALLOWLIST_20261027.txt>) liệt kê **135 đường dẫn đề xuất**, gồm cả nhiều file đã tracked và không đổi. Đây không phải 135 thay đổi mới, không phải lệnh đã stage; cần review diff trước commit.

### Bắt buộc giữ

- `README.md`, `requirements.txt`, `.gitignore` — ignore policy cần được chỉnh ở bước sau, chưa sửa trong lượt này.
- `src/*.py`, `tests/*.py`, các script audit/prepare/train/evaluate/runner/adapter/setup; cả các MLP/OCSVM/IF phục vụ ablation lịch sử vẫn có giá trị nghiên cứu, không xóa vì pipeline cuối không dùng chúng.
- `configs/*.json`: giữ cả cấu hình nghiên cứu lịch sử và 9 trial R3 để tái hiện, dù có tên ngày cũ.
- Markdown hướng dẫn/audit/findings dưới `docs/`; `.bib`, `.tex`, `prepare_evidence.py` và review khoa học.
- `.vscode/settings.json` dùng `${workspaceFolder}`; không chứa interpreter path tuyệt đối tại máy khác.

### File mới quan trọng đang chưa tracked

```text
scripts/09_run_cse_cic_ids2018.py
scripts/10_run_cic_unsw_nb15.py
scripts/11_run_loaco_finetuning.py
scripts/12_select_gate_threshold.py
scripts/13_run_recall_gate_study.py
scripts/14_run_mahalanobis_comparison.py
scripts/15_run_knn_distance_study.py
scripts/16_run_confirmatory_study.py
src/gate_policy.py
src/knn_distance.py
src/mahalanobis.py
src/novelty_benchmark.py
src/study_reporting.py
tests/test_gate_policy.py
tests/test_knn_distance.py
tests/test_mahalanobis.py
tests/test_novelty_benchmark.py
docs/research_alignment/RECALL_GATE_TRAINING_GUIDE.md
docs/research_alignment/MAHALANOBIS_REUSE_GUIDE.md
docs/research_alignment/KNN_LATENT_STUDY_GUIDE.md
docs/research_alignment/NOVELTY_MULTISEED_TRAINING_GUIDE.md
docs/research_alignment/NOVELTY_R3_FINDINGS.md
docs/research_alignment/CLEANUP_20261027.md
```

`scripts/maintenance_archive_old_runs.py` là công cụ vận hành one-time, không thuật toán luận văn. Có thể commit để truy vết cách archive an toàn (đã có trong allowlist), nhưng không chạy lại danh sách hard-coded cũ như lệnh dọn hiện hành.

### Config trùng byte nhưng nên giữ theo provenance

- `configs/base_round1_20261026_s42.json` và `base_round2_20261027_fp32_s42.json` giống SHA-256.
- `configs/external_data_cicunsw_r1.json`, `external_data_cicunsw_r2_20261026_iofix.json`, `external_data_cicunsw_zero_day_v2.json` giống SHA-256.

Chúng chỉ vài KB, đường dẫn được nhắc trong protocol/run lịch sử. Không xóa chỉ vì trùng nội dung; nếu muốn gộp template phải có migration/tài liệu mới, không sửa ngầm config đã khóa.

### Chưa nên dùng nguyên trạng làm entrypoint IDE

`.vscode/launch.json` và `.vscode/tasks.json` vẫn có lệnh AE/Stage 1 kiểu legacy, thiếu `--protocol revised_v1`, dùng run ID `main`. Các parser hiện yêu cầu protocol nên các task này sẽ lỗi nếu bấm trực tiếp. Đã loại **khỏi allowlist đề xuất cho thay đổi mới**, không untrack/xóa bản đang có. Nên cập nhật task theo protocol mới trước khi coi repo sẵn sàng cho người khác chạy IDE.

## 7. Không đưa vào commit mới

```text
.venv/**
**/__pycache__/**
.pytest_cache/**
CICIDS2017/*.csv
data/**                         # ngoại trừ placeholder nếu cần
models/**                       # ngoại trừ placeholder nếu cần
results/**                      # cả metrics JSON/CSV/log/NPZ theo phạm vi commit hiện yêu cầu
artifacts/metadata/**            # generated run metadata; metadata input cần quyết định riêng
artifacts/preprocessors/**
artifacts/thresholds/**
artifacts/external_training.lock
Tài liệu tham khảo/*.pdf
```

**Không commit không đồng nghĩa xóa local.** Nhiều file trong các nhóm này là bằng chứng quan trọng nhất của luận văn.

### Các lỗ hổng ignore được xác minh

Trước khi thêm hai tệp kiểm kê: **1.227 untracked visible paths**, trong đó `results/` 1.068, `artifacts/` 110, `configs/` 25, `scripts/` 9, `src/` 5, `tests/` 4, `docs/` 6. Nếu dùng `git add .`, nhiều artifacts không mong muốn sẽ được stage.

- **63 `predictions.npz`**, khoảng **37,49 MiB**, chưa được ignore.
- **15 `.joblib`** dưới study results chưa được ignore, gồm **12 kNN indexes khoảng 12,87 MiB/file** và 3 Mahalanobis models.
- **316 `.log`**, lock file và nhiều metadata/report generated chưa bị loại.
- `.gitignore` hiện chỉ loại `results/**/*.npy` và `results/**/*.csv.gz`; comment “giữ JSON/CSV metric nhỏ” không còn khớp yêu cầu commit source/config/docs, không đưa kết quả thực nghiệm.

Đề xuất bước sau: giới hạn `results/**`, run metadata/model/score/prediction/log bằng ignore phù hợp hoặc staging theo allowlist; nếu chuyển metadata input sang schema/config versioned phải bảo toàn provenance. **Chưa áp dụng thay đổi ignore.**

Có **28 tracked paths dưới results** và **22 dưới artifacts** từ trước, gồm placeholders. Thêm ignore không làm chúng tự untrack; cần quyết định riêng nếu đổi chính sách Git, giữ bản local và không rewrite lịch sử tùy tiện. Đây là hành vi được mô tả trong [tài liệu Git chính thức](https://git-scm.com/docs/gitignore).

Git hiện báo **19 tracked file deletions** dưới kết quả legacy `main`/`loaco_26` do lần dọn trước. Chưa stage các deletion này. Chỉ staging allowlist source/config/docs sẽ không tự đưa chúng vào commit; tránh `git add -A` hoặc `git commit -a` khi chưa quyết định phạm vi.

## 8. Rủi ro lịch sử Git và khả năng chạy từ clone sạch

### Nhánh hiện tại sạch blob lớn, nhánh backup không sạch

- Tất cả blobs có thể truy tới từ `HEAD`: **166 blobs, 2.271.762 byte**, không blob >100 MiB. Đây không phải toàn dung lượng `.git`.
- Xét mọi refs local/remote đã có: **179 blobs, 7.084.438.387 byte**, **11 blobs >100 MiB** thuộc dữ liệu lịch sử.
- Có nhánh `backup/before-dataset-cleanup` tại `2db80e8ac4e351d557123e6832048871d3038cb9`, xác minh bằng `git show-ref --heads`.
- Blob lớn nhất `5608d5119caed0998ebfd9907430c5e450df219c`: nội dung **4.054.347.563 byte**, file nén object tại `.git/objects/56/08d5119caed0998ebfd9907430c5e450df219c` chiếm **1.232.801.163 byte**. Đường dẫn lịch sử là tệp CSE `.csv.757702C0` chưa hoàn chỉnh; nó không còn là raw file đang có trong working tree. Không coi blob đó là dữ liệu CSE đã xác minh.

**Không dùng `git push --all` hoặc `--mirror`** khi chưa xử lý rõ nhánh backup. GitHub chặn blob >100 MiB trong regular Git, theo [GitHub Docs](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). Việc `.git` lớn không có nghĩa push riêng nhánh hiện tại chắc chắn đẩy mọi object cũ. Chưa xóa ref backup, rewrite history hoặc prune object nào.

### Source-only commit chưa tự đảm bảo “clone rồi chạy ngay R3”

`scripts/16_run_confirmatory_study.py` hiện cần prepared arrays/reproduction checks của round2, preprocessing nguồn recall-gate và các `comparison.json` MCP/Mahalanobis/kNN lịch sử. Những artifacts này được giữ local nhưng không nằm trong gói source-only đề xuất.

Do đó cần một trong hai hướng ở bước triển khai tiếp theo: tài liệu/lệnh tái tạo đầy đủ prerequisites từ raw, hoặc một chế độ bootstrap độc lập sinh lại chúng mà không phụ thuộc artifacts lịch sử. Không giải quyết bằng cách commit data/model/results khổng lồ, cũng không xóa các prerequisites rồi vẫn khẳng định latest runner chạy được. Config generated có đường dẫn tuyệt đối `D:\CAO HOC\IDS System`; giữ nguyên bản lịch sử, tạo portable template riêng nếu cần, không chỉnh config đã khóa chỉ để làm đẹp Git.

Chưa thấy file tên `.env`, private key `.pem/.pfx/.key`, `id_rsa`, `credentials.json` trong phần project ngoài `.venv/.git` theo lượt rà tên file. Đây **không phải** một secret/security audit nội dung đầy đủ. Chưa có `LICENSE` ở root; nếu muốn public/reuse nên quyết định giấy phép phù hợp và giữ attribution phần vendored.

## 9. Thứ tự xử lý đề xuất — chưa thực hiện

1. Review allowlist 135 đường dẫn và các diff source/config/docs; không dùng add-all. Giữ code ba detector, các đối chứng và tài liệu luận văn.
2. Chốt ignore/staging policy cho artifacts, đồng thời quyết định 19 deletion legacy và metadata/results đã tracked; không lẫn thao tác này với dọn ổ đĩa.
3. Nếu cần dung lượng ngay: ưu tiên cache/smoke/cache run lỗi và Git tmp được xác minh. Tổng các nhóm có thể xem xét khoảng **1,11 GiB**, nhưng Git tmp cần quy trình backup/kiểm an toàn riêng, không xóa ngay theo tên.
4. Nếu vẫn thiếu: lập archive có checksum cho hai baseline cũ (~1,98 GiB) hoặc bundle run lỗi. Không cộng trùng cache đã nằm trong bundle; giữ status/summary/selection/provenance và chỉ bỏ bản D sau khi kiểm restore/dependency.
5. Hợp nhất layout prepared duplicate và xử lý Git backup branch chỉ sau phê duyệt riêng; không xóa ancestry recall-gate của R3. Chỉnh IDE/bootstrap portability ở một thay đổi code có kiểm thử riêng.

**Kết luận:** phần lớn dung lượng lớn vẫn liên quan trực tiếp đến luận văn. Dọn để commit GitHub chủ yếu là **lọc file được version control**, không phải xóa datasets/model/bằng chứng. Chưa có thao tác xóa hoặc commit nào được thực hiện theo danh sách này.
