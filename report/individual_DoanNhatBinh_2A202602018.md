# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đoàn Nhật Bình |
| MSSV | 2A202602018 |
| Khóa/Lớp | K3 / E403 |
| Tên nhóm | C11 |
| Vai trò chính | Integration & Evidence |
| Repository | https://github.com/Binhdn04/K3_Day10_Data-Pipeline-Data-Observability_E403_C11 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Baseline orchestration | `src/pipelines/phase1.py`, `main()` | Settings, raw records, các module ingestion/cleaning/retrieval/evaluation/observability | Clean artifacts, index, evaluation, quality/freshness và baseline report | Hoàn thành |
| Hugging Face integration | `_configure_huggingface_auth()` trong `phase1.py` | `HF_KEY` từ `.env` | `HF_TOKEN` được cấu hình trước khi tải embedding model | Hoàn thành |
| Integration evidence | `data/results/`, `data/quality/`, `data/reports/` | Artifact của baseline/corruption/repair | Metrics và kết luận đối chiếu | Hoàn thành |
| Group report | `report/group_report.md` | Code và artifact thực tế | Báo cáo nhóm khớp số liệu | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Module/thành viên được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra contract giữa các module | `core/config.py`, ingestion, evaluation, observability và retrieval | Đảm bảo pipeline dùng đúng các path trong `Settings.paths` và cùng test set |
| Kiểm tra kết quả ba trạng thái | `corruption_flow.py` và các artifact `data/results/`, `data/quality/` | Xác nhận corrupted giảm chất lượng và repaired phục hồi về baseline |
| Phân tích agent demo | `retrieval/qa.py`, `retrieval/agent.py`, `agent_demo_answers.json` | Ghi nhận lỗi matching title Unicode/markup thay vì kết luận agent đạt tuyệt đối |

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/hàm/artifact | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Điều phối baseline | `src/pipelines/phase1.py::main` | Pipeline đi qua load/fetch, clean, index, test set, evaluate, quality, freshness và report | `data/reports/phase1_report.md`, các file trong `data/` |
| Cache-aware raw ingestion | `_load_or_fetch_records()` | Dùng raw cache khi có và `REFRESH_SOURCE` chưa bật; fetch khi cần | `data/raw/crossref_records.json`, `source_summary` trong phase1 report |
| Persist clean artifacts | `_write_clean_artifacts()` | Ghi CSV và JSON từ cùng dataframe | `data/clean/papers_clean.csv/json` |
| Reuse evaluation set | `_ensure_test_set()` | Giữ `data/eval/test_set.json` ổn định nếu chưa bật `REFRESH_TEST_SET` | 12 samples được dùng trong cả ba metrics artifact |
| Build và evaluate baseline | `LocalEmbeddingIndex.build()`, `evaluate_pipeline()` | Collection `papers-baseline`, 24 documents, 12 câu hỏi | `baseline_metrics.json`, `papers_embeddings.json` |
| Tạo agent demo | `_run_agent_demo()` | 3 câu hỏi đại diện cho các question type, artifact có status từng câu | `data/results/agent_demo_answers.json` |
| Đối chiếu corruption/repair | `corruption_flow.py` và comparison artifacts | 24 → 23 → 24 rows; metrics 100% → 50% → 100% retrieval hit | `corruption_log.json`, `corruption_report.md` |
| Viết evidence report | `report/group_report.md` | Report không còn placeholder và khớp artifact | `git diff --check`, kiểm tra JSON/CSV/Markdown |

Output quan trọng nhất của phần integration là chuỗi bằng chứng nhất quán:

```text
baseline: 24 rows -> 12 questions -> 100% retrieval hit
corrupted: 23 rows -> same 12 questions -> 50% retrieval hit
repaired: 24 rows -> same 12 questions -> 100% retrieval hit
```

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module của bài lab có contract nối tiếp nhau: ingestion tạo `PaperRecord`, cleaning tạo dataframe có `text_for_embedding`, index cần đúng schema đó, evaluation cần index và test set, còn observability/reporting cần dataframe và metrics. Phần integration phải điều phối đúng thứ tự, dùng đúng path trong `Settings`, không làm thay đổi test set giữa baseline/corrupted/repaired và lưu đủ artifact để kết luận có thể kiểm tra lại.

### Cách triển khai

`phase1.py` thực hiện theo trình tự:

1. Gọi `load_settings()` để lấy cấu hình và toàn bộ đường dẫn artifact.
2. Dùng raw records đã lưu nếu có; nếu không hoặc refresh được bật thì gọi Crossref fetch.
3. Gọi `build_clean_dataframe(records, now_utc())`, dừng với lỗi rõ ràng nếu không có record hợp lệ.
4. Ghi clean dataframe ra CSV/JSON.
5. Build `LocalEmbeddingIndex` với manifest baseline, collection `papers-baseline` và Chroma persistence path.
6. Tạo test set nếu chưa có hoặc đọc lại test set hiện tại.
7. Gọi `evaluate_pipeline()` để ghi metrics và answers.
8. Chạy agent demo riêng, sau đó chạy quality checks, freshness report và phase report.

Trước khi build embedding, `_configure_huggingface_auth()` ánh xạ `HF_KEY` trong `.env` sang `HF_TOKEN` nếu `HF_TOKEN` chưa được cấu hình. Token giúp Hugging Face xác thực và tránh giới hạn tải ẩn danh; không ghi token vào artifact hoặc report.

`corruption_flow.py` giữ cùng integration contract cho ba trạng thái. Flow không sửa corrupted dataframe để tạo repaired dataframe; nó đọc raw snapshot, chạy lại cleaning, build collection repaired và evaluate trên cùng `test_set.json`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `Settings`, raw `PaperRecord` list, clean dataframe, `data/eval/test_set.json` |
| Output baseline | `data/clean/papers_clean.*`, `data/embeddings/papers_embeddings.json`, `data/results/baseline_*.json`, `data/quality/`, `data/reports/phase1_report.md` |
| Output corruption | `papers_clean_corrupted.*`, corrupted embeddings/metrics/answers, `corruption_log.json` |
| Output repair | `papers_clean_repaired.*`, repaired embeddings/metrics/answers, `corruption_report.md` |
| Module phụ thuộc | `core.config`, ingestion, retrieval, evaluation, observability |
| Module sử dụng output | `corruption_flow.py`, các report và bước review trước khi nộp |
| Điều kiện lỗi | Empty clean dataset, empty test set, thiếu baseline artifact, thiếu raw snapshot hoặc metrics không hợp lệ |

### Cách xác minh

```bash
uv sync
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

Các kiểm tra tĩnh đã thực hiện:

```bash
.venv\Scripts\python.exe -m py_compile src\pipelines\phase1.py
git diff --check
```

- **Kết quả mong đợi:** phase 1 tạo baseline artifacts; corruption flow tạo corrupted/repaired artifacts và comparison report.
- **Kết quả thực tế:** có đủ raw, clean, embedding, eval, results, quality và reports; baseline/corrupted/repaired lần lượt có 24/23/24 rows.
- **Artifact/log:** `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `data/results/corruption_log.json`, `data/quality/*.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Crossref là nguồn live, còn embedding và evaluation tốn thời gian; nếu mỗi lần chạy đều fetch hoặc tạo test set mới thì so sánh corruption không còn reproducible.
- **Các phương án đã cân nhắc:** (1) luôn fetch Crossref và luôn rebuild test set; (2) luôn chỉ đọc artifact cũ; (3) mặc định reuse cache/test set nhưng cho phép refresh bằng `REFRESH_SOURCE` và `REFRESH_TEST_SET`.
- **Phương án đã chọn:** phương án 3.
- **Lý do:** giữ được raw snapshot và test set ổn định để so sánh, nhưng vẫn hỗ trợ refresh chủ động khi cần cập nhật dữ liệu. Đây là cân bằng giữa reproducibility và khả năng cập nhật nguồn.
- **Bằng chứng:** baseline, corrupted và repaired đều đánh giá 12 samples từ `data/eval/test_set.json`; metrics thay đổi theo data state thay vì theo câu hỏi khác nhau.

Một quyết định liên quan là dùng các path từ `Settings.paths` thay vì hard-code trong pipeline. Nhờ đó output được phân biệt rõ theo collection/manifest: `papers-baseline`, `papers-corrupted` và `papers-repaired`.

## 6. Một lỗi hoặc blocker đã xử lý

### Blocker đã phân tích: agent demo không nhận diện một title

- **Triệu chứng:** trong `agent_demo_answers.json`, 3 câu hỏi đều có status `completed`, nhưng câu summary đầu tiên trả lời rằng không tìm thấy paper; câu authors và date của cùng paper vẫn trả lời được.
- **Bước tái hiện:** chạy phase 1 và kiểm tra câu `summary-001` trong `data/results/agent_demo_answers.json`.
- **Nguyên nhân gốc:** title chứa markup `<scp>` và ký tự Unicode đặc biệt. Exact lookup trong `LocalEmbeddingIndex.lookup()` dùng chuỗi lower-case trực tiếp; regex lấy title từ câu hỏi và title lưu trong index chưa được canonicalize thống nhất.
- **Cách xử lý hiện tại:** tách rõ agent demo khỏi deterministic evaluation; lưu câu trả lời và trạng thái đầy đủ để report không đánh đồng `deterministic_metadata_qa` với chất lượng tool-using agent. Không thay đổi metrics để che lỗi này.
- **Cách xác minh sau khi phân tích:** `baseline_metrics.json` vẫn ghi `retrieval_hit_rate = 1.0` trên 12 câu deterministic; `agent_demo_answers.json` ghi đúng 3 answer records và nội dung câu summary lỗi.
- **Điều học được:** một metric deterministic có thể đạt tuyệt đối trong khi exact-title interface của agent vẫn có edge case. Cần dùng cùng hàm chuẩn hóa Unicode/HTML ở ingestion, lookup và evaluation.

Đây là vấn đề chưa được sửa tận gốc trong phạm vi deliverable integration. Bước tiếp theo là thêm canonical title key, strip markup và test các title có Unicode trước khi kết luận agent demo đạt đầy đủ.

## 7. Hiểu biết về luồng end-to-end

1. **Từ Crossref đến vector index:** Crossref response được parse thành `PaperRecord`, lưu raw; cleaning loại record không hợp lệ, chuẩn hóa list/text, deduplicate DOI và tạo `text_for_embedding`; MiniLM encode text và Chroma lưu vector cùng metadata DOI/title.
2. **Evaluation set và ground truth:** test set chọn 4 document mới nhất và sinh 12 câu hỏi summary/authors/date. Mỗi câu giữ `ground_truth_doc_ids` là DOI của document đúng. Retrieval hit kiểm tra DOI đó có nằm trong top-k hay không; answer metrics so sánh prediction với ground truth.
3. **Quality checks và freshness khác nhau:** quality checks kiểm tra cấu trúc/nội dung như row count, null/duplicate ID, title và summary. Freshness kiểm tra thời gian: published date, stale rows và ngưỡng 180 ngày. Một dataset có thể có schema tốt nhưng vẫn stale, hoặc còn fresh nhưng chứa duplicate/summary rỗng.
4. **Lý do dùng cùng test set:** nếu test set thay đổi, chênh lệch metrics có thể do câu hỏi/ground truth khác chứ không phải corruption. Giữ nguyên test set làm comparison baseline-corrupted-repaired có ý nghĩa.
5. **Tiêu chí repair thành công:** repaired dataset phải trở lại 24 rows, pass 5/5 quality checks, có 0 stale rows và phục hồi metrics về baseline: retrieval hit 100%, token F1 1.0000, judge accuracy 100%, mean judge score 5.00.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 100.0% | 50.0% | 100.0% | Corruption làm mất hoặc làm hỏng context của các câu hỏi thuộc record bị tác động; repair phục hồi hoàn toàn. |
| `mean_token_f1` | 1.0000 | 0.4327 | 1.0000 | Nội dung summary/title bị lỗi làm lexical overlap giảm mạnh. |
| `judge_accuracy` | 100.0% | 50.0% | 100.0% | Judge phản ánh cùng xu hướng với retrieval và answer quality. |
| `mean_judge_score` | 5.00 | 3.25 | 5.00 | Corruption làm giảm 1.75 điểm trên thang 5; raw repair phục hồi đủ. |
| Quality checks | 5/5 pass | 0/5 pass | 5/5 pass | Observability phát hiện đồng thời thiếu dòng, duplicate, title, summary và freshness. |
| Freshness status | Fresh, 0 stale | Stale, 1 stale | Fresh, 0 stale | Ngày `1900-01-01` là tín hiệu stale rõ ràng và được repair từ raw. |

### Chuỗi nguyên nhân–bằng chứng

1. **Drop latest records + field corruption** → corrupted còn 23 rows, có duplicate/title/summary/stale failures → retrieval hit giảm 100% xuống 50%, token F1 giảm 1.0000 xuống 0.4327.
2. **Rebuild từ raw snapshot và chạy lại cleaning** → repaired có 24 rows, 5/5 quality checks, 0 stale rows → retrieval, F1, judge accuracy và judge score trở lại baseline.

Corruption có ảnh hưởng rõ nhất là nhóm thay đổi trực tiếp khả năng truy hồi: drop latest records làm mất document, còn blank summary/truncated title làm giảm thông tin trong context. Tuy nhiên không tách riêng được contribution của từng corruption bằng artifact hiện tại vì các mutation được chạy trong cùng một deterministic experiment; kết luận phù hợp nhất là về tác động tổng hợp của scenario.

Kết quả khác kỳ vọng là agent demo không đồng nhất với deterministic metrics: summary question đầu tiên bị false negative do title normalization, trong khi evaluation 12 câu vẫn đạt 100%. Artifact `agent_demo_answers.json` giúp phát hiện giới hạn interface này.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** orchestration chỉ đáng tin cậy khi các module dùng chung schema, path và thứ tự chạy rõ ràng; raw snapshot là đầu vào quan trọng cho reproducibility và repair.
2. **Về observability:** quality và freshness không chỉ là báo cáo sau cùng; chúng là tín hiệu sớm cho biết dataset có đủ dòng, đúng identity, nội dung hợp lệ và còn mới hay không.
3. **Về RAG agent:** retrieval/answer metrics có thể giảm mạnh khi dữ liệu lỗi dù code agent không thay đổi. Đồng thời cần phân biệt deterministic QA với agent demo thực tế, đặc biệt ở exact lookup và normalization.

### Nếu có thêm thời gian

Ưu tiên xây dựng một hàm canonicalization chung cho title: Unicode normalization, bỏ HTML/markup, chuẩn hóa whitespace và tạo lookup key. Sau đó thêm test cho title có `<scp>`, dấu gạch Unicode và biến thể khoảng trắng; đo lại tỉ lệ thành công của agent demo trên bộ edge cases trước/sau thay đổi.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này tập trung vào vai trò cá nhân, không sao chép nguyên văn báo cáo nhóm.

**Họ và tên:** Đoàn Nhật Bình  
**Ngày xác nhận:** 2026-08-06
