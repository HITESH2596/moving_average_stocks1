import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="TradeSignal Pro", initial_sidebar_state="expanded")

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

DEFAULT_US = [
    "AAPL","MSFT","NVDA","GOOGL","GOOG","META","AMZN","TSLA","AMD","NFLX",
    "JPM","MS","GS","BAC","WFC","C","BLK","AXP","V","MA","PYPL",
    "JNJ","UNH","PFE","ABBV","MRK","LLY","TMO","ABT","CVS","AMGN",
    "XOM","CVX","COP","SLB","EOG","MPC","PSX","VLO","OXY","HAL",
    "WMT","HD","MCD","NKE","SBUX","TGT","COST","LOW","TJX",
    "BA","CAT","HON","UPS","RTX","LMT","GE","MMM","DE","FDX",
    "DIS","CMCSA","T","VZ","CHTR","TMUS","SNAP","PINS","UBER","LYFT",
    "INTC","QCOM","AVGO","TXN","MU","AMAT","LRCX","KLAC","MRVL","SMCI",
    "CRM","ORCL","ADBE","NOW","SNOW","PLTR","DDOG","ZS","NET","CRWD",
    "SPY","QQQ","IWM","DIA","XLK","XLF","XLE","XLV","XLI","ARKK",
]
DEFAULT_US = list(dict.fromkeys(DEFAULT_US))

DEFAULT_IN_50 = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
    "WIPRO.NS","BAJFINANCE.NS","SBIN.NS","LT.NS","TATAMOTORS.NS",
    "HINDUNILVR.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS",
    "ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS","NTPC.NS","ONGC.NS",
    "COALINDIA.NS","HCLTECH.NS","TECHM.NS","AXISBANK.NS","KOTAKBANK.NS",
    "INDUSINDBK.NS","BHARTIARTL.NS","ITC.NS","DRREDDY.NS","CIPLA.NS",
    "DIVISLAB.NS","EICHERMOT.NS","HEROMOTOCO.NS","BAJAJ-AUTO.NS","BPCL.NS",
    "GRASIM.NS","HINDALCO.NS","JSWSTEEL.NS","TATASTEEL.NS","TATACONSUM.NS",
    "UPL.NS","APOLLOHOSP.NS","ADANIENT.NS","ADANIGREEN.NS","ADANIPORTS.NS",
    "BAJAJFINSV.NS","BRITANNIA.NS","SBILIFE.NS","HDFCLIFE.NS","M&M.NS",
]

DEFAULT_IN = DEFAULT_IN_50 + [
    "AMBUJACEM.NS","AUROPHARMA.NS","BANDHANBNK.NS","BERGEPAINT.NS","BEL.NS",
    "BOSCHLTD.NS","CANBK.NS","CHOLAFIN.NS","COLPAL.NS","DABUR.NS",
    "DLF.NS","GAIL.NS","GODREJCP.NS","HAVELLS.NS","HINDPETRO.NS",
    "ICICIGI.NS","ICICIPRULI.NS","INDUSTOWER.NS","IRCTC.NS","JUBLFOOD.NS",
    "LICHSGFIN.NS","LUPIN.NS","MARICO.NS","MCDOWELL-N.NS","MUTHOOTFIN.NS",
    "NAUKRI.NS","NMDC.NS","OFSS.NS","PAGEIND.NS","PIDILITIND.NS",
    "PNB.NS","RECLTD.NS","SAIL.NS","SHREECEM.NS","SIEMENS.NS",
    "SRF.NS","TORNTPHARM.NS","TRENT.NS","VEDL.NS","VOLTAS.NS",
    "ZOMATO.NS","DMART.NS","PIIND.NS","ALKEM.NS","BALKRISIND.NS",
    "BIOCON.NS","CONCOR.NS","INDIGO.NS","MFSL.NS","MOTHERSON.NS",
    "ABCAPITAL.NS","ABFRL.NS","AJANTPHARM.NS","APOLLOTYRE.NS","ASHOKLEY.NS",
    "ASTRAL.NS","ATUL.NS","AUBANK.NS","BAJAJHLDNG.NS",
    "BATAINDIA.NS","BHEL.NS","BLUEDART.NS","CEATLTD.NS","CROMPTON.NS",
    "CUMMINSIND.NS","CYIENT.NS","DEEPAKNTR.NS","DIXON.NS","ELGIEQUIP.NS",
    "ESCORTS.NS","EXIDEIND.NS","FEDERALBNK.NS","FLUOROCHEM.NS",
    "GLENMARK.NS","GMRINFRA.NS","GNFC.NS","GODREJPROP.NS","GRANULES.NS",
    "GSPL.NS","GUJGASLTD.NS","HAL.NS","HFCL.NS","HONAUT.NS",
    "IDFCFIRSTB.NS","IEX.NS","INDHOTEL.NS","INDIANB.NS",
    "JKCEMENT.NS","JSL.NS","JUBLINGREA.NS","KAJARIACER.NS","KANSAINER.NS",
    "KEC.NS","LALPATHLAB.NS","LAURUSLABS.NS","LTTS.NS",
    "LUXIND.NS","MANAPPURAM.NS","MAXHEALTH.NS","MCX.NS",
    "METROPOLIS.NS","MRF.NS","NATCOPHARM.NS",
    "NAVINFLUOR.NS","NBCC.NS","NLCINDIA.NS","OBEROIRLTY.NS",
    "PERSISTENT.NS","PETRONET.NS","PFIZER.NS","PHOENIXLTD.NS","POLYCAB.NS",
    "PRAJIND.NS","PTC.NS","RAMCOCEM.NS",
    "RVNL.NS","SBICARD.NS","SCHAEFFLER.NS","SKFINDIA.NS","SOBHA.NS",
    "SONACOMS.NS","STARHEALTH.NS","SUMICHEM.NS","SUNDARMFIN.NS","SUNDRMFAST.NS",
    "SUPREMEIND.NS","SYNGENE.NS","TATACHEM.NS","TATACOMM.NS","TATAELXSI.NS",
    "TATAPOWER.NS","THERMAX.NS","TIMKEN.NS","TTKPRESTIG.NS",
    "TVSMOTOR.NS","UBLLTD.NS","UNIONBANK.NS",
    "VBL.NS","WHIRLPOOL.NS","ZEEL.NS","ZYDUSLIFE.NS",
]

DEFAULT_CR = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD"]
DEFAULT_CM = ["GC=F","SI=F","CL=F","NG=F","HG=F","PL=F"]
COMMODITY_NAMES = {
    "GC=F":"Gold","SI=F":"Silver","CL=F":"Crude Oil",
    "NG=F":"Natural Gas","HG=F":"Copper","PL=F":"Platinum"
}

ALL_TICKERS = list(dict.fromkeys(DEFAULT_US + DEFAULT_IN + DEFAULT_CR + DEFAULT_CM))

CRYPTO_ORDER_MAP = {
    "BTC-USD":"BTC/USD","ETH-USD":"ETH/USD","SOL-USD":"SOL/USD",
    "BNB-USD":"BNB/USD","XRP-USD":"XRP/USD","ADA-USD":"ADA/USD","DOGE-USD":"DOGE/USD",
}
CRYPTO_CLOSE_MAP = {
    "BTC-USD":"BTCUSD","ETH-USD":"ETHUSD","SOL-USD":"SOLUSD",
    "BNB-USD":"BNBUSD","XRP-USD":"XRPUSD","ADA-USD":"ADAUSD","DOGE-USD":"DOGEUSD",
}
CRYPTO_POSITION_MAP = {
    "BTCUSD":"BTC-USD","ETHUSD":"ETH-USD","SOLUSD":"SOL-USD",
    "BNBUSD":"BNB-USD","XRPUSD":"XRP-USD","ADAUSD":"ADA-USD","DOGEUSD":"DOGE-USD",
    "BTC/USD":"BTC-USD","ETH/USD":"ETH-USD","SOL/USD":"SOL-USD",
    "BNB/USD":"BNB-USD","XRP/USD":"XRP-USD","ADA/USD":"ADA-USD","DOGE/USD":"DOGE-USD",
}

STRATEGIES = [
    "Triple SMA Ribbon (20/50/200)","LuxAlgo ATR Channel","MACD Momentum",
    "EMA 9/21 Ribbon","Smart Money Concepts (SMC)","Supertrend","VWAP + RSI","Ichimoku Cloud",
]

STRATEGY_TF = {
    "Triple SMA Ribbon (20/50/200)":"1d","LuxAlgo ATR Channel":"4h",
    "MACD Momentum":"4h","EMA 9/21 Ribbon":"1h","Smart Money Concepts (SMC)":"4h",
    "Supertrend":"4h","VWAP + RSI":"1h","Ichimoku Cloud":"1d",
}

MARKET_THRESHOLDS = {"US":5,"India":4,"Crypto":3,"Commodity":4}

BACKTEST_PERIODS = {
    "6 Months":180,"1 Year":365,"2 Years":730,"5 Years":1825,"10 Years":3650,
}

CHART_INTERVALS = {
    "15 Minutes":"15m","1 Hour":"1h","4 Hours":"4h","1 Day":"1d",
}

for k, v in [("bt_results", []), ("bt_label", ""), ("bot_bt", []),
            ("bot_bt_label", ""), ("watchlist", []), ("bot_log", []),
            ("perf_compare", []), ("rec_results", []), ("rec_label", "")]:
    if k not in st.session_state:
        st.session_state[k] = v

def get_market(t):
    if t.endswith(".NS"): return "India"
    if t.endswith("-USD"): return "Crypto"
    if t.endswith("=F"): return "Commodity"
    return "US"

def ticker_label(t):
    if t in COMMODITY_NAMES: return COMMODITY_NAMES[t]
    return t.replace(".NS","").replace("-USD","")

def get_min_votes(t): return MARKET_THRESHOLDS.get(get_market(t),4)

def to_alpaca_order_symbol(ticker):
    return CRYPTO_ORDER_MAP.get(ticker, ticker)

def to_alpaca_close_symbol(ticker):
    return CRYPTO_CLOSE_MAP.get(ticker, ticker)

def normalize_position_symbol(sym):
    if sym in CRYPTO_POSITION_MAP:
        return CRYPTO_POSITION_MAP[sym]
    return sym

def fmt(v, suffix=""):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    if suffix == "" and isinstance(v, float): return f"{v:,.2f}"
    if isinstance(v, float): return f"{v:.2f}{suffix}"
    return f"{v}{suffix}"

def compute_sma(s, w): return s.rolling(w).mean()
def compute_ema(s, span): return s.ewm(span=span, adjust=False).mean()

def compute_atr(df, p=14):
    hl = df["High"] - df["Low"]
    hcp = (df["High"] - df["Close"].shift(1)).abs()
    lcp = (df["Low"] - df["Close"].shift(1)).abs()
    return pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(p).mean()

def compute_rsi(s, p=14):
    d = s.diff(); g = d.clip(lower=0).rolling(p).mean(); l = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - (100 / (1 + g / l.replace(0, np.nan)))

def compute_bb(s, w=20, n=2):
    mid = s.rolling(w).mean(); std = s.rolling(w).std()
    return mid + n * std, mid, mid - n * std

def clean_df(raw):
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = ["_".join([str(c) for c in col]).strip() for col in raw.columns]
        rmap = {}
        for col in raw.columns:
            for std in ["Close", "Open", "High", "Low", "Volume"]:
                if col.startswith(std): rmap[col] = std
        raw.rename(columns=rmap, inplace=True)
    raw.columns = [str(c).strip() for c in raw.columns]
    raw.index = pd.to_datetime(raw.index)
    if "Close" in raw.columns: raw = raw.dropna(subset=["Close"])
    return raw

def fetch_data(ticker, interval="1d", days=400):
    try:
        end_dt = datetime.now()
        max_days = min(days, 59) if interval in ["1h", "15m"] else min(days, 720) if interval == "4h" else days
        start_dt = end_dt - timedelta(days=max_days)
        raw = yf.download(ticker, start=start_dt, end=end_dt, interval=interval,
                          progress=False, auto_adjust=True, group_by="column")
        if raw is None or raw.empty: return None
        raw = clean_df(raw)
        if "Close" not in raw.columns or len(raw) < 20: return None
        return raw
    except Exception: return None

def fetch_data_with_fallback(ticker, interval="1d", days=400):
    effective_days = min(days, 59) if interval in ["15m"] else min(days, 720) if interval in ["1h", "4h"] else days
    raw = fetch_data(ticker, interval=interval, days=effective_days)
    if raw is not None and len(raw) >= 20:
        return raw, interval
    raw = fetch_data(ticker, interval="1d", days=days)
    return raw, "1d"

def generate_signals(df, strategy):
    df = df.copy()
    if len(df) < 20: return df

    if "Volume" not in df.columns:
        df["Volume"] = 1
    df["Volume"] = df["Volume"].fillna(1).replace(0, 1)

    strat = str(strategy).strip()

    if "Triple SMA" in strat:
        df["SMA20"] = compute_sma(df["Close"], min(20, len(df)))
        df["SMA50"] = compute_sma(df["Close"], min(50, len(df)))
        df["SMA200"] = compute_sma(df["Close"], min(200, len(df)))
        buy = (df["SMA20"] > df["SMA50"]) & (df["SMA50"] > df["SMA200"])
        sell = (df["Close"] < df["SMA50"]) | (df["Close"] < df["SMA200"])
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    elif "EMA 9/21" in strat:
        df["EMA9"] = compute_ema(df["Close"], 9)
        df["EMA21"] = compute_ema(df["Close"], 21)
        buy = df["EMA9"] > df["EMA21"]
        df["Signal"] = np.where(buy, 1, -1)

    elif "LuxAlgo ATR" in strat:
        df["ATR"] = compute_atr(df, 14)
        mid = (df["High"] + df["Low"]) / 2
        tf_v = (mid - 3.0 * df["ATR"]).values; tc_v = (mid + 3.0 * df["ATR"]).values
        closes = df["Close"].values
        floor, ceil_v, signals = [0.0] * len(df), [0.0] * len(df), [0] * len(df)
        for i in range(1, len(df)):
            floor[i] = max(tf_v[i], floor[i-1]) if closes[i-1] > floor[i-1] else tf_v[i]
            ceil_v[i] = min(tc_v[i], ceil_v[i-1]) if closes[i-1] < ceil_v[i-1] else tc_v[i]
            if closes[i] > ceil_v[i]: signals[i] = 1
            elif closes[i] < floor[i]: signals[i] = -1
            else: signals[i] = signals[i-1]
        df["Signal"] = signals
        df["Band"] = np.where(df["Signal"] == 1, pd.Series(floor, index=df.index), pd.Series(ceil_v, index=df.index))

    elif "MACD Momentum" in strat:
        df["EMA12"] = compute_ema(df["Close"], 12); df["EMA26"] = compute_ema(df["Close"], 26)
        df["MACD"] = df["EMA12"] - df["EMA26"]; df["MACDSig"] = compute_ema(df["MACD"], 9)
        df["Signal"] = np.where(df["MACD"] > df["MACDSig"], 1, -1)

    elif "Smart Money" in strat or "SMC" in strat:
        sma50 = compute_sma(df["Close"], min(50, len(df))); sma200 = compute_sma(df["Close"], min(200, len(df)))
        body = (df["Close"] - df["Open"]).abs(); avg_body = body.rolling(min(14, len(df))).mean()
        su = (df["Close"] > df["Open"]) & (body > avg_body * 1.5); sd = (df["Close"] < df["Open"]) & (body > avg_body * 1.5)
        obt = df["High"].shift(1).where(su, np.nan).ffill(); obb = df["Low"].shift(1).where(su, np.nan).ffill()
        obt2 = df["High"].shift(1).where(sd, np.nan).ffill(); obb2 = df["Low"].shift(1).where(sd, np.nan).ffill()
        ibo = (df["Close"] >= obb) & (df["Close"] <= obt); ibo2 = (df["Close"] >= obb2) & (df["Close"] <= obt2)
        n = min(20, max(2, len(df) // 2))
        bfvg = df["Low"] > df["High"].shift(2); bfvg2 = df["High"] < df["Low"].shift(2)
        shi = df["High"].rolling(n).max(); slo = df["Low"].rolling(n).min()
        bb2 = df["Close"] > shi.shift(1); bb3 = df["Close"] < slo.shift(1)
        cb = (df["Close"] > sma50) & (df["Close"].shift(1) <= sma50.shift(1))
        cb2 = (df["Close"] < sma50) & (df["Close"].shift(1) >= sma50.shift(1))
        phi = df["High"].rolling(n).max().shift(1); plo = df["Low"].rolling(n).min().shift(1)
        bsw = (df["Low"] < plo) & (df["Close"] > plo) & (df["Close"] > df["Open"])
        bsw2 = (df["High"] > phi) & (df["Close"] < phi) & (df["Close"] < df["Open"])
        nd = df["Close"] <= (plo * 1.05); ns = df["Close"] >= (phi * 0.95)
        bsc = ibo.astype(int) + bfvg.astype(int) + bsw.astype(int) * 3 + cb.astype(int) * 2 + bb2.astype(int) * 2 + nd.astype(int)
        bsc2 = ibo2.astype(int) + bfvg2.astype(int) + bsw2.astype(int) * 3 + cb2.astype(int) * 2 + bb3.astype(int) * 2 + ns.astype(int)
        mb = df["Close"] < sma200
        buy = (bsc >= 3) & (bsc > bsc2); sell = (bsc2 >= 3) & (bsc2 > bsc) & mb
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    elif "Supertrend" in strat:
        atr_v = compute_atr(df, 10); mult = 3.0
        hl2 = (df["High"] + df["Low"]) / 2
        upper = (hl2 + mult * atr_v).copy(); lower = (hl2 - mult * atr_v).copy()
        sig_arr = np.zeros(len(df))
        for i in range(1, len(df)):
            lower.iloc[i] = lower.iloc[i] if lower.iloc[i] > lower.iloc[i-1] or df["Close"].iloc[i-1] < lower.iloc[i-1] else lower.iloc[i-1]
            upper.iloc[i] = upper.iloc[i] if upper.iloc[i] < upper.iloc[i-1] or df["Close"].iloc[i-1] > upper.iloc[i-1] else upper.iloc[i-1]
            if df["Close"].iloc[i] > upper.iloc[i-1]: sig_arr[i] = 1
            elif df["Close"].iloc[i] < lower.iloc[i-1]: sig_arr[i] = -1
            else: sig_arr[i] = sig_arr[i-1]
        df["Signal"] = sig_arr; df["ST_Upper"] = upper; df["ST_Lower"] = lower

    elif "VWAP" in strat:
        typ = (df["High"] + df["Low"] + df["Close"]) / 3
        vol = df["Volume"]
        df["VWAP"] = (typ * vol).rolling(20).sum() / vol.rolling(20).sum()
        df["RSI"] = compute_rsi(df["Close"], 14)
        df["BBUp"], df["BBMid"], df["BBLow"] = compute_bb(df["Close"], 20, 2)
        buy = ((df["Close"] > df["VWAP"]) & (df["RSI"] > 50) & (df["RSI"] < 70)) | ((df["Close"] < df["BBLow"]) & (df["RSI"] < 35))
        sell = ((df["Close"] < df["VWAP"]) & (df["RSI"] < 50) & (df["RSI"] > 30)) | ((df["Close"] > df["BBUp"]) & (df["RSI"] > 65))
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    elif "Ichimoku" in strat:
        n1, n2, n3 = min(9, max(2, len(df) // 3)), min(26, max(3, len(df) // 2)), min(52, max(4, len(df) - 1))
        df["Tenkan"] = (df["High"].rolling(n1).max() + df["Low"].rolling(n1).min()) / 2
        df["Kijun"] = (df["High"].rolling(n2).max() + df["Low"].rolling(n2).min()) / 2
        df["SpanA"] = ((df["Tenkan"] + df["Kijun"]) / 2).shift(n2)
        df["SpanB"] = ((df["High"].rolling(n3).max() + df["Low"].rolling(n3).min()) / 2).shift(n2)
        ac = (df["Close"] > df["SpanA"]) & (df["Close"] > df["SpanB"])
        bc = (df["Close"] < df["SpanA"]) & (df["Close"] < df["SpanB"])
        tku = (df["Tenkan"] > df["Kijun"]) & (df["Tenkan"].shift(1) <= df["Kijun"].shift(1))
        tkd = (df["Tenkan"] < df["Kijun"]) & (df["Tenkan"].shift(1) >= df["Kijun"].shift(1))
        df["Signal"] = np.where(ac & tku, 1, np.where(bc & tkd, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    else:
        df["EMA9"] = compute_ema(df["Close"], 9)
        df["EMA21"] = compute_ema(df["Close"], 21)
        df["Signal"] = np.where(df["EMA9"] > df["EMA21"], 1, -1)

    if "Signal" not in df.columns: df["Signal"] = 0
    return df

def run_backtest(df, capital):
    log, in_pos, entry, portfolio, wins, total = [], False, 0.0, float(capital), 0, 0
    entry_date = ""
    signals = df["Signal"].values; closes = df["Close"].values; dates = df.index
    for i in range(len(df)):
        sig = signals[i]; price = closes[i]
        if price is None or (isinstance(price, float) and np.isnan(price)): continue
        price = float(price); date = str(dates[i])[:16]
        if sig == 1 and not in_pos:
            in_pos, entry, entry_date, total = True, price, date, total + 1
        elif sig == -1 and in_pos:
            in_pos = False; ret = (price - entry) / entry; portfolio *= (1 + ret)
            if price > entry: wins += 1
            log.append({"Status": "CLOSED", "Entry Date": entry_date, "Entry Price": round(entry, 4),
                        "Exit Date": date, "Exit Price": round(price, 4), "Return %": round(ret * 100, 2), "Portfolio": round(portfolio, 2)})
    if in_pos:
        last_v = next((closes[i] for i in range(len(closes) - 1, -1, -1)
                      if closes[i] is not None and not(isinstance(closes[i], float) and np.isnan(closes[i]))), entry)
        price = float(last_v); ret = (price - entry) / entry; portfolio *= (1 + ret)
        if price > entry: wins += 1
        log.append({"Status": "OPEN", "Entry Date": entry_date, "Entry Price": round(entry, 4),
                    "Exit Date": "Present", "Exit Price": round(price, 4), "Return %": round(ret * 100, 2), "Portfolio": round(portfolio, 2)})
    win_rate = wins / total * 100 if total > 0 else 0.0
    last_price = float(next((closes[i] for i in range(len(closes) - 1, -1, -1)
                            if closes[i] is not None and not(isinstance(closes[i], float) and np.isnan(closes[i]))), 0))
    valid = df[df["Close"].notna()]
    first_cl = float(valid["Close"].iloc[0]) if not valid.empty else last_price
    bh_pct = round((last_price / first_cl - 1) * 100, 2) if first_cl > 0 else 0.0
    return {"net_pct": round((portfolio / capital - 1) * 100, 2), "bh_pct": bh_pct, "end_val": round(portfolio, 2),
            "win_rate": round(win_rate, 1), "trades": total, "log": log,
            "last_sig": int(signals[-1]) if len(signals) > 0 else 0, "last_price": last_price}

def process_ticker(ticker, strategy, days, capital, interval):
    try:
        raw, used_tf = fetch_data_with_fallback(ticker, interval=interval, days=days + 50)
        if raw is None or raw.empty: return None
        
        start_date = raw.index.min()
        cutoff = datetime.now() - timedelta(days=days)
        actual_cutoff = max(start_date, pd.to_datetime(cutoff))
        
        sl = raw[raw.index >= actual_cutoff].copy()
        if len(sl) < 20: return None
        
        en = generate_signals(sl, strategy)
        bt = run_backtest(en, capital)
        
        return {
            "Ticker": ticker,
            "Market": get_market(ticker),
            "Label": ticker_label(ticker),
            "Price": round(bt["last_price"], 2),
            "Signal": "BUY" if bt["last_sig"] == 1 else ("SELL" if bt["last_sig"] == -1 else "HOLD"),
            "Net %": bt["net_pct"],
            "B&H %": bt["bh_pct"],
            "Win Rate": bt["win_rate"],
            "Trades": bt["trades"],
            "End Value": bt["end_val"],
            "_log": bt["log"],
            "_df": en
        }
    except Exception:
        return None

def run_engine(tickers, strategy, days, capital, interval):
    results = []; prog = st.progress(0); status = st.empty()
    for idx, ticker in enumerate(tickers):
        prog.progress((idx + 1) / len(tickers))
        status.caption(f"Processing {ticker_label(ticker)} ({idx + 1}/{len(tickers)})...")
        row = process_ticker(ticker, strategy, days, capital, interval)
        if row: results.append(row)
    prog.empty(); status.empty()
    results.sort(key=lambda x: x["Net %"] if x["Net %"] is not None and not(isinstance(x["Net %"], float) and np.isnan(x["Net %"])) else -999, reverse=True)
    return results

def draw_chart(df_view, log, strategy_name):
    df_view = df_view.copy()
    if isinstance(df_view.index, pd.MultiIndex): df_view.index = df_view.index.get_level_values(0)
    df_view.index = pd.to_datetime(df_view.index)
    fig = go.Figure()
    try: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Close"], name="Price", line=dict(color="white", width=1.5)))
    except: pass
    s = strategy_name
    try:
        if "Triple SMA" in s:
            for col, color, nm in [("SMA20", "#00FFFF", "SMA 20"), ("SMA50", "#FFD700", "SMA 50"), ("SMA200", "#FF00FF", "SMA 200")]:
                if col in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view[col], name=nm, line=dict(color=color, width=1)))
        elif "LuxAlgo ATR" in s:
            if "Band" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Band"], name="ATR Band", line=dict(color="lime", width=1.5, dash="dot")))
        elif "MACD" in s:
            if "MACD" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACD"], name="MACD", line=dict(color="#00FFFF", width=1)))
            if "MACDSig" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACDSig"], name="Signal", line=dict(color="#FF00FF", width=1, dash="dot")))
        elif "EMA 9/21" in s:
            if "EMA9" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA9"], name="EMA 9", line=dict(color="#00FF88", width=1)))
            if "EMA21" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA21"], name="EMA 21", line=dict(color="#FF8800", width=1)))
        elif "Supertrend" in s:
            if "ST_Upper" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["ST_Upper"], name="ST Resist", line=dict(color="#FF4444", width=1.5, dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["ST_Lower"], name="ST Support", line=dict(color="#44FF44", width=1.5, dash="dot")))
        elif "VWAP" in s:
            if "VWAP" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["VWAP"], name="VWAP", line=dict(color="#FFD700", width=1.5)))
            if "BBUp" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBUp"], name="BB Upper", line=dict(color="#FF8800", width=1, dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBLow"], name="BB Lower", line=dict(color="#FF8800", width=1, dash="dot")))
        elif "Ichimoku" in s:
            if "SpanA" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["SpanA"], name="Span A", line=dict(color="#00FF88", width=1)))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["SpanB"], name="Span B", line=dict(color="#FF4444", width=1)))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Tenkan"], name="Tenkan", line=dict(color="#00FFFF", width=1, dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Kijun"], name="Kijun", line=dict(color="#FF00FF", width=1, dash="dot")))
        elif "Smart Money" in s or "SMC" in s:
            dv = df_view.reset_index(); dc = dv.columns[0]; n = len(dv)
            if "Close" in dv.columns:
                fig.add_trace(go.Scatter(x=dv[dc], y=dv["Close"].rolling(min(50, n)).mean(), name="SMA 50", line=dict(color="#FF8800", width=1, dash="dot")))
                fig.add_trace(go.Scatter(x=dv[dc], y=dv["Close"].rolling(min(200, n)).mean(), name="SMA 200", line=dict(color="#FF00FF", width=1.5, dash="dot")))
    except: pass
    try:
        bd = [t["Entry Date"] for t in log]; bp = [t["Entry Price"] for t in log]
        sd = [t["Exit Date"] for t in log if t["Status"] == "CLOSED"]; sp = [t["Exit Price"] for t in log if t["Status"] == "CLOSED"]
        if bd: fig.add_trace(go.Scatter(x=bd, y=bp, mode="markers", name="BUY", marker=dict(symbol="triangle-up", color="lime", size=10)))
        if sd: fig.add_trace(go.Scatter(x=sd, y=sp, mode="markers", name="SELL", marker=dict(symbol="triangle-down", color="red", size=10)))
    except: pass
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=20, r=20, t=30, b=20),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# --- Sidebar Controls ---
st.sidebar.title("⚙️ Controls")
selected_strat = st.sidebar.selectbox("Strategy", STRATEGIES)
rec_tf = STRATEGY_TF.get(selected_strat, "1d")
st.sidebar.caption(f"Recommended timeframe: `{rec_tf}`")

chart_tf_label = st.sidebar.selectbox("Chart Timeframe", list(CHART_INTERVALS.keys()), index=1)
chart_tf = CHART_INTERVALS[chart_tf_label]

backtest_period_label = st.sidebar.selectbox("Backtest Period", list(BACKTEST_PERIODS.keys()), index=1)
backtest_days = BACKTEST_PERIODS[backtest_period_label]

capital_per_asset = st.sidebar.number_input("Capital per Asset", value=100000, step=10000)

st.sidebar.markdown("---")
st.sidebar.subheader("Quick Presets")
run_us = st.sidebar.button("📊 Run US Stocks (100)")
run_nifty50 = st.sidebar.button("🇮🇳 Run Nifty 50")
run_nifty200 = st.sidebar.button("🇮🇳 Run Nifty 200")

tickers_to_run = None
if run_us: tickers_to_run = DEFAULT_US
elif run_nifty50: tickers_to_run = DEFAULT_IN_50
elif run_nifty200: tickers_to_run = DEFAULT_IN

if tickers_to_run:
    st.session_state["bt_results"] = run_engine(tickers_to_run, selected_strat, backtest_days, capital_per_asset, chart_tf)
    st.session_state["bt_label"] = f"{selected_strat} ({backtest_period_label})"

# --- MAIN APP TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Backtester Engine", 
    "🤖 Recommendation Engine", 
    "⚡ Alpaca Trading Bot", 
    "📊 Performance & Watchlist"
])

# ==================== TAB 1: BACKTESTER ====================
with tab1:
    st.title("Global Backtest Analysis Engine")
    
    if st.session_state["bt_results"]:
        res_df = pd.DataFrame(st.session_state["bt_results"])
        st.subheader(f"Results: {st.session_state['bt_label']}")
        
        cols = ["Ticker", "Label", "Market", "Price", "Signal", "Net %", "B&H %", "Win Rate", "Trades", "End Value"]
        st.dataframe(res_df[cols], use_container_width=True)
        
        selected_ticker = st.selectbox("Select Asset to View Chart & Details", res_df["Ticker"].tolist())
        match_row = next((r for r in st.session_state["bt_results"] if r["Ticker"] == selected_ticker), None)
        
        if match_row:
            st.plotly_chart(draw_chart(match_row["_df"], match_row["_log"], selected_strat), use_container_width=True)
            st.subheader("Trade Log")
            st.dataframe(pd.DataFrame(match_row["_log"]), use_container_width=True)
    else:
        st.info("Select a preset from the sidebar to launch a backtest across assets.")

# ==================== TAB 2: RECOMMENDATION ENGINE ====================
with tab2:
    st.title("🤖 Multi-Strategy Recommendation Engine")
    st.caption("Evaluates consensus signals across all 8 strategies to issue STRONG BUY / BUY / HOLD / SELL calls.")
    
    col_rec1, col_rec2 = st.columns([2, 1])
    with col_rec1:
        rec_market = st.selectbox("Select Market", ["US Stocks", "Nifty 50", "Crypto", "Commodities"])
    with col_rec2:
        run_rec = st.button("🚀 Generate Recommendations")
        
    if run_rec:
        rec_list = DEFAULT_US if rec_market == "US Stocks" else DEFAULT_IN_50 if rec_market == "Nifty 50" else DEFAULT_CR if rec_market == "Crypto" else DEFAULT_CM
        rec_results = []
        prog = st.progress(0); status = st.empty()
        
        for idx, ticker in enumerate(rec_list):
            prog.progress((idx + 1) / len(rec_list))
            status.caption(f"Analyzing {ticker_label(ticker)} across all 8 strategies...")
            
            raw, _ = fetch_data_with_fallback(ticker, interval="1d", days=300)
            if raw is None or raw.empty: continue
            
            buy_votes, sell_votes = 0, 0
            for strat in STRATEGIES:
                df_sig = generate_signals(raw, strat)
                if not df_sig.empty and "Signal" in df_sig.columns:
                    last_sig = df_sig["Signal"].iloc[-1]
                    if last_sig == 1: buy_votes += 1
                    elif last_sig == -1: sell_votes += 1
                    
            min_v = get_min_votes(ticker)
            if buy_votes >= min_v + 1: rec_call = "STRONG BUY"
            elif buy_votes >= min_v: rec_call = "BUY"
            elif sell_votes >= min_v: rec_call = "SELL"
            else: rec_call = "HOLD"
            
            rec_results.append({
                "Ticker": ticker,
                "Label": ticker_label(ticker),
                "Market": get_market(ticker),
                "Price": round(float(raw["Close"].iloc[-1]), 2),
                "Recommendation": rec_call,
                "Buy Votes": buy_votes,
                "Sell Votes": sell_votes,
                "Required Threshold": min_v
            })
            
        prog.empty(); status.empty()
        st.session_state["rec_results"] = rec_results
        st.session_state["rec_label"] = rec_market

    if st.session_state["rec_results"]:
        st.subheader(f"Recommendations for {st.session_state['rec_label']}")
        rec_df = pd.DataFrame(st.session_state["rec_results"])
        st.dataframe(rec_df, use_container_width=True)

# ==================== TAB 3: ALPACA BOT ====================
with tab3:
    st.title("⚡ Alpaca Live / Paper Trading Bot")
    
    if not ALPACA_AVAILABLE:
        st.error("`alpaca-py` library is not installed in your Python environment. Install it via `pip install alpaca-py` to use automated execution.")
    else:
        st.markdown("Enter your Alpaca API credentials below to view live portfolio status and run automated execution.")
        c1, c2, c3 = st.columns(3)
        api_key = c1.text_input("Alpaca API Key", type="password")
        secret_key = c2.text_input("Alpaca Secret Key", type="password")
        paper_mode = c3.checkbox("Paper Trading", value=True)
        
        if api_key and secret_key:
            try:
                client = TradingClient(api_key, secret_key, paper=paper_mode)
                account = client.get_account()
                
                st.success("Connected to Alpaca (" + ("Paper" if paper_mode else "Live") + ") - Cash: $" + f"{float(account.cash):,.2f}" + " - Equity: $" + f"{float(account.portfolio_value):,.2f}")positions = client.get_all_positions()
                if positions:
                    pos_data = []
                    for p in positions:
                        pos_data.append({
                            "Symbol": p.symbol,
                            "Qty": p.qty,
                            "Entry Price": round(float(p.avg_entry_price), 2),
                            "Current Price": round(float(p.current_price), 2),
                            "Unrealized PnL": round(float(p.unrealized_pl), 2),
                            "Market Value": round(float(p.market_value), 2)
                        })
                    st.subheader("Current Open Positions")
                    st.dataframe(pd.DataFrame(pos_data), use_container_width=True)
                else:
                    st.info("No open positions on Alpaca.")
            except Exception as e:
                st.error(f"Alpaca Connection Failed: {str(e)}")

# ==================== TAB 4: WATCHLIST & PERFORMANCE ====================
with tab4:
    st.title("📊 Watchlist & Strategy Comparison")
    
    col_w1, col_w2 = st.columns([3, 1])
    with col_w1:
        new_ticker = st.text_input("Add Ticker to Watchlist (e.g. TSLA, BTC-USD, RELIANCE.NS):").upper()
    with col_w2:
        if st.button("Add Ticker") and new_ticker:
            if new_ticker not in st.session_state["watchlist"]:
                st.session_state["watchlist"].append(new_ticker)
                st.success(f"Added {new_ticker}")

    if st.session_state["watchlist"]:
        st.subheader("Your Custom Watchlist")
        wl_data = []
        for t in st.session_state["watchlist"]:
            raw, _ = fetch_data_with_fallback(t, interval="1d", days=30)
            if raw is not None and not raw.empty:
                last_p = round(float(raw["Close"].iloc[-1]), 2)
                chg = round(((last_p / float(raw["Close"].iloc[-2])) - 1) * 100, 2) if len(raw) > 1 else 0.0
                wl_data.append({"Ticker": t, "Label": ticker_label(t), "Market": get_market(t), "Price": last_p, "24h Change %": chg})
        
        if wl_data:
            st.dataframe(pd.DataFrame(wl_data), use_container_width=True)
            if st.button("Clear Watchlist"):
                st.session_state["watchlist"] = []
                st.rerun()
    else:
        st.info("Watchlist is currently empty.")
