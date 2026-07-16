"""
Danh sách cổ phiếu Việt Nam.
Tự động load từ VNStock API khi khởi động,
fallback về danh sách tĩnh nếu API không khả dụng.
"""

import logging
logger = logging.getLogger(__name__)

# ── Danh sách tĩnh fallback ────────────────────────────────────────────────────
_STATIC_STOCKS = [
    # Ngân hàng
    {"symbol": "VCB",  "name": "Vietcombank",              "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "BID",  "name": "BIDV",                     "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "CTG",  "name": "VietinBank",               "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "TCB",  "name": "Techcombank",              "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "ACB",  "name": "Asia Commercial Bank",     "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "MBB",  "name": "MB Bank",                  "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "VPB",  "name": "VPBank",                   "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "HDB",  "name": "HDBank",                   "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "STB",  "name": "Sacombank",                "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "EIB",  "name": "Eximbank",                 "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "LPB",  "name": "LienVietPostBank",         "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "OCB",  "name": "Orient Commercial Bank",   "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "SSB",  "name": "SeABank",                  "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "MSB",  "name": "Maritime Bank",            "exchange": "HoSE", "sector": "Ngân hàng"},
    {"symbol": "TPB",  "name": "TPBank",                   "exchange": "HoSE", "sector": "Ngân hàng"},
    # Bất động sản
    {"symbol": "VIC",  "name": "Vingroup",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "VHM",  "name": "Vinhomes",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "NVL",  "name": "Novaland",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "PDR",  "name": "Phát Đạt",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "DXG",  "name": "Đất Xanh Group",           "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "KDH",  "name": "Khang Điền",               "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "CEO",  "name": "C.E.O Group",              "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "DIG",  "name": "DIC Corp",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "HDG",  "name": "Ha Do Group",              "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "NLG",  "name": "Nam Long Group",           "exchange": "HoSE", "sector": "Bất động sản"},
    # Công nghệ
    {"symbol": "FPT",  "name": "FPT Corporation",          "exchange": "HoSE", "sector": "Công nghệ"},
    {"symbol": "CMG",  "name": "CMC Corporation",          "exchange": "HoSE", "sector": "Công nghệ"},
    {"symbol": "ELC",  "name": "Elcom Corporation",        "exchange": "HoSE", "sector": "Công nghệ"},
    {"symbol": "VGI",  "name": "Viettel Global",           "exchange": "HoSE", "sector": "Công nghệ"},
    {"symbol": "ITD",  "name": "IT Development",           "exchange": "HoSE", "sector": "Công nghệ"},
    # Tiêu dùng
    {"symbol": "VNM",  "name": "Vinamilk",                 "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "MSN",  "name": "Masan Group",              "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "MWG",  "name": "Mobile World Group",       "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "PNJ",  "name": "Phú Nhuận Jewelry",        "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "SAB",  "name": "Sabeco",                   "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "BHN",  "name": "Habeco",                   "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "KDC",  "name": "Kinh Đô Corporation",      "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "MCH",  "name": "Masan Consumer",           "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "QNS",  "name": "Quang Ngai Sugar",         "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "SBT",  "name": "Thanh Thanh Cong Sugar",   "exchange": "HoSE", "sector": "Tiêu dùng"},
    # Vật liệu
    {"symbol": "HPG",  "name": "Hòa Phát Group",           "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "HSG",  "name": "Hoa Sen Group",            "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "NKG",  "name": "Nam Kim Steel",            "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "DGC",  "name": "Đức Giang Chemicals",      "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "CSV",  "name": "Southern Chemicals",       "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "BMP",  "name": "Binh Minh Plastics",       "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "DCM",  "name": "Ca Mau Fertilizer",        "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "DPM",  "name": "PetroVietnam Fertilizer",  "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "PHR",  "name": "Phuoc Hoa Rubber",         "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "VHG",  "name": "Vietnamese Rubber",        "exchange": "HoSE", "sector": "Vật liệu"},
    # Năng lượng
    {"symbol": "GAS",  "name": "PetroVietnam Gas",         "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "PLX",  "name": "Petrolimex",               "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "PVD",  "name": "PetroVietnam Drilling",    "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "BSR",  "name": "Binh Son Refining",        "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "POW",  "name": "PetroVietnam Power",       "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "PVT",  "name": "PetroVietnam Transport",   "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "VSH",  "name": "Vinh Son Song Hinh Hydro", "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "REE",  "name": "REE Corporation",          "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "NT2",  "name": "PetroVietnam Ca Mau Power","exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "PC1",  "name": "PCC1",                     "exchange": "HoSE", "sector": "Năng lượng"},
    # Chứng khoán
    {"symbol": "SSI",  "name": "SSI Securities",           "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "VCI",  "name": "Viet Capital Securities",  "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "HCM",  "name": "HSC Securities",           "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "VND",  "name": "VNDirect Securities",      "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "MBS",  "name": "MB Securities",            "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "CTS",  "name": "Vietinbank Securities",    "exchange": "HNX",  "sector": "Chứng khoán"},
    {"symbol": "SHS",  "name": "Saigon Hanoi Securities",  "exchange": "HNX",  "sector": "Chứng khoán"},
    {"symbol": "AGR",  "name": "Agribank Securities",      "exchange": "HoSE", "sector": "Chứng khoán"},
    # Vận tải
    {"symbol": "HVN",  "name": "Vietnam Airlines",         "exchange": "HoSE", "sector": "Vận tải"},
    {"symbol": "VJC",  "name": "VietJet Air",              "exchange": "HoSE", "sector": "Vận tải"},
    {"symbol": "GMD",  "name": "Gemadept",                 "exchange": "HoSE", "sector": "Vận tải"},
    {"symbol": "DVP",  "name": "Dinh Vu Port",             "exchange": "HoSE", "sector": "Vận tải"},
    {"symbol": "HAH",  "name": "Hai An Transport",         "exchange": "HoSE", "sector": "Vận tải"},
    {"symbol": "PHP",  "name": "Hai Phong Port",           "exchange": "HoSE", "sector": "Vận tải"},
    {"symbol": "VTO",  "name": "Vitranschart",             "exchange": "HoSE", "sector": "Vận tải"},
    # Nông nghiệp
    {"symbol": "VHC",  "name": "Vinh Hoan Corporation",    "exchange": "HoSE", "sector": "Nông nghiệp"},
    {"symbol": "ANV",  "name": "Nam Viet Corporation",     "exchange": "HoSE", "sector": "Nông nghiệp"},
    {"symbol": "IDI",  "name": "I.D.I Corporation",        "exchange": "HoSE", "sector": "Nông nghiệp"},
    {"symbol": "FMC",  "name": "Sao Ta Foods",             "exchange": "HoSE", "sector": "Nông nghiệp"},
    {"symbol": "MPC",  "name": "Minh Phu Seafood",         "exchange": "HoSE", "sector": "Nông nghiệp"},
    {"symbol": "HNG",  "name": "Hoang Anh Gia Lai Agri",  "exchange": "HoSE", "sector": "Nông nghiệp"},
    # Bảo hiểm
    {"symbol": "BVH",  "name": "BaoViet Holdings",         "exchange": "HoSE", "sector": "Bảo hiểm"},
    {"symbol": "BMI",  "name": "BaoMinh Insurance",        "exchange": "HoSE", "sector": "Bảo hiểm"},
    {"symbol": "PVI",  "name": "PVI Holdings",             "exchange": "HNX",  "sector": "Bảo hiểm"},
    {"symbol": "MIG",  "name": "Military Insurance",       "exchange": "HoSE", "sector": "Bảo hiểm"},
    # Y tế
    {"symbol": "DHG",  "name": "Duoc Hau Giang",           "exchange": "HoSE", "sector": "Y tế"},
    {"symbol": "IMP",  "name": "Imexpharm",                "exchange": "HoSE", "sector": "Y tế"},
    {"symbol": "DMC",  "name": "Domesco",                  "exchange": "HoSE", "sector": "Y tế"},
    {"symbol": "TRA",  "name": "Traphaco",                 "exchange": "HoSE", "sector": "Y tế"},
    {"symbol": "DBD",  "name": "Binh Dinh Pharma",         "exchange": "HoSE", "sector": "Y tế"},
    {"symbol": "VMD",  "name": "Y Duoc Viet My",           "exchange": "HoSE", "sector": "Y tế"},
    # Xây dựng
    {"symbol": "CTD",  "name": "Coteccons",                "exchange": "HoSE", "sector": "Xây dựng"},
    {"symbol": "HBC",  "name": "Ha Long Construction",     "exchange": "HoSE", "sector": "Xây dựng"},
    {"symbol": "FCN",  "name": "FECON Corporation",        "exchange": "HoSE", "sector": "Xây dựng"},
    {"symbol": "VCG",  "name": "Vinaconex",                "exchange": "HoSE", "sector": "Xây dựng"},
    {"symbol": "CII",  "name": "Ho Chi Minh Infrastructure","exchange": "HoSE", "sector": "Xây dựng"},
]

# ── Tự động load từ VNStock API ────────────────────────────────────────────────
def _load_from_api() -> list:
    """
    Lấy danh sách toàn bộ cổ phiếu HoSE/HNX từ VNStock API.
    Trả về list dict {symbol, name, exchange, sector}.
    """
    try:
        from vnstock import Vnstock
        client = Vnstock()

        # Lấy danh sách niêm yết
        listing = client.stock(symbol="VNM", source="VCI").listing
        df = listing.symbols_by_exchange()

        if df is None or df.empty:
            logger.warning("API returned empty listing, using static list")
            return []

        result = []
        for _, row in df.iterrows():
            symbol   = str(row.get("ticker", "")).strip().upper()
            name     = str(row.get("organ_name", row.get("short_name", symbol)))
            exchange = str(row.get("exchange", "HoSE")).strip()
            # Chuẩn hoá tên sàn
            if "HOSE" in exchange.upper() or "HSX" in exchange.upper():
                exchange = "HoSE"
            elif "HNX" in exchange.upper():
                exchange = "HNX"
            else:
                exchange = "UPCoM"

            # Lấy ngành nếu có
            sector = str(row.get("icb_name3", row.get("icb_name2", "Khác"))).strip()
            if not sector or sector == "nan":
                sector = "Khác"

            if symbol and len(symbol) <= 10:
                result.append({
                    "symbol":   symbol,
                    "name":     name,
                    "exchange": exchange,
                    "sector":   sector,
                })

        # Chỉ lấy HoSE và HNX, bỏ UPCoM (rủi ro cao, ít dữ liệu)
        result = [s for s in result if s["exchange"] in ("HoSE", "HNX")]
        logger.info(f"Loaded {len(result)} stocks from VNStock API")
        return result

    except Exception as e:
        logger.warning(f"Failed to load from API: {e}. Using static list.")
        return []


def _build_stock_list() -> list:
    """Load từ API, fallback về static list nếu lỗi."""
    api_stocks = _load_from_api()
    if len(api_stocks) > 50:
        return api_stocks
    logger.info(f"Using static list ({len(_STATIC_STOCKS)} stocks)")
    return _STATIC_STOCKS


# ── Public API ─────────────────────────────────────────────────────────────────
STOCKS   = _build_stock_list()
SECTORS  = sorted(list(set(s["sector"] for s in STOCKS)))
STOCK_MAP = {s["symbol"]: s for s in STOCKS}


def get_stock_info(symbol: str) -> dict:
    return STOCK_MAP.get(symbol.upper(), {
        "symbol":   symbol.upper(),
        "name":     symbol.upper(),
        "exchange": "HoSE",
        "sector":   "Khác",
    })


@property
def total() -> int:
    return len(STOCKS)