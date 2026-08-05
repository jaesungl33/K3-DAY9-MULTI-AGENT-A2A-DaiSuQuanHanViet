# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                              |
| --------------- | --------------------------------------------------------------------- |
| Họ và tên       | Nguyễn Trường An                                                      |
| MSSV            | 01151                                                                 |
| Khóa/Lớp        | K3                                                                    |
| Vai trò chính   | Domain specialist — Delivery SLA & Payment reconciliation             |
| Ngày hoàn thành | 2026-08-05                                                            |

## 2. Vai trò và phạm vi công việc

Tôi phụ trách **hai agent domain** phân biệt trách nhiệm giao hàng và đối soát thanh toán. Không nhận ownership orchestration/LLM lead, không làm QA oracle, không phụ trách lọc evidence nộp điểm hay đóng gói ZIP.

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| Delivery Agent | `src/agents/delivery.py` | Findings order/item (carrier, customer, estimated, shipping_limit) | Handoff `delivery_findings`: late vs estimate, seller handoff late hay không | Hoàn thành |
| Payment Agent | `src/agents/payment.py` | Order bundle + item/freight totals | Handoff `payment_findings`: tổng payment, delta, split (≥2 row), match ±0.10 BRL | Hoàn thành |
| Chuẩn bị / đồng bộ input | `scripts/fetch_official_inputs.py`, hỗ trợ `scripts/generate_inputs.py` | Release hoặc Olist candidates | `input/EC_001.json`…`EC_050.json` sẵn để pipeline chạy | Hoàn thành |
| Quy ước so timestamp | Logic dùng trong delivery + store | Cột thời gian CSV (không đổi TZ) | Cờ `is_late_vs_estimate`, `seller_handoff_after_limit` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Làm rõ biên seller-late vs logistics-late cho Policy | Policy / evidence scoring | Policy nhận đúng cặp cờ để chọn `late_delivery_seller` hoặc `late_delivery_logistics` |
| Rà payment split cho rule ưu tiên 5 | Policy Agent | Case ≥2 payment row + match item+freight được đánh dấu `split_payment` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact | Kết quả bàn giao | Cách xác minh |
| --------------------- | ----------------- | ---------------- | ------------- |
| Phân tách late seller / late logistics | `src/agents/delivery.py` | Delivery handoff đủ 2 cờ độc lập | So output seller-late vs logistics-late |
| Đối soát payment | `src/agents/payment.py` | `payment_ids`, `payment_total_brl`, `payment_match` | Đối chiếu CSV payments |
| Hỗ trợ có bộ 50 input | `scripts/fetch_official_inputs.py` | Input đủ `EC_001`…`EC_050` | `(Get-ChildItem input\EC_*.json).Count` |

Artifact cụ thể:

- `src/agents/delivery.py`, `src/agents/payment.py`
- Script đồng bộ input (fetch/generate)
- Minh họa: `output/EC_037.json` — nếu là late seller thì carrier > shipping_limit; khác với case logistics cùng pipeline

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cùng một lời claim “giao trễ” có thể do **seller bàn giao muộn** hoặc **carrier giao muộn dù seller đúng hạn**. Payment cũng có thể là nhiều dòng hợp lệ (split) chứ không phải charge trùng. Hai agent domain phải tách facts trước khi Policy quyết định.

### Cách triển khai

**Delivery**

- `order_delivered_customer_date > order_estimated_delivery_date` → late so với estimate.
- `order_delivered_carrier_date > shipping_limit_date` (theo item/seller) → seller handoff late.
- Không suy diễn tracking checkpoint ngoài CSV.

**Payment**

- Cộng `payment_value` theo `payment_sequential`.
- So với `sum(price)+sum(freight)` trong sai số 0.10 BRL.
- Đánh dấu split khi ≥ 2 payment row.

Facts này handoff sang Policy; tôi không ghi đè `primary_issue` ở tầng Delivery/Payment.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | A2A message từ Order&Seller (order_id, items, timestamps) |
| Output | A2A message tới agent tiếp theo (`payment_findings` / `delivery_findings`) |
| Module phụ thuộc | `src/data/store.py`, Order&Seller Agent |
| Module dùng output | Policy Agent, sau đó Verifier |
| Điều kiện lỗi | Thiếu timestamp giao → không kết luận late; thiếu item → freight/item = 0 |

### Cách xác minh

```powershell
python main.py
# Kiểm tra một case logistics vs seller trong output/
Get-Content .\output\EC_017.json
Get-Content .\output\EC_001.json
```

- **Kết quả mong đợi:** Cùng pipeline, hai loại late khác `cause_code` / `responsible_parties`.
- **Kết quả thực tế:** Phân bố issue có đủ cả `late_delivery_seller` và `late_delivery_logistics`.
- **Artifact:** `logging/trace.jsonl` (handoff delivery/payment), `output/*.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** So sánh “muộn” nên theo ngày lịch hay theo timestamp đầy đủ trong CSV?
- **Các phương án:** (1) Chỉ so phần ngày; (2) So đúng giá trị timestamp như README (“so sánh theo giá trị trong CSV”).
- **Đã chọn:** (2) timestamp đầy đủ.
- **Lý do:** Đề yêu cầu không đổi múi giờ và so theo giá trị CSV; estimated thường 00:00:00 nên so ngày-only dễ lệch gold.
- **Bằng chứng:** Các case late trong output khớp khi carrier/customer vượt mốc theo timestamp.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Một số case tưởng “giao trễ” nhưng bị sang `unsupported_late_claim`.
- **Tái hiện:** Xem order có `delivered_customer_date` ≤ `estimated` trong CSV dù message khách nói trễ.
- **Nguyên nhân:** Tin message khách thay vì timestamp.
- **Xử lý:** Delivery chỉ emit cờ từ CSV; Policy ưu tiên facts đã verify.
- **Xác minh:** Case on-time + payment khớp → `unsupported_late_claim` / `reject_late_refund`.
- **Bài học:** Domain agent phải “cứng” với dữ liệu; claim chỉ là ngữ cảnh.

## 7. Hiểu biết về luồng end-to-end

1. Coordinator đọc input → Order&Seller lấy status/item/seller → **Payment** đối soát → **Delivery** so SLA → Policy chọn issue → Verifier → `output/`.
2. Join orders/items/payments/sellers vì mọi kết luận tiền và trách nhiệm dựa trên field có thật, không phải nội dung chat.
3. `EC_POLICY_V1` ưu tiên canceled/unavailable đã trả tiền, rồi mới late seller/logistics, rồi split, rồi reject claim.
4. Evidence chỉ năm dạng dựng từ CSV; ID bịa = false positive.
5. `trace.jsonl` chứng minh handoff domain đã chạy; `metadata.json` khai báo model ≤10B.

## 8. Cam kết của thành viên

- [x] Báo cáo đúng phần Delivery/Payment/input sync tôi phụ trách.
- [x] Giải thích được luồng end-to-end.
- [x] Không khai báo điểm leaderboard khi không có artifact điểm chính thức trong báo cáo này.
- [x] Không chứa secret/`.env`.
- [x] Không sao chép báo cáo của Lee Jae Sung, Dương Hoàng Lâm, Vũ Đức Duy hay Phạm Đức Hiệp.

**Họ và tên:** Nguyễn Trường An  
**Ngày xác nhận:** 2026-08-05
