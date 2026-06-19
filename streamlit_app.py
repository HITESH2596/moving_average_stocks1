import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="TradeSignal Pro")

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

DEFAULT_US = ["AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","AMD","NFLX","V","JPM","MS"]
DEFAULT_IN = ["RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","WIPRO.NS","BAJFINANCE.NS","SBIN.NS","LT.NS","TATAMOTORS.NS"]
DEFAULT_CR = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD"]
DEFAULT_CM = ["GC=F","SI=F","CL=F","NG=F","HG=F","PL=F"]

COMMODITY_NAMES = {"GC=F":"Gold","SI=F":"Silver","CL=F":"Crude Oil","NG=F":"Natural Gas","HG=F":"Copper","PL=F":"Platinum"}

if "results"   not in st.session_state: st.session_state.results   = {}
if "run_label" not in st.session_state: st.session_state.run_label = ""
if "watchlist" not in st.session_state: st.session_state.watchlist = []
if "bot_log"   not in st.session_state: st.session_state.bot_log   = []
if "bot_bt"    not in st.session_state: st.session_state.bot_bt    = {}

STRATEGIES = [
    "Triple SMA Ribbon (20/50/200)",
    "LuxAlgo ATR Channel",
    "MACD Momentum",
    "EMA 9/21 Ribbon",
    "Smart Money Concepts (SMC)",
    "Supertrend",
    "VWAP + RSI",
    "Ichimoku Cloud",
]

STRATEGY_TF = {
    "Triple SMA Ribbon (20/50/200)": "1d",
    "LuxAlgo ATR Channel":           "4h",
    "MACD Momentum":                 "4h",
    "EMA 9/21 Ribbon":               "4h",
    "Smart Money Concepts (SMC)":    "4h",
    "Supertrend":                    "4h",
    "VWAP + RSI":                    "1h",
    "Ichimoku Cloud":                "1d",
}

MARKET_THRESHOLDS = {"US":5,"India":4,"Crypto":3,"Commodity":4}

TIMEFRAMES = {"1 Hour":"1h","4 Hours":"4h","1 Day":"1d"}

tab_bt, tab_bot = st.tabs(["📊 Backtester", "🤖 Paper Trading Bot"])

# ═══════════════════════════════════════════════════════════════
# SHARED FUNCTIONS
# ═══════════════════════════════════════════════════════════════
def get_market(ticker):
    if ticker.endswith(".NS"):  return "India"
    if ticker.endswith("-USD"): return "Crypto"
    if ticker.endswith("=F"):   return "Commodity"
    return "US"

def ticker_label(ticker):
    if ticker in COMMODITY_NAMES: return COMMODITY_NAMES[ticker]
    return ticker.replace(".NS","").replace("-USD","")

def get_min_votes(ticker):
    return MARKET_THRESHOLDS.get(get_market(ticker), 4)

def compute_sma(s, w):    return s.rolling(w).mean()
def compute_ema(s, span): return s.ewm(span=span, adjust=False).mean()

def compute_atr(df, p=14):
    hl  = df["High"] - df["Low"]
    hcp = (df["High"] - df["Close"].shift(1)).abs()
    lcp = (df["Low"]  - df["Close"].shift(1)).abs()
    return pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(p).mean()

def compute_rsi(s, p=14):
    d = s.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - (100 / (1 + g / l.replace(0, np.nan)))

def compute_bb(s, w=20, n=2):
    mid = s.rolling(w).mean()
    std = s.rolling(w).std()
    return mid + n*std, mid, mid - n*std

def clean_df(raw):
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = ['_'.join([str(c) for c in col]).strip() for col in raw.columns]
        rename_map = {}
        for col in raw.columns:
            for std in ["Close","Open","High","Low","Volume"]:
                if col.startswith(std):
                    rename_map[col] = std
        raw.rename(columns=rename_map, inplace=True)
    raw.columns = [str(c).strip() for c in raw.columns]
    raw.index   = pd.to_datetime(raw.index)
    if "Close" in raw.columns:
        raw = raw.dropna(subset=["Close"])
    return raw

def fetch_data(ticker, interval="1d", days=400):
    try:
        end_dt   = datetime.now()
        # For 4h/1h need more periods not days
        if interval == "4h":
            start_dt = end_dt - timedelta(days=min(days, 729))
        elif interval == "1h":
            start_dt = end_dt - timedelta(days=min(days, 729))
        else:
            start_dt = end_dt - timedelta(days=days)
        raw = yf.download(ticker, start=start_dt, end=end_dt,
                          interval=interval, progress=False,
                          auto_adjust=True, group_by="column")
        if raw is None or raw.empty: return None
        raw = clean_df(raw)
        if "Close" not in raw.columns or len(raw) < 60: return None
        return raw
    except Exception:
        return None

def generate_signals(df, strategy):
    df = df.copy()

    if strategy == "Triple SMA Ribbon (20/50/200)":
        df["SMA20"]  = compute_sma(df["Close"], 20)
        df["SMA50"]  = compute_sma(df["Close"], 50)
        df["SMA200"] = compute_sma(df["Close"], 200)
        buy  = (df["SMA20"] > df["SMA50"]) & (df["SMA50"] > df["SMA200"])
        sell = (df["Close"] < df["SMA50"]) | (df["Close"] < df["SMA200"])
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    elif strategy == "LuxAlgo ATR Channel":
        df["ATR"] = compute_atr(df, 14)
        mid    = (df["High"] + df["Low"]) / 2
        tf     = (mid - 3.0 * df["ATR"]).values
        tc     = (mid + 3.0 * df["ATR"]).values
        closes = df["Close"].values
        floor, ceil_v, signals = [0.0]*len(df), [0.0]*len(df), [0]*len(df)
        for i in range(1, len(df)):
            floor[i]  = max(tf[i], floor[i-1])  if closes[i-1] > floor[i-1]  else tf[i]
            ceil_v[i] = min(tc[i], ceil_v[i-1]) if closes[i-1] < ceil_v[i-1] else tc[i]
            if   closes[i] > ceil_v[i]: signals[i] =  1
            elif closes[i] < floor[i]:  signals[i] = -1
            else:                        signals[i] =  signals[i-1]
        df["Signal"] = signals
        df["Band"]   = np.where(df["Signal"]==1, pd.Series(floor, index=df.index), pd.Series(ceil_v, index=df.index))

    elif strategy == "MACD Momentum":
        df["EMA12"]   = compute_ema(df["Close"], 12)
        df["EMA26"]   = compute_ema(df["Close"], 26)
        df["MACD"]    = df["EMA12"] - df["EMA26"]
        df["MACDSig"] = compute_ema(df["MACD"], 9)
        df["Signal"]  = np.where(df["MACD"] > df["MACDSig"], 1, -1)

    elif strategy == "EMA 9/21 Ribbon":
        df["EMA9"]   = compute_ema(df["Close"], 9)
        df["EMA21"]  = compute_ema(df["Close"], 21)
        df["Signal"] = np.where(df["EMA9"] > df["EMA21"], 1, -1)

    elif strategy == "Smart Money Concepts (SMC)":
        sma50  = compute_sma(df["Close"], 50)
        sma200 = compute_sma(df["Close"], 200)
        body      = (df["Close"] - df["Open"]).abs()
        avg_body  = body.rolling(14).mean()
        strong_up = (df["Close"] > df["Open"]) & (body > avg_body * 1.5)
        strong_dn = (df["Close"] < df["Open"]) & (body > avg_body * 1.5)
        ob_bull_top = df["High"].shift(1).where(strong_up, np.nan).ffill()
        ob_bull_bot = df["Low"].shift(1).where(strong_up, np.nan).ffill()
        ob_bear_top = df["High"].shift(1).where(strong_dn, np.nan).ffill()
        ob_bear_bot = df["Low"].shift(1).where(strong_dn, np.nan).ffill()
        in_bull_ob  = (df["Close"] >= ob_bull_bot) & (df["Close"] <= ob_bull_top)
        in_bear_ob  = (df["Close"] >= ob_bear_bot) & (df["Close"] <= ob_bear_top)
        bull_fvg    = df["Low"] > df["High"].shift(2)
        bear_fvg    = df["High"] < df["Low"].shift(2)
        swing_hi    = df["High"].rolling(20).max()
        swing_lo    = df["Low"].rolling(20).min()
        bos_bull    = df["Close"] > swing_hi.shift(1)
        bos_bear    = df["Close"] < swing_lo.shift(1)
        choch_bull  = (df["Close"] > sma50) & (df["Close"].shift(1) <= sma50.shift(1))
        choch_bear  = (df["Close"] < sma50) & (df["Close"].shift(1) >= sma50.shift(1))
        prev_hi     = df["High"].rolling(20).max().shift(1)
        prev_lo     = df["Low"].rolling(20).min().shift(1)
        bull_sweep  = (df["Low"] < prev_lo) & (df["Close"] > prev_lo) & (df["Close"] > df["Open"])
        bear_sweep  = (df["High"] > prev_hi) & (df["Close"] < prev_hi) & (df["Close"] < df["Open"])
        near_demand = df["Close"] <= (prev_lo * 1.05)
        near_supply = df["Close"] >= (prev_hi * 0.95)
        bull_score  = (in_bull_ob.astype(int) + bull_fvg.astype(int) +
                       bull_sweep.astype(int)*3 + choch_bull.astype(int)*2 +
                       bos_bull.astype(int)*2 + near_demand.astype(int))
        bear_score  = (in_bear_ob.astype(int) + bear_fvg.astype(int) +
                       bear_sweep.astype(int)*3 + choch_bear.astype(int)*2 +
                       bos_bear.astype(int)*2 + near_supply.astype(int))
        macro_bear  = df["Close"] < sma200
        buy  = (bull_score >= 3) & (bull_score > bear_score)
        sell = (bear_score >= 3) & (bear_score > bull_score) & macro_bear
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    elif strategy == "Supertrend":
        atr_v  = compute_atr(df, 10)
        mult   = 3.0
        hl2    = (df["High"] + df["Low"]) / 2
        upper  = hl2 + mult * atr_v
        lower  = hl2 - mult * atr_v
        st_arr = np.zeros(len(df))
        sig_arr= np.zeros(len(df))
        for i in range(1, len(df)):
            prev_upper = upper.iloc[i-1]
            prev_lower = lower.iloc[i-1]
            lower.iloc[i] = lower.iloc[i] if lower.iloc[i] > prev_lower or df["Close"].iloc[i-1] < prev_lower else prev_lower
            upper.iloc[i] = upper.iloc[i] if upper.iloc[i] < prev_upper or df["Close"].iloc[i-1] > prev_upper else prev_upper
            if df["Close"].iloc[i] > upper.iloc[i-1]:
                sig_arr[i] = 1
            elif df["Close"].iloc[i] < lower.iloc[i-1]:
                sig_arr[i] = -1
            else:
                sig_arr[i] = sig_arr[i-1]
        df["Signal"]     = sig_arr
        df["ST_Upper"]   = upper
        df["ST_Lower"]   = lower

    elif strategy == "VWAP + RSI":
        # VWAP approximation using daily reset not possible on daily — use rolling VWAP
        typical   = (df["High"] + df["Low"] + df["Close"]) / 3
        vol       = df["Volume"] if "Volume" in df.columns else pd.Series(1, index=df.index)
        cum_tp_v  = (typical * vol).rolling(20).sum()
        cum_v     = vol.rolling(20).sum()
        df["VWAP"]= cum_tp_v / cum_v
        df["RSI"] = compute_rsi(df["Close"], 14)
        df["BBUp"], df["BBMid"], df["BBLow"] = compute_bb(df["Close"], 20, 2)
        # BUY: price above VWAP + RSI 40-60 (momentum) OR price below VWAP lower band + RSI<35 (reversal)
        buy  = ((df["Close"] > df["VWAP"]) & (df["RSI"] > 50) & (df["RSI"] < 70)) | \
               ((df["Close"] < df["BBLow"]) & (df["RSI"] < 35))
        sell = ((df["Close"] < df["VWAP"]) & (df["RSI"] < 50) & (df["RSI"] > 30)) | \
               ((df["Close"] > df["BBUp"]) & (df["RSI"] > 65))
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    elif strategy == "Ichimoku Cloud":
        # Ichimoku components
        h9   = df["High"].rolling(9).max();   l9  = df["Low"].rolling(9).min()
        h26  = df["High"].rolling(26).max();  l26 = df["Low"].rolling(26).min()
        h52  = df["High"].rolling(52).max();  l52 = df["Low"].rolling(52).min()
        df["Tenkan"]   = (h9  + l9)  / 2   # Conversion line (9)
        df["Kijun"]    = (h26 + l26) / 2   # Base line (26)
        df["SpanA"]    = ((df["Tenkan"] + df["Kijun"]) / 2).shift(26)   # Leading A
        df["SpanB"]    = ((h52 + l52) / 2).shift(26)                     # Leading B
        df["Chikou"]   = df["Close"].shift(-26)                           # Lagging span
        above_cloud = (df["Close"] > df["SpanA"]) & (df["Close"] > df["SpanB"])
        below_cloud = (df["Close"] < df["SpanA"]) & (df["Close"] < df["SpanB"])
        tk_cross_up = (df["Tenkan"] > df["Kijun"]) & (df["Tenkan"].shift(1) <= df["Kijun"].shift(1))
        tk_cross_dn = (df["Tenkan"] < df["Kijun"]) & (df["Tenkan"].shift(1) >= df["Kijun"].shift(1))
        buy  = above_cloud & tk_cross_up
        sell = below_cloud & tk_cross_dn
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    return df

def run_backtest(df, capital):
    log, in_pos, entry, portfolio, wins, total = [], False, 0.0, float(capital), 0, 0
    entry_date = ""
    signals = df["Signal"].values
    closes  = df["Close"].values
    dates   = df.index
    for i in range(len(df)):
        sig   = signals[i]
        price = closes[i]
        if price is None or (isinstance(price, float) and np.isnan(price)): continue
        price = float(price)
        date  = dates[i].strftime("%Y-%m-%d %H:%M") if hasattr(dates[i], 'hour') else dates[i].strftime("%Y-%m-%d")
        if sig == 1 and not in_pos:
            in_pos, entry, entry_date, total = True, price, date, total + 1
        elif sig == -1 and in_pos:
            in_pos = False
            ret = (price - entry) / entry
            portfolio *= (1 + ret)
            if price > entry: wins += 1
            log.append({"Status":"CLOSED","Entry Date":entry_date,"Entry Price":round(entry,4),
                         "Exit Date":date,"Exit Price":round(price,4),
                         "Return %":round(ret*100,2),"Portfolio":round(portfolio,2)})
    if in_pos:
        last_v = next((closes[i] for i in range(len(closes)-1,-1,-1)
                       if closes[i] is not None and not (isinstance(closes[i],float) and np.isnan(closes[i]))), entry)
        price  = float(last_v)
        ret    = (price - entry) / entry
        portfolio *= (1 + ret)
        if price > entry: wins += 1
        log.append({"Status":"OPEN","Entry Date":entry_date,"Entry Price":round(entry,4),
                     "Exit Date":"Present","Exit Price":round(price,4),
                     "Return %":round(ret*100,2),"Portfolio":round(portfolio,2)})
    win_rate   = wins/total*100 if total > 0 else 0.0
    last_price = float(next((closes[i] for i in range(len(closes)-1,-1,-1)
                              if closes[i] is not None and not (isinstance(closes[i],float) and np.isnan(closes[i]))), 0))
    valid      = df[df["Close"].notna()]
    first_cl   = float(valid["Close"].iloc[0]) if not valid.empty else last_price
    bh_pct     = round((last_price/first_cl-1)*100,2) if first_cl > 0 else 0.0
    net_pct    = round((portfolio/capital-1)*100,2)
    return {"net_pct":net_pct,"bh_pct":bh_pct,"end_val":round(portfolio,2),
            "win_rate":round(win_rate,1),"trades":total,"log":log,
            "last_sig":int(signals[-1]),"last_price":last_price}

def run_bot_backtest(df, capital, min_votes=4):
    closes = df["Close"].values
    dates  = df.index
    n      = len(df)
    all_sigs = []
    for strat in STRATEGIES:
        try:
            e = generate_signals(df.copy(), strat)
            all_sigs.append(e["Signal"].values)
        except Exception:
            all_sigs.append(np.zeros(n))
    log, in_pos, entry, portfolio, wins, total = [], False, 0.0, float(capital), 0, 0
    entry_date = ""
    buy_v = sell_v = 0
    for i in range(n):
        price = closes[i]
        if price is None or (isinstance(price, float) and np.isnan(price)): continue
        price = float(price)
        date  = dates[i].strftime("%Y-%m-%d")
        buy_v  = sum(1 for s in all_sigs if i < len(s) and s[i] ==  1)
        sell_v = sum(1 for s in all_sigs if i < len(s) and s[i] == -1)
        sig    = 1 if (buy_v >= min_votes and buy_v > sell_v) else \
                -1 if (sell_v >= min_votes and sell_v > buy_v) else 0
        if sig == 1 and not in_pos:
            in_pos, entry, entry_date, total = True, price, date, total + 1
        elif sig == -1 and in_pos:
            in_pos = False
            ret = (price - entry) / entry
            portfolio *= (1 + ret)
            if price > entry: wins += 1
            log.append({"Status":"CLOSED","Entry Date":entry_date,"Entry Price":round(entry,4),
                         "Exit Date":date,"Exit Price":round(price,4),
                         "Return %":round(ret*100,2),"Portfolio":round(portfolio,2),
                         "Buy Votes":buy_v,"Sell Votes":sell_v})
    if in_pos:
        last_v = next((closes[i] for i in range(n-1,-1,-1)
                       if closes[i] is not None and not (isinstance(closes[i],float) and np.isnan(closes[i]))), entry)
        price  = float(last_v)
        ret    = (price - entry) / entry
        portfolio *= (1 + ret)
        if price > entry: wins += 1
        log.append({"Status":"OPEN","Entry Date":entry_date,"Entry Price":round(entry,4),
                     "Exit Date":"Present","Exit Price":round(price,4),
                     "Return %":round(ret*100,2),"Portfolio":round(portfolio,2),
                     "Buy Votes":buy_v,"Sell Votes":sell_v})
    win_rate   = wins/total*100 if total > 0 else 0.0
    last_price = float(next((closes[i] for i in range(n-1,-1,-1)
                              if closes[i] is not None and not (isinstance(closes[i],float) and np.isnan(closes[i]))), 0))
    valid    = df[df["Close"].notna()]
    first_cl = float(valid["Close"].iloc[0]) if not valid.empty else last_price
    bh_pct   = round((last_price/first_cl-1)*100,2) if first_cl > 0 else 0.0
    net_pct  = round((portfolio/capital-1)*100,2)
    return {"net_pct":net_pct,"bh_pct":bh_pct,"end_val":round(portfolio,2),
            "win_rate":round(win_rate,1),"trades":total,"log":log,"last_price":last_price,
            "last_buy_v":buy_v,"last_sell_v":sell_v,
            "last_sig":1 if buy_v>=min_votes and buy_v>sell_v else -1 if sell_v>=min_votes and sell_v>buy_v else 0}

def process_ticker(ticker, strategy, periods, capital, interval="1d"):
    try:
        max_days = max(periods.values()) + 250
        raw = fetch_data(ticker, interval=interval, days=max_days)
        if raw is None: return None
        mkt = get_market(ticker)
        result = {}
        end_dt = datetime.now()
        for label, days in periods.items():
            cutoff   = end_dt - timedelta(days=days)
            slice_df = raw[raw.index >= pd.to_datetime(cutoff)].copy()
            if len(slice_df) < 50: continue
            enriched = generate_signals(slice_df, strategy)
            bt       = run_backtest(enriched, capital)
            result[label] = {
                "Ticker":ticker,"Market":mkt,"Label":ticker_label(ticker),
                "Price":bt["last_price"],"Signal":"BUY" if bt["last_sig"]==1 else "SELL",
                "Net %":bt["net_pct"],"B&H %":bt["bh_pct"],"Win Rate":bt["win_rate"],
                "Trades":bt["trades"],"End Value":bt["end_val"],"_log":bt["log"],"_df":enriched,
            }
        return result if result else None
    except Exception:
        return None

def process_bot_ticker(ticker, periods, capital):
    try:
        min_votes = get_min_votes(ticker)
        max_days  = max(periods.values()) + 250
        # Bot uses 4H for most strategies
        raw = fetch_data(ticker, interval="4h", days=max_days)
        if raw is None:
            raw = fetch_data(ticker, interval="1d", days=max_days)
        if raw is None: return None
        mkt    = get_market(ticker)
        result = {}
        end_dt = datetime.now()
        for label, days in periods.items():
            cutoff   = end_dt - timedelta(days=days)
            slice_df = raw[raw.index >= pd.to_datetime(cutoff)].copy()
            if len(slice_df) < 50: continue
            bt      = run_bot_backtest(slice_df, capital, min_votes)
            sig_txt = "BUY" if bt["last_sig"]==1 else "SELL" if bt["last_sig"]==-1 else "HOLD"
            result[label] = {
                "Ticker":ticker,"Market":mkt,"Label":ticker_label(ticker),
                "Price":bt["last_price"],"Signal":sig_txt,
                "Min Votes":min_votes,"Buy Votes":bt["last_buy_v"],"Sell Votes":bt["last_sell_v"],
                "Net %":bt["net_pct"],"B&H %":bt["bh_pct"],"Win Rate":bt["win_rate"],
                "Trades":bt["trades"],"End Value":bt["end_val"],"_log":bt["log"],"_df":slice_df,
            }
        return result if result else None
    except Exception:
        return None

def run_engine(tickers, strategy, periods, capital, interval="1d"):
    results = {p: [] for p in periods}
    prog    = st.progress(0)
    status  = st.empty()
    for idx, ticker in enumerate(tickers):
        prog.progress((idx+1)/len(tickers))
        status.caption(f"Processing {ticker_label(ticker)} ({idx+1}/{len(tickers)})...")
        rows = process_ticker(ticker, strategy, periods, capital, interval)
        if rows:
            for label, row in rows.items():
                results[label].append(row)
    prog.empty(); status.empty()
    for label in results:
        results[label].sort(key=lambda x: x["Net %"] if x["Net %"] is not None and not (isinstance(x["Net %"],float) and np.isnan(x["Net %"])) else -999, reverse=True)
    return results

def draw_chart(df_view, log, strategy_name):
    df_view = df_view.copy()
    if isinstance(df_view.index, pd.MultiIndex):
        df_view.index = df_view.index.get_level_values(0)
    df_view.index = pd.to_datetime(df_view.index)
    fig = go.Figure()
    try:
        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Close"], name="Price", line=dict(color="white", width=1.5)))
    except Exception: pass
    s = strategy_name
    try:
        if s == "Triple SMA Ribbon (20/50/200)":
            for col, color, nm in [("SMA20","#00FFFF","SMA 20"),("SMA50","#FFD700","SMA 50"),("SMA200","#FF00FF","SMA 200")]:
                if col in df_view.columns:
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view[col], name=nm, line=dict(color=color, width=1)))
        elif s == "LuxAlgo ATR Channel":
            if "Band" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Band"], name="ATR Band", line=dict(color="lime", width=1.5, dash="dot")))
        elif s == "MACD Momentum":
            if "MACD"    in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACD"],    name="MACD",   line=dict(color="#00FFFF", width=1)))
            if "MACDSig" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACDSig"], name="Signal", line=dict(color="#FF00FF", width=1, dash="dot")))
        elif s == "EMA 9/21 Ribbon":
            if "EMA9"  in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA9"],  name="EMA 9",  line=dict(color="#00FF88", width=1)))
            if "EMA21" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA21"], name="EMA 21", line=dict(color="#FF8800", width=1)))
        elif s == "Supertrend":
            if "ST_Upper" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["ST_Upper"], name="ST Resistance", line=dict(color="#FF4444", width=1.5, dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["ST_Lower"], name="ST Support",    line=dict(color="#44FF44", width=1.5, dash="dot")))
        elif s == "VWAP + RSI":
            if "VWAP" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index, y=df_view["VWAP"], name="VWAP", line=dict(color="#FFD700", width=1.5)))
            if "BBUp" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBUp"],  name="BB Upper", line=dict(color="#FF8800", width=1, dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBLow"], name="BB Lower", line=dict(color="#FF8800", width=1, dash="dot")))
        elif s == "Ichimoku Cloud":
            if "SpanA" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["SpanA"],  name="Span A",  line=dict(color="#00FF88", width=1)))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["SpanB"],  name="Span B",  line=dict(color="#FF4444", width=1)))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Tenkan"], name="Tenkan",  line=dict(color="#00FFFF", width=1, dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Kijun"],  name="Kijun",   line=dict(color="#FF00FF", width=1, dash="dot")))
        elif s == "Smart Money Concepts (SMC)":
            dv = df_view.reset_index(); dc = dv.columns[0]; n = len(dv)
            if "Close" in dv.columns:
                fig.add_trace(go.Scatter(x=dv[dc], y=dv["Close"].rolling(min(50,n)).mean(),  name="SMA 50",  line=dict(color="#FF8800", width=1, dash="dot")))
                fig.add_trace(go.Scatter(x=dv[dc], y=dv["Close"].rolling(min(200,n)).mean(), name="SMA 200", line=dict(color="#FF00FF", width=1.5, dash="dot")))
            if all(c in dv.columns for c in ["Low","Open","Close"]):
                rn=min(20,max(2,n-1)); plo=dv["Low"].rolling(rn).min().shift(1)
                mask=((dv["Low"]<plo)&(dv["Close"]>dv["Open"])).fillna(False)
                if mask.any():
                    fig.add_trace(go.Scatter(x=dv[dc][mask],y=dv["Low"][mask],mode="markers",name="Liq Sweep",marker=dict(symbol="triangle-up",color="lime",size=12)))
    except Exception: pass
    try:
        bd=[t["Entry Date"] for t in log]; bp=[t["Entry Price"] for t in log]
        sd=[t["Exit Date"] for t in log if t["Status"]=="CLOSED"]; sp=[t["Exit Price"] for t in log if t["Status"]=="CLOSED"]
        if bd: fig.add_trace(go.Scatter(x=bd,y=bp,mode="markers",name="BUY",  marker=dict(symbol="triangle-up",   color="lime",size=10)))
        if sd: fig.add_trace(go.Scatter(x=sd,y=sp,mode="markers",name="SELL", marker=dict(symbol="triangle-down", color="red", size=10)))
    except Exception: pass
    fig.update_layout(template="plotly_dark",height=450,margin=dict(l=20,r=20,t=30,b=20),
                       legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
    return fig

def fmt(v, suffix=""):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    return f"{v}{suffix}"

def pct_color(v):
    try: return "color:#3fb950" if float(str(v).replace("%","")) >= 0 else "color:#f85149"
    except: return ""

def sig_color(v):
    if v=="BUY":  return "background-color:#1a3a1a;color:#3fb950;font-weight:bold"
    if v=="SELL": return "background-color:#3a1a1a;color:#f85149;font-weight:bold"
    if v=="HOLD": return "color:#e3b341"
    return ""

# ═══════════════════════════════════════════════════════════════
# TAB 1 — BACKTESTER
# ═══════════════════════════════════════════════════════════════
with tab_bt:
    st.title("Global Multi-Market Backtester Pro")

    st.sidebar.header("Backtest Settings")
    strategy_name = st.sidebar.selectbox("Strategy", STRATEGIES)

    rec_tf = STRATEGY_TF.get(strategy_name, "1d")
    st.sidebar.markdown(f"**Recommended timeframe for this strategy: `{rec_tf}`**")
    tf_label    = st.sidebar.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=list(TIMEFRAMES.values()).index(rec_tf) if rec_tf in TIMEFRAMES.values() else 2)
    interval    = TIMEFRAMES[tf_label]

    st.sidebar.markdown("**Periods**")
    use_1y  = st.sidebar.checkbox("1 Year",   value=True)
    use_5y  = st.sidebar.checkbox("5 Years",  value=False)
    use_10y = st.sidebar.checkbox("10 Years", value=False)
    selected_periods = {}
    if use_1y:  selected_periods["1Y"]  = 365
    if use_5y:  selected_periods["5Y"]  = 1825
    if use_10y: selected_periods["10Y"] = 3650

    capital = st.sidebar.number_input("Capital per Asset", min_value=1000, value=100000, step=5000)
    st.sidebar.markdown("---")
    run_us  = st.sidebar.button("Run US Stocks",     type="primary", use_container_width=True)
    run_in  = st.sidebar.button("Run Indian Stocks", type="primary", use_container_width=True)
    run_cr  = st.sidebar.button("Run Crypto",        type="primary", use_container_width=True)
    run_cm  = st.sidebar.button("Run Commodities",   type="primary", use_container_width=True)
    run_all = st.sidebar.button("Run ALL Markets",   use_container_width=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Bot Backtest (4H Consensus)")
    st.sidebar.caption("Market-specific thresholds: US=5/8 · India=4/8 · Crypto=3/8 · Commodities=4/8")
    run_bot_bt = st.sidebar.button("Run Bot Consensus Backtest", use_container_width=True, key="run_bot_bt")

    if run_us and selected_periods:
        with st.spinner("Running US Stocks..."):
            st.session_state.results   = run_engine(DEFAULT_US, strategy_name, selected_periods, capital, interval)
            st.session_state.run_label = f"US Stocks · {tf_label}"
            st.session_state.bot_bt    = {}
    elif run_in and selected_periods:
        with st.spinner("Running Indian Stocks..."):
            st.session_state.results   = run_engine(DEFAULT_IN, strategy_name, selected_periods, capital, interval)
            st.session_state.run_label = f"Indian Stocks · {tf_label}"
            st.session_state.bot_bt    = {}
    elif run_cr and selected_periods:
        with st.spinner("Running Crypto..."):
            st.session_state.results   = run_engine(DEFAULT_CR, strategy_name, selected_periods, capital, interval)
            st.session_state.run_label = f"Crypto · {tf_label}"
            st.session_state.bot_bt    = {}
    elif run_cm and selected_periods:
        with st.spinner("Running Commodities..."):
            st.session_state.results   = run_engine(DEFAULT_CM, strategy_name, selected_periods, capital, interval)
            st.session_state.run_label = f"Commodities · {tf_label}"
            st.session_state.bot_bt    = {}
    elif run_all and selected_periods:
        with st.spinner("Running ALL Markets..."):
            st.session_state.results   = run_engine(DEFAULT_US+DEFAULT_IN+DEFAULT_CR+DEFAULT_CM, strategy_name, selected_periods, capital, interval)
            st.session_state.run_label = f"All Markets · {tf_label}"
            st.session_state.bot_bt    = {}
    elif run_bot_bt and selected_periods:
        with st.spinner("Running Bot Consensus Backtest (4H, market-specific thresholds)..."):
            all_tickers = DEFAULT_US + DEFAULT_IN + DEFAULT_CR + DEFAULT_CM
            bot_results = {p: [] for p in selected_periods}
            prog = st.progress(0); status = st.empty()
            for idx, ticker in enumerate(all_tickers):
                prog.progress((idx+1)/len(all_tickers))
                votes = get_min_votes(ticker)
                status.caption(f"Bot [{votes}/8] {ticker_label(ticker)} ({idx+1}/{len(all_tickers)})...")
                rows = process_bot_ticker(ticker, selected_periods, capital)
                if rows:
                    for label, row in rows.items():
                        bot_results[label].append(row)
            prog.empty(); status.empty()
            for label in bot_results:
                bot_results[label].sort(key=lambda x: x["Net %"] if x["Net %"] is not None and not (isinstance(x["Net %"],float) and np.isnan(x["Net %"])) else -999, reverse=True)
            st.session_state.bot_bt    = bot_results
            st.session_state.run_label = "Bot Consensus · 4H · Market-Specific Thresholds"

    # ── SINGLE STRATEGY RESULTS ─────────────────────────────────
    if st.session_state.results:
        res       = st.session_state.results
        run_label = st.session_state.run_label
        st.markdown(f"## Results — {run_label}")
        available_periods = [p for p in res if res[p]]
        if not available_periods:
            st.error("No results.")
        else:
            period_tabs = st.tabs(available_periods)
            for tab, period_label in zip(period_tabs, available_periods):
                with tab:
                    period_data = res[period_label]
                    buy_stocks  = [r for r in period_data if r["Signal"]=="BUY"]
                    sell_stocks = [r for r in period_data if r["Signal"]=="SELL"]

                    st.markdown("### Signal Summary")
                    col_b, col_s = st.columns(2)
                    with col_b:
                        st.success(f"BUY — {len(buy_stocks)} stocks")
                        if buy_stocks:
                            st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                                "Price":fmt(r["Price"]),"Strat %":fmt(r["Net %"],"%"),
                                "B&H %":fmt(r["B&H %"],"%"),"Win Rate":fmt(r["Win Rate"],"%")}
                                for r in buy_stocks]), use_container_width=True, hide_index=True)
                        else: st.info("No BUY signals.")
                    with col_s:
                        st.error(f"SELL — {len(sell_stocks)} stocks")
                        if sell_stocks:
                            st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                                "Price":fmt(r["Price"]),"Strat %":fmt(r["Net %"],"%"),
                                "B&H %":fmt(r["B&H %"],"%"),"Win Rate":fmt(r["Win Rate"],"%")}
                                for r in sell_stocks]), use_container_width=True, hide_index=True)
                        else: st.info("No SELL signals.")

                    if st.session_state.watchlist:
                        st.markdown("---")
                        st.markdown("### My Watchlist")
                        wl_rows = [r for r in period_data if r["Ticker"] in st.session_state.watchlist]
                        if wl_rows:
                            st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                                "Price":fmt(r["Price"]),"Signal":r["Signal"],
                                "Strat %":fmt(r["Net %"],"%"),"B&H %":fmt(r["B&H %"],"%")}
                                for r in wl_rows]).style.map(sig_color, subset=["Signal"]),
                                use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.subheader("Full Leaderboard")
                    mkt_filter = st.radio("Filter:", ["All","US","India","Crypto","Commodity"], horizontal=True, key=f"mkt_{period_label}")
                    filtered   = period_data if mkt_filter=="All" else [r for r in period_data if r["Market"]==mkt_filter]
                    if filtered:
                        st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                            "Price":fmt(r["Price"]),"Signal":r["Signal"],
                            "Strategy %":fmt(r["Net %"],"%"),"B&H %":fmt(r["B&H %"],"%"),
                            "Win Rate":fmt(r["Win Rate"],"%"),"Trades":r["Trades"],"End Value":fmt(r["End Value"])}
                            for r in filtered]).style.map(sig_color, subset=["Signal"]),
                            use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.subheader("Chart & Trade Log")
                    ch1, ch2 = st.columns([3,1])
                    with ch1:
                        chart_search = st.text_input("Stock", placeholder="Type ticker or name...",
                            label_visibility="collapsed", key=f"cs_{period_label}")
                    with ch2:
                        chart_mkt = st.selectbox("Mkt", ["US","India (NSE)","Crypto","Commodity"],
                            label_visibility="collapsed", key=f"cm_{period_label}")

                    final_ticker = None
                    if chart_search.strip() and len(chart_search.strip()) >= 2:
                        try:
                            sq   = yf.Search(chart_search.strip(), max_results=7).quotes
                            sugg = [f"{q.get('symbol','')} — {q.get('shortname') or q.get('longname','')}" for q in sq if q.get("symbol")]
                            if sugg:
                                chosen = st.selectbox("Pick:", sugg, key=f"sg_{period_label}", label_visibility="collapsed")
                                if chosen: final_ticker = chosen.split(" — ")[0].strip()
                        except Exception: pass

                    if st.button("Search & View Chart", key=f"cg_{period_label}", use_container_width=True, type="primary"):
                        if final_ticker:
                            raw_t = final_ticker
                            if chart_mkt=="India (NSE)" and not raw_t.endswith(".NS"):  raw_t+=".NS"
                            elif chart_mkt=="Crypto"    and not raw_t.endswith("-USD"): raw_t+="-USD"
                        elif chart_search.strip():
                            raw_t = chart_search.strip().upper().replace(" ","")
                            if chart_mkt=="India (NSE)" and not raw_t.endswith(".NS"):  raw_t+=".NS"
                            elif chart_mkt=="Crypto"    and not raw_t.endswith("-USD"): raw_t+="-USD"
                        else: raw_t = None
                        if raw_t:
                            st.session_state[f"csel_{period_label}"] = raw_t
                            if not any(r["Ticker"]==raw_t for r in period_data):
                                with st.spinner(f"Fetching {raw_t}..."):
                                    nr = process_ticker(raw_t, strategy_name, selected_periods, capital, interval)
                                    if nr and period_label in nr:
                                        st.session_state.results[period_label].append(nr[period_label])
                                        st.session_state.results[period_label].sort(key=lambda x: x["Net %"] if x["Net %"] is not None and not (isinstance(x["Net %"],float) and np.isnan(x["Net %"])) else -999, reverse=True)
                                        st.rerun()
                                    else: st.error(f"No data for '{raw_t}'.")
                            else: st.rerun()

                    sel_ticker = st.session_state.get(f"csel_{period_label}")
                    row = None
                    if sel_ticker: row = next((r for r in period_data if r["Ticker"]==sel_ticker), None)
                    if row is None and period_data: row=period_data[0]; sel_ticker=row["Ticker"]

                    if row:
                        df_plot=row["_df"]; log_t=row["_log"]
                        curr="INR" if sel_ticker.endswith(".NS") else "USD"
                        lbl=row["Label"]; in_wl=sel_ticker in st.session_state.watchlist
                        st.markdown(f"#### {lbl} — {row['Market']} · {tf_label}")
                        m1,m2,m3,m4,m5=st.columns(5)
                        sc="#3fb950" if row["Signal"]=="BUY" else "#f85149"
                        m1.markdown(f"**Signal**<br><span style='color:{sc};font-size:20px;font-weight:bold'>{row['Signal']}</span>",unsafe_allow_html=True)
                        m2.metric("Strategy",fmt(row["Net %"],"%"))
                        m3.metric("B&H",fmt(row["B&H %"],"%"))
                        m4.metric("Win Rate",fmt(row["Win Rate"],"%"))
                        m5.metric("End Value",f"{curr} {row['End Value']:,.0f}" if row["End Value"] else "—")
                        if in_wl:
                            if st.button(f"Remove {lbl} from Watchlist",key=f"wlr_{period_label}"):
                                st.session_state.watchlist.remove(sel_ticker); st.rerun()
                        else:
                            if st.button(f"Add {lbl} to Watchlist",key=f"wla_{period_label}",type="primary"):
                                st.session_state.watchlist.append(sel_ticker); st.rerun()
                        tf2=st.radio("View:",["1M","3M","6M","1Y","Full"],index=4,horizontal=True,key=f"tf_{period_label}_{sel_ticker}")
                        tfm={"1M":30,"3M":90,"6M":180,"1Y":365}
                        dfv=df_plot if tf2=="Full" else df_plot[df_plot.index>=df_plot.index.max()-timedelta(days=tfm[tf2])]
                        st.plotly_chart(draw_chart(dfv,log_t,strategy_name),use_container_width=True)
                        st.subheader("Trade Log")
                        if log_t:
                            ldf=pd.DataFrame(log_t)
                            ldf.rename(columns={"Portfolio":f"Portfolio ({curr})"},inplace=True)
                            def cr(v):
                                try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                                except: return ""
                            def cs2(v):
                                if v=="OPEN": return "color:#3fb950;font-weight:bold"
                                if v=="CLOSED": return "color:#8b949e"
                                return ""
                            st.dataframe(ldf.style.map(cr,subset=["Return %"]).map(cs2,subset=["Status"]),use_container_width=True,hide_index=True)
                        else: st.info("No trades triggered.")
    else:
        st.info("Select a strategy and timeframe, then click a Run button.")

    # ── BOT CONSENSUS BACKTEST RESULTS ──────────────────────────
    if st.session_state.get("bot_bt"):
        bot_bt = st.session_state.bot_bt
        st.markdown("---")
        st.markdown(f"## Bot Consensus Backtest — 4H · Market-Specific Thresholds")
        avail = [p for p in bot_bt if bot_bt[p]]
        if avail:
            btabs = st.tabs(avail)
            for btab, plabel in zip(btabs, avail):
                with btab:
                    pdata = bot_bt[plabel]
                    buys  = [r for r in pdata if r["Signal"]=="BUY"]
                    sells = [r for r in pdata if r["Signal"]=="SELL"]
                    holds = [r for r in pdata if r["Signal"]=="HOLD"]
                    b1,b2,b3=st.columns(3)
                    b1.success(f"🟢 BUY — {len(buys)}")
                    b2.error(  f"🔴 SELL — {len(sells)}")
                    b3.info(   f"⚪ HOLD — {len(holds)}")
                    if buys:
                        st.markdown("**Top BUY Signals:**")
                        st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                            "Price":fmt(r["Price"]),"Threshold":f"{r['Min Votes']}/8",
                            "Buy Votes":r["Buy Votes"],"Strategy %":fmt(r["Net %"],"%"),
                            "B&H %":fmt(r["B&H %"],"%"),"Win Rate":fmt(r["Win Rate"],"%")}
                            for r in buys]),use_container_width=True,hide_index=True)
                    mf=st.radio("Filter:",["All","US","India","Crypto","Commodity"],horizontal=True,key=f"botmkt_{plabel}")
                    fd=pdata if mf=="All" else [r for r in pdata if r["Market"]==mf]
                    if fd:
                        st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                            "Price":fmt(r["Price"]),"Signal":r["Signal"],
                            "Threshold":f"{r['Min Votes']}/8","Buy V":r["Buy Votes"],"Sell V":r["Sell Votes"],
                            "Strategy %":fmt(r["Net %"],"%"),"B&H %":fmt(r["B&H %"],"%"),
                            "Win Rate":fmt(r["Win Rate"],"%"),"Trades":r["Trades"]}
                            for r in fd]).style.map(sig_color,subset=["Signal"]),
                            use_container_width=True,hide_index=True)

# ═══════════════════════════════════════════════════════════════
# TAB 2 — PAPER TRADING BOT
# ═══════════════════════════════════════════════════════════════
with tab_bot:
    st.title("🤖 Paper Trading Bot")
    st.markdown("4H consensus signals + Alpaca paper execution.")

    if not ALPACA_AVAILABLE:
        st.error("Add `alpaca-py` to requirements.txt and redeploy.")
        st.code("alpaca-py", language="text")
        st.stop()

    # Load keys from secrets, allow manual override
    default_key    = st.secrets.get("ALPACA_KEY",    "")
    default_secret = st.secrets.get("ALPACA_SECRET", "")

    if default_key and default_secret:
        st.success("Alpaca keys loaded from secrets automatically.")
        api_key    = default_key
        api_secret = default_secret
    else:
        b1, b2 = st.columns(2)
        with b1: api_key    = st.text_input("Alpaca API Key",    type="password", key="bot_api_key")
        with b2: api_secret = st.text_input("Alpaca API Secret", type="password", key="bot_api_secret")

    if not api_key or not api_secret:
        st.info("Enter Alpaca keys above or save them in Streamlit Secrets.")
        st.stop()
    try:
        bot_client = TradingClient(api_key, api_secret, paper=True)
            acct       = bot_client.get_account()
            st.markdown("### Account")
            a1,a2,a3,a4=st.columns(4)
            a1.metric("Portfolio",   f"${float(acct.portfolio_value):,.0f}")
            a2.metric("Cash",        f"${float(acct.cash):,.0f}")
            a3.metric("P&L Today",   f"${float(acct.equity)-float(acct.last_equity):+,.0f}")
            a4.metric("Buying Power",f"${float(acct.buying_power):,.0f}")

            st.markdown("---")
            st.markdown("### Bot Settings")
            s1,s2=st.columns(2)
            with s1: bot_cap_pct=st.slider("Capital % per trade",5,25,10,key="bot_cap")
            with s2: max_pos    =st.slider("Max open positions",1,10,5,key="max_pos")
            st.info("**Thresholds:** 🇺🇸 US=5/8 · 🇮🇳 India=4/8 · 🪙 Crypto=3/8 · 🛢️ Commodities=4/8 · Timeframe: 4H")

            bot_tickers=st.multiselect("Assets to scan",
                DEFAULT_US+DEFAULT_CR+DEFAULT_CM,
                default=["AAPL","NVDA","MSFT","BTC-USD","GC=F","CL=F"],
                format_func=ticker_label, key="bot_tickers")

            st.markdown("---")
            c1,c2=st.columns(2)
            with c1: auto_trade    = st.toggle("Enable Auto Trading",value=False,key="auto_trade")
            with c2: scan_interval = st.selectbox("Scan every",["5 mins","15 mins","30 mins","1 hour"],key="scan_interval")

            interval_map={"5 mins":300,"15 mins":900,"30 mins":1800,"1 hour":3600}
            interval_sec=interval_map[scan_interval]

            if auto_trade:
                st.success(f"Auto trading ON — scanning every {scan_interval}")
                import streamlit.components.v1 as components
                components.html(f"""<script>setTimeout(function(){{window.location.reload();}},{interval_sec*1000});</script>""",height=0)
                scan_btn=True
                st.info(f"Next auto-scan in {scan_interval}. Keep this tab open.")
            else:
                scan_btn=st.button("🔍 Scan & Execute Trades Now",type="primary",use_container_width=True)

            if scan_btn and bot_tickers:
                positions={}
                try: positions={p.symbol:float(p.qty) for p in bot_client.get_all_positions()}
                except: pass
                port_val=float(bot_client.get_account().portfolio_value)
                st.markdown("### Live Scan Results")
                prog=st.progress(0); rows=[]
                for i,ticker in enumerate(bot_tickers):
                    prog.progress((i+1)/len(bot_tickers))
                    try:
                        raw=fetch_data(ticker,interval="4h",days=400)
                        if raw is None:
                            raw=fetch_data(ticker,interval="1d",days=400)
                        if raw is None: continue
                        buy_v=sell_v=0
                        for strat in STRATEGIES:
                            try:
                                e2=generate_signals(raw.copy(),strat)
                                s2=int(e2["Signal"].iloc[-1])
                                buy_v  +=1 if s2== 1 else 0
                                sell_v +=1 if s2==-1 else 0
                            except: pass
                        price  = float(raw["Close"].iloc[-1])
                        min_v  = get_min_votes(ticker)
                        action = "—"; status="HOLD"
                        if buy_v>=min_v and buy_v>sell_v:
                            status="BUY"
                            if ticker not in positions and len(positions)<max_pos:
                                try:
                                    qty_usd=port_val*(bot_cap_pct/100)
                                    order=MarketOrderRequest(symbol=ticker,notional=round(qty_usd,2),side=OrderSide.BUY,time_in_force=TimeInForce.DAY)
                                    bot_client.submit_order(order)
                                    action=f"BOUGHT ${qty_usd:.0f}"
                                    st.session_state.bot_log.append({"Time":datetime.now().strftime("%H:%M:%S"),"Ticker":ticker_label(ticker),"Action":"BUY","Price":round(price,2),"Amount":f"${qty_usd:.0f}","Votes":f"{buy_v}/8"})
                                except Exception as e: action=f"Failed: {e}"
                            elif ticker in positions: action="Already holding"
                            else: action="Max positions reached"
                        elif sell_v>=min_v and sell_v>buy_v:
                            status="SELL"
                            if ticker in positions:
                                try:
                                    bot_client.close_position(ticker)
                                    action="SOLD position"
                                    st.session_state.bot_log.append({"Time":datetime.now().strftime("%H:%M:%S"),"Ticker":ticker_label(ticker),"Action":"SELL","Price":round(price,2),"Amount":"full","Votes":f"{sell_v}/8"})
                                except Exception as e: action=f"Failed: {e}"
                            else: action="No position"
                        rows.append({"Asset":ticker_label(ticker),"Market":get_market(ticker),"Price":round(price,2),
                            "Signal":status,"Threshold":f"{min_v}/8","Buy V":buy_v,"Sell V":sell_v,
                            "Action":action,"Holding":"Yes" if ticker in positions else "No"})
                    except Exception as e:
                        rows.append({"Asset":ticker_label(ticker),"Market":"—","Price":"—","Signal":"ERROR","Threshold":"—","Buy V":0,"Sell V":0,"Action":str(e),"Holding":"—"})
                prog.empty()
                if rows:
                    st.dataframe(pd.DataFrame(rows).style.map(sig_color,subset=["Signal"]),use_container_width=True,hide_index=True)

            st.markdown("---")
            st.subheader("Open Positions")
            try:
                positions=bot_client.get_all_positions()
                if positions:
                    def plc(v):
                        try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                        except: return ""
                    st.dataframe(pd.DataFrame([{"Asset":p.symbol,"Qty":float(p.qty),
                        "Avg Price":float(p.avg_entry_price),"Current":float(p.current_price),
                        "P&L $":round(float(p.unrealized_pl),2),"P&L %":round(float(p.unrealized_plpc)*100,2)}
                        for p in positions]).style.map(plc,subset=["P&L $","P&L %"]),use_container_width=True,hide_index=True)
                    if st.button("Close All Positions",type="primary"):
                        bot_client.close_all_positions(cancel_orders=True); st.success("All closed!"); st.rerun()
                else: st.info("No open positions.")
            except Exception as e: st.error(f"Error: {e}")

            st.markdown("---")
            st.subheader("Bot Trade Log")
            if st.session_state.bot_log:
                st.dataframe(pd.DataFrame(st.session_state.bot_log),use_container_width=True,hide_index=True)
            else: st.info("No trades this session.")

            st.markdown("---")
            st.subheader("All Orders (Alpaca)")
            try:
                orders=bot_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL,limit=20))
                if orders:
                    st.dataframe(pd.DataFrame([{"Time":o.created_at.strftime("%Y-%m-%d %H:%M"),
                        "Ticker":o.symbol,"Side":o.side.value.upper(),
                        "Amount":o.notional or o.qty,"Status":o.status.value,
                        "Fill $":o.filled_avg_price or "—"} for o in orders]),use_container_width=True,hide_index=True)
                else: st.info("No orders yet.")
            except Exception as e: st.error(f"Error: {e}")

        except Exception as e:
            st.error(f"Could not connect to Alpaca: {e}")