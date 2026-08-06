# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phan Bá Khánh Linh |
| MSSV | 2A202601989 |
| Khóa/Lớp | K3 |
| Tên nhóm | C11 |
| Vai trò chính | Source / Ingestion owner |
| Repository | https://github.com/Binhdn04/K3_Day10_Data-Pipeline-Data-Observability_E403_C11 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Source ingestion | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | `Settings` (`source_query`, `source_filter`, `max_results`) | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |

Các module còn lại của pipeline (`cleaning.py`, `testset.py`, `quality.py`, `reporting.py`, `corruption.py`, `phase1.py`, `corruption_flow.py`) do các thành viên khác trong nhóm phụ trách (theo lịch sử commit của repository). Báo cáo này chỉ nhận ownership cho phần Source Ingestion mà tôi trực tiếp thực hiện; các phần khác được mô tả ở Mục 7–8 dựa trên artifact thật do nhóm tạo ra, không phải phần tôi tự viết code.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Trao đổi schema `PaperRecord` (DOI dùng làm `paper_id`, định dạng ISO của `published`/`updated`) trước khi triển khai dedupe/`age_days` | `cleaning.py` (Nguyễn Minh Thu) | Thu xác nhận dedupe theo DOI case-insensitive và tính `age_days` đúng từ field `published` do ingestion cung cấp |
| Giải thích cấu trúc raw response (`data/raw/crossref_response.json`) và số lượng record gốc (24) khi thiết kế quality/freshness check | `quality.py` (Lê Trung Hiếu) | Hiếu dùng đúng 24 làm baseline kỳ vọng cho `row_count_check` |

Hai hoạt động trên là trao đổi kỹ thuật ở ranh giới ingestion → cleaning/observability, không phải sửa lỗi hay viết code cho module khác; không có artifact riêng để đối chiếu ngoài chính schema `PaperRecord` đã bàn giao.

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Gọi Crossref API với query/filter từ config, lưu raw response trước khi parse | `fetch_source_records` → `data/raw/crossref_response.json` | 24 items JSON gốc từ Crossref, chưa qua xử lý | Đọc file, đối chiếu `message.items` với params đã gửi |
| Parse payload thô thành `PaperRecord` (DOI làm `paper_id` ổn định) | `parse_crossref_payload` → `data/raw/crossref_records.json` | 24 `PaperRecord` với title/summary/authors/dates/urls đã chuẩn hóa | So khớp field-by-field với raw response thật (đã kiểm tra thủ công 3 item đầu) |
| Retry/backoff cho lỗi tạm thời | `_get_with_retry` (exponential backoff cho HTTP 429/503) | Không cần vì lần fetch thực tế trả 200 ngay | Đọc code, mô phỏng logic backoff |
| Nạp lại raw records từ snapshot (phục vụ repair) | `load_raw_records` | Reload đúng 24 record khớp với lần fetch gốc | Chạy lại `load_raw_records(...)`, so sánh số lượng với `fetch_source_records` |

Output cụ thể: `data/raw/crossref_records.json` là input trực tiếp cho bước Cleaning (`cleaning.py`) của thành viên khác, và là nguồn duy nhất được dùng để **repair** dữ liệu ở Pha 2 sau khi corruption — hai record bị `drop_latest_records` xóa khỏi bản sạch (`10.1111/exsy.70341`, `10.2118/234689-pa`) đã được phục hồi đúng nhờ đọc lại từ file này (`data/results/corruption_log.json`, `data/reports/corruption_report.md`).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Toàn bộ pipeline RAG cần một nguồn dữ liệu học thuật thật, có định danh ổn định để mọi bước sau (cleaning, embedding, evaluation, corruption/repair) có thể tham chiếu ngược lại. Phần của tôi giải quyết đúng bước đầu của luồng: lấy dữ liệu từ Crossref, chuẩn hóa về một schema nhất quán, và lưu lại raw artifact để đảm bảo có thể truy vết/khôi phục sau này.

### Cách triển khai

- Dùng DOI trực tiếp làm `paper_id` vì DOI là định danh do Crossref/nhà xuất bản cấp, duy nhất và không đổi — tránh phải tự sinh ID có thể trùng hoặc đổi theo lần fetch.
- Lưu raw response **trước** khi parse (`write_json` vào `data/raw/crossref_response.json`), sau đó mới parse và lưu records — đúng thứ tự đề bài yêu cầu để phục vụ truy vết.
- Loại bỏ record thiếu DOI/title/abstract ngay khi parse để các bước sau không phải xử lý dữ liệu rỗng.
- Retry với exponential backoff, chỉ áp dụng cho `429`/`503`; lỗi HTTP khác (4xx/5xx còn lại) raise ngay để tránh retry vô ích khi request sai cấu trúc.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `Settings.source_query`, `Settings.source_filter`, `Settings.max_results` (đọc từ `.env`/config, không hard-code) |
| Output | `list[PaperRecord]` với 11 field: `paper_id, title, summary, authors, categories, primary_category, published, updated, abs_url, pdf_url, comment` |
| Module phụ thuộc | `core.config.Settings`, `core.utils` (`write_json`, `read_json`, `normalize_whitespace`, `compact_join`) |
| Module sử dụng output | `ingestion.cleaning.build_clean_dataframe` (đọc trực tiếp `list[PaperRecord]`) |
| Điều kiện lỗi cần xử lý | HTTP 429/503 (retry), record thiếu DOI/title/abstract (loại bỏ), field `subject`/`link` không tồn tại trong payload (fallback về rỗng, không crash) |

### Cách xác minh

```bash
.venv/Scripts/python.exe -c "
from core.config import load_settings
from ingestion.crossref import fetch_source_records, load_raw_records
settings = load_settings()
records = fetch_source_records(settings)
reloaded = load_raw_records(settings.paths.raw_records_json)
print(len(records), len(reloaded))
"
```

- **Kết quả mong đợi:** Fetch được tối đa `max_results` (24) record hợp lệ, `load_raw_records` reload đúng số lượng đã lưu.
- **Kết quả thực tế:** 24/24 record fetch thành công, reload khớp 24/24.
- **Artifact/log:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (không chứa secret, chỉ chứa metadata công khai từ Crossref).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Trường `link[].content-type` của Crossref được kỳ vọng ghi `"application/pdf"` khi có bản PDF, nhưng khi kiểm tra trên payload thật, nhiều publisher gắn `content-type: "unspecified"` dù URL rõ ràng là PDF (ví dụ kết thúc bằng `/pdf/.../v1`).
- **Các phương án đã cân nhắc:**
  1. Giữ nguyên lọc chặt theo đúng chuẩn schema Crossref (`content-type == "application/pdf"`).
  2. Mở rộng điều kiện: khớp `content-type` chuẩn **hoặc** URL có chứa chuỗi `"pdf"`.
- **Phương án đã chọn:** Phương án 2 (mở rộng theo URL).
- **Lý do:** Ưu tiên độ chính xác dữ liệu thực tế hơn là bám cứng vào tài liệu chuẩn schema, vì metadata do publisher tự khai báo không đồng nhất.
- **Bằng chứng quyết định phù hợp:** Đo trên đúng 24 item đã fetch — lọc chặt chỉ bắt được `pdf_url` cho 8/24 record, lọc mở rộng bắt được 12/24 (tăng 50%). Đã regenerate `data/raw/crossref_records.json` sau khi sửa để artifact khớp với logic mới nhất.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `pdf_url` bị rỗng ở nhiều record dù `item["link"]` trong raw response thật có chứa URL PDF hợp lệ.
- **Lệnh hoặc bước tái hiện:** Parse trực tiếp `data/raw/crossref_response.json` đã lưu, đếm số record có `link` khác rỗng và số record `pdf_url` khác rỗng sau parse — thấy chênh lệch lớn (16/24 item có `link`, nhưng chỉ 8/24 ra được `pdf_url`).
- **Nguyên nhân gốc:** Điều kiện lọc `content-type == "application/pdf"` quá chặt so với thực tế: 15/24 link entries có `content-type: "unspecified"`, trong đó nhiều link vẫn là PDF thật.
- **Cách xử lý:** Thêm điều kiện phụ kiểm tra chuỗi `"pdf"` trong URL khi `content-type` không khớp chuẩn.
- **Cách xác minh sau khi sửa:** Parse lại đúng `crossref_response.json` cũ (không fetch lại API) — số record có `pdf_url` tăng từ 8/24 lên 12/24; regenerate lại `crossref_records.json`.
- **Điều học được:** Không thể tin tuyệt đối vào field metadata "chuẩn" của một API công khai — luôn phải đối chiếu logic parse với vài chục record thật trước khi coi là hoàn thành, vì cách publisher khai báo metadata không đồng nhất.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?** `fetch_source_records` gọi Crossref API theo query/filter cấu hình, lưu raw response và raw records vào `data/raw/`. Bước Cleaning đọc `PaperRecord` từ đây, chuẩn hóa title/summary/authors, tính `age_days`, tạo `text_for_embedding`, ghi vào `data/clean/`. Bước embedding (`LocalEmbeddingIndex`) đọc dataframe sạch, sinh embedding bằng MiniLM và nạp vào collection ChromaDB (`papers-baseline`/`papers-corrupted`/`papers-repaired` tùy trạng thái).
2. **Evaluation set và ground-truth doc IDs dùng để đo gì?** Test set (`data/eval/test_set.json`) tạo câu hỏi theo 4 loại (`summary`, `authors`, `date`, `categories`) từ chính dữ liệu sạch, mỗi câu hỏi gắn `ground_truth_doc_ids` là `paper_id` (DOI) thật của record nguồn. Khi agent trả lời, hệ thống so khớp document được retrieve với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và so khớp câu trả lời với `ground_truth` để tính `mean_token_f1`/`judge_accuracy`.
3. **Quality checks khác freshness monitoring ở điểm nào?** Quality checks (`row_count_check`, `paper_id_null_and_unique`, `title_not_null_or_empty`, `summary_validity`, `freshness_check`) đánh giá tính đúng đắn/toàn vẹn của schema tại một thời điểm dữ liệu; freshness monitoring cụ thể đo độ "cũ" của dữ liệu dựa trên `published`/`age_days` so với ngưỡng ngày, cho biết dữ liệu còn cập nhật hay đã lỗi thời — hai tín hiệu độc lập, có thể pass quality nhưng fail freshness hoặc ngược lại.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?** Vì mục tiêu là đo tác động của **thay đổi dữ liệu**, không phải thay đổi độ khó câu hỏi. Nếu đổi test set giữa các trạng thái, chênh lệch số liệu (`retrieval_hit_rate`, `judge_accuracy`...) không còn phản ánh đúng nguyên nhân do corruption/repair mà có thể do câu hỏi khác nhau.
5. **Repair thành công dựa trên artifact/metric nào?** Dựa trên `data/results/repaired_metrics.json` (khôi phục lại `retrieval_hit_rate = 1.0`, `judge_accuracy = 1.0`, `mean_judge_score = 5` — đúng bằng baseline) và `data/quality/repaired.json`/freshness report (quality checks pass lại 5/5, freshness trở lại `IS FRESH`). Vì repair đọc lại từ `data/raw/crossref_records.json` (raw records tôi phụ trách lưu), quá trình khôi phục có nguồn đáng tin để đối chiếu, không phải sửa tay kết quả.

## 8. Phân tích kết quả

### Metrics chính

(Nguồn: `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md`)

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0 | 0.5 | 1.0 | Giảm đúng 50% khi 2/24 record bị `drop_latest_records` xóa khỏi index — các câu hỏi trỏ tới 2 paper đó không còn tài liệu để retrieve |
| `mean_token_f1` | 1.0000 | 0.4327 | 1.0000 | Giảm gần một nửa, khớp hướng với retrieval hit rate — câu trả lời mất ngữ cảnh do thiếu record/blank summary |
| `judge_accuracy` | 1.0 | 0.5 | 1.0 | Giảm đúng bằng retrieval hit rate — cho thấy trong bài lab này judge phụ thuộc chặt vào việc có retrieve đúng tài liệu hay không |
| `mean_judge_score` | 5 / 5.0 | 3.25 / 5.0 | 5 / 5.0 | Phục hồi hoàn toàn sau repair, không chỉ pass/fail mà cả điểm số trung bình |
| Quality checks | 5 / 5 | 0 / 5 | 5 / 5 | Corruption làm fail toàn bộ 5 check cùng lúc (row_count, paper_id unique, title, summary, freshness) — cho thấy các corruption đã tạo đủ đa dạng để chạm mọi check |
| Freshness status | IS FRESH | STALE | IS FRESH | Do `stale_published_date` cố ý đẩy 1 record về `1900-01-01`, kéo cả bộ dữ liệu sang trạng thái STALE |

### Kết luận từ số liệu

1. **Data corruption → quality/freshness signal thay đổi → agent metric thay đổi:** `drop_latest_records` (xóa 2 record mới nhất) + `blank_summary` (1 record) làm `row_count_check` và `summary_validity` fail → `retrieval_hit_rate` giảm từ 1.0 xuống 0.5 vì đúng 2 câu hỏi test set không còn tài liệu nguồn để retrieve.
2. **Repair action → quality/freshness signal phục hồi → agent metric phục hồi:** Repair đọc lại từ `data/raw/crossref_records.json` (24 record gốc, không sửa tay) → quality checks trở lại 5/5, freshness trở lại `IS FRESH` → toàn bộ 4 metric agent (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`) phục hồi đúng bằng baseline.

**Corruption ảnh hưởng rõ nhất:** `drop_latest_records` — vì nó xóa thẳng 2/24 tài liệu khỏi index, nên bất kỳ câu hỏi nào có `ground_truth_doc_ids` trỏ tới 2 DOI đó chắc chắn miss ở bước retrieval, kéo theo miss luôn ở bước đánh giá câu trả lời (retrieval hit rate và judge accuracy giảm cùng tỷ lệ 50%, không lệch nhau).

**Kết quả khác kỳ vọng:** `judge_accuracy` giảm đúng bằng `retrieval_hit_rate` (cả hai đều 0.5) — ban đầu tôi nghĩ hai chỉ số này sẽ lệch nhau vì judge đánh giá nội dung câu trả lời còn retrieval chỉ đánh giá việc tìm đúng tài liệu. Số liệu cho thấy ở answer mode `deterministic_metadata_qa`, hai chỉ số gắn rất chặt với nhau vì câu trả lời phụ thuộc hoàn toàn vào tài liệu retrieve được — đây là điểm cần lưu ý khi diễn giải kết quả, không kết luận rằng judge đang đánh giá độc lập với retrieval.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Lưu raw response trước khi parse không chỉ là yêu cầu hình thức — nó thực sự là thứ duy nhất cho phép repair chạy đúng ở Pha 2, vì repair không "sửa" dữ liệu lỗi mà đọc lại từ raw để tái tạo từ đầu.
2. **Về data quality/observability:** Field metadata của một API công khai (như `content-type`, `subject`) không đáng tin 100% theo tài liệu — phải validate logic parse trên vài chục record thật trước khi coi là "đúng chuẩn".
3. **Về ảnh hưởng dữ liệu đến RAG agent:** Chỉ cần corrupt 2-3 trong 24 record (dưới 15% dữ liệu) đã đủ để kéo `retrieval_hit_rate` và `judge_accuracy` giảm 50% — chất lượng dữ liệu đầu vào ảnh hưởng phi tuyến (không tỷ lệ thuận theo % record lỗi) đến chất lượng agent.

### Nếu có thêm thời gian

Viết thêm unit test cho `parse_crossref_payload` với các payload giả lập thiếu field (`subject`, `link`, `published-print`) để đảm bảo hàm không crash khi Crossref trả về item thiếu metadata — đo cải thiện bằng số test case pass trên các payload biên đã liệt kê ở Mục 4 (điều kiện lỗi cần xử lý).

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phan Bá Khánh Linh
**Ngày xác nhận:** 2026-08-06
