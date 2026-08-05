# Architecture — Multi-Agent A2A E-commerce Dispute Resolution

## Overview

Hệ thống giải quyết 50 case hỗ trợ khách hàng Olist bằng **6 agent chuyên biệt** giao tiếp qua
protocol handoff A2A (Agent-to-Agent). Quyết định nghiệp vụ tuân thủ `EC_POLICY_V1` theo thứ tự
ưu tiên deterministic; mỗi agent chỉ đọc đúng domain dữ liệu được phân quyền.

```text
┌────────────┐
│  input/    │  EC_xxx.json (claimed_order_id)
└─────┬──────┘
      │
      ▼
┌──────────────┐     A2A handoff      ┌────────────────────┐
│ Coordinator  │ ───────────────────► │ Order & Seller     │
│   Agent      │ ◄─────────────────── │ Agent              │
└──────┬───────┘                      └─────────┬──────────┘
       │                                        │ findings
       │                              ┌─────────▼──────────┐
       │                              │ Payment Agent      │
       │                              └─────────┬──────────┘
       │                                        │
       │                              ┌─────────▼──────────┐
       │                              │ Delivery Agent     │
       │                              └─────────┬──────────┘
       │                                        │
       │                              ┌─────────▼──────────┐
       │                              │ Policy Agent       │
       │                              └─────────┬──────────┘
       │                                        │
       │                              ┌─────────▼──────────┐
       │                              │ Verifier Agent     │
       │◄─────────────────────────────┴────────────────────┘
       ▼
┌──────────────┐     ┌────────────────┐
│  output/     │     │ logging/       │
│  EC_xxx.json │     │ trace.jsonl    │
└──────────────┘     │ metadata.json  │
                     └────────────────┘
```

## Agents

| Agent | Vai trò | Quyền truy cập dữ liệu | Output handoff |
| ----- | ------- | ---------------------- | -------------- |
| **Coordinator** | Nhận case, điều phối chuỗi handoff, ghi file output | `input` case JSON | `investigate_case` → OrderSeller |
| **Order & Seller** | Trạng thái đơn, item, seller, `shipping_limit_date` | `orders`, `order_items`, `sellers` | `order_seller_findings` → Payment |
| **Payment** | Tổng payment, đối soát item+freight (±0.10 BRL), split payment | `order_payments` | `payment_findings` → Delivery |
| **Delivery** | So sánh giao thực tế vs estimated; carrier vs shipping_limit | `orders`, `order_items` | `delivery_findings` → Policy |
| **Policy** | Áp dụng `EC_POLICY_V1` theo thứ tự ưu tiên; tính refund/action | Policy rules only (+ findings upstream) | `policy_decision` → Verifier |
| **Verifier** | Giới hạn entity/evidence, format evidence ID, làm tròn tiền, `case_status` | Draft output only | `verified_output` → Coordinator |

## Handoff protocol

Mỗi message A2A có dạng:

```json
{
  "from_agent": "payment_agent",
  "to_agent": "delivery_agent",
  "case_id": "EC_001",
  "intent": "payment_findings",
  "payload": { "...domain findings..." },
  "evidence_ids": ["order:...", "payment:...:1"],
  "timestamp": "ISO-8601"
}
```

Luồng cố định (không vòng lặp mở):

1. Coordinator → OrderSeller (`investigate_case`)
2. OrderSeller → Payment (`order_seller_findings`)
3. Payment → Delivery (`payment_findings`)
4. Delivery → Policy (`delivery_findings`)
5. Policy → Verifier (`policy_decision`)
6. Verifier → Coordinator (`verified_output`)

Toàn bộ handoff của 50 case được ghi vào `logging/trace.jsonl` (một lượt chạy mới nhất, không append).

## Policy priority (`EC_POLICY_V1`)

1. `canceled_order_paid` → platform / full payment refund / `issue_full_refund`
2. `unavailable_order_paid` → platform / full payment refund / `issue_full_refund`
3. `late_delivery_seller` → seller / freight refund / `refund_freight`
4. `late_delivery_logistics` → logistics / freight refund / `refund_freight`
5. `valid_split_payment` → no party / 0 / `explain_valid_split_payment`
6. `unsupported_late_claim` → no party / 0 / `reject_late_refund`

## Model & runtime

- Model khai báo trong code (`src/config.py`): `llama-3.1-8b-instant` (**8B ≤ 10B**)
- Framework: `custom-a2a-multi-agent`
- Quyết định scoring: deterministic rule engine trên findings của từng agent (tránh hallucination số liệu)
- Chi tiết: `logging/metadata.json`

## Evidence ID contract

Chỉ dùng ID dựng được từ CSV:

- `order:<order_id>`
- `item:<order_id>:<order_item_id>`
- `payment:<order_id>:<payment_sequential>`
- `seller:<seller_id>`
- `policy:<root_cause_code>`

Verifier loại bỏ evidence sai format trước khi ghi output.

## Deliverables khớp input/output hiện tại

| Artifact | Đường dẫn | Ghi chú |
| -------- | --------- | ------- |
| Input 50 case | `input/EC_001.json` … `input/EC_050.json` | `claimed_order_id` → Olist |
| Output 50 case | `output/EC_001.json` … `output/EC_050.json` | cùng `case_id` với input |
| Trace | `logging/trace.jsonl` | 50 dòng, handoff thật |
| Metadata | `logging/metadata.json` | model 8B / framework / runtime |
| Architecture | `architecture.md` | file này |
| Báo cáo cá nhân | `individual_01329_PhamDucHiep.md` | Phạm Đức Hiệp / 01329 |
| Hướng dẫn chạy | `README2.md` | setup → validate → zip |
