"""
Danh sách cổ phiếu Việt Nam theo ngành.
File riêng để dễ mở rộng sau này.
"""

STOCKS = [
    # ── Ngân hàng ──────────────────────────────────────────────────────────
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

    # ── Bất động sản ───────────────────────────────────────────────────────
    {"symbol": "VIC",  "name": "Vingroup",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "VHM",  "name": "Vinhomes",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "NVL",  "name": "Novaland",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "PDR",  "name": "Phát Đạt",                 "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "DXG",  "name": "Đất Xanh Group",           "exchange": "HoSE", "sector": "Bất động sản"},
    {"symbol": "KDH",  "name": "Khang Điền",               "exchange": "HoSE", "sector": "Bất động sản"},

    # ── Công nghệ ──────────────────────────────────────────────────────────
    {"symbol": "FPT",  "name": "FPT Corporation",          "exchange": "HoSE", "sector": "Công nghệ"},
    {"symbol": "CMG",  "name": "CMC Corporation",          "exchange": "HoSE", "sector": "Công nghệ"},
    {"symbol": "ELC",  "name": "Elcom Corporation",        "exchange": "HoSE", "sector": "Công nghệ"},

    # ── Tiêu dùng ──────────────────────────────────────────────────────────
    {"symbol": "VNM",  "name": "Vinamilk",                 "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "MSN",  "name": "Masan Group",              "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "MWG",  "name": "Mobile World Group",       "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "PNJ",  "name": "Phú Nhuận Jewelry",        "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "SAB",  "name": "Sabeco",                   "exchange": "HoSE", "sector": "Tiêu dùng"},
    {"symbol": "BHN",  "name": "Habeco",                   "exchange": "HoSE", "sector": "Tiêu dùng"},

    # ── Công nghiệp / Vật liệu ─────────────────────────────────────────────
    {"symbol": "HPG",  "name": "Hòa Phát Group",           "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "HSG",  "name": "Hoa Sen Group",            "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "NKG",  "name": "Nam Kim Steel",            "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "DGC",  "name": "Đức Giang Chemicals",      "exchange": "HoSE", "sector": "Vật liệu"},
    {"symbol": "CSV",  "name": "Hóa chất Cơ bản",         "exchange": "HoSE", "sector": "Vật liệu"},

    # ── Năng lượng ─────────────────────────────────────────────────────────
    {"symbol": "GAS",  "name": "PetroVietnam Gas",         "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "PLX",  "name": "Petrolimex",               "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "PVD",  "name": "PetroVietnam Drilling",    "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "BSR",  "name": "Bình Sơn Refining",        "exchange": "HoSE", "sector": "Năng lượng"},
    {"symbol": "POW",  "name": "PetroVietnam Power",       "exchange": "HoSE", "sector": "Năng lượng"},

    # ── Chứng khoán ────────────────────────────────────────────────────────
    {"symbol": "SSI",  "name": "SSI Securities",           "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "VCI",  "name": "Viet Capital Securities",  "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "HCM",  "name": "HSC Securities",           "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "VND",  "name": "VNDirect Securities",      "exchange": "HoSE", "sector": "Chứng khoán"},
    {"symbol": "MBS",  "name": "MB Securities",            "exchange": "HoSE", "sector": "Chứng khoán"},

    # ── Hàng không / Vận tải ───────────────────────────────────────────────
    {"symbol": "HVN",  "name": "Vietnam Airlines",         "exchange": "HoSE", "sector": "Vận tải"},
    {"symbol": "VJC",  "name": "VietJet Air",              "exchange": "HoSE", "sector": "Vận tải"},
    {"symbol": "GMD",  "name": "Gemadept",                 "exchange": "HoSE", "sector": "Vận tải"},

    # ── Nông nghiệp / Thủy sản ─────────────────────────────────────────────
    {"symbol": "VHC",  "name": "Vĩnh Hoàn Corporation",   "exchange": "HoSE", "sector": "Nông nghiệp"},
    {"symbol": "ANV",  "name": "Nam Việt Corporation",     "exchange": "HoSE", "sector": "Nông nghiệp"},
    {"symbol": "IDI",  "name": "I.D.I Corporation",        "exchange": "HoSE", "sector": "Nông nghiệp"},

    # ── Bảo hiểm ───────────────────────────────────────────────────────────
    {"symbol": "BVH",  "name": "BaoViet Holdings",         "exchange": "HoSE", "sector": "Bảo hiểm"},
    {"symbol": "BMI",  "name": "BaoMinh Insurance",        "exchange": "HoSE", "sector": "Bảo hiểm"},

    # ── Y tế / Dược ────────────────────────────────────────────────────────
    {"symbol": "DHG",  "name": "Dược Hậu Giang",           "exchange": "HoSE", "sector": "Y tế"},
    {"symbol": "IMP",  "name": "Imexpharm",                "exchange": "HoSE", "sector": "Y tế"},
    {"symbol": "DMC",  "name": "Domesco",                  "exchange": "HoSE", "sector": "Y tế"},
]

# Lấy danh sách tất cả sectors
SECTORS = sorted(list(set(s["sector"] for s in STOCKS)))

# Dict để lookup nhanh
STOCK_MAP = {s["symbol"]: s for s in STOCKS}

def get_stock_info(symbol: str) -> dict:
    return STOCK_MAP.get(symbol.upper(), {
        "symbol": symbol.upper(),
        "name": symbol.upper(),
        "exchange": "HoSE",
        "sector": "Khác"
    })
