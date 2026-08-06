# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K3 / E403 |
| Tên nhóm | C11 |
| Repository | https://github.com/Binhdn04/K3_Day10_Data-Pipeline-Data-Observability_E403_C11 |
| Ngày hoàn thành | 2026-08-06 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable |
| ---: | --- | --- | --- | --- |
| 1 | Phan Bá Khánh Linh | 2A202601989 | Source ingestion | `src/ingestion/crossref.py` |
| 2 | Nguyễn Minh Thu | 2A202601631 | Cleaning và evaluation set | `cleaning.py`, `testset.py` |
| 3 | Lê Trung Hiếu | 2A202601917 | Observability và reporting | `quality.py`, `reporting.py` |
| 4 | Bùi Duy Hải | 2A202601878 | Corruption và repair | `corruption.py`, `corruption_flow.py` |
| 5 | Đoàn Nhật Bình | 2A202602018 | Integration và evidence | `phase1.py`, `group_report.md` |

## 2. Tóm tắt kết quả

Nhóm xây dựng và chạy một pipeline dữ liệu cho corpus bài báo học thuật từ Crossref. Pipeline lưu raw response và raw records, làm sạch thành 24 tài liệu hợp lệ, tạo `text_for_embedding`, lập chỉ mục Chroma bằng `sentence-transformers/all-MiniLM-L6-v2`, rồi đánh giá trên 12 câu hỏi deterministic metadata QA. Baseline đạt `retrieval_hit_rate = 1.0`, `mean_token_f1 = 1.0`, `judge_accuracy = 1.0` và `mean_judge_score = 5/5`. Quality baseline đạt 5/5 checks; toàn bộ 24 dòng còn fresh trong ngưỡng 180 ngày.

Nhóm tiếp tục tạo corruption có kiểm soát: xóa 2 record mới nhất, làm rỗng summary, thêm noise, cắt ngắn title, đặt một ngày xuất bản về 1900 và thêm duplicate. Dataset corrupted còn 23 dòng, fail cả 5 quality checks, có 1 stale row. Hiệu năng giảm rõ rệt: retrieval hit rate từ 100% xuống 50% và token F1 từ 1.0000 xuống 0.4327. Repair được tạo lại từ raw records thay vì sửa trực tiếp dữ liệu lỗi; kết quả phục hồi 24 dòng, 5/5 checks, freshness và toàn bộ metrics về đúng baseline. Ragas không chạy vì được cấu hình skip. Agent demo gọi thành công 3 câu hỏi, nhưng câu summary đầu tiên gặp lỗi matching title do markup/Unicode trong title; đây là giới hạn khác với deterministic QA.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref REST API
    -> data/raw/crossref_response.json
    -> data/raw/crossref_records.json
    -> cleaning và deduplication
    -> data/clean/papers_clean.csv/json
    -> MiniLM embeddings + ChromaDB cosine index
    -> data/embeddings/ và data/chroma/
    -> test set dùng chung
    -> baseline evaluation
    -> quality/freshness reports
    -> deterministic corruption
    -> corrupted evaluation
    -> repair lại từ raw records
    -> repaired evaluation và comparison report
```

| Khối | Input | Xử lý chính | Output | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref `/works` | Query, filter, retry tối đa 5 lần với backoff cho HTTP 429/503, parse schema | `data/raw/` | Phan Bá Khánh Linh |
| Cleaning | Raw `PaperRecord` | Chuẩn hóa text/list, loại record thiếu ID/title/summary/date, deduplicate DOI | `data/clean/` | Nguyễn Minh Thu |
| Embedding/index | Clean dataframe | MiniLM normalized embeddings, Chroma cosine, collection riêng cho từng trạng thái | `data/embeddings/`, `data/chroma/` | Đoàn Nhật Bình |
| Evaluation | Clean index và test set | Retrieval, deterministic answer, token F1, judge metrics | `data/results/*_metrics.json`, `*_answers.json` | Nguyễn Minh Thu / Đoàn Nhật Bình |
| Observability | Clean/corrupted/repaired dataframe | Row count, ID uniqueness, title, summary, freshness | `data/quality/` | Lê Trung Hiếu |
| Corruption/repair | Baseline clean và raw snapshot | Corrupt có log, rebuild clean từ raw, đánh giá lại | `corruption_log.json`, comparison report | Bùi Duy Hải |
| Orchestration | Settings và module contracts | Điều phối phase 1 và corruption flow | Metrics/reports end-to-end | Đoàn Nhật Bình |

## 4. Cấu hình và cách tái hiện

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị thực tế |
| --- | --- |
| `LLM_PROVIDER` trong agent demo | `openai` |
| `LLM_MODEL` trong agent demo | `gpt-4o-mini` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Crossref query | `agentic retrieval augmented generation large language model` |
| Crossref filter | `from-pub-date:2026-02-07,has-abstract:true` |
| Số record tối đa | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày |
| Ragas | Không chạy; artifact ghi rõ `RUN_RAGAS=1` để bật |

Không đưa API key, token hoặc nội dung `.env` vào report.

### Lệnh tái hiện

```bash
uv sync
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

Các artifact chính đã có trong repository:

- `data/raw/crossref_response.json`, `crossref_records.json`
- `data/clean/papers_clean*.csv/json`
- `data/embeddings/papers_embeddings*.json` và `data/chroma/`
- `data/eval/test_set.json`
- `data/results/*_metrics.json`, `*_answers.json`, `corruption_log.json`
- `data/quality/*.json`
- `data/reports/phase1_report.md`, `corruption_report.md`

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API, endpoint `https://api.crossref.org/works` |
| Query/filter | Query agentic RAG/LLM; chỉ lấy record có abstract và trong 180 ngày gần thời điểm chạy |
| Raw records | 24 |
| Clean records | 24 |
| Retry/backoff | Retry HTTP 429/503 và lỗi request; tối đa 5 lần, exponential backoff bắt đầu 1 giây |

### Raw schema

`PaperRecord` gồm: `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `abs_url`, `pdf_url`, `comment`.

Parser loại record thiếu DOI, title hoặc abstract; loại HTML trong abstract; chuẩn hóa whitespace; trích xuất ngày từ các trường Crossref; chọn URL PDF nếu có.

### Clean schema và quy tắc

Clean dataset có 17 cột: các trường raw chính, `authors_joined`, `categories_joined`, `summary_chars`, `age_days` và `text_for_embedding`. Cleaning:

1. Loại record thiếu `paper_id`, `title`, `summary` hoặc ngày `published` không hợp lệ.
2. Chuẩn hóa text và list, loại phần tử trùng nhưng giữ thứ tự.
3. Deduplicate `paper_id` không phân biệt hoa thường; giữ bản có `updated` mới hơn.
4. Tính `age_days` từ ngày chạy và ngày published, không cho giá trị âm.
5. Tạo text embedding theo thứ tự Title, Authors, Categories, Published, Abstract.

`paper_id` là DOI và là document identity. Chroma dùng record id dạng `{paper_id}::{row_index}`; metadata vẫn giữ DOI để kiểm tra retrieval hit.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 12 |
| Document được chọn | 4 bài mới nhất trong clean dataframe |
| Question types | `summary` 4, `authors` 4, `date` 4 |
| Ground truth document ID | DOI của bài tương ứng |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | ChromaDB, cosine distance |
| Collection baseline | `papers-baseline` |
| Retrieval `top_k` | 4 |
| Answer mode | `deterministic_metadata_qa` |
| Test set dùng chung | `data/eval/test_set.json` cho baseline/corrupted/repaired |

Test set được giữ nguyên để mọi thay đổi metrics phản ánh thay đổi dữ liệu/index thay vì thay đổi câu hỏi hoặc ground truth. Ragas được để skip trong run này nên không được diễn giải là một score Ragas thực tế.

## 7. Kết quả baseline

| Artifact | Trạng thái | Evidence |
| --- | --- | --- |
| Raw response/records | Có | `data/raw/` |
| Cleaned dataset | Có | `data/clean/papers_clean.csv/json` |
| Embedding manifest/index | Có | `data/embeddings/papers_embeddings.json`, `data/chroma/` |
| Evaluation set | Có | `data/eval/test_set.json` |
| Baseline metrics | Có | `data/results/baseline_metrics.json` |
| Quality/freshness | Có | `data/quality/baseline.json`, `freshness_report.json` |
| Baseline report | Có | `data/reports/phase1_report.md` |

| Metric | Baseline | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0000 (100%) | 12/12 câu truy hồi đúng DOI |
| `mean_token_f1` | 1.0000 | Prediction trùng ground truth theo token set |
| `judge_accuracy` | 1.0000 (100%) | Tất cả câu được judge là đúng |
| `mean_judge_score` | 5.00 / 5 | Điểm trung bình cao nhất |
| `ragas` | Skipped | Chưa bật `RUN_RAGAS=1` |

## 8. Data quality và freshness

### Baseline và repair

- Baseline: 24 dòng, **5/5 checks pass**.
- Repaired: 24 dòng, **5/5 checks pass**.
- Cả hai trạng thái đều có 0 null/blank ID, 0 duplicate DOI, 0 title bị truncate, 0 summary lỗi và 0 stale row.

### Corrupted

| Check | Kết quả corrupted | Bằng chứng |
| --- | --- | --- |
| Row count | Fail: 23 thay vì 24 | `data/quality/corrupted.json` |
| ID null/unique | Fail: 1 duplicate | `data/quality/corrupted.json` |
| Title validity | Fail: 1 truncation marker | `data/quality/corrupted.json` |
| Summary validity | Fail: 1 empty, 1 short, 1 noise | `data/quality/corrupted.json` |
| Freshness | Fail: 1 stale row | `freshness_corrupted.json` |

Freshness baseline/repaired: latest `2026-08-01`, oldest `2026-02-12`, stale `0/24`, status fresh. Corrupted: oldest `1900-01-01`, stale `1/23`, status stale.

## 9. Corruption scenarios và repair

| Corruption | Số record/tác động | Quality signal | Repair |
| --- | ---: | --- | --- |
| Drop latest records | Xóa 2 record mới nhất | Row count giảm 24 → 23; ảnh hưởng các tài liệu test mới nhất | Rebuild từ raw records |
| Blank summary | 1 | Empty/short summary | Rebuild từ raw |
| Inject summary noise | 1 | Noise marker trong summary | Rebuild từ raw |
| Truncate title | 1 | Title truncation marker | Rebuild từ raw |
| Stale published date | 1, đổi thành `1900-01-01` | Freshness stale | Rebuild từ raw |
| Duplicate record | Thêm 1 bản sao | Duplicate `paper_id` | Rebuild và deduplicate từ raw |

`data/results/corruption_log.json` ghi `deterministic: true`, input 24 rows, output 23 rows và đầy đủ affected IDs/parameters cho 6 event. Repair không chỉnh trực tiếp dataframe corrupted; flow đọc raw snapshot, chạy lại cleaning với run date baseline và build lại index/metrics.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Impact | Recovery |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 100.0% | 50.0% | 100.0% | -50.0 điểm % | +50.0 điểm % |
| `mean_token_f1` | 1.0000 | 0.4327 | 1.0000 | -0.5673 | +0.5673 |
| `judge_accuracy` | 100.0% | 50.0% | 100.0% | -50.0 điểm % | +50.0 điểm % |
| `mean_judge_score` | 5.00 | 3.25 | 5.00 | -1.75 | +1.75 |
| Quality checks | 5/5 pass | 0/5 pass | 5/5 pass | Tất cả checks fail | Phục hồi toàn bộ |
| Freshness | Fresh, 0 stale | Stale, 1 stale | Fresh, 0 stale | Fresh → stale | Stale → fresh |

Hai kết luận nhân quả được artifact hỗ trợ:

1. Xóa và làm hỏng các trường của record làm thiếu tài liệu/giảm chất lượng context; đồng thời quality gates phát hiện row count, duplicate, title, summary và freshness lỗi. Cùng test set, retrieval hit rate giảm 50 điểm phần trăm và token F1 giảm 0.5673.
2. Repair từ raw snapshot phục hồi đúng số dòng, uniqueness, nội dung và ngày xuất bản; quality/freshness trở lại pass/fresh và cả bốn metrics trở lại đúng baseline.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** deterministic QA đạt 12/12, nhưng agent demo có một câu summary không tìm thấy paper `Hi-RAG`; hai câu hỏi còn lại của demo trả lời được.
- **Nguyên nhân:** title trong dữ liệu chứa markup như `<scp>` và ký tự Unicode đặc biệt. Regex/exact lookup trong `retrieval/qa.py` và `LocalEmbeddingIndex.lookup()` chưa có bước chuẩn hóa title tương đương ở cả hai phía.
- **Cách xử lý hiện tại:** vẫn lưu đầy đủ demo artifact và tách rõ deterministic QA khỏi tool-using agent demo; không dùng demo 3 câu để thay thế metrics 12 câu.
- **Cải thiện đề xuất:** chuẩn hóa Unicode, strip HTML/markup, collapse whitespace và dùng normalized title key trước exact lookup; bổ sung test cho title có Unicode/markup.

## 12. Giới hạn và hướng cải thiện

| Giới hạn | Ảnh hưởng | Cải thiện kiểm chứng được |
| --- | --- | --- |
| Corpus chỉ có 24 Crossref records | Metrics chưa đại diện cho corpus lớn | Chạy nhiều batch/query và theo dõi metrics theo snapshot |
| Test set chỉ có 12 câu, lấy từ 4 bài đầu | Có thể bị overfit vào các record mới nhất | Mở rộng câu hỏi, thêm negative cases và exact-title edge cases |
| Ragas đang skipped | Chưa có context precision/recall và faithfulness | Bật `RUN_RAGAS=1`, lưu version/model và thời gian chạy |
| Deterministic QA lấy metadata trực tiếp | Không phản ánh đầy đủ hành vi LLM production | Đánh giá thêm agent trên bộ câu hỏi độc lập và kiểm tra citation |
| Title normalization chưa đồng nhất | Agent demo có false negative khi title có markup | Dùng một hàm canonicalization chung cho ingestion, lookup và test |
| Crossref là nguồn live | Các lần chạy sau có thể khác record/ngày | Lưu raw snapshot, query/filter và timestamp; so sánh trong cùng snapshot |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm, repository và phân công đã ghi rõ.
- [x] Raw, clean, embedding, evaluation, quality, results và reports đều có artifact.
- [x] Baseline/corrupted/repaired dùng cùng `data/eval/test_set.json`.
- [x] Metrics trong report khớp `data/results/*_metrics.json`.
- [x] Quality/freshness conclusions khớp `data/quality/*.json`.
- [x] Corruption log ghi đủ 6 scenario và repair từ raw snapshot.
- [x] Report nêu rõ Ragas chưa chạy và giới hạn agent demo.
- [x] Không đưa secret, API key hoặc token vào report.
- [ ] Các individual report riêng của từng thành viên cần được kiểm tra trước khi nộp nhóm.
