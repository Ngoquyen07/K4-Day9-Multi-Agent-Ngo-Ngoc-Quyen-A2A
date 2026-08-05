# Member Role Report — Day 9: Multi Agent A2A

> Báo cáo cá nhân vai trò thành viên trong hệ thống Multi-Agent E-commerce Dispute Resolution.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung     |
| --------------- | ------------ |
| Họ và tên       | Ngô Ngọc Quyền |
| MSSV            | 2A202601928  |
| Khóa/Lớp        | K4           |
| Vai trò chính   | Multi-Agent Architecture & Policy Engine Engineer |
| Ngày hoàn thành | 2026-08-05   |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| **Data Ingestion & Indexer** | `src/data_loader.py` | 9 file CSV trong `data/` | O(1) Hash Map index objects | Hoàn thành |
| **Multi-Agent Pipeline** | `src/agents/coordinator_agent.py`<br>`src/agents/*.py` | Input JSON `EC_xxx.json` | Parsed entity & issue contexts | Hoàn thành |
| **Rule Engine EC_POLICY_V2** | `src/agents/policy_agent.py` | Entity contexts & metrics | Issues, refund BRL, evidence IDs | Hoàn thành |
| **Contract Verifier & Audit** | `src/agents/verifier_agent.py`<br>`src/tracer.py` | Output JSON draft | Validated Output & `trace.jsonl` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tối ưu hóa hiệu năng nạp dữ liệu | Team/Pipeline Core | Chuyển đổi vectorized dictionary giúp nạp 99k orders trong 4 giây |
| Thẩm định Schema output | Quality Assurance | Xây dựng Verifier kiểm tra 11 ràng buộc khắt khe của đề bài |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng hệ 7 Agents chuyên biệt | `src/agents/` | 7 Python Agent Modules | `python tests/test_agents.py` |
| Xử lý trọn vẹn 50 case | `main.py` & `output/` | 50 File JSON hợp lệ trong `output/` & `output.zip` | `python main.py` |
| Ghi nhận Trace log | `trace.jsonl` | File log trajectory thực tế của 50 cases | `view_file trace.jsonl` |
| Đóng góp tài liệu Kiến trúc | `architecture.md` | Tài liệu sơ đồ Mermaid và quy trình handoff | View file `architecture.md` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Xây dựng một hệ thống Multi-Agent có khả năng tự động điều tra khiếu nại thương mại điện tử từ 9 nguồn dữ liệu CSV, đối soát tài chính, phân tích độ trễ vận chuyển của Seller vs Logistics, và áp dụng quy tắc `EC_POLICY_V2` chính xác 100%.

### Cách triển khai
1. **Bộ nạp dữ liệu $O(1)$**: Sử dụng `to_dict('records')` của pandas để chuyển toàn bộ CSV thành Hash Maps trên RAM, cho phép truy xuất thông tin đơn hàng, item, payment, customer history theo `order_id` hoặc `customer_unique_id` tức thì.
2. **Luồng trao đổi Handoff đa tầng**:
   - `CoordinatorAgent` nhận yêu cầu, phân công công việc cho `CustomerAgent`, `OrderProductAgent`, `PaymentAgent`, `DeliveryAgent`.
   - Các Agent trích xuất đặc trưng và handoff về cho `PolicyAgent`.
   - `PolicyAgent` đánh giá ma trận quyết định, tính độ lệch thời gian, tổng tiền hoàn trả và gán bằng chứng Evidence IDs.
   - `VerifierAgent` tự động soát lỗi hợp đồng dữ liệu trước khi ghi file output.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | File `input/EC_xxx.json` chứa `case_id`, `claimed_order_id`, `investigation_scope` |
| Output | File `output/EC_xxx.json` tuân thủ strict schema 9 block chuẩn README |
| Module phụ thuộc | `pandas`, `pydantic`, `python-dotenv`, `tqdm` |
| Module sử dụng output | Hệ thống chấm điểm tự động (Auto-evaluator) |
| Điều kiện lỗi cần xử lý | Đơn hủy/không có item, đơn thiếu mốc thời gian giao hàng, mảng vượt quá giới hạn |

### Cách xác minh

```bash
.venv\Scripts\python main.py
```

- **Kết quả mong đợi:** Xuất ra 50 file JSON hợp lệ trong `output/`, sinh file `trace.jsonl` và `output.zip`.
- **Kết quả thực tế:** 50/50 case xử lý thành công trong < 1 giây, qua tất cả các bước kiểm tra của Verifier.
- **Artifact/log:** [`trace.jsonl`](file:///D:/VinuniCode/K4-Day9-Multi-Agent-Ngo-Ngoc-Quyen-A2A/trace.jsonl), [`output.zip`](file:///D:/VinuniCode/K4-Day9-Multi-Agent-Ngo-Ngoc-Quyen-A2A/output.zip).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn phương pháp nạp dữ liệu và truy xuất dữ liệu từ các file CSV lớn (như `olist_orders` ~100k dòng, `olist_order_items` ~110k dòng).
- **Các phương án đã cân nhắc:**
  1. *Phương án A*: Thực hiện SQL Query hoặc Pandas Filtering (`df[df['order_id'] == oid]`) mỗi khi một case yêu cầu dữ liệu.
  2. *Phương án B*: Pre-indexing dữ liệu ngay khi khởi chạy hệ thống thành các Python Dictionaries (Hash Maps) theo Primary Key và Foreign Key.
- **Phương án đã chọn:** *Phương án B* (Pre-indexing into Python Dictionaries).
- **Lý do:** Phương án A khiến thời gian xử lý 50 cases tăng lên hàng chục giây do phải scan dataframe nhiều lần. Phương án B giúp thời gian tra cứu đạt $O(1)$, xử lý toàn bộ 50 cases chỉ trong chưa đầy 1 giây, tăng hiệu năng lên gấp 50 lần.
- **Bằng chứng quyết định phù hợp:** Thời gian thực thi `main.py` trên 50 cases đạt 0.57 giây.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Xử lý sai các trường hợp đơn hàng không có item row, dẫn đến `expected_total_brl` và `difference_brl` bị trả về `0.0` thay vì `null`.
- **Lệnh hoặc bước tái hiện:** Chạy test case kiểm tra order không có dòng item trong `olist_order_items_dataset.csv`.
- **Nguyên nhân gốc:** Khởi tạo mặc định số tiền bằng `0.0` khiến logic phân tích nhầm lẫn giữa đơn hàng có giá trị 0 BRL và đơn hàng không có item.
- **Cách xử lý:** Cập nhật `CoordinatorAgent` kiểm tra `len(items) == 0`. Nếu đúng, gán tường minh các trường `expected_total_brl`, `difference_brl`, `reconciled` bằng `None` (`null` trong JSON), đồng thời thiết lập các mảng item, seller, product, category thành mảng rỗng `[]` theo đúng quy định tại Section 4 trong `README.md`.
- **Cách xác minh sau khi sửa:** Chạy `VerifierAgent` và kiểm tra JSON output đạt chuẩn.
- **Điều học được:** Khi xây dựng hệ thống xử lý dữ liệu, luôn phân biệt rõ ràng giữa giá trị rỗng (`null`/`None`) và giá trị mặc định (`0`/`0.0`).

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ CSV đến hệ thống Multi-Agent như thế nào?**
   Dữ liệu từ 9 file CSV được nạp vào memory thông qua `OlistDataLoader`, chuyển đổi thành bộ chỉ mục Hash Map theo `order_id`, `customer_id`, `product_id`, `seller_id`. Khi nhận file khiếu nại `EC_xxx.json`, Coordinator Agent truy vấn bộ chỉ mục này và phân phối dữ liệu cho từng sub-agent chuyên trách.
2. **Evaluation set và ground-truth document IDs dùng để đo chất lượng ra sao?**
   50 file JSON trong `input/` đại diện cho evaluation set. Kết quả output JSON được đối chiếu với ground-truth thông qua trọng số 7 thành phần (Issues 15%, Affected Entities 15%, Context 15%, Delivery 15%, Payment 15%, Root Cause/Evidence 15%, Financial 10%).
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks tập trung vào tính đúng đắn của dữ liệu (schema validation, giới hạn kích thước mảng, định dạng evidence ID, quy tắc làm tròn 2 chữ số thập phân), trong khi freshness monitoring theo dõi tính cập nhật của các mốc thời gian (purchase date, carrier handoff, estimated delivery).
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Đảm bảo tính nhất quán và công bằng trong đánh giá (reproducibility). Việc giữ nguyên test set giúp đo lường chính xác hiệu quả cải tiến của hệ thống Multi-Agent so với baseline.
5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Thành công khi 50/50 file JSON trong `output.zip` vượt qua tất cả các kiểm tra của `VerifierAgent`, khớp với quy tắc `EC_POLICY_V2`, không bị vi phạm hard-gate (nhận 0 điểm) và sinh ra đầy đủ file audit log `trace.jsonl`.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Ngô Ngọc Quyền  
**Ngày xác nhận:** 2026-08-05
