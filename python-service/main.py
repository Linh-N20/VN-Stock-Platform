"""
VNStock Data Service
--------------------
FastAPI microservice cung cấp dữ liệu chứng khoán Việt Nam cho Spring Boot.

Chạy: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import logging

# ── Khởi tạo app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="VNStock Data Service",
    description="Cung cấp dữ liệu chứng khoán Việt Nam từ TCBS/SSI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # Spring Boot
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Danh sách cổ phiếu theo dõi mặc định ──────────────────────────────────────
DEFAULT_WATCHLIST = [
    "VNM", "VCB", "HPG", "MWG", "FPT",
    "VIC", "MSN", "TCB", "VHM", "ACB"
]


def get_stock_client():
    """Lấy client VNStock - lazy import để tránh crash khi chưa cài."""
    try:
        from vnstock import Vnstock
        return Vnstock()
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="vnstock3 chưa được cài. Chạy: pip install vnstock3"
        )


def safe_float(val) -> Optional[float]:
    """Convert giá trị sang float, trả về None nếu NaN/None."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    """Kiểm tra service còn sống không."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/stocks/quote/{symbol}")
def get_quote(symbol: str):
    """
    Lấy giá hiện tại của một cổ phiếu.
    
    Ví dụ: GET /stocks/quote/VNM
    """
    symbol = symbol.upper().strip()
    logger.info(f"Fetching quote for {symbol}")
    try:
        stock = get_stock_client().stock(symbol=symbol, source="VCI")
        df = stock.quote.history(
            start=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
            end=datetime.now().strftime("%Y-%m-%d"),
            interval="1D"
        )
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy dữ liệu cho {symbol}")

        latest = df.iloc[-1]
        prev   = df.iloc[-2] if len(df) > 1 else latest

        current_price = safe_float(latest.get("close"))
        prev_price    = safe_float(prev.get("close"))
        change        = round(current_price - prev_price, 2) if current_price and prev_price else None
        change_pct    = round((change / prev_price) * 100, 2) if change and prev_price else None

        return {
            "symbol":        symbol,
            "currentPrice":  current_price,
            "open":          safe_float(latest.get("open")),
            "high":          safe_float(latest.get("high")),
            "low":           safe_float(latest.get("low")),
            "volume":        safe_float(latest.get("volume")),
            "change":        change,
            "changePct":     change_pct,
            "date":          str(latest.get("time", datetime.now().date())),
            "source":        "TCBS"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching quote for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/history/{symbol}")
def get_history(
    symbol: str,
    days: int = Query(default=90, ge=7, le=365, description="Số ngày lịch sử")
):
    """
    Lấy lịch sử giá theo ngày.
    Dùng để vẽ candlestick chart và tính technical indicators.
    
    Ví dụ: GET /stocks/history/VNM?days=90
    """
    symbol = symbol.upper().strip()
    logger.info(f"Fetching {days}-day history for {symbol}")
    try:
        stock  = get_stock_client().stock(symbol=symbol, source="VCI")
        start  = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end    = datetime.now().strftime("%Y-%m-%d")
        df     = stock.quote.history(start=start, end=end, interval="1D")

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"Không có dữ liệu lịch sử cho {symbol}")

        records = []
        for _, row in df.iterrows():
            records.append({
                "date":   str(row.get("time", "")),
                "open":   safe_float(row.get("open")),
                "high":   safe_float(row.get("high")),
                "low":    safe_float(row.get("low")),
                "close":  safe_float(row.get("close")),
                "volume": safe_float(row.get("volume")),
            })

        return {"symbol": symbol, "days": days, "data": records, "count": len(records)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/indicators/{symbol}")
def get_indicators(
    symbol: str,
    days: int = Query(default=90, ge=30, le=365)
):
    """
    Tính toán các chỉ số kỹ thuật: RSI, MACD, Bollinger Bands, MA.
    Đây là engine chính để tạo tín hiệu BUY/HOLD/SELL.
    
    Ví dụ: GET /stocks/indicators/VNM
    """
    symbol = symbol.upper().strip()
    logger.info(f"Computing indicators for {symbol}")
    try:
        stock  = get_stock_client().stock(symbol=symbol, source="VCI")
        start  = (datetime.now() - timedelta(days=days + 60)).strftime("%Y-%m-%d")
        end    = datetime.now().strftime("%Y-%m-%d")
        df     = stock.quote.history(start=start, end=end, interval="1D")

        if df is None or df.empty or len(df) < 20:
            raise HTTPException(status_code=404, detail="Không đủ dữ liệu để tính indicators")

        close = df["close"].astype(float)

        # ── RSI (14 ngày) ─────────────────────────────────────────────────────
        delta  = close.diff()
        gain   = delta.where(delta > 0, 0).rolling(14).mean()
        loss   = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs     = gain / loss.replace(0, float("inf"))
        rsi    = (100 - 100 / (1 + rs)).round(2)

        # ── MACD (12/26/9) ────────────────────────────────────────────────────
        ema12      = close.ewm(span=12, adjust=False).mean()
        ema26      = close.ewm(span=26, adjust=False).mean()
        macd_line  = (ema12 - ema26).round(4)
        signal     = macd_line.ewm(span=9, adjust=False).mean().round(4)
        histogram  = (macd_line - signal).round(4)

        # ── Bollinger Bands (20 ngày) ──────────────────────────────────────────
        ma20    = close.rolling(20).mean().round(2)
        std20   = close.rolling(20).std().round(2)
        bb_up   = (ma20 + 2 * std20).round(2)
        bb_down = (ma20 - 2 * std20).round(2)

        # ── MA50 ──────────────────────────────────────────────────────────────
        ma50 = close.rolling(50).mean().round(2)

        # ── Lấy giá trị mới nhất ──────────────────────────────────────────────
        latest_idx    = -1
        current_price = safe_float(close.iloc[latest_idx])
        current_rsi   = safe_float(rsi.iloc[latest_idx])
        current_macd  = safe_float(macd_line.iloc[latest_idx])
        current_sig   = safe_float(signal.iloc[latest_idx])
        current_hist  = safe_float(histogram.iloc[latest_idx])
        current_ma20  = safe_float(ma20.iloc[latest_idx])
        current_ma50  = safe_float(ma50.iloc[latest_idx])
        current_bb_up = safe_float(bb_up.iloc[latest_idx])
        current_bb_dn = safe_float(bb_down.iloc[latest_idx])

        # ── Tín hiệu tổng hợp (rule-based scoring) ────────────────────────────
        score  = 0
        reason = []

        # RSI
        if current_rsi is not None:
            if current_rsi < 30:
                score += 2
                reason.append(f"RSI={current_rsi} — vùng quá bán, khả năng phục hồi")
            elif current_rsi > 70:
                score -= 2
                reason.append(f"RSI={current_rsi} — vùng quá mua, rủi ro điều chỉnh")
            else:
                reason.append(f"RSI={current_rsi} — vùng trung tính")

        # MACD cross
        if current_hist is not None:
            prev_hist = safe_float(histogram.iloc[-2]) if len(histogram) > 1 else None
            if prev_hist is not None:
                if current_hist > 0 and prev_hist <= 0:
                    score += 2
                    reason.append("MACD cắt lên signal line — tín hiệu tăng")
                elif current_hist < 0 and prev_hist >= 0:
                    score -= 2
                    reason.append("MACD cắt xuống signal line — tín hiệu giảm")
                elif current_hist > 0:
                    score += 1
                    reason.append("MACD dương — xu hướng tăng")
                else:
                    score -= 1
                    reason.append("MACD âm — xu hướng giảm")

        # MA trend
        if current_price and current_ma20 and current_ma50:
            if current_price > current_ma20 > current_ma50:
                score += 2
                reason.append("Giá > MA20 > MA50 — uptrend rõ ràng")
            elif current_price < current_ma20 < current_ma50:
                score -= 2
                reason.append("Giá < MA20 < MA50 — downtrend rõ ràng")

        # Bollinger Band position
        if current_price and current_bb_up and current_bb_dn:
            if current_price <= current_bb_dn:
                score += 1
                reason.append("Giá chạm dải dưới Bollinger — có thể là hỗ trợ")
            elif current_price >= current_bb_up:
                score -= 1
                reason.append("Giá chạm dải trên Bollinger — có thể là kháng cự")

        # Kết luận
        if score >= 3:
            signal_label = "BUY"
        elif score <= -3:
            signal_label = "SELL"
        else:
            signal_label = "HOLD"

        return {
            "symbol":        symbol,
            "currentPrice":  current_price,
            "signal":        signal_label,
            "score":         score,
            "reasons":       reason,
            "indicators": {
                "rsi":        current_rsi,
                "macd":       current_macd,
                "macdSignal": current_sig,
                "macdHist":   current_hist,
                "ma20":       current_ma20,
                "ma50":       current_ma50,
                "bbUpper":    current_bb_up,
                "bbLower":    current_bb_dn,
            },
            "disclaimer": "Thông tin mang tính tham khảo kỹ thuật, KHÔNG phải lời khuyên đầu tư.",
            "calculatedAt": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing indicators for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/watchlist")
def get_watchlist(symbols: str = Query(default=",".join(DEFAULT_WATCHLIST))):
    """
    Lấy quote cho nhiều cổ phiếu cùng lúc.
    
    Ví dụ: GET /stocks/watchlist?symbols=VNM,VCB,FPT
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = []
    for sym in symbol_list[:15]:  # giới hạn 15 để tránh timeout
        try:
            quote = get_quote(sym)
            results.append(quote)
        except Exception as e:
            logger.warning(f"Skip {sym}: {e}")
            results.append({"symbol": sym, "error": str(e)})
    return {"watchlist": results, "count": len(results)}


@app.get("/stocks/search")
def search_stocks(q: str = Query(min_length=1, max_length=10)):
    """
    Tìm kiếm cổ phiếu theo mã.
    Trả về danh sách gợi ý.
    """
    q = q.upper().strip()
    # Danh sách cổ phiếu phổ biến HoSE/HNX (mở rộng sau)
    all_stocks = [
        {"symbol": "VNM",  "name": "Vinamilk",                   "exchange": "HoSE"},
        {"symbol": "VCB",  "name": "Vietcombank",                 "exchange": "HoSE"},
        {"symbol": "HPG",  "name": "Hòa Phát Group",              "exchange": "HoSE"},
        {"symbol": "MWG",  "name": "Mobile World Group",          "exchange": "HoSE"},
        {"symbol": "FPT",  "name": "FPT Corporation",             "exchange": "HoSE"},
        {"symbol": "VIC",  "name": "Vingroup",                    "exchange": "HoSE"},
        {"symbol": "MSN",  "name": "Masan Group",                 "exchange": "HoSE"},
        {"symbol": "TCB",  "name": "Techcombank",                 "exchange": "HoSE"},
        {"symbol": "VHM",  "name": "Vinhomes",                    "exchange": "HoSE"},
        {"symbol": "ACB",  "name": "Asia Commercial Bank",        "exchange": "HoSE"},
        {"symbol": "BID",  "name": "BIDV",                        "exchange": "HoSE"},
        {"symbol": "CTG",  "name": "VietinBank",                  "exchange": "HoSE"},
        {"symbol": "GAS",  "name": "PetroVietnam Gas",            "exchange": "HoSE"},
        {"symbol": "SAB",  "name": "Sabeco",                      "exchange": "HoSE"},
        {"symbol": "PLX",  "name": "Petrolimex",                  "exchange": "HoSE"},
        {"symbol": "PNJ",  "name": "Phú Nhuận Jewelry",           "exchange": "HoSE"},
        {"symbol": "REE",  "name": "REE Corporation",             "exchange": "HoSE"},
        {"symbol": "SSI",  "name": "SSI Securities",              "exchange": "HoSE"},
        {"symbol": "DGC",  "name": "Đức Giang Chemicals",         "exchange": "HoSE"},
        {"symbol": "KDC",  "name": "Kinh Đô Corporation",         "exchange": "HoSE"},
    ]
    matches = [s for s in all_stocks if q in s["symbol"] or q.lower() in s["name"].lower()]
    return {"query": q, "results": matches[:10]}
