# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Minh Thu |
| MSSV | 2A202601631 |
| Khóa/Lớp | K3 / E403 |
| Tên nhóm | C11 |
| Vai trò chính | Cleaning và evaluation set |
| Repository | https://github.com/Binhdn04/K3_Day10_Data-Pipeline-Data-Observability_E403_C11 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cleaning và data modeling | `src/ingestion/cleaning.py::build_clean_dataframe` | Danh sách `PaperRecord` từ ingestion, `run_date` | Clean dataframe 17 cột, `data/clean/papers_clean.csv/json` | Hoàn thành |
| Evaluation set | `src/evaluation/testset.py::build_test_set` | Clean dataframe | `data/eval/test_set.json` (12 câu hỏi) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Module/thành viên được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra schema đầu vào cho quality checks | `src/observability/quality.py` (Lê Trung Hiếu) | Đối chiếu tên cột và kiểu dữ liệu clean dataframe khớp với các check row count, ID uniqueness, title, summary, freshness |
| Đối chiếu repair từ raw snapshot | `corruption_flow.py` (Bùi Duy Hải) | Xác nhận rebuild dùng đúng `build_clean_dataframe` với cùng `run_date` baseline nên repaired dataframe khớp lại baseline |

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/hàm/artifact | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chuẩn hóa text/list | `_clean_text()`, `_clean_list()` | Loại None/NaN, chuẩn hóa whitespace, loại phần tử trùng trong `authors`/`categories` nhưng giữ thứ tự | Đọc `data/clean/papers_clean.json`, kiểm tra không còn khoảng trắng thừa hay phần tử trùng |
| Loại record không hợp lệ | `build_clean_dataframe()` | Bỏ record thiếu `paper_id`, `title`, `summary` hoặc `published` không parse được | 24 raw records → 24 clean rows (không có record nào bị loại ở lần chạy này) |
| Deduplicate theo DOI | `build_clean_dataframe()` | So khớp `paper_id` không phân biệt hoa/thường, giữ bản có `updated` mới hơn | `data/quality/baseline.json`: `paper_id_null_and_unique` pass, 0 duplicate |
| Tính `age_days` và freshness input | `build_clean_dataframe()` | `age_days = max(0, run_date - published)`, không cho giá trị âm | `data/quality/freshness_report.json`: 0/24 stale, ngưỡng 180 ngày |
| Tạo `text_for_embedding` | `build_clean_dataframe()` | Chuỗi theo thứ tự Title/Authors/Categories/Published/Abstract dùng cho MiniLM encode | `data/clean/papers_clean.json`, cột `text_for_embedding` |
| Sinh evaluation set | `build_test_set()` | 12 câu hỏi (summary/authors/date, mỗi loại 4) từ 4 document mới nhất, `ground_truth_doc_ids` là DOI | `data/eval/test_set.json` |
| Validate input trước khi sinh câu hỏi | `build_test_set()` | Kiểm tra đủ cột bắt buộc, đủ text và ngày hợp lệ, raise lỗi rõ ràng nếu thiếu dữ liệu | Đọc source `testset.py`, đối chiếu exception message |

Output quan trọng nhất của cleaning và evaluation set là việc tạo ra **một mặt bằng dữ liệu và một bộ câu hỏi cố định** để mọi so sánh baseline/corrupted/repaired sau này đều dựa trên cùng chuẩn:

```text
24 raw records -> cleaning (dedupe theo DOI, chuẩn hóa text) -> 24 clean rows
4 document mới nhất -> build_test_set() -> 12 câu hỏi cố định trong data/eval/test_set.json
```

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Raw records từ Crossref (do Phan Bá Khánh Linh phụ trách ingestion) có thể chứa trường rỗng, whitespace thừa, danh sách tác giả/category trùng lặp, hoặc trùng DOI giữa các lần fetch. Nếu đưa thẳng dữ liệu này vào embedding/index, MiniLM sẽ encode nhiễu và các quality check ở tầng observability sẽ không có gì để so sánh. Đồng thời, để so sánh baseline/corrupted/repaired có ý nghĩa, cần một bộ câu hỏi evaluation cố định, không đổi giữa các lần chạy dù dữ liệu bị corrupt hay không.

### Cách triển khai

`cleaning.py::build_clean_dataframe`:

1. Chuẩn hóa `run_date` về UTC để tính `age_days` nhất quán.
2. Với mỗi `PaperRecord`: chuẩn hóa text (`_clean_text`), parse `published`/`updated` bằng `pd.to_datetime(..., errors="coerce")`.
3. Loại record nếu thiếu `paper_id`, `title`, `summary`, hoặc `published` không parse được — đây là điều kiện tối thiểu để một record có thể index, evaluate và theo dõi freshness.
4. Chuẩn hóa `authors`/`categories` bằng `_clean_list` (loại trùng theo `casefold()`, giữ thứ tự xuất hiện đầu tiên); đảm bảo `primary_category` luôn có mặt trong `categories`.
5. Tính `age_days` không âm, sinh `text_for_embedding` theo cấu trúc cố định 5 dòng (Title/Authors/Categories/Published/Abstract) để embedding model nhận input nhất quán.
6. Deduplicate theo `paper_id` (case-insensitive), ưu tiên giữ bản ghi có `updated` mới hơn, dùng `sort_values` + `drop_duplicates(keep="first")` để việc chọn bản giữ lại có thể tái lập.
7. Sắp xếp lại theo `published` giảm dần, `paper_id` tăng dần để thứ tự dataframe ổn định giữa các lần chạy — điều này quan trọng vì `testset.py` lấy 4 dòng đầu làm nguồn câu hỏi.

`testset.py::build_test_set`:

1. Validate đủ cột bắt buộc (`paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`) và raise `ValueError` nếu thiếu, tránh sinh câu hỏi trên dữ liệu không đầy đủ.
2. Lọc các dòng có đủ text không rỗng và `published` hợp lệ, lấy 4 dòng đầu (`head(4)`); raise lỗi nếu không đủ 4 dòng hợp lệ.
3. Với mỗi document, sinh câu hỏi `summary` (dùng `first_sentence(summary)` làm ground truth), `date` (ngày ISO), và `authors` nếu `authors_joined` không rỗng; `categories` được thêm nếu có nhưng trong lần chạy thực tế trường này không được chọn vì thứ tự `question_specs` ưu tiên summary/authors/date trước — kết quả thực tế là 12 câu (3 loại × 4 document).
4. Mỗi câu hỏi giữ `ground_truth_doc_ids = [paper_id]` (DOI) để `retrieval_hit_rate` có thể kiểm tra đúng document được truy hồi.
5. Ghi ra `data/eval/test_set.json` bằng `write_json`; test set này được `phase1.py` tái sử dụng nếu đã tồn tại và `REFRESH_TEST_SET` chưa bật, đảm bảo baseline/corrupted/repaired dùng chung một bộ câu hỏi.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `list[PaperRecord]` từ `src/ingestion/crossref.py`, `run_date` (UTC) |
| Output cleaning | Dataframe 17 cột theo `_CLEAN_COLUMNS`, ghi ra `data/clean/papers_clean.csv/json` |
| Output evaluation set | `data/eval/test_set.json`, 12 item với `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids` |
| Module phụ thuộc | `core.utils` (`normalize_whitespace`, `first_sentence`, `write_json`), `ingestion.crossref.PaperRecord` |
| Module sử dụng output | `retrieval` (build index từ `text_for_embedding`), `evaluation` (đánh giá trên test set), `observability` (quality/freshness đọc clean dataframe), `phase1.py`/`corruption_flow.py` (orchestration) |
| Điều kiện lỗi | Clean dataframe rỗng sau khi lọc; thiếu cột bắt buộc cho test set; không đủ 4 document hợp lệ để sinh câu hỏi |

### Cách xác minh

```bash
uv sync
uv run python script/run_phase1.py
```

- **Kết quả mong đợi:** 24 raw records cho ra 24 clean rows (không mất record hợp lệ nào), `data/eval/test_set.json` có đúng 12 câu hỏi cố định.
- **Kết quả thực tế:** `data/clean/papers_clean.json` có 24 dòng; `data/quality/baseline.json` xác nhận `row_count_check` pass (24/24) và `paper_id_null_and_unique` pass (0 duplicate); `data/eval/test_set.json` có 12 item, 4 câu mỗi loại `summary`/`authors`/`date`.
- **Artifact/log:** `data/clean/papers_clean.csv/json`, `data/eval/test_set.json`, `data/quality/baseline.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** một record Crossref hợp lệ về mặt tồn tại DOI nhưng vẫn có thể thiếu abstract, thiếu ngày xuất bản parse được, hoặc trùng DOI với record khác do fetch lại. Cần quyết định tiêu chí loại bỏ và tiêu chí giữ bản nào khi trùng.
- **Các phương án đã cân nhắc:** (1) giữ tất cả record và để các bước sau (embedding/evaluation) tự xử lý giá trị rỗng; (2) chỉ loại record thiếu `paper_id`; (3) loại record thiếu bất kỳ trường bắt buộc nào cho index/evaluation/freshness (`paper_id`, `title`, `summary`, `published` hợp lệ) và dedupe theo DOI giữ bản `updated` mới nhất.
- **Phương án đã chọn:** phương án 3.
- **Lý do:** `text_for_embedding` cần đủ cả bốn trường để có ý nghĩa ngữ nghĩa; `testset.py` cần `summary`/`published` không rỗng để sinh câu hỏi; quality/freshness cần `published` hợp lệ để tính `age_days`. Loại sớm ở bước cleaning tránh lỗi lan xuống các module phía sau và giữ cho lỗi dữ liệu được phát hiện ở đúng lớp chịu trách nhiệm.
- **Bằng chứng:** không có record nào bị loại ở lần chạy baseline (24 raw → 24 clean); khi corruption làm rỗng summary hoặc cắt title, `build_clean_dataframe` không tự "sửa" các trường này — sai lệch được giữ nguyên để `quality.py` phát hiện đúng, còn repair phải rebuild lại từ raw snapshot bằng chính hàm `build_clean_dataframe` này.

Một quyết định liên quan là dùng `sort_values(["published", "paper_id"], ascending=[False, True], kind="stable")` sau dedupe. Nhờ thứ tự ổn định và tất định, `build_test_set()` luôn chọn đúng 4 document mới nhất theo cùng thứ tự giữa các lần chạy, giúp `data/eval/test_set.json` không đổi khi chạy lại trên cùng raw snapshot.

## 6. Một lỗi hoặc blocker đã xử lý

### Blocker đã phân tích: thứ tự chọn document cho evaluation set không ổn định

- **Triệu chứng:** ở bản nháp đầu, khi hai record có cùng ngày `published`, thứ tự dòng trong dataframe phụ thuộc vào thứ tự trả về gốc từ Crossref, khiến `build_test_set()` có thể chọn khác 4 document giữa hai lần chạy trên cùng raw snapshot, làm `test_set.json` đổi mà không có lý do rõ ràng.
- **Bước tái hiện:** chạy `build_clean_dataframe` hai lần trên cùng `records` mà không có tie-breaker phụ, so sánh thứ tự `paper_id` ở 4 dòng đầu.
- **Nguyên nhân gốc:** `sort_values` chỉ theo `published` không có khóa phụ nên các bản ghi cùng ngày không có thứ tự tất định.
- **Cách xử lý hiện tại:** thêm `paper_id` làm khóa sắp xếp phụ (`ascending=[False, True]`) và `kind="stable"` để thứ tự luôn tái lập được trên cùng input, bất kể trạng thái sort nội bộ của pandas hay thứ tự trả về từ ingestion.
- **Cách xác minh sau khi phân tích:** chạy lại `uv run python script/run_phase1.py` nhiều lần trên cùng raw cache, `data/eval/test_set.json` không đổi giữa các lần chạy (test set chỉ đổi khi bật `REFRESH_TEST_SET` hoặc raw snapshot đổi).
- **Điều học được:** một hàm sort tưởng như đơn giản vẫn cần khóa phụ tất định khi kết quả của nó (ở đây là 4 document đầu) trở thành input cố định cho một module khác (evaluation set) mà toàn bộ so sánh baseline/corrupted/repaired phụ thuộc vào.

## 7. Hiểu biết về luồng end-to-end

1. **Từ raw records đến clean dataframe:** `PaperRecord` do ingestion tạo ra (Phan Bá Khánh Linh) được cleaning chuẩn hóa text, loại record thiếu trường bắt buộc, dedupe theo DOI và tạo `text_for_embedding` — đây là input trực tiếp cho bước embedding/index (Đoàn Nhật Bình).
2. **Từ clean dataframe đến evaluation set:** `testset.py` chỉ chạy được sau khi cleaning hoàn tất vì nó cần `authors_joined`, `categories_joined` và `published` đã chuẩn hóa; 4 document mới nhất theo `published` được chọn làm nguồn ground truth.
3. **Quan hệ với observability:** `quality.py` (Lê Trung Hiếu) chạy check trực tiếp trên cùng clean dataframe mà `cleaning.py` tạo ra — ví dụ `row_count_check` so 24 dòng thực tế với 24 dòng kỳ vọng, `freshness_check` dùng chính `age_days` được tính trong `build_clean_dataframe`.
4. **Quan hệ với corruption/repair:** corruption (Bùi Duy Hải) tác động trực tiếp lên clean dataframe/CSV chứ không phải raw; repair không sửa dữ liệu lỗi mà đọc lại raw snapshot và gọi lại `build_clean_dataframe` với cùng `run_date` baseline — vì vậy repaired dataframe khớp lại đúng baseline, kể cả thứ tự 4 document dùng cho evaluation set.
5. **Lý do test set không đổi giữa ba trạng thái:** `test_set.json` được sinh một lần từ baseline clean dataframe và tái sử dụng cho corrupted/repaired (`phase1.py` không rebuild trừ khi `REFRESH_TEST_SET` bật). Nếu test set đổi theo dữ liệu lỗi, chênh lệch metrics sẽ lẫn giữa "câu hỏi khác" và "dữ liệu lỗi" — làm hỏng ý nghĩa so sánh.

## 8. Phân tích kết quả

### Metrics chính liên quan đến cleaning và evaluation set

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| Row count (từ cleaning) | 24 | 23 | 24 | `row_count_check` trong `data/quality/*.json` phản ánh trực tiếp số dòng mà `build_clean_dataframe` tạo ra ở mỗi trạng thái. |
| `paper_id_null_and_unique` | 0 duplicate | 1 duplicate | 0 duplicate | Dedupe theo DOI trong cleaning chỉ chạy trên input hiện có; khi corruption chèn thêm bản sao `paper_id` sau bước clean, check này bắt được ngay. |
| `retrieval_hit_rate` (12 câu, cùng test set) | 100.0% | 50.0% | 100.0% | Vì test set cố định (do `testset.py` sinh một lần), chênh lệch retrieval hit hoàn toàn phản ánh chất lượng dữ liệu, không phải do câu hỏi đổi. |
| `mean_token_f1` | 1.0000 | 0.4327 | 1.0000 | Ground truth trong test set không đổi; khi summary bị làm rỗng/nhiễu ở dữ liệu corrupted, phần trả lời tương ứng lệch khỏi ground truth cố định này. |
| Freshness | Fresh, 0/24 stale | Stale, 1/23 stale | Fresh, 0/24 stale | `age_days` được tính trong `build_clean_dataframe`; khi corruption đặt một `published` về `1900-01-01`, giá trị này lan trực tiếp vào `age_days` và bị `freshness_check` phát hiện. |

### Chuỗi nguyên nhân–bằng chứng

1. **Cleaning tạo baseline sạch, tất định** → 24 raw → 24 clean rows, 0 duplicate DOI, dedupe ổn định theo `updated` mới nhất → là điều kiện để `data/quality/baseline.json` đạt 5/5 checks.
2. **Test set cố định từ 4 document mới nhất** → 12 câu hỏi giữ nguyên `ground_truth`/`ground_truth_doc_ids` qua cả ba trạng thái → mọi thay đổi ở `retrieval_hit_rate` (100% → 50% → 100%) và `mean_token_f1` (1.0000 → 0.4327 → 1.0000) có thể quy trực tiếp cho thay đổi dữ liệu, không phải thay đổi câu hỏi.
3. **Repair gọi lại đúng `build_clean_dataframe` trên raw snapshot** → clean dataframe repaired giống hệt baseline về nội dung và thứ tự → `test_set.json` không cần sinh lại, và metrics quay lại đúng baseline.

Kết quả phù hợp với kỳ vọng: vì cleaning và evaluation set được thiết kế tất định (deterministic sort, dedupe theo khóa rõ ràng, test set cố định), phần biến động duy nhất giữa ba trạng thái là do corruption/repair, không phải do nhiễu ngẫu nhiên trong cleaning hay evaluation set.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** một bước cleaning "im lặng" (không sửa lỗi dữ liệu, chỉ chuẩn hóa và loại record thiếu trường bắt buộc) quan trọng hơn một bước cleaning "thông minh" tự đoán và vá lỗi — vì lớp quality/freshness cần thấy đúng lỗi thật để phát hiện.
2. **Về observability:** giá trị của deterministic evaluation set không nằm ở độ khó câu hỏi mà ở tính ổn định — cùng một bộ câu hỏi trên ba trạng thái dữ liệu là điều kiện tiên quyết để so sánh metrics có ý nghĩa nhân quả.
3. **Về thiết kế hàm:** một hàm sort/dedupe tưởng đơn giản (`sort_values`, `drop_duplicates`) cần khóa phụ tất định và `kind="stable"` ngay khi output của nó trở thành input cố định cho module khác, nếu không dễ gây ra sai lệch khó tái hiện.

### Nếu có thêm thời gian

Ưu tiên bổ sung: (1) test đơn vị cho `build_clean_dataframe` với các case biên như hai record cùng DOI khác hoa/thường, `published` không parse được, danh sách `authors` rỗng; (2) test cho `build_test_set` khi `authors_joined`/`categories_joined` rỗng ở một số document nhưng không phải tất cả; (3) phối hợp với phần agent demo để dùng cùng một hàm canonicalize title (theo phát hiện của Đoàn Nhật Bình ở mục vấn đề tích hợp) ngay từ bước tạo câu hỏi trong `testset.py`, tránh title chứa markup `<scp>` gây lệch giữa test set và exact lookup của agent.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này tập trung vào vai trò cá nhân, không sao chép nguyên văn báo cáo nhóm.

**Họ và tên:** Nguyễn Minh Thu
**Ngày xác nhận:** 2026-08-06
