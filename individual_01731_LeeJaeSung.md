# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                      |
| --------------- | --------------------------------------------- |
| Họ và tên       | Lee Jae Sung                                  |
| MSSV            | 01731                                         |
| Khóa/Lớp        | K3                                            |
| Vai trò chính   | Lead developer — multi-agent pipeline & tích hợp OpenAI |
| Ngày hoàn thành | 2026-08-05                                    |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable              | File/hàm phụ trách                                                                 | Input nhận vào                          | Output bàn giao                         | Trạng thái   |
| ------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------- | ------------ |
| Multi-agent orchestration       | `src/orchestrator.py`, `src/agents/coordinator.py`, `main.py`                      | `input/EC_*.json`, `.env`               | `output/EC_*.json`, `trace.jsonl`       | Hoàn thành   |
| Domain agents & policy engine   | `src/agents/order_seller.py`, `payment.py`, `delivery.py`, `policy.py`, `verifier.py` | `claimed_order_id`, CSV Olist           | Handoff reports, policy decision        | Hoàn thành   |
| OpenAI provider & agent prompts | `src/llm_client.py`, `src/config.py`, `src/prompts.py`                             | Verified CSV facts, customer message    | `llm_call` events trong trace           | Hoàn thành   |
| Data access layer               | `src/data_loader.py`, `src/models.py`                                              | Olist CSV trong `data/`                 | Order/item/payment records, evidence check | Hoàn thành |
| Tài liệu & metadata lab         | `architecture.md`, `metadata.json`                                                 | Thiết kế hệ thống                       | Sơ đồ agent, model declaration          | Hoàn thành   |

Chỉ nhận ownership cho phần trực tiếp thực hiện. Các agent domain handoff tuần tự qua Coordinator; Policy Agent dùng rule engine làm nguồn quyết định chính thức, LLM chỉ bổ sung phân tích và confidence.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                              | Thành viên/module được hỗ trợ | Kết quả                                      |
| -------------------------------------- | ----------------------------- | -------------------------------------------- |
| Tải input chính thức 50 case từ release | Toàn pipeline                 | `input/EC_001.json` … `EC_050.json`          |
| Script probe scenario Olist            | Testing local                 | `scripts/probe_scenarios.py`                 |
| Fork repo & push source/output         | Nhóm                          | `jaesungl33/K3-DAY9-MULTI-AGENT-A2A-DaiSuQuanHanViet` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                         | File/hàm/artifact liên quan              | Kết quả bàn giao                                      | Cách xác minh                    |
| --------------------------------------------- | ---------------------------------------- | ----------------------------------------------------- | -------------------------------- |
| Xây pipeline 6 agent với handoff + trace      | `src/agents/*`, `trace.jsonl`            | 50 case complete, 300 LLM calls                       | `grep -c case_complete trace.jsonl` |
| Tích hợp OpenAI gpt-4o-mini per-agent         | `src/llm_client.py`, `src/config.py`     | Model khai báo trong code & `metadata.json`           | Đọc `src/config.py`              |
| Chạy 50 case chính thức & tạo output nộp bài  | `output/EC_*.json`, `output.zip`         | 32 action_required, 18 no_action; 6 loại primary issue | `python3 main.py`                |
| Viết architecture & design doc                | `architecture.md`                        | Sơ đồ Mermaid, handoff protocol, policy priority      | Đọc file root repo               |

Nêu một output cụ thể mà phần việc tạo ra:

`output/EC_003.json` — case `late_delivery_seller`, refund freight 8.96 BRL, evidence IDs khớp CSV (`order:`, `item:`, `seller:`, `payment:`, `policy:SELLER_HANDOFF_AFTER_LIMIT`). File này minh họa đúng luồng: seller bàn giao muộn → policy áp dụng rule ưu tiên 3 → Verifier pass.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mỗi khiếu nại CS không thể giải quyết chỉ từ lời khách hàng. Hệ thống phải join nhiều bảng Olist (orders, items, payments, sellers), áp dụng `EC_POLICY_V1` theo thứ tự ưu tiên, và mô phỏng nhiều agent chuyên domain phối hợp qua handoff — không gom toàn bộ vào một prompt duy nhất.

### Cách triển khai

Coordinator khởi chạy pipeline tuần tự: Order & Seller → Payment → Delivery → Policy → Verifier. Mỗi agent:

1. Trích xuất **facts có thể kiểm chứng** từ CSV (timestamp so sánh trực tiếp, tổng payment, freight, trạng thái đơn).
2. Gọi **OpenAI gpt-4o-mini** với system prompt riêng (`src/prompts.py`) để phân tích domain và ghi `llm_call` vào trace.
3. Handoff report (dataclass) cho agent tiếp theo.

Policy Agent chạy rule engine deterministic theo 6 rule README; LLM điều chỉnh `confidence` trong `[0, 1]`. Verifier kiểm evidence ID tồn tại trong CSV và giới hạn schema trước khi ghi output.

### Input, output và contract

| Thành phần              | Mô tả                                                                 |
| ----------------------- | --------------------------------------------------------------------- |
| Input                   | `input/EC_XXX.json`: `case_id`, `claimed_order_id`, `customer_request.message` |
| Output                  | `output/EC_XXX.json` theo schema README (assessment, entities, RCA, evidence, financial, actions) |
| Module phụ thuộc        | `data/olist_*.csv`, `src/data_loader.py`, OpenAI API qua `.env`       |
| Module sử dụng output   | Ban chấm điểm (zip `output/`), Verifier Agent                        |
| Điều kiện lỗi cần xử lý | Order không tồn tại → `unsupported_late_claim`; evidence sai → hard gate 0 điểm |

### Cách xác minh

```bash
pip install -r requirements.txt
python3 main.py
grep -c '"event_type": "case_complete"' trace.jsonl
ls output/EC_*.json | wc -l
```

- **Kết quả mong đợi:** 50 output JSON, 50 case_complete, mỗi case ~6 LLM calls.
- **Kết quả thực tế:** 50 output, 50 case_complete, 300 llm_call; phân bố 8 case/loại issue (trừ valid_split_payment và unsupported_late_claim mỗi loại 9 case).
- **Artifact/log:** `trace.jsonl`, `output/EC_001.json` … `EC_050.json`, `metadata.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** LLM có thể hallucinate refund amount hoặc primary issue nếu chỉ dựa vào message khách hàng.
- **Các phương án đã cân nhắc:**
  1. Toàn bộ quyết định do LLM (một hoặc nhiều prompt).
  2. Hybrid: CSV facts + rule engine quyết định, LLM phân tích từng domain.
  3. Pure rule-based, không dùng LLM.
- **Phương án đã chọn:** Hybrid (2).
- **Lý do:** Đáp ứng yêu cầu multi-agent A2A với provider thật, đồng thời đảm bảo correctness cho các trường chấm điểm (primary issue, refund, evidence ID). Rule engine tái lập được; LLM bổ sung reasoning trong trace.
- **Bằng chứng quyết định phù hợp:** Chạy 50 case official input — mỗi primary issue khớp điều kiện CSV; không có evidence ID invented (Verifier pass 50/50).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `trace.jsonl` không xuất hiện ở root repo sau lần chạy đầu; chỉ có 6 file input mẫu tự tạo, không phải bộ chính thức 50 case.
- **Lệnh hoặc bước tái hiện:** Chạy `python3 main.py` → trace ghi vào `src/trace.jsonl`; input chỉ có `EC_001`–`EC_006` với `claimed_order_id` khác release chính thức.
- **Nguyên nhân gốc:** `TRACE_PATH` trong `base.py` resolve sai depth (`parent.parent` thay vì `parent.parent.parent`); input chính thức nằm trong GitHub release tag `input`, chưa được tải về repo local.
- **Cách xử lý:** Sửa path trace về root; tải `input.zip` từ release `VinUni-AI20k/K3-Day9-Multi-Agent-A2A` tag `input`, copy 50 file vào `input/`, chạy lại pipeline.
- **Cách xác minh sau khi sửa:** `trace.jsonl` ở root với 50 case_complete; `EC_001.json` official có `claimed_order_id: e2a03ccf5ea816036608b2d8c3ab8e60`.
- **Điều học được:** Artifact path và input dataset phải được xác minh trước khi claim pipeline hoàn chỉnh; release lab thường tách input khỏi repo chính.

## 7. Hiểu biết về luồng end-to-end

1. **Case đi từ input đến output như thế nào?**  
   `input/EC_XXX.json` cung cấp `claimed_order_id` → Coordinator giao lần lượt cho 5 domain agent → Policy áp dụng rule → Verifier validate → ghi `output/EC_XXX.json` và events vào `trace.jsonl`.

2. **Dữ liệu Olist được join và dùng ra sao?**  
   `data_loader.py` load orders, items, payments theo `order_id`. Items cho seller/shipping_limit; payments đối soát với price+freight; orders cho delivery timestamps và status.

3. **Quality checks ở đâu trong pipeline?**  
   Verifier Agent kiểm evidence ID tồn tại trong CSV, giới hạn entity/evidence/action, confidence range, làm tròn BRL. LLM Verifier call bổ sung ghi chú schema trong trace.

4. **Vì sao ưu tiên dữ liệu CSV hơn lời khiếu nại?**  
   Olist không có refund ledger hay tracking chi tiết; chỉ có thể kết luận từ field có sẵn. Customer message có thể sai (vd. claim giao trễ nhưng `order_delivered_customer_date <= order_estimated_delivery_date`).

5. **Pipeline được xem thành công dựa trên artifact và metric nào?**  
   50 file output đúng schema; `trace.jsonl` có handoff + llm_call per agent; phân bố primary issue cân bằng (~8–9 case/loại); zip `output/` sẵn sàng nộp; source + metadata commit lên repo.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lee Jae Sung  
**Ngày xác nhận:** 2026-08-05
