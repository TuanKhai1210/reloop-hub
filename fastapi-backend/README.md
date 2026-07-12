# ReLoop Hub Backend

Backend FastAPI cho nền tảng logistics ngược ReLoop Hub. API này triển khai prototype end-to-end từ người dùng đưa chai vào Smart RVM, Edge AI/cảm biến kiểm định, cộng điểm, cập nhật mức đầy realtime, lập tuyến DVRP, thu gom, truy xuất vật liệu đến báo cáo ESG.

## Chức năng đã triển khai

- Giám sát Hub: trạng thái online/offline/full, camera, cảm biến, tải hiện tại, lịch sử telemetry.
- Realtime: WebSocket `/ws/hubs?token=...` phát sự kiện telemetry và giao dịch mới.
- Kiểm soát chất lượng: chỉ nhận PET/HDPE khi AI confidence >= 0,80, độ sạch >= 0,70, không còn nước và không có dị vật.
- Điểm thưởng: cộng điểm theo khối lượng (PET 10 điểm/100g, HDPE 12 điểm/100g) và lưu sổ cái đối soát.
- Quản lý người dùng: lọc tài khoản theo vai trò/trạng thái, thay đổi quyền, khóa tài khoản và đổi điểm có kiểm tra số dư.
- DVRP prototype: nearest-neighbour theo vị trí, ngưỡng đầy và dung tích xe; so sánh với lịch cố định.
- Truy xuất nguồn gốc: một `trace_code` cho mỗi giao dịch và timeline từ Hub đến nhà máy tái chế.
- Dashboard/ESG: tổng hợp ngày, tuần hoặc tháng; PET, HDPE, CO2e, quãng đường giảm, người tham gia, giao dịch, chất lượng và số tuyến.
- Phân quyền: admin, operator, driver, recycler và resident bằng JWT; Hub dùng API key riêng.

## Chạy nhanh bằng Python

Yêu cầu Python 3.11 trở lên.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
python -m app.seed
uvicorn app.main:app --reload
```

Mở Swagger UI tại `http://localhost:8000/docs`. Tài khoản demo:

- Admin: `admin@reloop.vn` / `Admin@123`
- Người dân: `student@reloop.vn` / `Student@123`
- Device API key: `demo-device-key`

## Chạy bằng Docker

```powershell
docker compose up --build
```

Compose sử dụng PostgreSQL 16 và tự seed dữ liệu mẫu. Trước khi triển khai thật, phải thay `JWT_SECRET`, `DEVICE_API_KEY` và mật khẩu PostgreSQL.

## Luồng demo

1. Gọi `POST /api/v1/auth/token` theo OAuth2 form để lấy JWT.
2. Hub gửi `POST /api/v1/hubs/{hub_code}/telemetry` với header `X-Device-Key`.
3. Edge AI gửi kết quả đến `POST /api/v1/deposits/inspect`. API trả `accept_and_store` hoặc `reject_and_return` và hướng dẫn cụ thể.
4. Operator gọi `POST /api/v1/routes/optimize`, sau đó driver bắt đầu tuyến, ghi nhận pickup tại từng stop và hoàn thành tuyến.
5. Tra cứu hành trình tại `GET /api/v1/traceability/{trace_code}`.
6. Dashboard gọi `GET /api/v1/dashboard/summary` và `GET /api/v1/reports/esg?period=day|week|month&anchor_date=YYYY-MM-DD`.

API đổi điểm ghi nhận giao dịch nội bộ và kênh thanh toán mong muốn. Việc chuyển tiền thật qua MoMo/ZaloPay được giữ ở ranh giới tích hợp; production cần adapter theo hợp đồng và webhook của nhà cung cấp tương ứng.

## Ví dụ kiểm định chai

```bash
curl -X POST http://localhost:8000/api/v1/deposits/inspect \
  -H "Content-Type: application/json" \
  -H "X-Device-Key: demo-device-key" \
  -d '{"user_id":2,"hub_code":"HUB-UEH-01","material_type":"PET","weight_g":120,"ai_confidence":0.97,"cleanliness_score":0.91,"liquid_detected":false,"foreign_object_detected":false}'
```

## Kiểm thử

```powershell
pytest
```

Test tự động kiểm tra auth, telemetry, nhận/từ chối chai, điểm thưởng, dashboard, tạo và hoàn thành tuyến, truy xuất nguồn gốc, ESG và bảo vệ API thiết bị.

## Ghi chú cho pilot thực tế

- Hệ số CO2e trong `app/services/reporting.py` là giả định prototype và được trả kèm trường `methodology`; cần thay bằng hệ số LCA đã được thẩm định trước khi dùng cho ESG chính thức.
- Heuristic hiện tại phù hợp simulation prototype. Pilot nhiều xe/cửa sổ thời gian nên thay bằng OR-Tools DVRP, dùng dịch vụ ma trận thời gian đường bộ thay cho khoảng cách Haversine.
- `create_all` giúp demo chạy nhanh. Khi đưa vào production nên quản lý schema bằng Alembic, luân chuyển device key, dùng Redis pub/sub cho nhiều API replica và hàng đợi sự kiện để Hub có thể đồng bộ bù sau khi mất mạng.
