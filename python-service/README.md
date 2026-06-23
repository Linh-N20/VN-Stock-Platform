# VNStock Data Service

FastAPI microservice cung cấp dữ liệu chứng khoán Việt Nam.

## Cài đặt

```bash
cd python-service

# Tạo virtual environment (khuyến nghị)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Cài dependencies
pip install -r requirements.txt

# Chạy service
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoints

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/health` | Kiểm tra service |
| GET | `/stocks/quote/{symbol}` | Giá hiện tại |
| GET | `/stocks/history/{symbol}?days=90` | Lịch sử giá |
| GET | `/stocks/indicators/{symbol}` | RSI, MACD, BB + tín hiệu |
| GET | `/stocks/watchlist?symbols=VNM,VCB` | Nhiều cổ phiếu cùng lúc |
| GET | `/stocks/search?q=VN` | Tìm kiếm cổ phiếu |

## Swagger UI

Sau khi chạy, truy cập: http://localhost:8000/docs

## Test nhanh

```bash
curl http://localhost:8000/health
curl http://localhost:8000/stocks/quote/VNM
curl http://localhost:8000/stocks/indicators/FPT
```
