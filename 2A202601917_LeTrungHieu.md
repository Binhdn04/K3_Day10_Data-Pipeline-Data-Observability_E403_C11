# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lê Trung Hiếu |
| MSSV | 2A202601917 |
| Khóa/Lớp | K3 / E403 |
| Tên nhóm | C11 |
| Vai trò chính | Data Observability và Reporting |
| Repository | https://github.com/Binhdn04/K3_Day10_Data-Pipeline-Data-Observability_E403_C11 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data Quality Checks | `src/observability/quality.py`, `run_data_quality_checks()` | Clean/Corrupted/Repaired DataFrame, `Settings` | Các báo cáo chất lượng dạng JSON trong `data/quality/` | Hoàn thành |
| Data Freshness | `src/observability/quality.py`, `build_freshness_report()` | DataFrame, `Settings` | Báo cáo độ tươi dữ liệu dạng JSON | Hoàn thành |
| Phase 1 Markdown Report | `src/observability/reporting.py`, `generate_phase1_report()` | Quality, Freshness, Evaluation metrics JSONs | `data/reports/phase1_report.md` | Hoàn thành |
| Corruption Impact Report | `src/observability/reporting.py`, `generate_corruption_report()` | Các metrics và quality status của Baseline, Corrupted, Repaired | `data/reports/corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Module/thành viên được hỗ trợ | Kết quả |
| --- | --- | --- |
| Xử lý lỗi module import | Toàn nhóm (khi chạy entrypoint script) | Đảm bảo `sys.path` được append đúng đường dẫn `src`, giúp pipeline chạy end-to-end mượt mà |
| Phân tích lỗi cài đặt | Toàn nhóm (khi cài `datasets`, `langchain-google-genai`) | Khắc phục `ModuleNotFoundError` để pipeline chạy evaluation không bị crash |

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/hàm/artifact | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Quality Checks | `run_data_quality_checks()` | Phát hiện lỗi số lượng dòng, duplicate ID, title bị truncate, summary ngắn/nhiễu và độ tươi dữ liệu | Kiểm tra `data/quality/*.json` ở 3 trạng thái. Baseline 5/5 pass, Corrupted 0/5 pass |
| Freshness Check | `build_freshness_report()` | Báo cáo chi tiết ngày xuất bản mới nhất/cũ nhất và số dòng quá hạn (stale) | Kiểm tra `freshness_*.json` xem có nhận diện đúng record sinh năm 1900 ở Corrupted không |
| Baseline Report | `generate_phase1_report()` | Báo cáo Markdown tự động tóm tắt Data Quality, Freshness và Metrics (Retrieval, Judge) | Đọc `data/reports/phase1_report.md` |
| Impact Report | `generate_corruption_report()` | So sánh tự động và làm nổi bật phần chênh lệch hiệu suất (impact) và khả năng phục hồi (recovery) | Đọc `data/reports/corruption_report.md` |

Output quan trọng nhất của Data Observability & Reporting là cung cấp cái nhìn định lượng, theo thời gian thực về "sức khỏe" của pipeline, giúp phát hiện lỗi từ sớm mà không cần phải chờ đến bước LLM QA.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Trong một data pipeline, dữ liệu có thể đi qua nhiều chặng (từ Crossref, qua Cleaning, tạo Embedding). Nếu không có Data Observability (khả năng quan sát), khi có lỗi xảy ra (ví dụ: bị mất records, text chứa ký tự lạ, dữ liệu quá cũ), ta chỉ có thể phát hiện thông qua kết quả tệ ở phía LLM (Retrieval Hit Rate giảm). Nhiệm vụ của tôi là xây dựng các chốt chặn (Quality Gates) để đánh giá Data Quality ngay sau khi làm sạch, và tự động tạo các báo cáo Markdown dễ đọc cho end-user thay vì bắt họ đọc JSON.

### Cách triển khai

- Trong `src/observability/quality.py`, tôi dùng thư viện `pandas` để tạo 5 loại rules:
  1. **Row Count Check**: Đối chiếu tổng số bản ghi với lượng mong đợi (để bắt lỗi rớt data).
  2. **ID Null & Unique Check**: Đảm bảo `paper_id` (DOI) không rỗng và không bị duplicate.
  3. **Title Check**: Loại trừ title bị null, rỗng hoặc có chứa truncation marker ("...").
  4. **Summary Check**: Đảm bảo summary đủ độ dài tối thiểu (>20 ký tự) và không chứa các noise token.
  5. **Freshness Check**: So sánh `age_days` với ngưỡng cấu hình (`Settings.freshness_threshold_days`).
- Trong `src/observability/reporting.py`, thay vì hardcode chuỗi string, tôi viết logic đọc dữ liệu tổng hợp từ các metrics dict. Ở `generate_corruption_report()`, tôi tự động tính phần trăm thay đổi (`_diff_pct`, `_diff_num`) giữa Baseline vs Corrupted (Impact) và Corrupted vs Repaired (Recovery).

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Dataframe sau khi clean/corrupt/repair, `Settings`, các file `.json` metrics |
| Output Observability | `data/quality/*.json` chứa `passed` flags và details của mỗi rules |
| Output Reporting | `data/reports/*.md` |
| Xử lý ngoại lệ | Pipeline kiểm tra nếu có DataFrame rỗng thì set toàn bộ quality rule `passed = False` thay vì ném exception. |

### Cách xác minh

```bash
uv sync
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Thư mục `data/quality/` chứa các file log json thể hiện trạng thái pass/fail. Thư mục `data/reports/` sinh ra `phase1_report.md` và `corruption_report.md`.
- **Kết quả thực tế:** Code đã sinh ra đúng artifact, định dạng markdown lên bảng rất rõ ràng, phần diff trong corruption báo cáo chính xác.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi đánh giá độ tươi của dữ liệu (Freshness), có nên gộp chung nó làm một quality check rule, hay tách thành một module riêng?
- **Các phương án đã cân nhắc:** (1) Chỉ để Freshness trong data quality; (2) Tách hẳn thành `freshness.py` riêng và không liên quan quality; (3) Vẫn đưa vào quality checks (1 check cho rule threshold) nhưng đồng thời build một report tổng hợp chuyên sâu cho freshness (ngày cũ nhất, ngày mới nhất).
- **Phương án đã chọn:** Phương án 3.
- **Lý do:** Freshness có tính chất thay đổi theo thời gian thực dù dữ liệu không đổi (ví dụ: hôm nay một bài báo vẫn là "fresh", nhưng 1 năm sau nó tự nhiên thành "stale"). Đưa vào quality checks giúp pipeline có thể block ngay nếu quá stale. Nhưng report riêng `freshness_report` lại giúp cung cấp cái nhìn chi tiết về distribution of published dates, rất cần thiết cho phân tích.

## 6. Một lỗi hoặc blocker đã xử lý

### Blocker đã phân tích: Handle thiếu cột (Missing Columns) thay vì Crash

- **Triệu chứng:** Khi chạy trên một DataFrame bị lỗi ngẫu nhiên trong pipeline (ví dụ corruption xóa hẳn cột `summary` hoặc `age_days`), code `quality.py` ban đầu có thể bị throw `KeyError`.
- **Nguyên nhân gốc:** Pandas yêu cầu cột phải tồn tại thì mới làm toán (như `.str.len()` hay `> threshold`).
- **Cách xử lý hiện tại:** Tôi đã bọc logic kiểm tra bằng câu lệnh `if "column_name" in df.columns and total_rows > 0:`. Nếu thiếu cột, module quality sẽ nhẹ nhàng log `passed: False` và báo `details: "Column 'summary' missing"` thay vì làm crash toàn bộ workflow.
- **Điều học được:** Data Observability phải hoạt động thật kiên cường (resilient). Chức năng của nó là bắt lỗi của các pipeline khác, nên bản thân nó không được phép sập khi dữ liệu đầu vào nát bét.

## 7. Hiểu biết về luồng end-to-end

1. **Ingestion & Cleaning:** Crossref Data được tải về, parser thành các trường chuẩn, lọc HTML trong abstract và deduplicate. Quá trình này cấp đầu vào (Dataframe) cho module của tôi.
2. **Observability Rules Engine (của tôi):** Ngay sau khi Cleaning xong, tôi quét Dataframe để chốt chặn (gate-keeping). Nếu quality checks rớt thảm hại, hệ thống nên sinh cảnh báo ngay.
3. **Embedding & Evaluation:** Dataframe được chuyển sang dạng Index, rồi được đánh giá với tập Test Set. Kết quả của chúng được push ra file JSON (metrics).
4. **Reporting (của tôi):** Sau khi Evaluation chạy xong, hàm reporting của tôi gom toàn bộ metadata (quality JSON, evaluation JSON, source summary JSON) để format ra thành một báo cáo Markdown duy nhất.
5. **Corruption & Repair:** Quá trình corruption tác động lên dữ liệu. Module observability của tôi giúp "chụp X-quang" dữ liệu bị hỏng, phát hiện ra ngay 5/5 lỗi (mất record, duplicate, title lỗi, v.v.). Sau khi Repair thành công, module của tôi xác nhận 5/5 quality check xanh trở lại.

## 8. Phân tích kết quả (Từ góc độ Data Observability)

### Metrics chính về Data Quality

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| Quality: Row Count | 24 | 23 | 24 | Corruption drop record; Repair hồi phục đủ. |
| Quality: ID Unique | Pass | Fail (1 duplicate) | Pass | Observability phát hiện thành công nhiễu do duplicate data. |
| Quality: Summary Validity | Pass | Fail (empty/noise) | Pass | Bắt được các lỗi text corruption. |
| Freshness | Fresh (0 stale) | Stale (1 stale) | Fresh (0 stale) | Record có năm 1900 bị phát hiện ngay lập tức bởi rules age_days. |
| Automation Report | Thành công | Thành công | Thành công | Báo cáo `corruption_report.md` đã làm nổi bật phần chênh lệch metric rất rõ ràng. |

### Chuỗi nguyên nhân–bằng chứng

Việc Observability phát hiện lỗi ở khâu đầu (`Corrupted Quality = 0/5 Pass`) là **nguyên nhân dự đoán** chính xác cho hậu quả `Retrieval Hit Rate` giảm 50% và `Mean Token F1` rớt xuống `0.4327`.
Khi Repair chạy, việc `Repaired Quality = 5/5 Pass` chính là **bằng chứng tiền đề** để khẳng định dữ liệu đã sẵn sàng, và điều này được chứng minh bằng việc RAG metrics hồi phục 100%.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về Observability:** Data quality không chỉ là đếm số dòng, mà phải thấu hiểu cả định dạng string, giá trị rỗng ngầm (ví dụ: title kết thúc bằng '...') và tính thời gian thực (Freshness).
2. **Về Reporting:** Báo cáo tự động rất có giá trị. Nó tiết kiệm hàng giờ đọc log file cho các Data Engineer và Machine Learning Engineer. Việc viết logic so sánh tự động (tính diff) giúp thấy ngay tác động (impact) của bất kỳ sự thay đổi nào.
3. **Về Resiliency:** Tool quan sát không được phép crash dù dữ liệu đang quan sát có tệ đến đâu.

### Nếu có thêm thời gian

Tôi sẽ thêm các kiểm tra phức tạp hơn: kiểm tra phân phối ngôn ngữ (language detection để bắt các văn bản không phải tiếng Anh), hoặc check độ đa dạng của vector embedding. Tôi cũng sẽ tích hợp các framework như Great Expectations để quản lý quality rules có hệ thống hơn là viết tay bằng Pandas.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này tập trung vào vai trò cá nhân, không sao chép nguyên văn báo cáo nhóm.

**Họ và tên:** Lê Trung Hiếu  
**Ngày xác nhận:** 2026-08-06
