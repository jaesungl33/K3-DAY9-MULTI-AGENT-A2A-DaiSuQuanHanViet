# Member Role Report — Day 9: Multi Agent A2A

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này. Thay nội dung trong dấu `[ ]` và xóa dòng hướng dẫn trước khi nộp. Không sao chép nguyên báo cáo của người khác.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung        |
| --------------- | --------------- |
| Họ và tên       | Phạm Đức Hiệp   |
| MSSV            | 01329           |
| Khóa/Lớp        | [K3]            |
| Vai trò chính   | [Ví dụ: Policy Agent / Data / Coordinator / Docs] |
| Ngày hoàn thành | [YYYY-MM-DD]    |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| [Ví dụ: Policy rules] | [src/data/policy.py] | [OrderBundle findings] | [PolicyDecision] | [Hoàn thành] |
| [Ví dụ: Pipeline] | [src/pipeline.py / main.py] | [input/EC_*.json] | [output/ + trace.jsonl] | [Hoàn thành] |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| [Debug / docs / test] | [Tên hoặc module] | [Kết quả] |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact | Kết quả bàn giao | Cách xác minh |
| --------------------- | ----------------- | ---------------- | ------------- |
| [Mô tả] | [Đường dẫn] | [Artifact] | [Lệnh] |

Artifact cụ thể phần bạn tạo ra:

[Ví dụ: 50 file output/, logging/trace.jsonl, architecture.md, README2.md]

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

[Phần của bạn giải quyết gì trong pipeline điều tra khiếu nại Olist?]

### Cách triển khai

[Thuật toán / quy tắc / orchestration / handoff A2A chính]

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | [Schema case JSON / OrderBundle] |
| Output | [Output schema / A2A message] |
| Module phụ thuộc | [store / agent trước] |
| Module dùng output | [agent sau / pipeline] |
| Điều kiện lỗi | [order không tồn tại, thiếu timestamp, ...] |

### Cách xác minh

```bash
python main.py
python scripts/pack_output.py
```

- **Kết quả mong đợi:** 50 output JSON, 0 errors, zip 50 file
- **Kết quả thực tế:** [Điền sau khi chạy]
- **Artifact/log:** `logging/trace.jsonl`, `logging/metadata.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** [Vấn đề cần chọn hướng]
- **Các phương án:** [Ít nhất 2]
- **Phương án đã chọn:** [Ví dụ: deterministic EC_POLICY_V1 + A2A handoffs thay vì 1 prompt LLM]
- **Lý do:** [Correctness / reproducibility / tránh hallucination số tiền]
- **Bằng chứng:** [Summary by_issue, sample output]

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** [Mô tả]
- **Tái hiện:** [Lệnh]
- **Nguyên nhân gốc:** [Root cause]
- **Cách xử lý:** [Thay đổi cụ thể]
- **Xác minh sau sửa:** [Lệnh + kết quả]
- **Bài học:** [Lesson]

## 7. Hiểu biết về luồng end-to-end

Trả lời bằng lời của bạn:

1. Case JSON đi từ `input/` qua các agent như thế nào đến `output/`?
2. Vì sao phải join orders / order_items / order_payments / sellers thay vì chỉ tin `customer_request.message`?
3. Thứ tự ưu tiên `EC_POLICY_V1` quyết định primary issue ra sao?
4. Evidence ID nào được phép và vì sao ID bịa sẽ thành false positive?
5. `trace.jsonl` và `metadata.json` dùng để kiểm chứng gì khi chấm?

**Câu trả lời:**

[Viết tại đây]

## 8. Cam kết của thành viên

- [ ] Báo cáo phản ánh đúng phần việc và mức hiểu của tôi
- [ ] Tôi giải thích được luồng end-to-end, không chỉ module mình
- [ ] Không ghi “đã chạy thành công” cho phần chưa kiểm chứng
- [ ] Không chứa `.env`, API key, token hoặc secret
- [ ] Không sao chép nguyên văn báo cáo nhóm/thành viên khác

**Họ và tên:** Phạm Đức Hiệp  
**Ngày xác nhận:** [YYYY-MM-DD]
