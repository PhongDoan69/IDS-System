# Kiểm tra tài liệu tham khảo

Đầu vào: `C:\Users\Admin\Downloads\references (2).bib`. Ngày kiểm tra: 25/10/2026. File gốc được giữ nguyên; `references_reviewed.bib` là bản đề xuất dùng sau khi cấu hình bibliography style phù hợp.

## Kết quả kiểm tra cấu trúc

- 29 entry: 20 article, 8 inproceedings, 1 incollection.
- Không có citation key trùng; không có DOI trùng trong các trường DOI đã khai báo.
- 27/29 entry có trường DOI. Hai mục không có DOI là Guo et al. 2017 và Hendrycks–Gimpel 2017; không tự coi thiếu DOI là tài liệu không hợp lệ.
- Có 15 `note={doi: ...}` lặp lại đúng DOI của entry. PDF hiển thị DOI không đồng đều giữa các mục; cần kiểm tra style, vì nhiều mục có `doi` nhưng không có note không hiện DOI trong PDF được cung cấp.
- Có tài liệu từ 1986 đến 2026, gồm nền tảng, survey, cascade, calibration và open-set. Hai entry năm 2026 không bị coi là sai chỉ vì mới: thời điểm review là 25/10/2026.
- Trích xuất PDF thu được các số trong dải [1]–[29]. Một số dấu ngoặc số ngoài dải là cấu hình mạng/giá trị khác; không báo chúng là dangling citation. Kiểm tra này không thay được đối chiếu citation key trong nguồn LaTeX, và không chứng minh mọi trích dẫn hỗ trợ đúng phát biểu.

## Thay đổi đã thực hiện trong bản BibTeX riêng

| Thay đổi | Phạm vi | Lý do |
|---|---|---|
| Bỏ note DOI trùng | 15 mục | Dùng một trường DOI có cấu trúc, tránh lặp hoặc hiển thị không nhất quán |
| Đổi URL ở `hendrycks2017baseline` | URL thành `https://arxiv.org/abs/1610.02136` | Trang tác giả trên arXiv xác nhận đúng title, tác giả và ICLR 2017; thay link PDF reference khó kiểm chứng bằng trang định danh đã đọc |
| Giữ nguyên các nội dung khác | 29 key; 27 DOI; tác giả/title/year/venue/pages | Không sửa metadata chưa xác minh, không thêm bài cho đủ quota |

**Lưu ý khi ghép:** nếu `.bst` hiện tại bỏ qua trường `doi`, bỏ note sẽ làm mất phần DOI đang được hiển thị nhờ note. Cần bật hỗ trợ DOI hoặc đổi/cấu hình style được trường chấp nhận, rồi build và kiểm tra. Bản đề xuất này chưa được biên dịch trong project luận văn gốc. Không kết luận URL cũ của Hendrycks trỏ sai bài khi chưa truy cập được nội dung đích; thay đổi ở đây nhằm dùng link đúng đã xác minh.

Diff đầy đủ: `evidence/references_patch.diff`. Bản gốc lưu đối chiếu: `evidence/references_original.bib`. Script kiểm tra chỉ dùng parser cho các entry/field có dấu ngoặc nhọn trong file này; đây không phải bộ kiểm định BibTeX tổng quát cho mọi cú pháp.

## Những đối chiếu nguồn đã thực hiện

| Nguồn gốc | Mức xác minh trong lượt này | Giới hạn |
|---|---|---|
| [Trang CICIDS2017 của UNB/CIC](https://www.unb.ca/cic/datasets/ids-2017.html) | Benchmark có PCAP và flow CSV; trang mô tả năm ngày thu thập và trích bài Sharafaldin et al. | Không chứng minh checksum/archive của năm CSV local chính là một release cụ thể |
| [Hendrycks–Gimpel trên arXiv](https://arxiv.org/abs/1610.02136) | Title, hai tác giả và journal reference ICLR 2017; baseline dùng maximum softmax probability | Không coi nguồn này là chứng minh hiệu quả MCP trên corpus của luận văn |
| [Hi-MLIC, IEEE](https://doi.org/10.1109/ACCESS.2024.3450671) | Title, năm, volume/pages; mô tả hierarchical classification và dataset consolidation | Không đồng nhất representation của Hi-MLIC với 84 features local; chưa kiểm mọi claim của bài |
| [Wang et al., CMC/SciOpen](https://www.sciopen.com/article/10.32604/cmc.2025.062094) | Title, tác giả, volume/pages; tầng đầu có normal/majority/minority và tầng sau tinh chỉnh minority | Không gọi đây là binary gate giống hệt mô hình luận văn; chưa tái lập kết quả của họ |
| [Ashraf–Masoodi, Springer](https://link.springer.com/article/10.1007/s10791-026-10486-2) | Title, tác giả, volume 29, article 577, công bố 27/08/2026 | Xác minh metadata và phạm vi survey, không kiểm tra toàn bộ 124 dataset mà bài khảo sát |
| Hussein–Répás 2026, PDF nhà xuất bản có sẵn ở `Tài liệu tham khảo/ai-07-00039.pdf` | Trang đầu xác nhận tác giả/title, DOI, công bố 25/01/2026 và phạm vi AE-GMM + supervised models trên hai dataset | Website MDPI trả 429; dùng PDF local, không báo là đã truy cập web thành công |
| Hewapathirana 2025, PDF nhà xuất bản có sẵn ở `Tài liệu tham khảo/knowledge-05-00006.pdf` | Trang đầu xác nhận tác giả/title/DOI, ngày công bố 12/03/2025 và score feature cho second-stage classifier | Không tự suy diễn từ abstract rằng mọi bước OOF/calibration khớp thiết kế luận văn |

Đây là **đối chiếu chọn lọc**, không phải xác minh đầy đủ 29 DOI, mọi tác giả hay mọi phát biểu trích dẫn, cũng không phải systematic literature review. Các nguồn thứ cấp xuất hiện trong kết quả tìm kiếm không được dùng làm căn cứ sửa metadata.

## Cách tăng chất lượng related work mà không thêm citation trang trí

Giữ bảng so sánh gần nhất ở §2.9, nhưng ghi rõ cho mỗi nghiên cứu: dữ liệu/version; predictor/label space; split; Stage 2 có BENIGN hay không; protocol tạo score feature; holdout/threshold; population của metric. Khi chưa đọc đủ bài, ghi chưa xác minh thay vì gán thuộc tính vắng mặt.

Đối chiếu trực tiếp các thành phần đã có trong literature trước khi gọi là mới. Autoencoder, XGBoost, MLP, stacking và các novelty estimators đều có tiền lệ. Đóng góp có thể nằm ở phép so sánh có kiểm soát, protocol, phân tích error propagation và artifact có thể truy vết. Những đóng góp đó phải có bằng chứng của nghiên cứu hiện tại, không chỉ có citation về khả năng của thuật toán.

Không bắt buộc nâng 29 mục thành 40–60 chỉ để đạt tiêu chí bài báo triết học trong nguồn. Mọi mục bổ sung cần lấp một thiếu hụt nội dung cụ thể và được kiểm chứng trước khi trích.
