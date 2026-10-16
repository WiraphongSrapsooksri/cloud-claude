"""Markdown report for the SET100 scan (Thai labels)."""
from __future__ import annotations

import pandas as pd

LIST_TITLES = {
    "swing_long": ("Swing ขาขึ้น", "เทรนด์ขึ้นและเงื่อนไขเข้าครบตั้งแต่ 3 จาก 6 ข้อ (EMA, RSI, EMA ตัดขึ้น, เบรก 20 วัน, FVG, วอลุ่ม)"),
    "breakout": ("เบรกไฮ 20 วัน", "ราคาปิดเหนือ high ของ 20 วันก่อนหน้า เรียงตามวอลุ่ม"),
    "unusual_volume": ("วอลุ่มผิดปกติ", "วอลุ่มวันล่าสุดมากกว่าค่าเฉลี่ย 20 วันตั้งแต่ 2 เท่า"),
    "oversold": ("RSI ต่ำ (Oversold)", "RSI ต่ำกว่า 30 ซึ่งอาจเด้ง แต่เป็นการสวนเทรนด์ ต้องระวัง"),
    "overbought": ("RSI สูง (Overbought)", "RSI สูงกว่า 75 ไม่ควรไล่ราคา"),
    "breakdown": ("หลุดโลว์ 20 วัน", "ราคาปิดต่ำกว่า low ของ 20 วันก่อนหน้า ควรหลีกเลี่ยงฝั่งซื้อ"),
    "day_trade": ("เหมาะ Day trade", "สภาพคล่องสูง (มูลค่าเฉลี่ยตั้งแต่ 300 ล้านบาทต่อวัน) เรียงตามช่วงแกว่งเฉลี่ยต่อวัน"),
}

COLS = {
    "swing_long": ["close", "chg_1d", "rsi", "swing_score", "vol_ratio", "breakout_20d", "fvg_bull_retest", "atr_pct"],
    "breakout": ["close", "chg_1d", "high_20d", "vol_ratio", "rsi", "trend"],
    "unusual_volume": ["close", "chg_1d", "vol_ratio", "value_mthb", "trend"],
    "oversold": ["close", "chg_5d", "rsi", "dist_low_pct", "trend"],
    "overbought": ["close", "chg_5d", "rsi", "dist_high_pct", "trend"],
    "breakdown": ["close", "chg_1d", "low_20d", "vol_ratio", "trend"],
    "day_trade": ["close", "avg_day_range_pct", "avg_value_mthb", "best_slot", "best_slot_ret", "worst_slot", "worst_slot_ret"],
}

HEADERS = {
    "close": "ราคา", "chg_1d": "%1วัน", "chg_5d": "%5วัน", "chg_20d": "%20วัน", "rsi": "RSI",
    "swing_score": "คะแนน", "vol_ratio": "วอลุ่ม(x)", "breakout_20d": "เบรก", "fvg_bull_retest": "FVG",
    "atr_pct": "ATR%", "high_20d": "ไฮ20วัน", "low_20d": "โลว์20วัน", "trend": "เทรนด์",
    "value_mthb": "มูลค่า(ลบ.)", "avg_value_mthb": "มูลค่าเฉลี่ย(ลบ.)", "dist_low_pct": "ห่างโลว์%",
    "dist_high_pct": "ห่างไฮ%", "avg_day_range_pct": "แกว่ง/วัน%", "best_slot": "ช่วงมักขึ้น",
    "best_slot_ret": "ขึ้นเฉลี่ย%", "worst_slot": "ช่วงมักลง", "worst_slot_ret": "ลงเฉลี่ย%",
    "stocks": "จำนวน", "up_trend": "เทรนด์ขึ้น", "avg_ret_pct": "เฉลี่ย%", "up_pct": "ขึ้นกี่%ของวัน",
    "days": "วัน",
}


INT_COLS = {"stocks", "up_trend", "days", "up_pct", "swing_score"}


def _fmt(v, col=""):
    if isinstance(v, bool) or str(v) in ("True", "False"):
        return "✓" if str(v) == "True" else ""
    if col in INT_COLS:
        return f"{int(v)}"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def md_table(df: pd.DataFrame, cols: list[str] | None = None, index_name: str = "หุ้น") -> str:
    cols = [c for c in (cols or list(df.columns)) if c in df.columns]
    head = "| " + " | ".join([index_name] + [HEADERS.get(c, c) for c in cols]) + " |"
    sep = "|" + "---|" * (len(cols) + 1)
    lines = [head, sep]
    for idx, row in df[cols].iterrows():
        lines.append("| " + " | ".join([str(idx)] + [_fmt(row[c], c) for c in cols]) + " |")
    return "\n".join(lines)


def build_report(res, lists, sectors, set_profile, as_of_daily, as_of_intraday, set_daily=None) -> str:
    out = [
        f"# สแกน SET100 — ข้อมูลวันที่ {as_of_daily}",
        "",
        f"ข้อมูลรายวันถึง **{as_of_daily}** · แท่ง 15 นาทีล่าสุด **{as_of_intraday}** · แหล่งข้อมูล Yahoo Finance (ดีเลย์ประมาณ 15–20 นาที)",
        "",
        "> รายงานนี้เป็นเครื่องมือช่วยคัดกรองหุ้นเท่านั้น ไม่ใช่คำแนะนำการลงทุน ต้องตั้งจุดตัดขาดทุนทุกครั้ง",
        "> ถ้ารันระหว่างที่ตลาดเปิดอยู่ วอลุ่มของวันนั้นจะยังนับไม่ครบ ค่าวอลุ่ม(x) จึงออกมาต่ำกว่าความจริง",
        "",
    ]
    if set_daily is not None:
        out += [f"**ดัชนี SET:** {set_daily['close']:,.2f} ({set_daily['chg_1d']:+.2f}% วันล่าสุด, "
                f"{set_daily['chg_5d']:+.2f}% 5 วัน, RSI {set_daily['rsi']}, เทรนด์ {set_daily['trend']})", ""]
    breadth = res["trend"].value_counts()
    out += [f"**ภาพรวม SET100:** เทรนด์ขึ้น {breadth.get('up', 0)} ตัว · ออกข้าง {breadth.get('sideways', 0)} ตัว · "
            f"เทรนด์ลง {breadth.get('down', 0)} ตัว · บวกวันล่าสุด {(res['chg_1d'] > 0).sum()} ตัว / ลบ {(res['chg_1d'] < 0).sum()} ตัว", ""]

    for key, (title, desc) in LIST_TITLES.items():
        df = lists.get(key)
        if df is None:
            continue
        out += [f"## {title}", f"_{desc}_", ""]
        out += [md_table(df, COLS[key]) if not df.empty else "ไม่มีหุ้นเข้าเงื่อนไข", ""]

    out += ["## กลุ่มอุตสาหกรรม (เรียงตาม %5วัน)", "",
            md_table(sectors, ["stocks", "chg_1d", "chg_5d", "chg_20d", "up_trend"], "กลุ่ม"), ""]

    if set_profile is not None and not set_profile.empty:
        out += ["## ดัชนี SET: ช่วงเวลาไหนมักขึ้นหรือลง (แท่ง 15 นาที ย้อนหลัง 60 วัน)",
                "_ค่าเฉลี่ยผลตอบแทนของแต่ละแท่ง 15 นาที และสัดส่วนวันที่แท่งนั้นปิดบวก_", "",
                md_table(set_profile, ["avg_ret_pct", "up_pct", "days"], "เวลา"), ""]
    return "\n".join(out)
