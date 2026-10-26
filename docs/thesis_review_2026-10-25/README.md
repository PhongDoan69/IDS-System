# Bộ tiêu chí và review luận văn IDS

Ngày: **25/10/2026**. Đã dùng năm file được yêu cầu của [lishix520/academic-paper-skills](https://github.com/lishix520/academic-paper-skills), bản PDF 107 trang và BibTeX 29 mục. Không thay đổi file đầu vào, mã pipeline, dữ liệu hay kết quả huấn luyện.

## Mở các kết quả chính

1. [Khung review điều chỉnh cho luận văn IDS](KHUNG_REVIEW_IDS.md): ánh xạ tiêu chí gốc, cách chấm, điều kiện bắt buộc về dữ liệu/leakage/thực nghiệm và checklist nghiệm thu.
2. [Review chi tiết theo trang/mục](REVIEW_LUAN_VAN.md): điểm tốt cần giữ, phát hiện ưu tiên, bảng kết quả và trình tự hoàn thiện.
3. [Các đoạn tiếng Anh đã soạn để thay vào luận văn](DOAN_CHINH_SUA_EN.md): abstract, mục tiêu, phương pháp, đóng góp, roadmap, Chương 4 và dự thảo Chương 6.
4. [Kiểm tra tài liệu tham khảo](KIEM_TRA_TAI_LIEU_THAM_KHAO.md) và [BibTeX chỉnh riêng](references_reviewed.bib): giữ 29 key/DOI, bỏ 15 note DOI lặp và thay một URL đã xác minh. Cần cấu hình style DOI khi ghép.
5. [Bảng đủ 27 nhãn và số lượng theo split](CLASS_DISTRIBUTION.md), kèm [fragment LaTeX](class_distribution.tex). Đây là số đã đọc từ artifact hiện có, không phải split mới.

## Toàn văn năm file tiêu chí gốc

Repo không có `SKILL.md` ở thư mục gốc tại thời điểm kiểm tra: listing gốc không chứa file và đường dẫn gốc trả 404. Hai skill nằm trong thư mục `strategist/` và `composer/`.

| File | Bản nội dung đã lưu local | Nguồn |
|---|---|---|
| Strategist | [strategist/SKILL.md](upstream/strategist/SKILL.md) | [GitHub](https://github.com/lishix520/academic-paper-skills/blob/main/strategist/SKILL.md) |
| Quality standards | [quality_standards.md](upstream/strategist/references/quality_standards.md) | [GitHub](https://github.com/lishix520/academic-paper-skills/blob/main/strategist/references/quality_standards.md) |
| Composer | [composer/SKILL.md](upstream/composer/SKILL.md) | [GitHub](https://github.com/lishix520/academic-paper-skills/blob/main/composer/SKILL.md) |
| Writing standards | [writing_standards.md](upstream/composer/references/writing_standards.md) | [GitHub](https://github.com/lishix520/academic-paper-skills/blob/main/composer/references/writing_standards.md) |
| Section guides | [section_guides.md](upstream/composer/references/section_guides.md) | [GitHub](https://github.com/lishix520/academic-paper-skills/blob/main/composer/references/section_guides.md) |

Các nội dung gốc được giữ bằng UTF-8, chuẩn hóa newline/cuối file. [Giấy phép MIT của repo](upstream/LICENSE) được lưu cùng. Hash nội dung local, URL nguồn và ngày lấy được ghi trong [input_audit.json](evidence/input_audit.json). Nguồn được lấy từ branch `main` vào ngày review; chưa xác định remote commit bất biến nên không gán một SHA commit không được kiểm chứng.

## Phạm vi hoàn thành

Đã hoàn thành việc lấy tiêu chí, điều chỉnh khung, review bản được cung cấp, soạn các phần thay thế, tạo bảng support và bản BibTeX đề xuất. **Chưa ghép vào project LaTeX và chưa xuất bản PDF luận văn mới**, vì đầu vào không có nguồn `.tex`/project. Chưa thực thi các cải tiến protocol hoặc thí nghiệm mới; các kế hoạch vẫn được giữ là kế hoạch. Điểm review chỉ là đánh giá biên tập tham khảo, không thay chuẩn chính thức của trường.

Các hướng dẫn trong nguồn ngoài được xử lý như nội dung tham khảo theo yêu cầu người dùng. Không cài skill toàn cục, không chạy script tải về từ repo, không tìm/chọn nền tảng preprint hoặc nộp luận văn. Khung gốc được điều chỉnh vì tập trung vào triết học/liên ngành, còn luận văn này cần bằng chứng thực nghiệm IDS.

## Bằng chứng và cách kiểm tra lại

- [input_audit.json](evidence/input_audit.json): hash đầu vào, thống kê BibTeX, tổng split, danh sách nguồn gốc và phạm vi kiểm tra citation.
- [references_patch.diff](evidence/references_patch.diff): các chỉnh sửa BibTeX.
- `evidence/pdf_pages.json` và `evidence/thesis_extracted.txt`: text trích xuất, có chỉ số trang PDF; không dùng để kết luận layout.
- `evidence/page-015.png`, `page-044.png`, `page-094.png`, `page-102.png`: các trang đã render để đối chiếu trực quan.
- [prepare_evidence.py](prepare_evidence.py): kiểm tra cấu trúc BibTeX và tạo bảng phân phối từ artifact local; không train hoặc chọn model.

Lệnh đã dùng để kiểm tra đầu vào sau khi trích PDF, tại thư mục repo:

```powershell
& 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'docs\thesis_review_2026-10-25\prepare_evidence.py'
```

Script phụ thuộc các file bằng chứng và đường dẫn đầu vào được ghi trong nó; không phải chương trình thay thế cho pipeline nghiên cứu. Nguồn số per-class là `results/split_summary.csv`; `results/dataset_summary.csv` chỉ là thống kê năm file CSV nguồn. Run cũ, audit lịch sử và HEAD hiện tại được phân biệt trong báo cáo.
