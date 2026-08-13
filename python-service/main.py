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

from functools import lru_cache
import time

# ── In-memory cache với TTL ────────────────────────────────────────────────────
_history_cache: dict = {}   # symbol -> {"data": df, "ts": timestamp}
_signal_cache:  dict = {}   # symbol -> {"data": result, "ts": timestamp}
HISTORY_TTL = 3600          # 1 giờ — dữ liệu lịch sử không đổi trong ngày
SIGNAL_TTL  = 1800          # 30 phút — tín hiệu cần fresh hơn

def get_cached_history(symbol: str, days: int):
    """Lấy history từ cache nếu còn hạn."""
    key = f"{symbol}_{days}"
    now = time.time()
    if key in _history_cache:
        entry = _history_cache[key]
        if now - entry["ts"] < HISTORY_TTL:
            return entry["data"]
    return None

def set_cached_history(symbol: str, days: int, df):
    """Lưu history vào cache."""
    key = f"{symbol}_{days}"
    _history_cache[key] = {"data": df, "ts": time.time()}

def get_cached_signal(symbol: str):
    """Lấy signal từ cache nếu còn hạn."""
    now = time.time()
    if symbol in _signal_cache:
        entry = _signal_cache[symbol]
        if now - entry["ts"] < SIGNAL_TTL:
            return entry["data"]
    return None

def set_cached_signal(symbol: str, result: dict):
    """Lưu signal vào cache."""
    _signal_cache[symbol] = {"data": result, "ts": time.time()}

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
    """Helper: lấy DataFrame lịch sử giá — có cache TTL 1 giờ."""
    # Kiểm tra cache trước
    cached = get_cached_history(symbol, days)
    if cached is not None:
        logger.info(f"Cache hit: history {symbol} {days}d")
        return cached

    # Cache miss → gọi VCI API
    logger.info(f"Cache miss: fetching history {symbol} {days}d from VCI")
    stock = get_stock_client().stock(symbol=symbol, source="VCI")
    start = (datetime.now() - timedelta(days=days + 60)).strftime("%Y-%m-%d")
    end   = datetime.now().strftime("%Y-%m-%d")
    df    = stock.quote.history(start=start, end=end, interval="1D")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Không có dữ liệu cho {symbol}")

    # Lưu vào cache
    set_cached_history(symbol, days, df)
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
    """RSI, MACD, Bollinger Bands + tín hiệu BUY/HOLD/SELL — có cache 30 phút."""
    symbol = symbol.upper().strip()

    # Kiểm tra cache signal
    cached = get_cached_signal(symbol)
    if cached is not None:
        logger.info(f"Cache hit: signal {symbol}")
        return cached

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

        info   = get_stock_info(symbol)
        result = {
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

        # Lưu vào cache
        set_cached_signal(symbol, result)
        return result

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

# ══════════════════════════════════════════════════════════════════════════════
# INTRADAY — Giá realtime + Order book
# Thêm 2 endpoint này vào cuối main.py
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/stocks/intraday/{symbol}")
def get_intraday(symbol: str):
    """Giá realtime trong phiên + % thay đổi so với hôm qua."""
    symbol = symbol.upper().strip()
    try:
        from datetime import datetime as dt, timedelta, date as dt_date
        stock = get_stock_client().stock(symbol=symbol, source="VCI")

        today     = dt.now().strftime("%Y-%m-%d")
        week_ago  = (dt.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        df = stock.quote.history(start=week_ago, end=today, interval="1D")

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"Không có dữ liệu cho {symbol}")

        latest      = df.iloc[-1]
        prev        = df.iloc[-2] if len(df) > 1 else latest

        cur_price   = safe_float(latest.get("close"))
        open_price  = safe_float(latest.get("open"))
        high_price  = safe_float(latest.get("high"))
        low_price   = safe_float(latest.get("low"))
        volume      = safe_float(latest.get("volume"))
        prev_close  = safe_float(prev.get("close"))

        # Tham chiếu = giá đóng cửa hôm qua
        ref_price   = prev_close
        change      = round(cur_price - ref_price, 2)   if cur_price and ref_price else None
        change_pct  = round(change / ref_price * 100, 2) if change and ref_price   else None

        return {
            "symbol":       symbol,
            "currentPrice": cur_price,
            "openPrice":    open_price,
            "highPrice":    high_price,
            "lowPrice":     low_price,
            "refPrice":     ref_price,
            "change":       change,
            "changePct":    change_pct,
            "volume":       volume,
            "date":         str(latest.get("time", today)),
            "updatedAt":    dt.now().strftime("%H:%M:%S"),
            "isTrading":    _is_trading_hours(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intraday error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/orderbook/{symbol}")
def get_orderbook(symbol: str):
    """
    Order book: top 3 lệnh mua (bid) và bán (ask).
    Dùng price_depth nếu có, fallback về synthetic từ OHLC.
    """
    symbol = symbol.upper().strip()
    try:
        from datetime import datetime as dt, timedelta
        stock = get_stock_client().stock(symbol=symbol, source="VCI")

        # Thử lấy price_depth thực
        try:
            df_depth = stock.quote.price_depth()
            if df_depth is not None and not df_depth.empty:
                bids, asks = [], []
                for _, row in df_depth.iterrows():
                    side   = str(row.get("side", "")).upper()
                    price  = safe_float(row.get("price"))
                    volume = safe_float(row.get("volume"))
                    if price and volume:
                        item = {"price": price, "volume": volume}
                        if side in ("BID", "BUY", "MUA"):
                            bids.append(item)
                        elif side in ("ASK", "SELL", "BAN"):
                            asks.append(item)

                bids.sort(key=lambda x: x["price"], reverse=True)
                asks.sort(key=lambda x: x["price"])

                if bids or asks:
                    return {
                        "symbol":    symbol,
                        "bids":      bids[:3],
                        "asks":      asks[:3],
                        "updatedAt": dt.now().strftime("%H:%M:%S"),
                    }
        except Exception as depth_err:
            logger.warning(f"price_depth failed for {symbol}: {depth_err}")

        # Fallback: synthetic order book từ OHLC
        today    = dt.now().strftime("%Y-%m-%d")
        week_ago = (dt.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        df = stock.quote.history(start=week_ago, end=today, interval="1D")

        if df is None or df.empty:
            return {
                "symbol":    symbol,
                "bids":      [],
                "asks":      [],
                "note":      "Không có dữ liệu",
                "updatedAt": dt.now().strftime("%H:%M:%S")
            }

        latest    = df.iloc[-1]
        cur_price = safe_float(latest.get("close")) or 0
        vol       = safe_float(latest.get("volume")) or 100000
        tick      = max(round(cur_price * 0.001, 2), 0.01)

        bids = [{"price": round(cur_price - tick * i, 2), "volume": int(vol / (i + 2))}
                for i in range(1, 4)]
        asks = [{"price": round(cur_price + tick * i, 2), "volume": int(vol / (i + 2))}
                for i in range(1, 4)]

        return {
            "symbol":    symbol,
            "bids":      bids,
            "asks":      asks,
            "note":      "Dữ liệu ước tính (ngoài giờ giao dịch)",
            "updatedAt": dt.now().strftime("%H:%M:%S"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Orderbook error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _is_trading_hours() -> bool:
    """Kiểm tra giờ giao dịch HoSE: 9:00-14:45 thứ 2-6."""
    from datetime import datetime as dt
    now = dt.now()
    if now.weekday() >= 5:
        return False
    h, m = now.hour, now.minute
    return (9, 0) <= (h, m) <= (14, 45)


@app.get("/stocks/intraday-chart/{symbol}")
def get_intraday_chart(
    symbol: str,
    days:   int = Query(default=1, ge=1, le=7)
):
    symbol = symbol.upper().strip()
    try:
        from datetime import datetime as dt, timedelta

        now     = dt.now()
        weekday = now.weekday()  # 0=T2 ... 4=T6, 5=T7, 6=CN

        # ── Tìm ngày giao dịch gần nhất ───────────────────────────────────────
        if weekday == 5:      # Thứ 7
            last_trading = now - timedelta(days=1)
            is_weekend, label_day = True, "Thứ 6"
        elif weekday == 6:    # Chủ nhật
            last_trading = now - timedelta(days=2)
            is_weekend, label_day = True, "Thứ 6"
        else:
            last_trading = now
            is_weekend, label_day = False, "Hôm nay"

        # ── Tính danh sách N ngày giao dịch hợp lệ ────────────────────────────
        # Đi ngược từ last_trading, bỏ T7(5) và CN(6)
        valid_dates = []
        cursor = last_trading
        while len(valid_dates) < days:
            if cursor.weekday() < 5:  # T2–T6
                valid_dates.append(cursor.strftime("%Y-%m-%d"))
            cursor -= timedelta(days=1)

        valid_dates_set = set(valid_dates)  # để lookup O(1)

        # ── Fetch từ ngày cũ nhất trong valid_dates ────────────────────────────
        fetch_start = min(valid_dates)
        fetch_end   = max(valid_dates)
        interval    = "5m" if days == 1 else "15m"

        stock = get_stock_client().stock(symbol=symbol, source="VCI")
        df    = stock.quote.history(start=fetch_start, end=fetch_end, interval=interval)

        if df is None or df.empty:
            raise HTTPException(status_code=404,
                detail=f"Không có dữ liệu intraday cho {symbol}")

        # ── Lọc chỉ lấy đúng các ngày trong valid_dates + giờ GD ──────────────
        records = []
        for _, row in df.iterrows():
            ts = row.get("time")

            if hasattr(ts, 'to_pydatetime'):
                ts_dt = ts.to_pydatetime()
            elif isinstance(ts, str):
                try:    ts_dt = dt.fromisoformat(ts)
                except: continue
            else:
                continue

            date_str = ts_dt.strftime("%Y-%m-%d")

            # Chỉ lấy đúng các ngày trong danh sách
            if date_str not in valid_dates_set:
                continue

            # Giờ giao dịch 9:00 – 14:45
            h, m = ts_dt.hour, ts_dt.minute
            if not ((9, 0) <= (h, m) <= (14, 45)):
                continue

            close  = safe_float(row.get("close"))
            volume = safe_float(row.get("volume"))
            if close is None:
                continue

            label = ts_dt.strftime("%H:%M") if days == 1 \
                    else ts_dt.strftime("%d/%m %H:%M")

            records.append({
                "label":  label,
                "date":   date_str,
                "time":   ts_dt.strftime("%H:%M"),
                "open":   safe_float(row.get("open")),
                "high":   safe_float(row.get("high")),
                "low":    safe_float(row.get("low")),
                "close":  close,
                "volume": volume,
            })

        if not records:
            raise HTTPException(status_code=404,
                detail="Không có dữ liệu trong giờ giao dịch")

        label_day_out = label_day if days == 1 else f"{days} ngày"

        return {
            "symbol":     symbol,
            "interval":   interval,
            "days":       days,
            "labelDay":   label_day_out,
            "isWeekend":  is_weekend,
            "targetDate": fetch_end,
            "validDates": sorted(valid_dates),
            "data":       records,
            "count":      len(records),
            "updatedAt":  now.strftime("%H:%M:%S"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intraday chart error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/profile/{symbol}")
def get_company_profile(symbol: str):
    """
    Company profile đầy đủ: tên, ngành, market cap, 52W high/low,
    cổ tức, mô tả, cổ đông lớn.
    """
    symbol = symbol.upper().strip()
    try:
        from datetime import datetime as dt

        stock    = get_stock_client().stock(symbol=symbol, source="VCI")
        overview = stock.company.overview()

        if overview is None or overview.empty:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy {symbol}")

        row = overview.iloc[0]

        def sv(key, default=None):
            val = row.get(key, default)
            if val is None or (isinstance(val, float) and __import__('math').isnan(val)):
                return default
            return val

        # Market cap — VCI trả về đơn vị đồng, đổi sang tỷ đồng
        market_cap_raw = sv("market_cap")
        market_cap_billion = round(market_cap_raw / 1_000_000_000, 1) if market_cap_raw else None

        # Cổ tức VND/cổ phiếu
        dividend = sv("dividend_per_share_tsr")

        # Lấy cổ đông lớn
        shareholders = []
        try:
            df_sh = stock.company.shareholders()
            if df_sh is not None and not df_sh.empty:
                for _, sh in df_sh.head(5).iterrows():
                    name  = sh.get("share_holder", "")
                    pct   = sh.get("share_own_percent", 0)
                    if name:
                        shareholders.append({
                            "name":    str(name),
                            "percent": round(float(pct) * 100, 2) if pct else 0
                        })
        except Exception:
            pass

        # Ngày niêm yết
        listing_date = sv("listing_date", "")
        if listing_date and "T" in str(listing_date):
            listing_date = str(listing_date).split("T")[0]

        return {
            "symbol":          symbol,
            "name":            sv("organ_name", symbol),
            "shortName":       sv("organ_short_name", symbol),
            "sector":          sv("sector", ""),
            "exchange":        "HoSE",

            # Thị giá & định giá
            "currentPrice":    safe_float(sv("current_price")),
            "marketCap":       market_cap_billion,      # tỷ VND
            "issueShares":     safe_float(sv("issue_share")),
            "targetPrice":     safe_float(sv("target_price")),
            "analystRating":   sv("rating", ""),

            # 52 tuần
            "high52w":         safe_float(sv("highest_price1_year")),
            "low52w":          safe_float(sv("lowest_price1_year")),

            # Cổ tức
            "dividendPerShare": safe_float(dividend),

            # Sở hữu
            "foreignPercent":  round(float(sv("foreigner_percentage", 0)) * 100, 2),
            "statePercent":    round(float(sv("state_percentage", 0)) * 100, 2),
            "freeFloat":       round(float(sv("free_float_percentage", 0)) * 100, 2),

            # Khác
            "listingDate":     listing_date,
            "companyProfile":  sv("company_profile", ""),
            "shareholders":    shareholders,

            "updatedAt":       dt.now().strftime("%H:%M:%S"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Company profile error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))