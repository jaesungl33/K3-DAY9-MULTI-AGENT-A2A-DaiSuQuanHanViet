# Báo cáo vai trò cá nhân — Day 9: Multi-Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Vũ Đức Duy |
| MSSV | 01023 |
| Khóa/Lớp | K3 |
| Vai trò lựa chọn | QA / Output Evaluation & Verification |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

Vai trò của tôi là kiểm tra độc lập chất lượng 50 file kết quả trước khi đóng gói nộp bài. Phần việc tập trung vào các tiêu chí có thể tái hiện từ đề bài và dữ liệu Olist, không nhận ownership cho việc xây dựng các domain agent hoặc tích hợp LLM.

| Module/deliverable phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- |
| `scripts/validate_outputs.py` | 50 input, 50 output, 4 CSV liên quan, `EC_POLICY_V1` | Bộ kiểm tra độc lập chạy bằng một lệnh | Hoàn thành |
| Audit `output/EC_001.json` … `EC_050.json` | JSON output và dữ liệu nguồn | Kết quả 50/50 case pass | Hoàn thành |
| Kiểm tra artifact nộp bài | Nội dung thư mục `output/` | Loại `.gitkeep`, còn đúng 50 JSON | Hoàn thành |
| Báo cáo cá nhân | Source, output, trace và kết quả audit | `individual_01023_VuDucDuy.md` | Hoàn thành |

Các hạng mục kiểm tra gồm:

1. Đủ và đúng tên `EC_001.json` đến `EC_050.json`, không có file lạ trong `output/`.
2. Đủ các trường bắt buộc, đúng `case_id`, giới hạn entity/evidence/root cause/party/action và `confidence` trong `[0, 1]`.
3. Đối chiếu order, item, seller và payment ID trực tiếp với CSV.
4. Tính lại item total, freight total, payment total và refund, làm tròn hai chữ số thập phân.
5. Tính lại `primary_issue` theo đúng thứ tự ưu tiên của `EC_POLICY_V1`, sau đó kiểm tra case status, root cause, responsible party và action.

## 3. Kết quả đánh giá output

Lệnh kiểm tra:

```powershell
python scripts\validate_outputs.py
```

Kết quả cuối:

| Chỉ số | Kết quả |
| --- | ---: |
| Số case đã kiểm tra | 50 |
| Case pass toàn bộ tiêu chí | 50 |
| Case lỗi | 0 |
| File lạ trong `output/` | 0 |

Phân bố kết quả tính lại từ CSV:

| Primary issue | Số case |
| --- | ---: |
| `canceled_order_paid` | 8 |
| `unavailable_order_paid` | 8 |
| `late_delivery_seller` | 8 |
| `late_delivery_logistics` | 8 |
| `valid_split_payment` | 9 |
| `unsupported_late_claim` | 9 |

Đây là kết quả kiểm tra nội bộ theo rubric và dữ liệu trong repo. Repo không chứa artifact điểm số từ leaderboard/hệ thống chấm bên ngoài, vì vậy tôi không suy diễn hay khai báo điểm chính thức.

### Case minh họa: `EC_001`

Order `e2a03ccf5ea816036608b2d8c3ab8e60` có:

- Ngày giao thực tế `2017-12-15 18:56:35`, muộn hơn ngày dự kiến `2017-12-12 00:00:00`.
- Carrier nhận hàng `2017-12-13 13:45:24`, muộn hơn `shipping_limit_date` là `2017-12-04 11:50:50`.
- Item total `119.90` BRL, freight `12.04` BRL, payment `131.94` BRL.

Do đó kết quả đúng là `late_delivery_seller`, seller chịu trách nhiệm, action `refund_freight` và khoản hoàn đề xuất `12.04` BRL. `output/EC_001.json` khớp đầy đủ kết quả này; các evidence ID của order, item, seller, payment và policy đều tồn tại.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Cách bộ kiểm tra hoạt động

Script audit dùng thư viện chuẩn Python (`csv`, `json`, `pathlib`) và tự xây một oracle độc lập:

1. Đọc `claimed_order_id` từ từng input.
2. Join order với item và payment bằng `order_id`; tạo tập seller hợp lệ từ sellers CSV.
3. Tính các facts: tổng tiền, payment reconciliation, giao trễ, seller bàn giao trễ và split payment.
4. Áp dụng lần lượt sáu policy rule theo thứ tự ưu tiên trong README.
5. So sánh expected result với từng phần của output và trả exit code khác 0 nếu có sai lệch.

Tôi không gọi lại trực tiếp `PolicyAgent` hay `VerifierAgent` trong script audit. Cách này giúp tránh trường hợp code sinh output và code kiểm tra cùng dùng một hàm sai nhưng vẫn báo pass.

### Các hạng mục đã xác minh thêm

`trace.jsonl` có 650 event thuộc đủ 50 case:

| Event | Số lượng |
| --- | ---: |
| `case_start` | 50 |
| `llm_call` | 300 |
| `handoff` | 200 |
| `verification` | 50 |
| `case_complete` | 50 |

Mỗi agent trong sáu agent (`order_seller`, `payment`, `delivery`, `policy`, `verifier`, `coordinator`) có 50 `llm_call`. Điều này xác nhận trace có luồng xử lý thực cho toàn bộ 50 case, không chỉ có output tĩnh.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần kiểm tra output nhưng nếu tái sử dụng chính logic sản xuất thì có thể bỏ sót lỗi chung giữa generator và validator.
- **Phương án cân nhắc:** đọc mẫu thủ công; gọi lại các agent; hoặc xây oracle độc lập từ CSV và policy được công bố.
- **Lựa chọn:** xây oracle độc lập trong `scripts/validate_outputs.py`.
- **Lý do:** kiểm tra được cả sáu thành phần chấm điểm, chạy lại nhanh, không cần API key và phát hiện được sai lệch thực sự so với dữ liệu nguồn.
- **Bằng chứng:** script kiểm tra đủ 50 case, tính ra sáu nhóm issue với phân bố 8/8/8/8/9/9 và kết thúc exit code 0 sau khi sửa artifact đóng gói.

## 6. Một lỗi đã phát hiện và xử lý

- **Triệu chứng:** lần chạy audit đầu tiên báo `unexpected non-JSON files in output/: ['.gitkeep']` và trả exit code 1.
- **Nguyên nhân:** file giữ chỗ `.gitkeep` vẫn nằm trong `output/`, trong khi README yêu cầu file zip chứa đúng 50 JSON và không có file lạ.
- **Xử lý:** xóa `output/.gitkeep`.
- **Xác minh sau sửa:** chạy lại `python scripts\validate_outputs.py` cho kết quả `checked_cases: 50`, `passed_cases: 50`, `failed_cases: []`, `file_errors: []`.
- **Điều học được:** kiểm tra nội dung từng JSON là chưa đủ; cấu trúc artifact đóng gói cũng là một điều kiện nộp bài có thể làm kết quả bị từ chối.

## 7. Hiểu biết về luồng end-to-end

1. **Input đi đến output thế nào?** Coordinator đọc input, lần lượt nhận handoff từ Order & Seller, Payment, Delivery và Policy; Verifier kiểm tra draft trước khi Coordinator ghi output.
2. **Nguồn sự thật là gì?** Các facts về order, item, seller, payment và timestamp đến từ CSV. Nội dung khiếu nại cung cấp ngữ cảnh nhưng không được dùng để tự tạo evidence.
3. **Vì sao policy phải có thứ tự ưu tiên?** Một order có thể đồng thời thỏa nhiều dấu hiệu. Ví dụ order canceled đã thanh toán phải ưu tiên hoàn toàn bộ trước khi xét giao trễ hoặc split payment.
4. **Hard gate quan trọng ở đâu?** Evidence ID không tồn tại, JSON sai schema hoặc thiếu output có thể làm cả case nhận 0 điểm; vì vậy audit kiểm tra các điều kiện này trước khi đánh giá nội dung.
5. **Artifact nào chứng minh pipeline đã chạy?** 50 output chứng minh kết quả; `trace.jsonl` chứng minh chuỗi agent/handoff/LLM call; script audit chứng minh output khớp policy và dữ liệu nguồn.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc QA/output verification tôi đã thực hiện.
- [x] Tôi có thể giải thích luồng end-to-end và cách từng phần output được xác minh.
- [x] Tôi không khai báo điểm leaderboard khi repo không có artifact điểm chính thức.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo không sao chép nguyên văn báo cáo của thành viên khác.

**Họ và tên:** Vũ Đức Duy  
**Ngày xác nhận:** 2026-08-05
