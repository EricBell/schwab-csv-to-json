
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, csv, json, re, sys
from datetime import datetime
from typing import List, Dict, Any, Optional

SECTIONS = {
    "TOP": "Top",
    "WORKING": "Working Orders",
    "FILLED": "Filled Orders",
    "CANCELED": "Canceled Orders",
    "ROLLING": "Rolling Strategies",
}

SECTION_HEADERS_HINTS = {
    SECTIONS["WORKING"]: ["Time Placed"],
    SECTIONS["FILLED"]: ["Exec Time"],
    SECTIONS["CANCELED"]: ["Time Canceled"],
    SECTIONS["ROLLING"]: ["Covered Call Position", "Rolling"],
}

NUMERIC_RE = re.compile(r'^-?\d+(?:\.\d+)?$')
PRICE_LIKE_RE = re.compile(r'^\.?-?\d+(?:\.\d+)?$')
AMEND_REF_RE = re.compile(r'^RE\s*#\s*(\d+)', re.IGNORECASE)

MONTH_MAP = {
    'JAN':'01','FEB':'02','MAR':'03','APR':'04','MAY':'05','JUN':'06',
    'JUL':'07','AUG':'08','SEP':'09','OCT':'10','NOV':'11','DEC':'12'
}

def normalize_header_key(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r'[\s/]+', '_', s.lower())
    s = re.sub(r'[^a-z0-9_]+', '', s)
    return s

def parse_datetime_maybe(s: Optional[str]) -> Optional[str]:
    if not s: return None
    s = s.strip()
    fmts = [
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.isoformat()
        except Exception:
            continue
    return None

def to_number(x: Optional[str]) -> Optional[float]:
    if x is None: return None
    sx = str(x).strip()
    if sx in {"~","-",""}: return None
    if sx.startswith(".") and sx != ".":
        sx = "0" + sx
    try:
        return float(sx)
    except Exception:
        return None

def parse_exp_date(exp: Optional[str]) -> Optional[str]:
    if not exp: return None
    exp = exp.strip().upper()
    m = re.match(r'^(\d{1,2})\s+([A-Z]{3})\s+(\d{2,4})$', exp)
    if not m: 
        try:
            return datetime.strptime(exp, "%Y-%m-%d").date().isoformat()
        except Exception:
            return None
    day, mon3, yr = m.groups()
    MONTH_MAP = {
        'JAN':'01','FEB':'02','MAR':'03','APR':'04','MAY':'05','JUN':'06',
        'JUL':'07','AUG':'08','SEP':'09','OCT':'10','NOV':'11','DEC':'12'
    }
    mon = MONTH_MAP.get(mon3)
    if not mon: return None
    if len(yr)==2:
        yr = ("20" + yr) if int(yr) <= 69 else ("19" + yr)
    return f"{yr}-{mon}-{int(day):02d}"

def classify_row(cells: List[str]) -> str:
    if not cells or all((c.strip()=="" for c in cells)):
        return "noise"
    for c in cells:
        if re.match(r'^RE\s*#\s*\d+', c.strip(), re.IGNORECASE):
            return "amendment"
    header_markers = {"exec time","time canceled","time placed","spread","side","qty","pos effect","symbol","type"}
    joins = ",".join([normalize_header_key(c) for c in cells])
    if any(h in joins for h in ["exec_time","time_canceled","time_placed"]) and "side" in joins and "qty" in joins:
        return "header"
    return "data"

def build_order_record(section: str, header: List[str], cells: List[str]) -> Optional[Dict[str,Any]]:
    keymap = [normalize_header_key(h) for h in header]
    values = { keymap[i]: (cells[i].strip() if i < len(cells) else "") for i in range(len(keymap)) }

    get = lambda *names: next((values.get(n) for n in names if n in values), None)

    exec_time = get("exec_time")
    time_canceled = get("time_canceled","time_cancelled")
    spread = get("spread")
    side = (get("side") or "").strip().upper() or None
    qty_s = get("qty","quantity")
    pos_effect = (get("pos_effect") or "").strip().upper() or None
    symbol = (get("symbol") or "").strip().upper() or None
    exp = get("exp","expiration")
    strike_s = get("strike")
    typ = (get("type","right","option_type") or "").strip().upper() or None
    price_s = get("price","limit_price","exec_price")
    net_price_s = get("net_price","net_price_")
    price_impr_s = get("price_improvement","price_impr")
    order_type = (get("order_type","ordertype","order_type_") or "").strip().upper() or None
    tif = (get("tif","time_in_force") or "").strip().upper() or None
    status = (get("status") or "").strip().upper() or None
    notes = get("notes")
    mark_s = get("mark")

    if not side and not qty_s and not symbol and not typ:
        return None

    qty = to_number(qty_s)
    if qty is not None:
        qty_abs = abs(int(qty)) if float(qty).is_integer() else abs(float(qty))
    else:
        qty_abs = None

    price = to_number(price_s)
    net_price = to_number(net_price_s)
    price_improvement = to_number(price_impr_s)
    strike = to_number(strike_s)
    mark = to_number(mark_s)

    asset_type = "OPTION" if typ in {"CALL","PUT"} else ("STOCK" if typ=="STOCK" else None)

    option = None
    if asset_type == "OPTION":
        option = {
            "exp_date": parse_exp_date(exp),
            "strike": strike,
            "right": typ,
        }

    if section == "Filled Orders":
        event_type = "fill"
    elif section == "Canceled Orders":
        event_type = "cancel"
    elif section == "Working Orders":
        event_type = "working"
    else:
        event_type = "other"

    rec = {
        "section": section.lower().replace(" ", "_"),
        "event_type": event_type,
        "exec_time": parse_datetime_maybe(exec_time),
        "time_canceled": parse_datetime_maybe(time_canceled),
        "symbol": symbol,
        "asset_type": asset_type,
        "side": side,
        "pos_effect": pos_effect,
        "qty_abs": qty_abs,
        "price": price,
        "net_price": net_price,
        "price_improvement": price_improvement,
        "order_type": order_type,
        "tif": tif,
        "status": status,
        "option": option,
        "raw_cells": cells,
    }
    return rec

def build_amendment_record(section: str, cells: List[str]) -> Dict[str,Any]:
    ref = None
    stop_price = None
    order_type = None
    tif = None

    for c in cells:
        c_str = c.strip()
        m = re.match(r'^RE\s*#\s*(\d+)', c_str, re.IGNORECASE)
        if m:
            ref = m.group(1)
            continue
        if stop_price is None and re.match(r'^\.?-?\d+(?:\.\d+)?$', c_str):
            try:
                stop_price = float(c_str if not c_str.startswith(".") else "0"+c_str)
            except Exception:
                pass
        if c_str.upper() in {"STP","STP LMT","LMT","MKT"}:
            order_type = c_str.upper()
        if c_str.upper() in {"DAY","GTC","STD"}:
            tif = c_str.upper()

    rec = {
        "section": section.lower().replace(" ", "_"),
        "event_type": "amend",
        "amendment": {
            "ref": ref,
            "stop_price": stop_price,
            "order_type": order_type,
            "tif": tif,
        },
        "raw_cells": cells,
    }
    return rec

def parse_file(path: str, include_rolling: bool=False) -> list:
    results = []
    section = "Top"
    in_data = False
    current_header = None

    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            cells = [c for c in row]
            raw_join = ",".join(row).strip()

            if raw_join.strip() in {"Working Orders","Filled Orders","Canceled Orders","Rolling Strategies"}:
                section = raw_join.strip()
                in_data = False
                current_header = None
                continue

            if section == "Rolling Strategies" and not include_rolling:
                continue

            cls = classify_row(cells)
            if cls == "header":
                current_header = cells
                in_data = True
                continue
            elif cls in {"noise"}:
                continue

            if not in_data or not current_header:
                continue

            if cls == "amendment":
                results.append(build_amendment_record(section, cells))
                continue

            rec = build_order_record(section, current_header, cells)
            if rec:
                results.append(rec)

    return results

def validate(records: list) -> dict:
    issues = {}
    def bump(k): issues[k] = issues.get(k,0)+1

    for r in records:
        et = r.get("event_type")
        if et == "amend":
            if not r.get("amendment",{}).get("ref"):
                bump("amend_missing_ref")
            if r.get("amendment",{}).get("stop_price") is None:
                bump("amend_missing_stop_price")
            continue

        if not r.get("symbol"):
            bump("missing_symbol")
        if not r.get("side"):
            bump("missing_side")
        if r.get("qty_abs") is None:
            bump("missing_qty")
        asset_type = r.get("asset_type")
        if asset_type == "OPTION":
            opt = r.get("option") or {}
            if not opt.get("exp_date"):
                bump("option_missing_exp")
            if opt.get("strike") is None:
                bump("option_missing_strike")
            if not opt.get("right") in {"PUT","CALL"}:
                bump("option_missing_right")
        elif asset_type == None and r.get("event_type") != "amend":
            bump("unknown_asset_type")
    return issues

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--include-rolling", action="store_true")
    args = ap.parse_args()

    records = parse_file(args.input, include_rolling=args.include_rolling)
    issues = validate(records)

    with open(args.output, "w", encoding="utf-8") as out:
        for r in records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    sys.stderr.write(f"Parsed records: {len(records)}\n")
    if issues:
        sys.stderr.write("Validation issues:\n")
        for k,v in sorted(issues.items()):
            sys.stderr.write(f"  - {k}: {v}\n")
    else:
        sys.stderr.write("No validation issues detected.\n")

if __name__ == "__main__":
    main()
