"""
VNStock Data Service v2
-----------------------
FastAPI microservice cung cấp dữ liệu chứng khoán Việt Nam cho Spring Boot.

Chạy: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import time
from stocks_list import STOCKS, SECTORS, get_stock_info

# ── In-memory cache ────────────────────────────────────────────────────────────
_market_cache: dict = {}          # symbol -> row data
_cache_time:   dict = {}          # symbol -> timestamp
CACHE_TTL = 3600                  # 1 giờ — dữ liệu cuối ngày không cần refresh liên tục

app = FastAPI(
    title="VNStock Data Service",
    description="Dữ liệu chứng khoán Việt Nam từ VCI",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_WATCHLIST = ["VNM", "VCB", "HPG", "FPT", "MWG", "TCB", "VIC", "ACB"]

# Khởi tạo client một lần duy nhất — tránh tốn quota mỗi lần gọi
_vnstock_client = None

def get_stock_client():
    global _vnstock_client
    if _vnstock_client is None:
        try:
            from vnstock import Vnstock
            _vnstock_client = Vnstock()
            logger.info("VNStock client initialized")
        except ImportError:
            raise HTTPException(status_code=503, detail="vnstock chưa được cài.")
    return _vnstock_client


def safe_float(val) -> Optional[float]:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return float(val)
    except:
        return None


def fetch_history_df(symbol: str, days: int):
    """Helper: lấy DataFrame lịch sử giá."""
    stock = get_stock_client().stock(symbol=symbol, source="VCI")
    start = (datetime.now() - timedelta(days=days + 60)).strftime("%Y-%m-%d")
    end   = datetime.now().strftime("%Y-%m-%d")
    df    = stock.quote.history(start=start, end=end, interval="1D")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Không có dữ liệu cho {symbol}")
    return df


def compute_indicators(df) -> dict:
    """Tính RSI, MACD, BB, MA từ DataFrame."""
    close = df["close"].astype(float)

    # RSI
    delta = close.diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs    = gain / loss.replace(0, float("inf"))
    rsi   = (100 - 100 / (1 + rs)).round(2)

    # MACD
    ema12     = close.ewm(span=12, adjust=False).mean()
    ema26     = close.ewm(span=26, adjust=False).mean()
    macd_line = (ema12 - ema26).round(4)
    signal    = macd_line.ewm(span=9, adjust=False).mean().round(4)
    histogram = (macd_line - signal).round(4)

    # Bollinger Bands
    ma20   = close.rolling(20).mean().round(2)
    std20  = close.rolling(20).std().round(2)
    bb_up  = (ma20 + 2 * std20).round(2)
    bb_dn  = (ma20 - 2 * std20).round(2)

    # MA50
    ma50 = close.rolling(50).mean().round(2)

    return {
        "close":    close,
        "rsi":      rsi,
        "macd":     macd_line,
        "signal":   signal,
        "hist":     histogram,
        "ma20":     ma20,
        "ma50":     ma50,
        "bb_up":    bb_up,
        "bb_dn":    bb_dn,
    }


def compute_signal(price, rsi_val, macd_val, prev_hist, curr_hist, ma20_val, ma50_val, bb_up_val, bb_dn_val):
    """Tính điểm tín hiệu BUY/HOLD/SELL."""
    score  = 0
    reason = []

    if rsi_val is not None:
        if rsi_val < 30:
            score += 2; reason.append(f"RSI={rsi_val:.1f} — vùng quá bán, khả năng phục hồi")
        elif rsi_val > 70:
            score -= 2; reason.append(f"RSI={rsi_val:.1f} — vùng quá mua, rủi ro điều chỉnh")
        else:
            reason.append(f"RSI={rsi_val:.1f} — vùng trung tính")

    if curr_hist is not None and prev_hist is not None:
        if curr_hist > 0 and prev_hist <= 0:
            score += 2; reason.append("MACD cắt lên signal line — tín hiệu tăng")
        elif curr_hist < 0 and prev_hist >= 0:
            score -= 2; reason.append("MACD cắt xuống signal line — tín hiệu giảm")
        elif curr_hist > 0:
            score += 1; reason.append("MACD dương — xu hướng tăng")
        else:
            score -= 1; reason.append("MACD âm — xu hướng giảm")

    if price and ma20_val and ma50_val:
        if price > ma20_val > ma50_val:
            score += 2; reason.append("Giá > MA20 > MA50 — uptrend rõ ràng")
        elif price < ma20_val < ma50_val:
            score -= 2; reason.append("Giá < MA20 < MA50 — downtrend rõ ràng")

    if price and bb_up_val and bb_dn_val:
        if price <= bb_dn_val:
            score += 1; reason.append("Giá chạm dải dưới Bollinger — vùng hỗ trợ")
        elif price >= bb_up_val:
            score -= 1; reason.append("Giá chạm dải trên Bollinger — vùng kháng cự")

    label = "BUY" if score >= 3 else ("SELL" if score <= -3 else "HOLD")
    return label, score, reason


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "cached_symbols": len(_market_cache)
    }

@app.post("/cache/clear")
def clear_cache():
    """Xóa cache để force fetch dữ liệu mới."""
    _market_cache.clear()
    _cache_time.clear()
    return {"message": "Cache cleared", "timestamp": datetime.now().isoformat()}


@app.get("/stocks/list")
def list_stocks(sector: Optional[str] = None):
    """Danh sách tất cả cổ phiếu, filter theo ngành."""
    result = STOCKS if not sector else [s for s in STOCKS if s["sector"] == sector]
    return {"stocks": result, "sectors": SECTORS, "total": len(result)}


@app.get("/stocks/quote/{symbol}")
def get_quote(symbol: str):
    """Giá hiện tại + thay đổi so với hôm qua."""
    symbol = symbol.upper().strip()
    try:
        stock = get_stock_client().stock(symbol=symbol, source="VCI")
        df = stock.quote.history(
            start=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            end=datetime.now().strftime("%Y-%m-%d"),
            interval="1D"
        )
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy {symbol}")

        latest = df.iloc[-1]
        prev   = df.iloc[-2] if len(df) > 1 else latest
        current_price = safe_float(latest.get("close"))
        prev_price    = safe_float(prev.get("close"))
        change        = round(current_price - prev_price, 2) if current_price and prev_price else None
        change_pct    = round((change / prev_price) * 100, 2) if change and prev_price else None

        info = get_stock_info(symbol)
        return {
            "symbol":       symbol,
            "name":         info.get("name", symbol),
            "sector":       info.get("sector", ""),
            "exchange":     info.get("exchange", "HoSE"),
            "currentPrice": current_price,
            "open":         safe_float(latest.get("open")),
            "high":         safe_float(latest.get("high")),
            "low":          safe_float(latest.get("low")),
            "volume":       safe_float(latest.get("volume")),
            "change":       change,
            "changePct":    change_pct,
            "date":         str(latest.get("time", datetime.now().date())),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error quote {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/history/{symbol}")
def get_history(symbol: str, days: int = Query(default=90, ge=7, le=365)):
    """Lịch sử giá OHLCV."""
    symbol = symbol.upper().strip()
    try:
        stock = get_stock_client().stock(symbol=symbol, source="VCI")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end   = datetime.now().strftime("%Y-%m-%d")
        df    = stock.quote.history(start=start, end=end, interval="1D")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"Không có dữ liệu cho {symbol}")

        records = []
        for _, row in df.iterrows():
            records.append({
                "date":   str(row.get("time", ""))[:10],
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
        logger.error(f"Error history {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/indicators/{symbol}")
def get_indicators(symbol: str, days: int = Query(default=90, ge=30, le=365)):
    """RSI, MACD, Bollinger Bands + tín hiệu BUY/HOLD/SELL."""
    symbol = symbol.upper().strip()
    try:
        df   = fetch_history_df(symbol, days)
        ind  = compute_indicators(df)

        price     = safe_float(ind["close"].iloc[-1])
        rsi_val   = safe_float(ind["rsi"].iloc[-1])
        macd_val  = safe_float(ind["macd"].iloc[-1])
        sig_val   = safe_float(ind["signal"].iloc[-1])
        curr_hist = safe_float(ind["hist"].iloc[-1])
        prev_hist = safe_float(ind["hist"].iloc[-2]) if len(ind["hist"]) > 1 else None
        ma20_val  = safe_float(ind["ma20"].iloc[-1])
        ma50_val  = safe_float(ind["ma50"].iloc[-1])
        bb_up_val = safe_float(ind["bb_up"].iloc[-1])
        bb_dn_val = safe_float(ind["bb_dn"].iloc[-1])

        label, score, reason = compute_signal(
            price, rsi_val, macd_val, prev_hist, curr_hist,
            ma20_val, ma50_val, bb_up_val, bb_dn_val
        )

        info = get_stock_info(symbol)
        return {
            "symbol":       symbol,
            "name":         info.get("name", symbol),
            "sector":       info.get("sector", ""),
            "currentPrice": price,
            "signal":       label,
            "score":        score,
            "reasons":      reason,
            "indicators": {
                "rsi":        rsi_val,
                "macd":       macd_val,
                "macdSignal": sig_val,
                "macdHist":   curr_hist,
                "ma20":       ma20_val,
                "ma50":       ma50_val,
                "bbUpper":    bb_up_val,
                "bbLower":    bb_dn_val,
            },
            "disclaimer":   "Thông tin tham khảo kỹ thuật, KHÔNG phải lời khuyên đầu tư.",
            "calculatedAt": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indicators {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/market")
def get_market(
    sector:   Optional[str] = None,
    signal:   Optional[str] = None,
    sort_by:  str = Query(default="symbol", pattern="^(symbol|price|changePct|rsi|score)$"),
    sort_dir: str = Query(default="asc",    pattern="^(asc|desc)$"),
    limit:    int = Query(default=10, ge=1, le=50)
):
    from urllib.parse import unquote
    sector_decoded = unquote(sector) if sector else None

    stocks_to_fetch = STOCKS
    if sector_decoded:
        stocks_to_fetch = [s for s in STOCKS if s["sector"] == sector_decoded]

    results    = []
    need_fetch = []
    now        = time.time()

    # Pass 1: lấy từ cache trước
    for stock_info in stocks_to_fetch:
        sym = stock_info["symbol"]
        if sym in _market_cache and (now - _cache_time.get(sym, 0)) < CACHE_TTL:
            row = _market_cache[sym]
            if not signal or row["signal"] == signal.upper():
                results.append(row)
        else:
            need_fetch.append(stock_info)

    # Pass 2: chỉ fetch những symbol chưa có cache
    remaining = limit - len(results)
    for stock_info in need_fetch[:max(remaining, 0)]:
        sym = stock_info["symbol"]
        try:
            time.sleep(3.0)
            df_ind = fetch_history_df(sym, 90)
            if df_ind is None or df_ind.empty or len(df_ind) < 5:
                continue

            ind           = compute_indicators(df_ind)
            current_price = safe_float(df_ind["close"].iloc[-1])
            prev_price    = safe_float(df_ind["close"].iloc[-2]) if len(df_ind) > 1 else None
            change_pct    = round((current_price - prev_price) / prev_price * 100, 2) \
                            if current_price and prev_price and prev_price != 0 else None

            rsi_val   = safe_float(ind["rsi"].iloc[-1])
            macd_val  = safe_float(ind["macd"].iloc[-1])
            curr_hist = safe_float(ind["hist"].iloc[-1])
            prev_hist = safe_float(ind["hist"].iloc[-2]) if len(ind["hist"]) > 1 else None
            ma20_val  = safe_float(ind["ma20"].iloc[-1])
            ma50_val  = safe_float(ind["ma50"].iloc[-1])
            bb_up_val = safe_float(ind["bb_up"].iloc[-1])
            bb_dn_val = safe_float(ind["bb_dn"].iloc[-1])

            sig_label, score, _ = compute_signal(
                current_price, rsi_val, macd_val, prev_hist, curr_hist,
                ma20_val, ma50_val, bb_up_val, bb_dn_val
            )

            row = {
                "symbol":    sym,
                "name":      stock_info["name"],
                "sector":    stock_info["sector"],
                "exchange":  stock_info["exchange"],
                "price":     current_price,
                "changePct": change_pct,
                "volume":    safe_float(df_ind["volume"].iloc[-1]) if "volume" in df_ind.columns else None,
                "rsi":       rsi_val,
                "ma20":      ma20_val,
                "ma50":      ma50_val,
                "signal":    sig_label,
                "score":     score,
            }

            _market_cache[sym] = row
            _cache_time[sym]   = time.time()

            if not signal or row["signal"] == signal.upper():
                results.append(row)

        except Exception as e:
            logger.warning(f"Skip {sym}: {type(e).__name__}: {e}")
            continue

    # Sort rồi giới hạn
    reverse = (sort_dir == "desc")
    results.sort(
        key=lambda x: (x.get(sort_by) is None, x.get(sort_by) or 0),
        reverse=reverse
    )
    results = results[:limit]

    return {
        "data":    results,
        "total":   len(results),
        "sectors": SECTORS,
        "cached":  len(_market_cache),
        "filters": {"sector": sector_decoded, "signal": signal,
                    "sort_by": sort_by, "sort_dir": sort_dir}
    }


@app.get("/stocks/watchlist")
def get_watchlist(symbols: str = Query(default=",".join(DEFAULT_WATCHLIST))):
    """Quote cho nhiều cổ phiếu."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = []
    for sym in symbol_list[:15]:
        try:
            results.append(get_quote(sym))
        except Exception as e:
            results.append({"symbol": sym, "error": str(e)})
    return {"watchlist": results, "count": len(results)}


@app.get("/stocks/search")
def search_stocks(q: str = Query(min_length=1, max_length=20)):
    """Tìm kiếm cổ phiếu theo mã hoặc tên."""
    q = q.strip()
    q_upper = q.upper()
    q_lower = q.lower()
    matches = [
        s for s in STOCKS
        if q_upper in s["symbol"] or q_lower in s["name"].lower()
    ]
    return {"query": q, "results": matches[:10]}