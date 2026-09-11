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
import os
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import time
from functools import lru_cache
from stocks_list import STOCKS, SECTORS, get_stock_info

# ── Logger ─────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── In-memory cache ────────────────────────────────────────────────────────────
_market_cache: dict = {}
_cache_time:   dict = {}
CACHE_TTL = 3600

_history_cache: dict = {}
_signal_cache:  dict = {}
HISTORY_TTL = 3600
SIGNAL_TTL  = 1800

_intraday_cache = {}

_orderbook_cache = {}

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

HNX_STOCKS = {
    "SHB", "NVB", "BVS", "VCG", "PVI", "CEO", "HUT", "PVS",
    "DGW", "VCS", "MBS", "SHS", "HLC", "NET", "TNG", "VGC",
    "PLC", "HCD", "BCC", "VNR", "HBS", "PIV", "DTD", "SGT",
    "CTX", "KLF", "BXH", "VNF", "IDJ", "VNT", "TH1", "HHG",
}
 
UPCOM_STOCKS = {
    "OIL", "MVN", "LDG", "ASM", "HAH", "BSR", "PLX",
    "MCH", "VEA", "ACV", "SBV", "VGI", "PTB", "FOX",
}
 
def detect_exchange(symbol: str) -> str:
    """Detect sàn từ mã CK mà không cần gọi API."""
    sym = symbol.upper().strip()
    if sym in HNX_STOCKS:
        return "HNX"
    if sym in UPCOM_STOCKS:
        return "UPCOM"
    return "HoSE"  # mặc định
 
def get_price_limits(symbol: str, ref_price: float) -> dict:
    """Tính giá trần/sàn dựa trên sàn giao dịch."""
    exchange = detect_exchange(symbol)
 
    if exchange == "HNX":
        pct = 0.10
    elif exchange == "UPCOM":
        pct = 0.15
    else:
        pct = 0.07
 
    def round_price(p):
        if p is None: return None
        if p >= 50000: return round(p / 100) * 100
        if p >= 10000: return round(p / 50)  * 50
        return round(p / 10) * 10
 
    ceiling = round_price(ref_price * (1 + pct)) if ref_price else None
    floor   = round_price(ref_price * (1 - pct)) if ref_price else None
 
    return {
        "exchange": exchange,
        "pctLimit": pct * 100,
        "ceiling":  ceiling,
        "floor":    floor,
    }

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

DEFAULT_WATCHLIST = ["VNM", "VCB", "HPG", "FPT", "MWG"]

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


def compute_signal(price, rsi, macd, prev_hist, curr_hist,
                   ma20, ma50, bb_upper, bb_lower):
    """
    Tính tín hiệu dự đoán phiên hôm sau: TĂNG / GIẢM / GIỮ NGUYÊN.
    Trả về (label, score, reason_string).
    """
    score   = 0
    reasons = []
 
    # RSI
    if rsi is not None:
        if rsi < 30:
            score += 2; reasons.append(f"RSI={rsi:.1f} — vùng quá bán, dễ phục hồi")
        elif rsi > 70:
            score -= 2; reasons.append(f"RSI={rsi:.1f} — vùng quá mua, dễ điều chỉnh")
        elif rsi > 55:
            score += 1; reasons.append(f"RSI={rsi:.1f} — momentum tích cực")
        elif rsi < 45:
            score -= 1; reasons.append(f"RSI={rsi:.1f} — momentum yếu")
 
    # MACD histogram crossover
    if curr_hist is not None and prev_hist is not None:
        if curr_hist > 0 and prev_hist <= 0:
            score += 3; reasons.append("MACD cắt lên — tín hiệu tăng mạnh")
        elif curr_hist < 0 and prev_hist >= 0:
            score -= 3; reasons.append("MACD cắt xuống — tín hiệu giảm mạnh")
        elif curr_hist > prev_hist:
            score += 1; reasons.append("MACD histogram tăng dần")
        else:
            score -= 1; reasons.append("MACD histogram giảm dần")
 
    # MA trend
    if price and ma20 and ma50:
        if price > ma20 > ma50:
            score += 2; reasons.append("Giá > MA20 > MA50 — uptrend rõ ràng")
        elif price < ma20 < ma50:
            score -= 2; reasons.append("Giá < MA20 < MA50 — downtrend rõ ràng")
        elif ma20 > ma50:
            score += 1; reasons.append("MA20 > MA50 — xu hướng tăng trung hạn")
 
    # Bollinger Bands
    if price and bb_upper and bb_lower:
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_pct = (price - bb_lower) / bb_range
            if bb_pct <= 0.1:
                score += 2; reasons.append("Giá chạm dải dưới BB — vùng hỗ trợ")
            elif bb_pct >= 0.9:
                score -= 2; reasons.append("Giá chạm dải trên BB — vùng kháng cự")
 
    # Xác định nhãn
    if score >= 3:
        label = "TĂNG"
    elif score <= -3:
        label = "GIẢM"
    else:
        label = "GIỮ NGUYÊN"
 
    return label, score, "|".join(reasons)


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
    """
    Giá realtime trong phiên + giá trần/sàn.

    - Ưu tiên lấy dữ liệu mới từ VNStock/VCI.
    - Nếu VCI timeout/lỗi -> dùng cache gần nhất nếu có.
    - Nếu chưa có cache -> trả 503 thay vì 500.
    """

    symbol = symbol.upper().strip()

    try:
        from datetime import datetime as dt, timedelta

        stock = get_stock_client().stock(
            symbol=symbol,
            source="VCI"
        )

        today = dt.now().strftime("%Y-%m-%d")
        week_ago = (
            dt.now() - timedelta(days=7)
        ).strftime("%Y-%m-%d")

        df = stock.quote.history(
            start=week_ago,
            end=today,
            interval="1D"
        )

        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Không có dữ liệu cho {symbol}"
            )

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        cur_price = safe_float(latest.get("close"))
        open_price = safe_float(latest.get("open"))
        high_price = safe_float(latest.get("high"))
        low_price = safe_float(latest.get("low"))
        volume = safe_float(latest.get("volume"))
        ref_price = safe_float(prev.get("close"))

        change = (
            round(cur_price - ref_price, 2)
            if cur_price is not None and ref_price is not None
            else None
        )

        change_pct = (
            round(change / ref_price * 100, 2)
            if change is not None and ref_price
            else None
        )

        # Giá trần / sàn
        limits = get_price_limits(symbol, ref_price)

        result = {
            "symbol": symbol,
            "currentPrice": cur_price,
            "openPrice": open_price,
            "highPrice": high_price,
            "lowPrice": low_price,
            "refPrice": ref_price,
            "ceiling": limits["ceiling"],
            "floor": limits["floor"],
            "exchange": limits["exchange"],
            "pctLimit": limits["pctLimit"],
            "change": change,
            "changePct": change_pct,
            "volume": volume,
            "date": str(latest.get("time", today)),
            "updatedAt": dt.now().strftime("%H:%M:%S"),
            "isTrading": _is_trading_hours(),
            "fromCache": False,
        }

        # ==========================================================
        # LƯU CACHE
        # ==========================================================
        _intraday_cache[symbol] = result

        return result

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Intraday error {symbol}: {e}"
        )

        # ==========================================================
        # FALLBACK CACHE
        # ==========================================================
        cached = _intraday_cache.get(symbol)

        if cached is not None:
            logger.warning(
                f"Using cached intraday data for {symbol}"
            )

            cached_result = dict(cached)
            cached_result["fromCache"] = True
            cached_result["updatedAt"] = dt.now().strftime("%H:%M:%S")

            return cached_result

        # ==========================================================
        # KHÔNG CÓ CACHE
        # ==========================================================
        raise HTTPException(
            status_code=503,
            detail=(
                f"Dữ liệu intraday của {symbol} "
                f"tạm thời không khả dụng. "
                f"VNStock/VCI có thể đang timeout."
            )
        )


@app.get("/stocks/orderbook/{symbol}")
def get_orderbook(symbol: str):
    """
    Order book: top 3 lệnh mua (bid) và bán (ask).
    - Ưu tiên lấy order book thật bằng price_depth().
    - Nếu price_depth() lỗi -> fallback sang synthetic order book từ OHLC.
    - Nếu VCI timeout nhưng đã có cache -> trả cache.
    - Nếu chưa có cache -> trả 503 thay vì 500.
    """
    symbol = symbol.upper().strip()
    try:
        stock = get_stock_client().stock(
            symbol=symbol,
            source="VCI"
        )

        # ============================================================
        # 1. THỬ LẤY ORDER BOOK THẬT
        # ============================================================
        try:
            df_depth = stock.quote.price_depth()
            if df_depth is not None and not df_depth.empty:
                bids = []
                asks = []
                for _, row in df_depth.iterrows():
                    side = str(
                        row.get("side", "")
                    ).upper()
                    price = safe_float(
                        row.get("price")
                    )
                    volume = safe_float(
                        row.get("volume")
                    )
                    if price is not None and volume is not None:

                        item = {
                            "price": price,
                            "volume": volume
                        }
                        if side in ("BID", "BUY", "MUA"):
                            bids.append(item)
                        elif side in ("ASK", "SELL", "BAN"):
                            asks.append(item)
                # Bid: giá cao nhất trước
                bids.sort(
                    key=lambda x: x["price"],
                    reverse=True
                )
                # Ask: giá thấp nhất trước
                asks.sort(
                    key=lambda x: x["price"]
                )

                if bids or asks:
                    result = {
                        "symbol": symbol,
                        "bids": bids[:3],
                        "asks": asks[:3],
                        "updatedAt": datetime.now().strftime("%H:%M:%S"),
                        "fromCache": False,
                        "isRealOrderbook": True,
                    }

                    # Lưu cache
                    _orderbook_cache[symbol] = result
                    return result

        except Exception as depth_err:
            logger.warning(
                f"price_depth failed for {symbol}: "
                f"{depth_err}"
            )

        # ============================================================
        # 2. FALLBACK: SYNTHETIC ORDER BOOK TỪ OHLC
        # ============================================================

        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (
            datetime.now() - timedelta(days=7)
        ).strftime("%Y-%m-%d")
        df = stock.quote.history(
            start=week_ago,
            end=today,
            interval="1D"
        )
        if df is None or df.empty:
            raise ValueError(
                f"Không có dữ liệu OHLC cho {symbol}"
            )
        latest = df.iloc[-1]
        cur_price = (safe_float(latest.get("close"))or 0)
        vol = (safe_float(latest.get("volume"))or 100000)
        if cur_price <= 0:
            raise ValueError(
                f"Giá hiện tại không hợp lệ cho {symbol}"
            )

        # Khoảng giá giả lập
        tick = max(round(cur_price * 0.001, 2),0.01)

        bids = [
            {
                "price": round(cur_price - tick * i, 2),
                "volume": int(vol / (i + 2))
            }
            for i in range(1, 4)
        ]

        asks = [
            {
                "price": round(
                    cur_price + tick * i,
                    2
                ),
                "volume": int(
                    vol / (i + 2)
                )
            }
            for i in range(1, 4)
        ]
        result = {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "note": "Dữ liệu ước tính từ OHLC",
            "updatedAt": datetime.now().strftime("%H:%M:%S"),
            "fromCache": False,
            "isRealOrderbook": False,
        }
        # Lưu cache
        _orderbook_cache[symbol] = result
        return result

    # ================================================================
    # 3. HTTPException
    # ================================================================
    except HTTPException:
        raise

    # ================================================================
    # 4. VCI / VNStock LỖI
    # ================================================================
    except Exception as e:
        logger.error(
            f"Orderbook error {symbol}: {e}"
        )

        # Có cache -> dùng dữ liệu cũ
        cached = _orderbook_cache.get(symbol)
        if cached is not None:
            logger.warning(
                f"Using cached orderbook for {symbol}"
            )
            cached_result = dict(cached)
            cached_result["fromCache"] = True
            cached_result["note"] = (
                "Dữ liệu cache - "
                "VNStock/VCI hiện không phản hồi"
            )
            return cached_result

        # Không có cache
        raise HTTPException(
            status_code=503,
            detail=(
                f"Order book của {symbol} "
                f"tạm thời không khả dụng. "
                f"VNStock/VCI có thể đang timeout."
            )
        )


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


# ══════════════════════════════════════════════════════════════════════════════
# PREDICTION ENDPOINT
# Dự đoán Tăng/Giảm/Giữ phiên hôm sau dựa trên 3 thuật toán
# ══════════════════════════════════════════════════════════════════════════════

def _predict_technical(df) -> tuple[str, float, list]:
    """
    Thuật toán 1: RSI + MACD + MA (đang có sẵn).
    Trả về (label, confidence, reasons).
    """
    ind   = compute_indicators(df)
    close = ind["close"]

    rsi       = safe_float(ind["rsi"].iloc[-1])
    macd      = safe_float(ind["macd"].iloc[-1])
    macd_prev = safe_float(ind["macd"].iloc[-2]) if len(ind["macd"]) > 1 else None
    hist      = safe_float(ind["hist"].iloc[-1])
    hist_prev = safe_float(ind["hist"].iloc[-2]) if len(ind["hist"]) > 1 else None
    ma20      = safe_float(ind["ma20"].iloc[-1])
    ma50      = safe_float(ind["ma50"].iloc[-1])
    price     = safe_float(close.iloc[-1])

    score   = 0
    reasons = []

    # RSI signals
    if rsi is not None:
        if rsi < 30:
            score += 2; reasons.append(f"RSI={rsi:.1f} vùng quá bán → phục hồi")
        elif rsi > 70:
            score -= 2; reasons.append(f"RSI={rsi:.1f} vùng quá mua → điều chỉnh")
        elif rsi > 55:
            score += 1; reasons.append(f"RSI={rsi:.1f} momentum tích cực")
        elif rsi < 45:
            score -= 1; reasons.append(f"RSI={rsi:.1f} momentum yếu")

    # MACD crossover
    if hist is not None and hist_prev is not None:
        if hist > 0 and hist_prev <= 0:
            score += 3; reasons.append("MACD cắt lên → tín hiệu tăng mạnh")
        elif hist < 0 and hist_prev >= 0:
            score -= 3; reasons.append("MACD cắt xuống → tín hiệu giảm mạnh")
        elif hist > 0 and hist > hist_prev:
            score += 1; reasons.append("MACD histogram đang tăng")
        elif hist < 0 and hist < hist_prev:
            score -= 1; reasons.append("MACD histogram đang giảm")

    # MA trend
    if price and ma20 and ma50:
        if price > ma20 > ma50:
            score += 2; reasons.append("Giá > MA20 > MA50 → uptrend")
        elif price < ma20 < ma50:
            score -= 2; reasons.append("Giá < MA20 < MA50 → downtrend")

    if score >= 3:   return "TĂNG",   min(0.5 + score*0.05, 0.85), reasons
    if score <= -3:  return "GIẢM",   min(0.5 + abs(score)*0.05, 0.85), reasons
    return "GIỮ NGUYÊN", 0.5 + abs(score)*0.02, reasons


def _predict_extended(df) -> tuple[str, float, list]:
    """
    Thuật toán 2: Bollinger Bands + Volume + momentum ngắn hạn.
    """
    ind     = compute_indicators(df)
    close   = ind["close"]
    price   = safe_float(close.iloc[-1])
    bb_up   = safe_float(ind["bb_up"].iloc[-1])
    bb_dn   = safe_float(ind["bb_dn"].iloc[-1])
    bb_mid  = safe_float(ind["ma20"].iloc[-1])

    # Volume trend (3 ngày gần nhất)
    vol_col = "volume" if "volume" in df.columns else None
    vol_trend = 0
    if vol_col and len(df) >= 3:
        vols = df[vol_col].astype(float).tail(3).values
        vol_avg = df[vol_col].astype(float).tail(10).mean()
        if vols[-1] > vol_avg * 1.5:
            vol_trend = 1 if close.pct_change().iloc[-1] > 0 else -1

    # Momentum 5 ngày
    mom5 = None
    if len(close) >= 5:
        mom5 = (price - safe_float(close.iloc[-5])) / safe_float(close.iloc[-5]) * 100

    score   = 0
    reasons = []

    # Bollinger Bands
    if price and bb_up and bb_dn and bb_mid:
        bb_pct = (price - bb_dn) / (bb_up - bb_dn) if bb_up != bb_dn else 0.5
        if bb_pct <= 0.1:
            score += 2; reasons.append("Giá chạm dải dưới BB → hỗ trợ mạnh")
        elif bb_pct >= 0.9:
            score -= 2; reasons.append("Giá chạm dải trên BB → kháng cự mạnh")
        elif bb_pct > 0.6:
            score += 1; reasons.append("Giá trong vùng trên BB → tích cực")
        elif bb_pct < 0.4:
            score -= 1; reasons.append("Giá trong vùng dưới BB → tiêu cực")

    # Volume
    if vol_trend == 1:
        score += 1; reasons.append("Volume tăng kèm giá tăng → xác nhận")
    elif vol_trend == -1:
        score -= 1; reasons.append("Volume tăng kèm giá giảm → bán tháo")

    # Momentum
    if mom5 is not None:
        if mom5 > 3:
            score += 1; reasons.append(f"Momentum 5 ngày +{mom5:.1f}% tích cực")
        elif mom5 < -3:
            score -= 1; reasons.append(f"Momentum 5 ngày {mom5:.1f}% tiêu cực")

    if score >= 2:   return "TĂNG",      min(0.5 + score*0.06, 0.82), reasons
    if score <= -2:  return "GIẢM",      min(0.5 + abs(score)*0.06, 0.82), reasons
    return "GIỮ NGUYÊN", 0.5 + abs(score)*0.02, reasons


def _predict_ml(df) -> tuple[str, float, list]:
    """
    Thuật toán 3: Linear Regression trên các features kỹ thuật.
    Predict % change ngày mai dựa trên pattern 30 ngày qua.
    """
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        if len(df) < 30:
            return "GIỮ NGUYÊN", 0.5, ["Không đủ dữ liệu cho ML"]

        close = df["close"].astype(float).values

        # Features: returns 1,2,3,5 ngày + RSI-like + momentum
        def make_features(closes):
            features = []
            for i in range(5, len(closes)):
                r1 = (closes[i] - closes[i-1]) / closes[i-1]
                r2 = (closes[i] - closes[i-2]) / closes[i-2]
                r3 = (closes[i] - closes[i-3]) / closes[i-3]
                r5 = (closes[i] - closes[i-5]) / closes[i-5]
                # Volatility 5 ngày
                vol5 = float(np.std(closes[i-5:i]) / closes[i])
                # MA ratio
                ma5  = float(np.mean(closes[i-5:i]) / closes[i])
                ma10 = float(np.mean(closes[i-10:i]) / closes[i]) if i >= 10 else ma5
                features.append([r1, r2, r3, r5, vol5, ma5, ma10])
            return np.array(features)

        X = make_features(close)
        # Label: ngày mai tăng (1) / giảm (-1) / giữ (0)
        labels = []
        for i in range(5, len(close) - 1):
            ret = (close[i+1] - close[i]) / close[i] * 100
            if ret > 0.5:   labels.append(1)
            elif ret < -0.5: labels.append(-1)
            else:            labels.append(0)

        if len(labels) < 20 or len(X) < len(labels):
            return "GIỮ NGUYÊN", 0.5, ["Không đủ dữ liệu ML"]

        X_train = X[:len(labels)]
        y_train = labels

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_train)

        model = LogisticRegression(max_iter=200, C=0.5)
        model.fit(X_scaled, y_train)

        # Predict cho ngày mai (dùng feature của ngày hôm nay)
        X_pred   = scaler.transform(X[-1:])
        pred     = model.predict(X_pred)[0]
        proba    = model.predict_proba(X_pred)[0]
        confidence = float(max(proba))

        label_map = {1: "TĂNG", -1: "GIẢM", 0: "GIỮ NGUYÊN"}
        label     = label_map.get(pred, "GIỮ NGUYÊN")
        reasons   = [f"ML dự đoán: {label} (confidence: {confidence:.0%})"]

        return label, confidence, reasons

    except ImportError:
        return "GIỮ NGUYÊN", 0.5, ["scikit-learn chưa cài (pip install scikit-learn)"]
    except Exception as e:
        return "GIỮ NGUYÊN", 0.5, [f"ML error: {str(e)[:50]}"]


@app.get("/stocks/predict/{symbol}")
def predict_next_session(symbol: str, days: int = Query(default=90, ge=30, le=365)):
    """
    Dự đoán Tăng/Giảm/Giữ nguyên phiên giao dịch hôm sau.
    Kết hợp 3 thuật toán: Technical + Extended + ML.
    """
    symbol = symbol.upper().strip()
    try:
        from datetime import datetime as dt

        df = fetch_history_df(symbol, days)
        if df is None or df.empty or len(df) < 15:
            raise HTTPException(status_code=404, detail="Không đủ dữ liệu để dự đoán")

        # Chạy 3 thuật toán
        label1, conf1, reasons1 = _predict_technical(df)
        label2, conf2, reasons2 = _predict_extended(df)
        label3, conf3, reasons3 = _predict_ml(df)

        # Ensemble: vote có trọng số (technical:3, extended:2, ml:4)
        weights = {"technical": 3, "extended": 2, "ml": 4}
        votes   = {"TĂNG": 0.0, "GIẢM": 0.0, "GIỮ NGUYÊN": 0.0}

        votes[label1] += weights["technical"] * conf1
        votes[label2] += weights["extended"]  * conf2
        votes[label3] += weights["ml"]        * conf3

        total          = sum(votes.values())
        final_label    = max(votes, key=votes.get)
        final_conf     = votes[final_label] / total if total > 0 else 0.5

        # Tất cả reasons
        all_reasons = (
            ["Technical Analysis:"] + reasons1 +
            ["Extended Indicators:"] + reasons2 +
            ["Machine Learning:"]    + reasons3
        )

        return {
            "symbol":      symbol,
            "prediction":  final_label,         # "TĂNG" / "GIẢM" / "GIỮ NGUYÊN"
            "confidence":  round(final_conf, 3),
            "confidencePct": round(final_conf * 100, 1),
            "models": {
                "technical": {"label": label1, "confidence": round(conf1, 3)},
                "extended":  {"label": label2, "confidence": round(conf2, 3)},
                "ml":        {"label": label3, "confidence": round(conf3, 3)},
            },
            "reasons":     all_reasons,
            "predictedAt": dt.now().isoformat(),
            "forDate":     (dt.now()).strftime("%Y-%m-%d"),  # ngày dự đoán cho
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Predict error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import os, pickle
import numpy as np
 
MODEL_PATH = "ml_model.pkl"
_online_model = None
_online_scaler = None
_training_buffer = []   # buffer lưu (features, label) chờ retrain
RETRAIN_THRESHOLD = 10  # retrain mỗi khi có thêm 10 mẫu mới
 
 
def _load_or_init_model():
    """Load model từ file hoặc khởi tạo mới."""
    global _online_model, _online_scaler
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                data = pickle.load(f)
                _online_model  = data["model"]
                _online_scaler = data["scaler"]
                logger.info(f"Loaded ML model from {MODEL_PATH}")
                return
        except Exception as e:
            logger.warning(f"Cannot load model: {e}")
 
    # Khởi tạo mới
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    _online_model  = LogisticRegression(max_iter=500, C=0.5)
    _online_scaler = StandardScaler()
    logger.info("Initialized new ML model")
 
 
def _save_model():
    """Lưu model vào file."""
    try:
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"model": _online_model, "scaler": _online_scaler}, f)
        logger.info("Saved ML model")
    except Exception as e:
        logger.error(f"Cannot save model: {e}")
 
 
def add_training_sample(features: list, label: str):
    """
    Thêm 1 mẫu training mới (gọi sau khi verify kết quả thực tế).
    features: [r1, r2, r3, r5, vol5, ma5, ma10]
    label: "TĂNG" / "GIẢM" / "GIỮ NGUYÊN"
    """
    global _training_buffer
    label_map = {"TĂNG": 1, "GIẢM": -1, "GIỮ NGUYÊN": 0}
    y = label_map.get(label, 0)
    _training_buffer.append((features, y))
 
    # Retrain khi đủ mẫu
    if len(_training_buffer) >= RETRAIN_THRESHOLD:
        _retrain()
 
 
def _retrain():
    """Retrain model với toàn bộ buffer."""
    global _training_buffer, _online_model, _online_scaler
    if len(_training_buffer) < 5:
        return
 
    try:
        X = np.array([s[0] for s in _training_buffer])
        y = np.array([s[1] for s in _training_buffer])
 
        _online_scaler.fit(X)
        X_scaled = _online_scaler.transform(X)
        _online_model.fit(X_scaled, y)
        _save_model()
 
        logger.info(f"Retrained ML model with {len(_training_buffer)} samples")
        _training_buffer = []  # reset buffer
    except Exception as e:
        logger.error(f"Retrain error: {e}")
 
 
# Load model khi khởi động
_load_or_init_model()

@app.post("/ml/feedback")
def ml_feedback(data: dict):
    """
    Nhận kết quả thực tế để model tự học.
    Body: {"symbol": "FPT", "features": [...], "actual": "TĂNG"}
    Gọi từ Spring Boot Scheduler sau khi verify prediction.
    """
    try:
        symbol   = data.get("symbol", "").upper()
        features = data.get("features", [])
        actual   = data.get("actual", "")
 
        if not features or not actual:
            raise HTTPException(status_code=400, detail="Thiếu features hoặc actual")
 
        add_training_sample(features, actual)
 
        return {
            "status":        "ok",
            "symbol":        symbol,
            "actual":        actual,
            "bufferSize":    len(_training_buffer),
            "willRetrain":   len(_training_buffer) >= RETRAIN_THRESHOLD,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/ml/status")
def ml_status():
    """Trạng thái model ML."""
    return {
        "modelLoaded":    _online_model is not None,
        "modelPath":      MODEL_PATH,
        "modelExists":    os.path.exists(MODEL_PATH),
        "bufferSize":     len(_training_buffer),
        "retrainAt":      RETRAIN_THRESHOLD,
    }

# ══════════════════════════════════════════════════════════════════════════════
# BACKTEST + AUTO TRAIN
# Paste vào cuối main.py
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/ml/backtest/{symbol}")
def backtest_and_train(
    symbol: str,
    days:   int = Query(default=90, ge=30, le=365)
):
    """
    Chạy backtest trên dữ liệu lịch sử:
    1. Với mỗi ngày trong quá khứ → tạo dự đoán
    2. So sánh với giá thực tế ngày hôm sau
    3. Dùng kết quả để train ML model
    4. Trả về accuracy report
    """
    symbol = symbol.upper().strip()
    try:
        import numpy as np
        from datetime import datetime as dt

        df = fetch_history_df(symbol, days)
        if df is None or df.empty or len(df) < 30:
            raise HTTPException(status_code=404,
                detail="Không đủ dữ liệu để backtest")

        close_col  = "close"
        closes     = df[close_col].astype(float).values
        n          = len(closes)

        results    = []
        X_train    = []
        y_train    = []

        # Duyệt từng ngày, dùng 20 ngày trước đó để predict ngày tiếp theo
        window = 20
        for i in range(window, n - 1):
            sub_df = df.iloc[:i+1].copy()

            # Tính features
            try:
                ind = compute_indicators(sub_df)

                rsi       = safe_float(ind["rsi"].iloc[-1])
                macd_val  = safe_float(ind["macd"].iloc[-1])
                prev_hist = safe_float(ind["hist"].iloc[-2]) if len(ind["hist"]) > 1 else None
                curr_hist = safe_float(ind["hist"].iloc[-1])
                ma20      = safe_float(ind["ma20"].iloc[-1])
                ma50      = safe_float(ind["ma50"].iloc[-1])
                bb_up     = safe_float(ind["bb_up"].iloc[-1])
                bb_dn     = safe_float(ind["bb_dn"].iloc[-1])
                price     = closes[i]

                # Prediction từ technical signal
                label, score, _ = compute_signal(
                    price, rsi, macd_val, prev_hist, curr_hist,
                    ma20, ma50, bb_up, bb_dn
                )

                # Kết quả thực tế ngày hôm sau
                next_price  = closes[i + 1]
                change_pct  = (next_price - price) / price * 100

                if change_pct > 0.5:
                    actual = "TĂNG"
                elif change_pct < -0.5:
                    actual = "GIẢM"
                else:
                    actual = "GIỮ NGUYÊN"

                is_correct = label == actual

                # Features cho ML
                r1   = (closes[i] - closes[i-1]) / closes[i-1] if i > 0 else 0
                r2   = (closes[i] - closes[i-2]) / closes[i-2] if i > 1 else 0
                r3   = (closes[i] - closes[i-3]) / closes[i-3] if i > 2 else 0
                r5   = (closes[i] - closes[i-5]) / closes[i-5] if i > 4 else 0
                vol5 = float(np.std(closes[max(0,i-5):i+1]) / closes[i]) if closes[i] else 0
                ma5  = float(np.mean(closes[max(0,i-5):i+1]) / closes[i]) if closes[i] else 1
                ma10 = float(np.mean(closes[max(0,i-10):i+1]) / closes[i]) if closes[i] else 1
                rsi_n = (rsi or 50) / 100
                macd_n = min(max((macd_val or 0) / (price * 0.01), -1), 1)

                features = [r1, r2, r3, r5, vol5, ma5, ma10, rsi_n, macd_n]
                X_train.append(features)

                label_map = {"TĂNG": 1, "GIẢM": -1, "GIỮ NGUYÊN": 0}
                y_train.append(label_map.get(actual, 0))

                results.append({
                    "date":       str(df.index[i]) if hasattr(df.index[i], 'strftime')
                                  else str(df.iloc[i].get("time", i)),
                    "prediction": label,
                    "actual":     actual,
                    "changePct":  round(change_pct, 2),
                    "correct":    is_correct,
                })

            except Exception as e:
                logger.warning(f"Backtest skip day {i}: {e}")
                continue

        if not results:
            raise HTTPException(status_code=500, detail="Backtest không ra kết quả")

        # ── Train ML model từ backtest data ───────────────────────────────
        if len(X_train) >= 20:
            try:
                import numpy as np
                from sklearn.linear_model import LogisticRegression
                from sklearn.preprocessing import StandardScaler
                from sklearn.model_selection import cross_val_score

                X = np.array(X_train)
                y = np.array(y_train)

                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)

                model = LogisticRegression(max_iter=500, C=0.5, class_weight='balanced')
                model.fit(X_scaled, y)

                # Cross-validation accuracy
                cv_scores = cross_val_score(model, X_scaled, y, cv=5)
                cv_acc    = float(cv_scores.mean())

                # Lưu model
                global _online_model, _online_scaler
                _online_model  = model
                _online_scaler = scaler
                _save_model()

                ml_trained = True
                ml_cv_acc  = round(cv_acc * 100, 1)
                logger.info(f"Trained ML model from backtest: CV acc={ml_cv_acc}%")

            except Exception as e:
                ml_trained = False
                ml_cv_acc  = 0
                logger.error(f"ML training error: {e}")
        else:
            ml_trained = False
            ml_cv_acc  = 0

        # ── Thống kê kết quả backtest ──────────────────────────────────────
        total   = len(results)
        correct = sum(1 for r in results if r["correct"])
        accuracy = round(correct / total * 100, 1) if total > 0 else 0

        # Accuracy theo từng label
        for lbl in ["TĂNG", "GIẢM", "GIỮ NGUYÊN"]:
            subset  = [r for r in results if r["prediction"] == lbl]
            correct_subset = sum(1 for r in subset if r["correct"])
            pct = round(correct_subset / len(subset) * 100, 1) if subset else 0
            logger.info(f"  {lbl}: {correct_subset}/{len(subset)} = {pct}%")

        tang_res  = [r for r in results if r["prediction"] == "TĂNG"]
        giam_res  = [r for r in results if r["prediction"] == "GIẢM"]
        giu_res   = [r for r in results if r["prediction"] == "GIỮ NGUYÊN"]

        def acc_stats(subset):
            if not subset: return {"total": 0, "correct": 0, "accuracy": 0}
            c = sum(1 for r in subset if r["correct"])
            return {"total": len(subset), "correct": c,
                    "accuracy": round(c/len(subset)*100, 1)}

        return {
            "symbol":   symbol,
            "days":     days,
            "total":    total,
            "correct":  correct,
            "accuracy": accuracy,
            "byLabel": {
                "TĂNG":       acc_stats(tang_res),
                "GIẢM":       acc_stats(giam_res),
                "GIỮ NGUYÊN": acc_stats(giu_res),
            },
            "mlTrained":  ml_trained,
            "mlCvAccuracy": ml_cv_acc,
            "sampleResults": results[-10:],  # 10 kết quả gần nhất
            "backtestAt": dt.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ml/backtest-all")
def backtest_all(days: int = Query(default=90, ge=30, le=180)):
    """
    Chạy backtest cho tất cả mã trong cache → train model tổng hợp.
    Gọi 1 lần để khởi động model, sau đó model tự cải thiện dần.
    """
    from datetime import datetime as dt
    cached_symbols = list(_history_cache.keys())

    if not cached_symbols:
        return {"message": "Chưa có symbol trong cache. Hãy vào xem một số cổ phiếu trước."}

    results = {}
    for key in cached_symbols[:10]:  # Tối đa 10 mã để tránh timeout
        symbol = key.split("_")[0]
        try:
            result = backtest_and_train(symbol, days=days)
            results[symbol] = {
                "accuracy":   result["accuracy"],
                "total":      result["total"],
                "mlTrained":  result["mlTrained"],
            }
        except Exception as e:
            results[symbol] = {"error": str(e)}

    return {
        "backtestAt": dt.now().isoformat(),
        "symbols":    results,
        "mlModelPath": MODEL_PATH,
    }