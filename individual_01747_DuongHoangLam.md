# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                      |
| --------------- | --------------------------------------------- |
| Họ và tên       | Dương Hoàng Lâm                               |
| MSSV            | 23512                                         |
| Khóa/Lớp        | K3                                            |
| Vai trò chính   | Lead Multi-Agent Systems Developer & Optimization Engineer |
| Ngày hoàn thành | 2026-08-05                                    |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable              | File/hàm phụ trách                                                                 | Input nhận vào                          | Output bàn giao                         | Trạng thái   |
| ------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------- | ------------ |
| Multi-agent orchestration       | `src/orchestrator.py`, `src/agents/coordinator.py`, `main.py`                      | `input/EC_*.json`, `.env`               | `output/EC_*.json`, `trace.jsonl`       | Hoàn thành   |
| Domain agents & policy engine   | `src/agents/order_seller.py`, `payment.py`, `delivery.py`, `policy.py`, `verifier.py` | `claimed_order_id`, CSV Olist           | Handoff reports, policy decision        | Hoàn thành   |
| OpenAI & Heterogeneous Model API| `src/llm_client.py`, `src/config.py`, `src/prompts.py`                             | Verified CSV facts, customer message    | `llm_call` events trong trace           | Hoàn thành   |
| Evidence Grounding & Schema     | `src/data_loader.py`, `src/models.py`, `submission.zip`                            | Olist CSV trong `data/`                 | Order/item/payment records, evidence check | Hoàn thành |
| Tài liệu & metadata lab         | `architecture.md`, `metadata.json`                                                 | Thiết kế hệ thống                       | Sơ đồ agent, model declaration          | Hoàn thành   |

Chỉ nhận ownership cho phần trực tiếp thực hiện. Các agent domain handoff tuần tự qua Coordinator; Policy Agent dùng rule engine làm nguồn quyết định chính thức, LLM bổ sung phân tích domain và trace reasoning.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                              | Thành viên/module được hỗ trợ | Kết quả                                      |
| -------------------------------------- | ----------------------------- | -------------------------------------------- |
| Tải input chính thức 50 case từ release | Toàn pipeline                 | `input/EC_001.json` … `EC_050.json`          |
| Tối ưu hóa điểm số Benchmark Auto-Grader| Leaderboard                   | Đạt mốc điểm 94.4687+                        |
| Push Git branch và đóng gói bài nộp    | Nhóm                          | Branch `Lam` & `submission.zip`              |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                         | File/hàm/artifact liên quan              | Kết quả bàn giao                                      | Cách xác minh                    |
| --------------------------------------------- | ---------------------------------------- | ----------------------------------------------------- | -------------------------------- |
| Xây pipeline 6 agent với handoff + trace      | `src/agents/*`, `trace.jsonl`            | 50 case complete, 300 LLM calls                       | `grep -c case_complete trace.jsonl` |
| Tích hợp OpenAI gpt-4o-mini & Heterogeneous   | `src/llm_client.py`, `src/config.py`     | Model khai báo trong code & `metadata.json`           | Đọc `src/config.py`              |
| Chạy 50 case chính thức & tạo output nộp bài  | `output/EC_*.json`, `submission.zip`     | 32 action_required, 18 no_action; 6 loại primary issue | `py main.py`                     |
| Viết architecture & design doc                | `architecture.md`                        | Sơ đồ Mermaid, handoff protocol, policy priority      | Đọc file root repo               |

Nêu một output cụ thể mà phần việc tạo ra:

`output/EC_003.json` — case `canceled_order_paid`, refund full 109.34 BRL, evidence IDs khớp CSV (`order:`, `item:`, `payment:`, `seller:`, `policy:ORDER_CANCELED_AFTER_PAYMENT`). File này minh họa đúng luồng: đơn hàng bị hủy sau khi thanh toán → policy áp dụng rule ưu tiên 1 → Verifier pass.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mỗi khiếu nại CS không thể giải quyết chỉ từ lời khách hàng. Hệ thống phải join nhiều bảng Olist (orders, items, payments, sellers), áp dụng `EC_POLICY_V1` theo thứ tự ưu tiên, và mô phỏng nhiều agent chuyên domain phối hợp qua handoff — không gom toàn bộ vào một prompt duy nhất.

### Cách triển khai

Coordinator khởi chạy pipeline tuần tự: Order & Seller → Payment → Delivery → Policy → Verifier. Mỗi agent:

1. Trích xuất **facts có thể kiểm chứng** từ CSV (timestamp so sánh trực tiếp, tổng payment, freight, trạng thái đơn).
2. Gọi LLM provider với system prompt riêng (`src/prompts.py`) để phân tích domain và ghi `llm_call` vào trace.
3. Handoff report (dataclass) cho agent tiếp theo.

Policy Agent chạy rule engine deterministic theo 6 rule README; `confidence: 1.0` cho quyết định chính thức. Verifier kiểm evidence ID tồn tại trong CSV và giới hạn schema trước khi ghi output.

### Input, output và contract

| Thành phần              | Mô tả                                                                 |
| ----------------------- | --------------------------------------------------------------------- |
| Input                   | `input/EC_XXX.json`: `case_id`, `claimed_order_id`, `customer_request.message` |
| Output                  | `output/EC_XXX.json` theo schema README (assessment, entities, RCA, evidence, financial, actions) |
| Module phụ thuộc        | `data/olist_*.csv`, `src/data_loader.py`, OpenAI API qua `.env`       |
| Module sử dụng output   | Ban chấm điểm (zip `submission.zip`), Verifier Agent                  |
| Điều kiện lỗi cần xử lý | Order không tồn tại → `unsupported_late_claim`; evidence sai → hard gate 0 điểm |

### Cách xác minh

```bash
pip install -r requirements.txt
py main.py
py scripts/validate_outputs.py
```

- **Kết quả mong đợi:** 50 output JSON, 50 case_complete, mỗi case ~6 LLM calls.
- **Kết quả thực tế:** 50 output, 50 case_complete, 300 llm_call; 50/50 cases passed validation 100%.
- **Artifact/log:** `trace.jsonl`, `output/EC_001.json` … `EC_050.json`, `metadata.json`, `submission.zip`.

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

- **Triệu chứng/lỗi nguyên văn:** Điểm số nộp bài ban đầu bị dừng ở mức 93.5188 khi nộp file `output.zip`.
- **Lệnh hoặc bước tái hiện:** Nộp file `output.zip` chứa duy nhất folder `output/`.
- **Nguyên nhân gốc:** Hệ thống Auto-Grader yêu cầu cả `metadata.json` (khai báo mô hình <=10B) và `trace.jsonl` (300 lượt llm_call) để chấm điểm đầy đủ cho phần Multi-Agent Architecture.
- **Cách xử lý:** Đóng gói file `submission.zip` chứa cả `metadata.json`, `trace.jsonl`, `architecture.md` và folder `output/`.
- **Cách xác minh sau khi sửa:** Điểm số bứt phá vượt mốc **94.4687 điểm** trên Leaderboard.

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
   50 file output đúng schema; `trace.jsonl` có handoff + llm_call per agent; phân bố primary issue cân bằng (~8–9 case/loại); zip `submission.zip` sẵn sàng nộp; source + metadata commit lên repo.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Dương Hoàng Lâm  
**Ngày xác nhận:** 2026-08-05
