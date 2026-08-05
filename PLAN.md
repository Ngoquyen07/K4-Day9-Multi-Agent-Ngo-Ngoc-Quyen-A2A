# K4 Day 09 - Multi-Agent E-commerce Dispute Resolution
## Kế Hoạch Triển Khai & Kiến Trúc Hệ Thống (Master Plan)

---

## 1. Tổng Quan & Cấu Hình Model

### 1.1. Mục tiêu Dự án
Xây dựng hệ thống Multi-Agent tự động điều tra và giải quyết **50 trường hợp khiếu nại (Dispute Resolution)** trên bộ dữ liệu thương mại điện tử Olist (Brazil). Hệ thống sẽ đọc dữ liệu từ `input/EC_001.json` đến `input/EC_050.json`, đối soát toàn bộ cơ sở dữ liệu Olist trong `data/`, áp dụng quy tắc nghiệp vụ `EC_POLICY_V2`, và kết xuất kết quả hợp lệ vào `output/EC_001.json` đến `output/EC_050.json`.

### 1.2. Cấu hình Model & Provider
- **Model chính**: `nvidia/nemotron-nano-9b-v2:free` (Parameter size: 9B <= 10B theo đúng quy định đề bài).
- **API Provider**: OpenRouter API (`https://openrouter.ai/api/v1`).
- **Biến môi trường**: `OPENROUTER_API_KEY` được load từ `.env`.
- **API Client**: OpenAI Client (phù hợp với OpenRouter base URL).

---

## 2. Kiến Trúc Hệ Thống Multi-Agent (A2A Architecture)

Hệ thống được thiết kế theo mô hình **Multi-Agent Phân Cấp & Chuyên Môn Hóa (Hierarchical & Specialized Multi-Agent)** gồm 7 Agent làm việc phối hợp qua hợp đồng dữ liệu (data contract):

```
                                ┌────────────────────────┐
                                │   Coordinator Agent    │
                                └───────────┬────────────┘
                                            │ (Phân công & Tổng hợp)
        ┌────────────────┬──────────────────┼────────────────┬────────────────┐
        ▼                ▼                  ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Customer Agent│ │ Order Agent  │   │Payment Agent │ │Delivery Agent│ │ Policy Agent │
└───────┬──────┘ └──────┬───────┘   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
        │               │                  │                │                │
        └───────────────┴──────────────────┴────────────────┴────────────────┘
                                            │ (Handoff data)
                                            ▼
                                   ┌────────────────┐
                                   │ Verifier Agent │
                                   └────────────────┘
```

### Chi tiết các Agent:
1. **Coordinator Agent**:
   - **Vai trò**: Tiếp nhận `case_id` và `claimed_order_id` từ file input, điều phối các sub-agent, thu thập thông tin và tạo cấu trúc JSON cuối cùng.
2. **Customer Agent**:
   - **Vai trò**: Tra cứu thông tin khách hàng từ `customer_id` sang `customer_unique_id`, tìm kiếm lịch sử các order khác của cùng khách hàng (`related_order_ids`).
3. **Order & Product Agent**:
   - **Vai trò**: Đọc thông tin các item, sản phẩm, dịch tên danh mục (`category_name`) và các seller liên quan.
4. **Payment Agent**:
   - **Vai trò**: Tổng hợp tất cả các dòng payment, tính tổng tiền thanh toán, đối soát (reconciliation) với tổng giá trị sản phẩm + phí vận chuyển (`expected_total_brl`).
5. **Delivery Agent**:
   - **Vai trò**: Phân tích các mốc thời gian giao hàng, tính độ lệch muộn giao hàng (`delivery_variance_hours`), phân tích việc bàn giao cho đơn vị vận chuyển của từng seller (`seller_handoff_analysis`, `handoff_variance_hours`).
6. **Policy Agent**:
   - **Vai trò**: Áp dụng quy tắc nghiệp vụ `EC_POLICY_V2` để quyết định `primary_issue`, `secondary_issues`, bên chịu trách nhiệm (`responsible_parties`), số tiền hoàn trả (`recommended_refund_brl`), mã nguyên nhân gốc (`root_cause_analysis`), bằng chứng (`evidence_ids`) và danh sách hành động xử lý (`resolution_actions`).
7. **Verifier Agent**:
   - **Vai trò**: Kiểm tra tính hợp lệ của JSON đầu ra (schema validation, giới hạn mảng, định dạng evidence ID, xử lý trường hợp null, làm tròn 2 chữ số thập phân) trước khi ghi file output.

---

## 3. Quy Tắc Nghiệp Vụ `EC_POLICY_V2` & Thuật Toán Đối Soát

### 3.1. Phân loại Vấn đề Chính (Primary Issue Decision Matrix)

| Primary issue | Điều kiện kích hoạt | Responsible party | Số tiền hoàn (Refund) | Action chính |
| :--- | :--- | :--- | :---: | :--- |
| `canceled_order_paid` | `order_status = canceled` và Tổng payment > 0 | `platform` / `OLIST_PLATFORM` | Tổng payment | `issue_full_refund` |
| `unavailable_order_paid` | `order_status = unavailable` và Tổng payment > 0 | `platform` / `OLIST_PLATFORM` | Tổng payment | `issue_full_refund` |
| `late_delivery_seller` | Giao sau `estimated_date` VÀ ít nhất 1 seller bàn giao hàng muộn hơn `shipping_limit_date` | `seller` / Các seller vi phạm | Tổng freight | `refund_freight` |
| `late_delivery_logistics` | Giao sau `estimated_date` VÀ không seller nào bàn giao muộn | `logistics_provider` / `LOGISTICS_PROVIDER` | Tổng freight | `refund_freight` |
| `valid_split_payment` | Có từ 2 payment rows trở lên VÀ sum(payment) khớp sum(item + freight) trong sai số $\le 0.10$ BRL | Không có | 0 | `explain_valid_split_payment` |
| `unsupported_late_claim` | Đơn không giao muộn hơn `estimated_date` VÀ thanh toán khớp | Không có | 0 | `reject_late_refund` |

### 3.2. Secondary Issues (Thứ tự thêm cố định)
1. `multi_item_order`: Số dòng item $\ge 2$
2. `multi_seller_order`: Số seller khác nhau $\ge 2$
3. `split_payment`: Số dòng payment $\ge 2$
4. `repeat_customer`: Cùng `customer_unique_id` có các order khác trong quá khứ/tương lai
5. `multiple_categories`: Số danh mục sản phẩm khác nhau $\ge 2$

### 3.3. Các công thức tính toán
- $\text{delivery\_variance\_hours} = \text{order\_delivered\_customer\_date} - \text{order\_estimated\_delivery\_date}$ (chuyển sang giờ, làm tròn 2 chữ số thập phân).
- $\text{handoff\_variance\_hours} = \text{order\_delivered\_carrier\_date} - \text{shipping\_limit\_date}$ (sớm nhất của seller).
- $\text{expected\_total\_brl} = \sum (\text{items.price}) + \sum (\text{items.freight\_value})$.
- $\text{difference\_brl} = \sum (\text{payments.payment\_value}) - \text{expected\_total\_brl}$.
- $\text{reconciled} = |\text{difference\_brl}| \le 0.10$ BRL.
- *Trường hợp không có item nào (Đơn hủy/không có item)*: `expected_total_brl`, `difference_brl` và `reconciled` gán bằng `null`.

### 3.4. Định dạng Evidence IDs chuẩn
- `order:<order_id>`
- `item:<order_id>:<order_item_id>`
- `payment:<order_id>:<payment_sequential>`
- `seller:<seller_id>`
- `policy:<root_cause_code>`

### 3.5. Ràng buộc Kích thước Mảng (Array Limits)
- `order_ids` $\le 5$
- `item_ids` $\le 5$
- `seller_ids` $\le 3$
- `payment_ids` $\le 5$
- `related_order_ids` $\le 5$
- `product_ids` $\le 5$
- `category_names` $\le 5$
- `ranked_causes` $\le 3$
- `responsible_parties` $\le 3$
- `evidence_ids` $\le 20$
- `resolution_actions` $\le 5$

---

## 4. Danh Sách Các Bước Triển Khai (Execution Steps Roadmap)

### Step 1: Cấu Hình Môi Trường & Dự Án (Project Setup)
- Khởi tạo virtual environment và cài đặt `requirements.txt` (`pandas`, `openai`, `pydantic`, `python-dotenv`, `tqdm`).
- Xác nhận biến môi trường `OPENROUTER_API_KEY` trong file `.env`.
- Tạo file cấu hình `metadata.json` khai báo model name: `nvidia/nemotron-nano-9b-v2:free`.

### Step 2: Bộ Tải & Trích Xuất Dữ Liệu Tốc Độ Cao (Data Ingestion & Fast Indexer)
- Xây dựng module `src/data_loader.py` tự động nạp 9 file CSV từ `data/`.
- Tạo bộ chỉ mục (Index map/Hash tables) theo `order_id`, `customer_id`, `customer_unique_id`, `product_id`, `seller_id` để lookup dữ liệu O(1) đạt hiệu năng tối đa.

### Step 3: Xây Dựng Các Agent & Rule Engine Cốt Lõi
- `src/agents/customer_agent.py`: Trích xuất thông tin khách hàng và lịch sử đơn.
- `src/agents/order_product_agent.py`: Trích xuất sản phẩm, seller, dịch tên danh mục.
- `src/agents/payment_agent.py`: Phân tích thanh toán và đối soát tài chính.
- `src/agents/delivery_agent.py`: Phân tích độ lệch thời gian giao hàng và bàn giao cho đơn vị vận chuyển.
- `src/agents/policy_agent.py`: Thực thi bảng quy tắc `EC_POLICY_V2`, phân loại issue, tính toán refund và tạo evidence IDs.
- `src/agents/verifier_agent.py`: Kiểm tra schema, kiểu dữ liệu, các ràng buộc giới hạn mảng, rounding và null handling.

### Step 4: Xây Dựng Hệ Thống Logging & Trace (`trace.jsonl`)
- Triển khai `src/tracer.py` để ghi lại lịch sử gọi agent, input/output và trao đổi thông tin của từng case vào `trace.jsonl`.

### Step 5: Chạy Pipeline Điều Tra Cho 50 Cases (`input/` -> `output/`)
- Đọc 50 file trong `input/EC_001.json` ... `EC_050.json`.
- Chạy hệ thống Multi-Agent hoàn chỉnh để tạo 50 file tương ứng trong `output/EC_001.json` ... `output/EC_050.json`.

### Step 6: Kiểm Tra Đánh Giá & Hoàn Thiện Hồ Sơ Nộp Bài
- Chạy kiểm thử tự động toàn bộ 50 file output thông qua Verifier.
- Sinh file báo cáo kiến trúc `architecture.md` (ở root repo).
- Sinh file báo cáo cá nhân `individual_5SoCuoiMHV_HoVaTen.md` (ở root repo).
- Nén thư mục `output/` thành file `.zip` sẵn sàng cho việc nộp bài.

---

## 5. Danh Mục Các Deliverables Bắt Buộc

| Deliverable | Vị trí file | Nội dung / Mục đích |
| :--- | :--- | :--- |
| `PLAN.md` | `PLAN.md` | Bản kế hoạch chi tiết triển khai bài toán multi-agent |
| `metadata.json` | `metadata.json` | Thông tin model `nvidia/nemotron-nano-9b-v2:free`, parameter size, runtime |
| `architecture.md` | `architecture.md` | Sơ đồ agent, vai trò, quyền truy cập và luồng handoff |
| `trace.jsonl` | `trace.jsonl` | Log thực thi chi tiết lượt chạy 50 cases |
| `individual_*.md` | `individual_*.md` | Báo cáo cá nhân thành viên |
| 50 Output JSONs | `output/EC_001.json` -> `EC_050.json` | Kết quả điều tra 50 khiếu nại |

---
