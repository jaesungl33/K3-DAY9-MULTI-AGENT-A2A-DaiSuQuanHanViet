# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                         |
| --------------- | ---------------------------------------------------------------- |
| Họ và tên       | Phạm Đức Hiệp                                                    |
| MSSV            | 01329                                                            |
| Khóa/Lớp        | K3                                                               |
| Vai trò chính   | Evidence precision & submission packaging (nhánh `phamduchiep`) |
| Ngày hoàn thành | 2026-08-05                                                       |

## 2. Vai trò và phạm vi công việc

Tôi **không** nhận ownership: lead orchestration/LLM (Lee), tối ưu benchmark tổng (Lâm), QA oracle độc lập (Duy), hay agent Delivery/Payment domain (An).  
Phần việc của tôi: **chỉnh `evidence_ids` / confidence cho tiêu chí chấm** và **đóng gói ZIP đúng layout `output/`**.

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| Evidence issue-aware | `src/data/evidence.py` (+ gọi từ `policy_agent.py`) | `OrderBundle` + `PolicyDecision` (sau khi Delivery/Payment đã handoff) | `evidence_ids`: chỉ gắn `seller:` khi `late_delivery_seller` | Hoàn thành |
| Hiệu chỉnh confidence | `src/data/policy.py` (`confidence=0.95`) | Sáu nhánh policy chính | `assessment.confidence` đồng nhất 50 case | Hoàn thành |
| Đóng gói ZIP | `scripts/pack_output.py` | `output/EC_*.json` | `output_submission.zip` với entry `output/EC_001.json`…`EC_050.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Khôi phục Entity sau khi lọc `seller_ids` quá tay | Toàn nhóm / `output/` | Entities giữ `seller_ids` từ item; evidence vẫn lọc `seller:` |
| Phân biệt việc với An | Delivery/Payment domain | Tôi không sửa logic cờ late/match; chỉ tiêu thụ kết quả khi build evidence |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact | Kết quả bàn giao | Cách xác minh |
| --------------------- | ----------------- | ---------------- | ------------- |
| Giảm FP evidence `seller:` | `src/data/evidence.py` | Non-seller issue không còn `seller:` trong evidence | So `EC_017` (logistics) vs `EC_001` (seller) |
| Confidence 0.95 | `src/data/policy.py` | 50/50 = 0.95 | Counter trên toàn bộ output |
| Pack ZIP đúng path | `output_submission.zip` | 50 entry dưới `output/` | Liệt kê nội dung zip |

Artifact chính: `src/data/evidence.py`, bản output sau vòng chỉnh evidence/confidence, `output_submission.zip`.

Case minh họa: **`output/EC_017.json`** — `late_delivery_logistics`, evidence có `policy:CARRIER_DELIVERED_AFTER_ESTIMATE` và **không** có `seller:`, nhưng `affected_entities.seller_ids` vẫn có seller của item.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Điểm Evidence thấp khi gắn `seller:` cho mọi case. Nếu xóa luôn `seller_ids` ở entities thì điểm Entity sụt. Cần tách hai lớp field.

### Cách triển khai

1. `build_evidence_ids`: luôn `order` + `item*` + `payment*` + `policy`; thêm `seller:` **chỉ** khi issue là `late_delivery_seller`.
2. Entities: giữ đủ `item_ids` / `seller_ids` / `payment_ids` từ order (order không item → rỗng + freight/item = 0).
3. `confidence = 0.95` cho nhánh policy chính.
4. Zip arcname = `output/{EC_xxx.json}`.

Facts late/match do agent của An cung cấp; tôi không tính lại SLA trong `evidence.py`.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | `PolicyDecision` + bundle sau handoff domain |
| Output | `evidence_ids` ≤ 10, entities đúng limit |
| Phụ thuộc | `policy.py`, `store.py`, Delivery/Payment findings |
| Dùng output | Verifier → `pipeline` ghi file |
| Lỗi cần tránh | Evidence không có trong CSV; zip thiếu prefix `output/` |

### Cách xác minh

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
python scripts/validate_outputs.py
python scripts/pack_output.py
```

- **Mong đợi / thực tế:** 50 case, validate pass, zip đúng 50 path `output/EC_*.json`, confidence toàn 0.95.
- **Artifact:** `logging/trace.jsonl`, `logging/metadata.json` (model khai báo trong code, không đặt tên model trong `.env`).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Tăng Evidence mà không phá Entity.
- **Phương án:** (1) Xóa seller ở cả evidence + entities; (2) Giữ hết ID; (3) Lọc seller chỉ trên evidence.
- **Chọn:** (3).
- **Lý do:** Evidence FP bị phạt nặng; entities vẫn cần phản ánh seller có trên đơn.
- **Bằng chứng:** Phương án (1) từng làm Entity ~77 trên bài nộp; sau khi hoàn tác entities + giữ lọc evidence thì hai tiêu chí cân bằng hơn.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Tổng điểm ~91, Entity ~77 sau vòng “tối ưu”.
- **Nguyên nhân:** Đồng nhất hóa entity với evidence (xóa `seller_ids` khi không blame seller).
- **Xử lý:** Khôi phục `seller_ids` trong entities; chỉ giữ filter trong `build_evidence_ids`.
- **Xác minh:** Case logistics/canceled có seller trong entities, không có `seller:` trong evidence (trừ late seller).
- **Bài học:** Mỗi field chấm điểm có hợp đồng riêng — đừng tối ưu một field bằng cách phá field khác.

## 7. Hiểu biết về luồng end-to-end

1. Input → Coordinator → Order&Seller → **Payment (An)** → **Delivery (An)** → Policy (+ evidence builder của tôi) → Verifier → `output/`.
2. Phải join CSV vì claim khách có thể sai so với timestamp/payment thật.
3. Priority `EC_POLICY_V1`: canceled/unavailable đã trả tiền → late seller → late logistics → split → unsupported.
4. Evidence chỉ năm prefix hợp lệ; ID bịa = false positive.
5. Trace/metadata chứng minh chạy thật và model ≤10B; zip nộp chỉ chứa `output/*.json`.

## 8. Cam kết của thành viên

- [x] Đúng phần evidence / confidence / pack trên nhánh `phamduchiep`.
- [x] Hiểu luồng end-to-end và ranh giới với An (domain) / Duy (QA) / Lee–Lâm (pipeline–tối ưu).
- [x] Không gắn điểm leaderboard như số liệu chính thức không có artifact kèm theo.
- [x] Không chứa secret.
- [x] Không sao chép báo cáo của Lee Jae Sung, Dương Hoàng Lâm, Vũ Đức Duy hay Nguyễn Trường An.

**Họ và tên:** Phạm Đức Hiệp  
**Ngày xác nhận:** 2026-08-05
