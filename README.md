# XAUUSD Grid Bot (EMA Cross + RSI + ATR Grid)

บอทเทรดทองคำ (XAUUSD) เขียนด้วย Python มีทั้ง backtest, paper trading และเทรดจริงผ่าน MetaTrader 5

> ⚠️ การเทรดแบบ grid กับทองคำมีความเสี่ยงสูง ให้ทดสอบกับบัญชี **DEMO** ก่อนเสมอ ผล backtest ในอดีตไม่ได้รับประกันผลในอนาคต

## กลยุทธ์

| ส่วน | กติกา (ค่าเริ่มต้น) |
|---|---|
| สัญญาณเข้า | EMA 20 ตัด EMA 50 ขึ้น → BUY / ตัดลง → SELL |
| ตัวกรอง | RSI(14) ต้องอยู่ช่วง 50–70 สำหรับ BUY และ 30–50 สำหรับ SELL |
| FVG (เลือกได้) | `FVG_MODE=confirm` คือต้องมี Fair Value Gap ทิศเดียวกันเกิดภายใน `FVG_LOOKBACK` แท่งก่อนหน้า<br>`FVG_MODE=retest` คือไม่ต้องรอ EMA ตัด ให้เข้าเมื่อราคาย่อกลับมาแตะ FVG ตามทิศเทรนด์ |
| Grid | ถ้าราคาวิ่งสวน เติมออเดอร์ทุก 1×ATR สูงสุด 4 ไม้ (รวมไม้แรกเป็น 5) |
| Take profit | ราคาเฉลี่ยของทั้งตะกร้า ± 1.5×ATR |
| Stop loss | เลยไม้ grid สุดท้ายไปอีก 1×ATR (ปิดทั้งตะกร้า) |
| ปิดเมื่อกลับทาง | EMA ตัดสวนทาง → ปิดทั้งตะกร้า |

ปรับค่าทุกตัวได้ผ่าน environment variable หรือไฟล์ `.env` (ดู `.env.example` และ `bot/config.py`)
ค่า `LOT_MULTIPLIER=1.0` คือใช้ lot เท่ากันทุกไม้ ถ้าตั้งมากกว่า 1 จะกลายเป็น martingale ซึ่งเสี่ยงล้างพอร์ตมาก

## ติดตั้ง

```bash
pip install -r requirements.txt
cp .env.example .env    # แล้วแก้ค่าในไฟล์ .env
```

## Backtest

```bash
python run_backtest.py                       # ทอง H1 ย้อนหลัง ~2 ปี (Yahoo GC=F)
python run_backtest.py --timeframe M15       # M15 ย้อนหลัง 60 วัน
python run_backtest.py --csv data/XAUUSD_M15.csv   # ไฟล์ที่ export จาก MT5
```

ผลจะอยู่ใน `logs/backtest/trades.csv` และ `equity.csv`
ข้อมูลจาก Yahoo เป็นราคาทองฟิวเจอร์ (GC=F) ไม่ใช่ spot XAUUSD จึงใช้แทนได้แค่คร่าวๆ ถ้าต้องการผลที่แม่นกว่า ให้ export ข้อมูลจาก MT5 มาใช้แทน

## ผลเทียบ FVG (backtest GC=F, 0.01 lot ต่อไม้, ทุน $10,000)

| โหมด | H1 ~2.4 ปี: กำไร / PF / DD | M15 60 วัน: กำไร / PF / DD |
|---|---|---|
| ไม่ใช้ FVG | +$462 / 1.10 / 9.1% | −$196 / 0.82 / 5.0% |
| confirm, lookback 10, min 0.5 ATR | +$420 / 1.19 / 4.8% | +$22 / 1.05 / 1.6% |
| retest (ค่าที่ดีที่สุด) | +$830 / 1.06 / 17.5% | −$293 / 0.91 / 8.9% |

`confirm` ช่วยลด drawdown ลงประมาณครึ่งหนึ่ง แต่ค่าตั้งที่อยู่ใกล้กัน (เช่น lookback 20) กลับให้ผลแย่ลงมาก แปลว่าผลนี้ยังไม่นิ่ง ต้องลองต่อบนบัญชี demo ก่อน
`retest` เข้าเทรดบ่อยมาก และโดน stop loss บ่อยจน drawdown สูง จึงยังไม่แนะนำให้ใช้

## Exness

- ชื่อ symbol ทอง: บัญชี Standard ใช้ `XAUUSDm`, บัญชี Pro/Raw Spread/Zero ใช้ `XAUUSD`, บัญชี Standard Cent ใช้ `XAUUSDc`
- `MT5_SERVER` ให้คัดลอกชื่อ server ให้ตรงตามที่แสดงในหน้า Personal Area ของ Exness (บัญชี demo จะมีชื่อแบบ `Exness-MT5Trial…`)
- ถ้าใช้บัญชี Cent ตัวเลขยอดเงินและกำไรขาดทุนในบัญชีจะเป็นหน่วย cent (USC)

## เทรดสด

**Paper (ไม่ต้องมีบัญชี รันที่ไหนก็ได้):**
```bash
python run_live.py --broker paper
```

**MetaTrader 5 (ต้องรันบน Windows ที่ติดตั้ง MT5 แล้ว):**
1. `pip install MetaTrader5`
2. ใส่ `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` ของบัญชี demo ลงใน `.env`
3. รัน `python run_live.py --broker mt5` ช่วงแรกจะเป็น **dry run** คือบอทจะแค่บันทึก log ว่าจะส่งออเดอร์อะไร โดยยังไม่ส่งจริง
4. ถ้าทุกอย่างดูถูกต้อง ให้ตั้ง `LIVE_TRADING=yes` แล้วบอทจะเริ่มส่งออเดอร์จริง

บอทจะดูเฉพาะออเดอร์ที่มี `MT5_MAGIC` ของตัวเอง ออเดอร์ที่คุณเปิดเองด้วยมือจะไม่ถูกแตะ

## บันทึกการเทรด (Journal)

ทุกครั้งที่ปิดตะกร้า บอทจะเขียนลง `logs/journal.csv` ประกอบด้วยเวลาเปิดและปิด, ฝั่ง, จำนวนไม้, lot, ราคาเฉลี่ย, เหตุผลที่ปิด, กำไรขาดทุน, ค่า indicator ตอนเข้า, ขาดทุนลึกสุดและกำไรสูงสุดระหว่างถือ (MAE/MFE) และค่าตั้งค่าที่ใช้อยู่ตอนนั้น
ไฟล์นี้ใช้วิเคราะห์ย้อนหลังเพื่อปรับกลยุทธ์ต่อ

## โครงสร้าง

```
bot/config.py       ค่าตั้งค่ากลยุทธ์และตลาด (อ่านจาก env ได้)
bot/indicators.py   EMA, RSI, ATR
bot/strategy.py     สัญญาณเข้า และตะกร้า grid (TP/SL) ใช้ร่วมกันทั้ง backtest และ live
bot/backtest.py     ตัว backtest แบบทีละแท่ง
bot/live.py         loop เทรดสด + เก็บ state + journal
bot/brokers/        paper.py (จำลอง) และ mt5.py (MetaTrader 5)
tests/              pytest
```

## ทดสอบ

```bash
python -m pytest -q
```
