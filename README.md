# VN Stock Platform

Website phân tích kỹ thuật và học chứng khoán Việt Nam.  
Dùng tín hiệu RSI, MACD, Bollinger Bands để gợi ý BUY/HOLD/SELL — **không phải lời khuyên đầu tư**.

![Java](https://img.shields.io/badge/Java-17+-orange)
![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.2-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-teal)

---

## Kiến trúc

```
python-service/     ← FastAPI + VNStock: lấy dữ liệu HoSE/HNX
spring-service/     ← Spring Boot + Thymeleaf: web app chính
```

```
Browser → Spring Boot (8080) → Python FastAPI (8000) → VNStock → TCBS API
                ↓
            H2 / MySQL (lưu lịch sử giá + tín hiệu)
```

---

## Tính năng

| Tính năng | Mô tả |
|---|---|
| **Dashboard** | Watchlist 8 cổ phiếu lớn + tín hiệu BUY/HOLD/SELL |
| **Chi tiết cổ phiếu** | Biểu đồ 90 ngày + RSI, MACD, Bollinger Bands |
| **Tín hiệu tổng hợp** | Scoring rule-based từ 4 chỉ số kỹ thuật |
| **Tìm kiếm** | Tìm cổ phiếu theo mã hoặc tên |
| **Học chứng khoán** | Bài học RSI, MACD, BB + từ điển thuật ngữ |
| **Auto refresh** | Scheduler tự cập nhật dữ liệu lúc 18:00 thứ 2–6 |

---

## Cài đặt & Chạy

### Yêu cầu
- Java 17+ & Maven 3.6+
- Python 3.10+

### Bước 1 — Chạy Python service

Mở Terminal 1:
```bash
cd python-service

pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Kiểm tra: http://localhost:8000/docs

### Bước 2 — Chạy Spring Boot

Mở Terminal 2:
```bash
cd spring-service
mvn spring-boot:run
```

Mở: **http://localhost:8080**

---

## Chỉ số kỹ thuật được sử dụng

| Chỉ số | Tham số | Tín hiệu |
|---|---|---|
| RSI | 14 phiên | < 30 = quá bán (+2đ), > 70 = quá mua (−2đ) |
| MACD | 12/26/9 | Cắt lên signal (+2đ), cắt xuống (−2đ) |
| MA Cross | MA20/MA50 | Giá > MA20 > MA50 = uptrend (+2đ) |
| Bollinger | 20 phiên | Chạm dải dưới (+1đ), chạm dải trên (−1đ) |

**Kết luận:** Tổng điểm ≥ 3 → BUY | ≤ −3 → SELL | còn lại → HOLD

---

## Disclaimer

Thông tin trên website **chỉ mang tính tham khảo kỹ thuật**, không phải lời khuyên đầu tư.  
Mọi quyết định đầu tư đều có rủi ro. Hãy tự nghiên cứu kỹ trước khi giao dịch.

---

*Portfolio project — HCMUT 2026*
