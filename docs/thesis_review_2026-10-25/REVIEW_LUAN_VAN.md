# Review luận văn IDS theo strategist và composer

Ngày review: 25/10/2026. Bản được review: `C:\Users\Admin\Downloads\main (3).pdf`, 107 trang; BibTeX: `references (2).bib`, 29 mục. Quy ước: **PDF n / in m** là trang thứ n của file và số trang in m; phần thân có m = n − 7. Không nhầm số trang file với số trang luận văn.

## 1. Nhận định chính

Bản thảo có nền tảng phù hợp cho một luận văn thực nghiệm: bốn RQ rõ, phân biệt classifier riêng với pipeline, không đồng nhất LOACO với zero-day thực tế, và Chương 5 diễn giải cả kết quả không cải thiện. Phần validity đã công khai nhiều hạn chế quan trọng. Vì vậy không nên viết lại thành một câu chuyện khẳng định AE, meta-feature hoặc novelty luôn có lợi.

**Chưa nên coi bản hiện tại là bản hoàn thiện để nộp/bảo vệ.** Lý do trực tiếp về văn bản là roadmap sai số chương, thiếu abstract/kết luận trong file được cung cấp, còn thông tin thiếu đã có thể điền và nhiều đoạn kể hoàn cảnh soạn thảo. Lý do về bằng chứng là strict LOACO/OOF còn hạn chế, đối chứng chưa đủ cho kết luận mạnh và chỉ có một holdout. Công khai các hạn chế là điểm tốt; công khai không thay thế việc sửa phương pháp nếu vẫn giữ mục tiêu kiểm chứng mạnh.

Không có quy định định dạng của trường trong đầu vào. Nhận xét về thiếu bìa/cam đoan/tóm tắt song ngữ là trạng thái của file này và danh sách cần đối chiếu; không phải kết luận vi phạm một mẫu trường đã được kiểm tra.

## 2. Phạm vi kiểm chứng

- Đọc cấu trúc PDF, các phần phương pháp/thực nghiệm/thảo luận liên quan, bibliography và các phát biểu được nêu dưới đây; đối chiếu các trang có phát hiện.
- Kiểm tra trực quan PDF 15, 44, 94, 102: văn bản bình thường đọc được; bảng 5.4 sát cột; bảng 5.11 có nhiều cột hẹp và ngắt từ gây khó đọc. Không kết luận lỗi mất khoảng trắng chỉ từ text extraction, vì ảnh render cho thấy nhiều chỗ vẫn hiển thị đúng.
- Đối chiếu trực tiếp JSON metric cho main latent-only pipeline, Stage-2 latent-only và novelty LOACO-26; đọc audit nội bộ cùng các bảng phân phối/split. Các phép tính lại prediction và 16 unit tests được nhắc trong luận văn thuộc audit lịch sử, **không phải kiểm tra đã chạy lại trong lượt review này**.
- HEAD local khi review: `8e96ddd0aeff5605496eb884a2a81ab8d9ee64d4`; audit mà Chương 5 trích dùng commit `895cc8bbba59497ceda625cf9947fa1828e20724`. Hai mốc có vai trò khác nhau. Không đồng nhất HEAD hiện tại với commit tạo model cũ.
- Không train, đổi split, chọn model/ngưỡng hoặc ghi đè kết quả. Không nhận nguồn LaTeX trong hai file đầu vào; các chỉnh sửa được cung cấp thành đoạn thay thế và phụ lục riêng, chưa ghép/biên dịch lại bản luận văn gốc.

## 3. Những nội dung cần giữ

| Nội dung có chất lượng | Bằng chứng trong bản thảo | Cách giữ khi chỉnh |
|---|---|---|
| RQ đặt theo phép so sánh, không mặc định kết quả | §1.4, PDF 12 / in 5 | Giữ 4 RQ và nối rõ với các bảng kết quả |
| Không gọi ghép thuật toán sẵn có là thuật toán mới | §2.9 và §5.6.1 | Định vị đóng góp là triển khai có truy vết, ablation và phân tích sai số có giới hạn |
| Nhận ra `P_attack` không thêm thông tin độc lập nếu là hàm của cùng latent | §2.9, §3.5.2 | Giữ lập luận; giải thích hiệu ứng có thể do cách biểu diễn cho learner hữu hạn |
| Chọn baseline Stage 2 theo validation | §4.3.4, §5.3 | Giữ latent-only là baseline trong ba cấu hình; không đảo lựa chọn theo test |
| Phân biệt AP với tích phân hình thang PR-AUC | §4.4.1 | Giữ tên Average Precision; giải thích key JSON `pr_auc` |
| Phân biệt novelty độc lập và final unknown sau gate | §4.4.4, §5.5.2 | Giữ hai kết quả riêng với mẫu số đúng |
| Chỉ ra lớp hiếm có F1 cuối bằng 0 | Bảng 5.7 | Giữ support 1, 2, 5; bổ sung bảng đầy đủ ở phụ lục |
| Không suy luận significance hay real-time từ một split hoặc giảm chiều | §5.2–5.6 | Giữ giới hạn và chỉ nêu các phép đo thực sự có |

## 4. Phát hiện và chỉnh sửa ưu tiên cao

### H01. Roadmap sai số chương

**Vị trí:** §1.8, PDF 15 / in 8. Đoạn hiện tại nói project chỉ có ba chương và không có chương sau. File thực tế có Chương 4 từ PDF 62 và Chương 5 từ PDF 88.

**Tiêu chí:** strategist: tổ chức; composer: nhất quán liên chương. **Sửa:** thay bằng roadmap đúng năm chương hiện có; nếu thêm kết luận riêng thì đổi thành sáu chương. Đã có cả hai phiên bản trong `DOAN_CHINH_SUA_EN.md`. Không giữ câu mô tả số lượng file LaTeX như một nội dung học thuật.

### H02. Thiếu abstract và kết luận tổng thể trong PDF được cung cấp

**Vị trí:** PDF bắt đầu bằng Contents, sau §5.6.3 chuyển thẳng sang Bibliography ở PDF 105. Có thảo luận và kế hoạch nhưng chưa có chương/mục kết luận cuối độc lập.

**Tiêu chí:** section guides: abstract phải phản ánh kết quả; conclusion trả lời vấn đề ban đầu. **Sửa:** thêm abstract và Chương 6 Conclusions and Future Work, hoặc một mục kết luận cuối rõ ràng theo mẫu trường. Đã soạn bản tiếng Anh dùng đúng các số hiện có và ghi rõ exploratory. Không dùng expected contributions thay thế achieved contributions.

### H03. Thông tin phân phối lớp còn trống dù artifact local có đủ

**Vị trí:** §4.2.3 và Bảng 4.6, PDF 68–69 / in 61–62: BENIGN, tần suất từng nhãn và per-split support ghi Not supplied. Trong Chương 5 đã có một số support cụ thể, tạo cảm giác các chương dùng các mốc dữ liệu khác nhau.

**Bằng chứng mới đọc tại local:** `results/split_summary.csv` có 27 nhãn × 3 split. BENIGN = **1,582,535/2,096,804 = 75.4737%**. Nhãn nhỏ nhất là Web Attack - SQL Injection - Attempted, tổng **5** mẫu, chia **3/1/1**. Các tổng theo split khớp 1,467,762 / 314,521 / 314,521.

**Sửa:** thay Bảng 4.6 bằng bảng thực có, hoặc bảng rút gọn và dẫn phụ lục. `CLASS_DISTRIBUTION.md` và `class_distribution.tex` đã chứa đủ 27 hàng. Sửa dẫn nguồn: **`dataset_summary.csv` là thống kê file nguồn** (file/rows/columns/bytes/sha256), không phải bảng tần suất nhãn; bảng nhãn lấy từ `split_summary.csv`.

### H04. Giọng văn kế hoạch và báo cáo đã làm chưa nhất quán

**Vị trí:** §1.3–1.7, đặc biệt PDF 11, 13–15; mở đầu Chương 4 ở PDF 62 / in 55. Có các câu kiểu chưa xác nhận đã train, will compare, không truy cập được GitHub và giới hạn của drafting batch; Chương 5 lại có kết quả cụ thể.

**Sửa:** trình bày công việc đã thực hiện ở quá khứ/hiện tại; dành will/planned cho cải tiến chưa chạy. Thay phần kể môi trường soạn thảo bằng phạm vi chứng cứ: saved artifacts, audit snapshot, exploratory protocol. Không xóa thông tin thiếu hardware của run cũ bằng cách đo máy hiện tại rồi gán ngược cho run cũ. Đã soạn đoạn thay thế cho objectives, methodology, contributions và mở đầu Chương 4.

### H05. Strict LOACO chưa được đáp ứng dù loại lớp ở model fitting

**Vị trí:** §3.2.1, §3.6.2, §4.5, §5.5–5.6; mô tả rõ nhất PDF 101 / in 94. Bản thảo đã công khai scaler main dùng cả 66,600 DDoS train trước khi LOACO loại DDoS.

**Đánh giá:** đây là hạn chế đã nhận diện đúng, không phải phát hiện mới bị tác giả bỏ sót. Metadata held-out label khớp giữa AE/S1/S2 chỉ kiểm một phần lineage; chưa chứng minh mọi fitting stage vắng unknown. Không có bằng chứng ở đây cho biết metric đã lệch bao nhiêu hoặc lệch theo hướng nào.

**Sửa văn bản ngay:** giữ nhãn exploratory, dùng cùng một mô tả ngắn và dẫn về validity, tránh lặp nguyên đoạn nhiều chương. **Cần thực nghiệm mới nếu giữ claim strict LOACO:** scaler và mọi thành phần phụ thuộc dữ liệu phải fit theo known-only training cho từng holdout; ngưỡng theo known validation; lưu ancestry/checksum và chạy mới. Không sửa metric hiện có bằng suy đoán.

### H06. OOF và calibration chưa độc lập đầy đủ cho meta-feature

**Vị trí:** §3.5.1, PDF 57–58 / in 50–51; §4.5.1; §5.3.2. Outer held-out fold cũng dùng early stopping; calibrator fit và áp lại trên cùng training OOF scores/labels. Scaler/encoder dùng chung làm phạm vi cross-fitting của toàn pipeline cần được diễn đạt chính xác.

**Sửa:** giữ phân biệt OOF đối với fit tham số chính và độc lập với mọi bước model selection/calibration. Không gọi mapping là đã được chứng minh calibrated chỉ vì đã fit Platt. Nếu đánh giá chặt, chọn stopping từ inner training, tạo calibration/cross-fitting không dùng target của hàng cần sinh feature, xác định rõ representation fit ở đâu và đánh giá Brier/ECE/reliability trên dữ liệu độc lập phù hợp. Đây là thay đổi phương pháp, cần code/lineage/run mới; lượt này chỉ điều chỉnh khung và văn bản.

### H07. Độ độc lập split và provenance dữ liệu còn giới hạn

**Vị trí:** §5.6.2, PDF 100–101 / in 93–94. Audit được trích báo 2,253 validation và 2,213 test feature vectors trùng train ở 84 predictors. Bản thảo cũng chưa xác định chắc upstream release và semantics của `Attempted`.

**Sửa:** tiếp tục gọi chính xác là feature-vector overlap; không tự kết luận cùng session hoặc định lượng inflation. Lưu bản đồ provenance/label policy; quy định đơn vị grouping và kiểm tra overlap trước thí nghiệm mới. Không tự merge/drop nhãn Attempted trong văn bản. Khi thay target/split, phải xem đó là task/protocol version khác; không so metric như cùng điều kiện. Việc xem test cũ phải được công khai, không được coi seed mới là dữ liệu kiểm chứng độc lập.

## 5. Những bổ sung để luận văn thuyết phục và gọn hơn

| ID / ưu tiên | Vị trí | Đề nghị cụ thể và điều kiện hoàn tất |
|---|---|---|
| M01 / trung bình | Chương 2, PDF 16–50 | Chương 2 khoảng 35 trang so với 8 trang mở đầu, 11 trang phương pháp và 17 trang kết quả. Không sai do một tỷ lệ cứng, nhưng nên rút kiến thức phổ thông/lặp validity để tăng mật độ phân tích liên quan trực tiếp RQ |
| M02 / trung bình | §3.1; List of Figures trống ở PDF 5 | Thêm hình training flow và inference decision; ghi rõ scaler, AE, OOF/calibrator, S1/S2/novelty; không minh họa như đã đo runtime conditional |
| M03 / trung bình | Bảng 4.11 và 5.1 | Hai manifest chiếm nhiều trang và lặp artifact path dài. Giữ bảng gọn ở Chương 4, chuyển đường dẫn/checksum đầy đủ sang phụ lục; Chương 5 chỉ trỏ run ID |
| M04 / trung bình | §4.4.4, PDF 81 / in 74 | Câu final unknown phải tính nếu calculation được thực hiện đã được đáp ứng trong §5.5.2. Đổi thành dẫn tới phép tính từ final CSV ở Chương 5, vẫn phân biệt với key `open_set_metrics` |
| M05 / trung bình | Bảng 5.3–5.5 | Giữ metric đầy đủ giữa các cấu hình: binary accuracy/balanced accuracy/precision/recall/F1/FPR/AUROC/AP; Stage 2 và pipeline accuracy/balanced accuracy/macro-F1/weighted-F1. Bản chính có thể rút gọn nhưng phụ lục phải đủ, cùng mẫu số |
| M06 / trung bình | §5.4 và Bảng 5.7 | Thêm toàn bộ per-class precision/recall/F1/support và confusion matrix chuẩn hóa. Ba lớp hiếm là ví dụ, không thay bảng tổng thể |
| M07 / trung bình | §4.3.2, PDF 73 / in 66 | Ghi rõ gate XGB latent là cấu hình dùng cho latent-based pipeline, không phải global validation winner. Bản thảo đã nhận ra điều này; giữ một câu rõ trong kết quả, không suy ra lý do thiết kế hậu nghiệm |
| M08 / trung bình | §2.9, Bảng 2.1 | Thêm các cột split, Stage-2 có BENIGN không, OOF/calibration, heldout, metric/population và nguồn xác minh. Không xếp hạng theo accuracy giữa corpus khác nhau; không dùng số lượng tài liệu để chứng minh novelty |
| M09 / trung bình | §5.3–5.6 | Nếu giữ kết luận lợi ích cascade: cần flat multiclass cùng task/split; nếu muốn khái quát meta-feature trong MLP: thêm MLP latent-only. Nếu thu hẹp phạm vi thì ghi rõ các so sánh chưa trả lời, không bắt buộc thêm mọi baseline chỉ để đủ danh sách |
| M10 / trung bình | Bảng 5.11, PDF 102–104 | Dùng mã vấn đề + phụ lục kế hoạch để giảm bảy cột hẹp. Giữ Planned — Not Yet Executed. Ảnh render cho thấy chưa có bằng chứng chữ chồng, nhưng nhiều ngắt từ gây đọc chậm |
| M11 / thấp | Bảng 5.4, PDF 94 | Dùng nhãn hiển thị Latent / Latent + P_attack (XGB) / Latent + P_attack (MLP); run ID đầy đủ chuyển sang manifest. Tách cột rõ, không thu font quá nhỏ |
| M12 / trung bình | Bibliography, PDF 105–107 | Đồng bộ DOI bằng style hỗ trợ `doi` hoặc cấu hình tương ứng; kiểm tra nguồn `.tex` sau ghép. Không dựa vào `note=doi:...` chỉ cho một nhóm tài liệu |

Đề cương sáu chương và checklist được đưa trong `KHUNG_REVIEW_IDS.md`. Các bổ sung baseline, nhiều holdout, uncertainty hay timing vẫn là kế hoạch; không có kết quả mới trong gói review này.

## 6. Bảng kết quả nên dùng làm trục diễn giải

Giữ các giá trị đã có; số dưới đây là tỷ lệ 0–1, không phải phần trăm. Bảng này tóm tắt phạm vi, không thay bảng metric đầy đủ.

| So sánh | Kết quả hiện có | Diễn giải có thể bảo vệ |
|---|---|---|
| RQ1–RQ2: Stage-1 XGB, standardized vs latent | F1 0.999857 vs 0.999339; FP/FN 15/7 vs 41/61 | Latent không cải thiện binary F1 ở cấu hình/split này. Không có timing để kết luận lợi ích tài nguyên |
| RQ3: S2 latent-only vs +P_attack XGB | Val macro-F1 0.880938 vs 0.858131; conditional test 0.902392 vs 0.910874 | Kết quả đảo thứ hạng giữa validation và conditional test; giữ baseline theo validation |
| Closed-set final, latent-only vs +P_attack XGB | Macro-F1 0.840758 vs 0.837458 | Không có lợi ích nhất quán của feature bổ sung; chưa chứng minh khác biệt thống kê |
| Closed-set latent-only | Accuracy 0.995298; balanced accuracy 0.830134; weighted-F1 0.995308 | Accuracy cao không đại diện đầy đủ cho các lớp hiếm |
| RQ4: MCP LOACO-26 standalone | Unknown recall 0.260650; F1 0.352690; known rejection 0.049357 | Một operating point trên attack-only population của một holdout |
| MCP LOACO-26 final labels | Recall 0.247197; precision 0.532207; F1 0.337592 | Kết quả sau gate trên toàn test; khác score-only JSON field |
| IF LOACO-26 standalone | AUROC 0.850716; unknown recall 0.030199 tại ngưỡng đã chọn | Ranking toàn đường cong không thay cho chất lượng tại operating point |

Nguồn: các Bảng 5.3–5.9, JSON kết quả được ghi trong bản thảo và audit nội bộ `docs/research_audit/03_experiment_review.md`. Direct JSON spot checks trong lượt này khớp các giá trị đã đọc; final-label novelty được dẫn theo audit lịch sử, không báo là đã recompute lần nữa.

## 7. Chấm theo khung nguồn, có điều chỉnh

Các điểm sau là **nhận định biên tập tạm thời**, dùng ưu tiên sửa; không phải điểm hội đồng, phần trăm hoàn thành hay xác suất bảo vệ thành công. Không chấm tuân thủ mẫu trường chưa được cung cấp.

| Chiều composer toàn văn | Điểm /10 | Căn cứ |
|---|---:|---|
| Lập luận | 7 | 4 RQ rõ, thảo luận khớp kết quả; chưa khép lại bằng kết luận tổng thể |
| Tích hợp tài liệu | 7 | 29 mục, có các đối chiếu trực tiếp và công trình nền tảng; chưa có full search/claim verification cho mọi nguồn |
| Rõ ràng | 7 | Định nghĩa task và metric tốt; còn nhiều lặp và câu theo hoàn cảnh drafting |
| Đóng góp | 5 | Đóng góp triển khai/phân tích có thể nhận diện; tính mới và sức mạnh bằng chứng còn hạn chế |
| Chặt chẽ phương pháp | 4 | LOACO scaler, OOF/calibration, overlap, một seed/holdout; giới hạn đã công khai nhưng chưa sửa |
| Tổ chức | 5 | Chương 1.8 mâu thuẫn, thiếu abstract/kết luận trong PDF, manifest lặp |
| Văn phong/trình bày nội bộ | 5 | Phần lớn đọc được; chưa hoàn tất front matter, nhãn bảng dài, nhiều cột hẹp; institutional conformity chưa đánh giá |
| **Tổng tạm thời** | **40/70** | Chưa đạt ngưỡng tham khảo 56/70; còn điều kiện khoa học bắt buộc |

Không dự báo điểm sau chỉnh sửa. Hoàn thiện văn bản có thể nâng chất lượng báo cáo nhưng không tự nâng độ chặt của thực nghiệm.

## 8. Trình tự hoàn thiện và tiêu chí đóng review

1. **Sửa ngay với bằng chứng đã có:** roadmap; abstract/conclusion; objectives/contributions; bảng 27 nhãn; dẫn đúng artifact; §4.4.4; BibTeX; nhãn bảng và lặp manifest. Các đoạn thay thế đã nằm trong gói này.
2. **Chốt phạm vi khoa học:** nếu giữ bản exploratory, nói rõ kết luận theo cấu hình/split và một holdout. Nếu muốn xác nhận hiệu quả phương pháp, cần protocol mới trước khi chạy: provenance/target, split independence, strict LOACO, OOF/calibration, baseline và quy tắc selection. Không dùng test cũ để chọn rồi báo là xác nhận độc lập.
3. **Thực nghiệm theo phạm vi đã chốt:** tạo run lineage mới; không ghi đè pre-improvement. Với GPU 4 GB chạy tuần tự, đo resource/timing nếu giữ câu hỏi về chi phí. Không mặc định sửa protocol sẽ làm metric tăng.
4. **Ghép từ nguồn và QA:** kiểm tra `.tex`/citation keys, build PDF, kiểm tra bảng/hình/cross-reference, đối chiếu mẫu trường; đánh giá lại sau khi bằng chứng và văn bản đồng bộ. Gói hiện tại chưa phải một PDF luận văn đã được biên dịch lại.

Khung nguồn được lưu trong `upstream/`; bản điều chỉnh ở `KHUNG_REVIEW_IDS.md`; các đoạn tiếng Anh ở `DOAN_CHINH_SUA_EN.md`; audit tài liệu ở `KIEM_TRA_TAI_LIEU_THAM_KHAO.md`; hashes và kết quả kiểm tra đầu vào ở `evidence/input_audit.json`.
