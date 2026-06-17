import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Global Multi-Market Backtester Pro")
st.title("Global Multi-Market Backtester Pro")

# ---------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------
def init_state():
    defaults = {
        "us_list":      [],
        "in_list":      [],
        "cr_list":      [],
        "watchlist":    [],
        "results":      {},
        "run_label":    "",
        "active_market": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ---------------------------------------------------------------
# STRATEGIES & PERIODS
# ---------------------------------------------------------------
STRATEGIES = [
    "Triple SMA Ribbon (20/50/200)",
    "LuxAlgo ATR Channel",
    "MACD Momentum",
    "Mean Reversion - Dip Buy",
    "EMA 9/21 Ribbon",
    "Bollinger Band Squeeze",
]
PERIODS = {"1Y": 365, "5Y": 1825, "10Y": 3650}

# ---------------------------------------------------------------
# SIDEBAR — SETTINGS ONLY
# ---------------------------------------------------------------
st.sidebar.header("Backtest Settings")
strategy_name = st.sidebar.selectbox("Strategy", STRATEGIES)

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
st.sidebar.markdown("**Run Backtest**")
run_us  = st.sidebar.button("Run US Stocks",     type="primary", use_container_width=True)
run_in  = st.sidebar.button("Run Indian Stocks", type="primary", use_container_width=True)
run_cr  = st.sidebar.button("Run Crypto",        type="primary", use_container_width=True)
run_all = st.sidebar.button("Run ALL Markets",   use_container_width=True)

# ---------------------------------------------------------------
# INDICATOR HELPERS
# ---------------------------------------------------------------
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

# ---------------------------------------------------------------
# SIGNAL GENERATION
# ---------------------------------------------------------------
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
        df["Band"]   = np.where(df["Signal"] == 1,
                                pd.Series(floor,  index=df.index),
                                pd.Series(ceil_v, index=df.index))

    elif strategy == "MACD Momentum":
        df["EMA12"]   = compute_ema(df["Close"], 12)
        df["EMA26"]   = compute_ema(df["Close"], 26)
        df["MACD"]    = df["EMA12"] - df["EMA26"]
        df["MACDSig"] = compute_ema(df["MACD"], 9)
        df["Signal"]  = np.where(df["MACD"] > df["MACDSig"], 1, -1)

    elif strategy == "Mean Reversion - Dip Buy":
        df["SMA20"]  = compute_sma(df["Close"], 20)
        df["SMA50"]  = compute_sma(df["Close"], 50)
        df["SMA200"] = compute_sma(df["Close"], 200)
        buy  = (df["SMA200"] > df["SMA50"]) & (df["SMA50"] > df["SMA20"]) & (df["Close"] < df["SMA20"])
        sell = (df["Close"] > df["SMA50"])
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    elif strategy == "EMA 9/21 Ribbon":
        df["EMA9"]   = compute_ema(df["Close"], 9)
        df["EMA21"]  = compute_ema(df["Close"], 21)
        df["Signal"] = np.where(df["EMA9"] > df["EMA21"], 1, -1)

    elif strategy == "Bollinger Band Squeeze":
        df["RSI"] = compute_rsi(df["Close"], 14)
        df["BBUp"], df["BBMid"], df["BBLow"] = compute_bb(df["Close"])
        buy  = (df["Close"] < df["BBLow"])  & (df["RSI"] < 35)
        sell = (df["Close"] > df["BBUp"])   | (df["RSI"] > 65)
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    return df

# ---------------------------------------------------------------
# BACKTEST ENGINE
# ---------------------------------------------------------------
def run_backtest(df, capital):
    log, in_pos, entry, portfolio, wins, total = [], False, 0.0, float(capital), 0, 0
    entry_date = ""
    signals = df["Signal"].values
    closes  = df["Close"].values
    dates   = df.index

    for i in range(len(df)):
        sig, price, date = signals[i], float(closes[i]), dates[i].strftime("%Y-%m-%d")
        if sig == 1 and not in_pos:
            in_pos, entry, entry_date, total = True, price, date, total + 1
        elif sig == -1 and in_pos:
            in_pos = False
            ret = (price - entry) / entry
            portfolio *= (1 + ret)
            if price > entry: wins += 1
            log.append({"Status": "CLOSED", "Entry Date": entry_date,
                         "Entry Price": round(entry, 4), "Exit Date": date,
                         "Exit Price": round(price, 4), "Return %": round(ret*100, 2),
                         "Portfolio": round(portfolio, 2)})

    if in_pos:
        price = float(closes[-1])
        ret   = (price - entry) / entry
        portfolio *= (1 + ret)
        if price > entry: wins += 1
        log.append({"Status": "OPEN", "Entry Date": entry_date,
                     "Entry Price": round(entry, 4), "Exit Date": "Present",
                     "Exit Price": round(price, 4), "Return %": round(ret*100, 2),
                     "Portfolio": round(portfolio, 2)})

    win_rate = wins / total * 100 if total > 0 else 0.0
    first_cl = df[df["Signal"].notna()]["Close"].iloc[0] if not df[df["Signal"].notna()].empty else closes[0]
    bh_pct   = (float(closes[-1]) / float(first_cl) - 1) * 100

    return {"net_pct": round((portfolio/capital-1)*100, 2), "bh_pct": round(bh_pct, 2),
            "end_val": round(portfolio, 2), "win_rate": round(win_rate, 1),
            "trades": total, "log": log, "last_sig": int(signals[-1]),
            "last_price": round(float(closes[-1]), 4)}

# ---------------------------------------------------------------
# SINGLE TICKER BACKTEST (for search-and-add)
# ---------------------------------------------------------------
def backtest_single(ticker, strategy, periods, capital):
    max_days = max(periods.values()) + 250
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=max_days)
    raw = yf.download(ticker, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
    if raw.empty or len(raw) < 60:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    rows = {}
    for label, days in periods.items():
        cutoff   = end_dt - timedelta(days=days)
        slice_df = raw[raw.index >= pd.to_datetime(cutoff)].copy()
        if len(slice_df) < 50:
            continue
        enriched = generate_signals(slice_df, strategy)
        bt       = run_backtest(enriched, capital)
        mkt = "India" if ticker.endswith(".NS") else "Crypto" if ticker.endswith("-USD") else "US"
        rows[label] = {
            "Ticker":    ticker,
            "Market":    mkt,
            "Price":     bt["last_price"],
            "Signal":    "BUY" if bt["last_sig"] == 1 else "SELL",
            "Net %":     bt["net_pct"],
            "B&H %":     bt["bh_pct"],
            "Win Rate":  bt["win_rate"],
            "Trades":    bt["trades"],
            "End Value": bt["end_val"],
            "_log":      bt["log"],
            "_df":       enriched,
        }
    return rows

# ---------------------------------------------------------------
# FULL ENGINE
# ---------------------------------------------------------------
def run_engine(tickers, strategy, periods, capital):
    results  = {p: [] for p in periods}
    max_days = max(periods.values()) + 250
    prog     = st.progress(0)
    status   = st.empty()

    for idx, ticker in enumerate(tickers):
        prog.progress((idx + 1) / len(tickers))
        status.caption(f"Processing {ticker} ({idx+1}/{len(tickers)})...")
        try:
            end_dt   = datetime.now()
            start_dt = end_dt - timedelta(days=max_days)
            raw = yf.download(ticker, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 60:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)

            for label, days in periods.items():
                cutoff   = end_dt - timedelta(days=days)
                slice_df = raw[raw.index >= pd.to_datetime(cutoff)].copy()
                if len(slice_df) < 50:
                    continue
                enriched = generate_signals(slice_df, strategy)
                bt       = run_backtest(enriched, capital)
                mkt = "India" if ticker.endswith(".NS") else "Crypto" if ticker.endswith("-USD") else "US"
                results[label].append({
                    "Ticker":    ticker, "Market":    mkt,
                    "Price":     bt["last_price"],
                    "Signal":    "BUY" if bt["last_sig"] == 1 else "SELL",
                    "Net %":     bt["net_pct"],   "B&H %":    bt["bh_pct"],
                    "Win Rate":  bt["win_rate"],  "Trades":   bt["trades"],
                    "End Value": bt["end_val"],   "_log":     bt["log"],
                    "_df":       enriched,
                })
        except Exception as e:
            status.caption(f"Skipped {ticker}: {e}")

    prog.empty()
    status.empty()
    for label in results:
        results[label].sort(key=lambda x: x["Net %"], reverse=True)
    return results

# ---------------------------------------------------------------
# TRIGGER RUN
# ---------------------------------------------------------------
run_tickers = None
run_label   = ""

if run_us:
    if not st.session_state.us_list:
        st.warning("No US stocks added. Use the search box in the results area.")
    else:
        run_tickers = st.session_state.us_list
        run_label   = "US Stocks"
        st.session_state.active_market = "US"

elif run_in:
    if not st.session_state.in_list:
        st.warning("No Indian stocks added. Use the search box in the results area.")
    else:
        run_tickers = st.session_state.in_list
        run_label   = "Indian Stocks"
        st.session_state.active_market = "IN"

elif run_cr:
    if not st.session_state.cr_list:
        st.warning("No Crypto added. Use the search box in the results area.")
    else:
        run_tickers = st.session_state.cr_list
        run_label   = "Crypto"
        st.session_state.active_market = "CR"

elif run_all:
    combined = st.session_state.us_list + st.session_state.in_list + st.session_state.cr_list
    if not combined:
        st.warning("No stocks added yet. Use the search boxes below.")
    else:
        run_tickers = combined
        run_label   = "All Markets"
        st.session_state.active_market = "ALL"

if run_tickers and selected_periods:
    with st.spinner(f"Running backtest for {run_label}..."):
        st.session_state.results   = run_engine(run_tickers, strategy_name, selected_periods, capital)
        st.session_state.run_label = run_label

# ---------------------------------------------------------------
# SEARCH BOXES (always visible — top of page)
# ---------------------------------------------------------------
st.markdown("---")
st.markdown("### Add Stocks to Backtest")
col_us, col_in, col_cr = st.columns(3)

def search_and_add(raw_input, market_key, suffix, list_key, col):
    raw = raw_input.strip().upper().replace(" ", "")
    if not raw:
        col.warning("Enter a ticker.")
        return
    ticker_try = raw + suffix if suffix and not raw.endswith(suffix) else raw
    with st.spinner(f"Looking up {ticker_try}..."):
        try:
            tk    = yf.Ticker(ticker_try)
            price = tk.fast_info.last_price
            name  = tk.info.get("shortName", ticker_try)
            if price and float(price) > 0:
                if ticker_try not in st.session_state[list_key]:
                    st.session_state[list_key].append(ticker_try)
                col.success(f"Added {name} @ {round(float(price),2)}")
            else:
                col.error(f"'{ticker_try}' not found.")
        except Exception:
            col.error(f"'{ticker_try}' not found.")

with col_us:
    st.markdown("🇺🇸 **US Stocks**")
    us_input = st.text_input("Ticker", placeholder="AAPL, NVDA, COIN...", key="us_input", label_visibility="collapsed")
    if st.button("Add to US", use_container_width=True, key="add_us"):
        search_and_add(us_input, "US", "", "us_list", col_us)
    if st.session_state.us_list:
        for i, t in enumerate(st.session_state.us_list):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"`{t}`")
            if c2.button("✕", key=f"rm_us_{i}"):
                st.session_state.us_list.pop(i)
                st.rerun()

with col_in:
    st.markdown("🇮🇳 **Indian Stocks (NSE)**")
    in_input = st.text_input("Ticker", placeholder="RELIANCE, ZOMATO...", key="in_input", label_visibility="collapsed")
    if st.button("Add to India", use_container_width=True, key="add_in"):
        search_and_add(in_input, "IN", ".NS", "in_list", col_in)
    if st.session_state.in_list:
        for i, t in enumerate(st.session_state.in_list):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"`{t.replace('.NS','')}`")
            if c2.button("✕", key=f"rm_in_{i}"):
                st.session_state.in_list.pop(i)
                st.rerun()

with col_cr:
    st.markdown("🪙 **Crypto**")
    cr_input = st.text_input("Ticker", placeholder="BTC, ETH, SOL...", key="cr_input", label_visibility="collapsed")
    if st.button("Add to Crypto", use_container_width=True, key="add_cr"):
        search_and_add(cr_input, "CR", "-USD", "cr_list", col_cr)
    if st.session_state.cr_list:
        for i, t in enumerate(st.session_state.cr_list):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"`{t.replace('-USD','')}`")
            if c2.button("✕", key=f"rm_cr_{i}"):
                st.session_state.cr_list.pop(i)
                st.rerun()

# ---------------------------------------------------------------
# RESULTS
# ---------------------------------------------------------------
if st.session_state.results:
    res       = st.session_state.results
    run_label = st.session_state.run_label

    st.markdown("---")
    st.markdown(f"## Results — {run_label} · {strategy_name}")

    available_periods = [p for p in res if res[p]]
    if not available_periods:
        st.error("No results returned. Try adding more stocks or a longer period.")
        st.stop()

    period_tabs = st.tabs(available_periods)

    for tab, period_label in zip(period_tabs, available_periods):
        with tab:
            period_data = res[period_label]

            buy_stocks  = [r for r in period_data if r["Signal"] == "BUY"]
            sell_stocks = [r for r in period_data if r["Signal"] == "SELL"]

            # ---- BUY / SELL signal panels ----
            st.markdown("### Signal Summary")
            col_b, col_s = st.columns(2)

            with col_b:
                st.success(f"BUY Signals — {len(buy_stocks)} stocks")
                if buy_stocks:
                    buy_tbl = pd.DataFrame([{
                        "Ticker":  r["Ticker"].replace(".NS","").replace("-USD",""),
                        "Market":  r["Market"],
                        "Price":   r["Price"],
                        "Strat %": r["Net %"],
                        "B&H %":   r["B&H %"],
                    } for r in buy_stocks])

                    def cp(v):
                        try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                        except: return ""

                    st.dataframe(
                        buy_tbl.style.map(cp, subset=["Strat %","B&H %"]),
                        use_container_width=True, hide_index=True
                    )

                    # Add to watchlist buttons
                    st.markdown("**Add to Watchlist:**")
                    wl_cols = st.columns(min(len(buy_stocks), 4))
                    for j, r in enumerate(buy_stocks):
                        label_t = r["Ticker"].replace(".NS","").replace("-USD","")
                        if wl_cols[j % 4].button(f"+ {label_t}", key=f"wl_add_buy_{period_label}_{j}"):
                            if r["Ticker"] not in st.session_state.watchlist:
                                st.session_state.watchlist.append(r["Ticker"])
                                st.toast(f"Added {label_t} to watchlist!")
                else:
                    st.info("No BUY signals.")

            with col_s:
                st.error(f"SELL / CASH — {len(sell_stocks)} stocks")
                if sell_stocks:
                    sell_tbl = pd.DataFrame([{
                        "Ticker":  r["Ticker"].replace(".NS","").replace("-USD",""),
                        "Market":  r["Market"],
                        "Price":   r["Price"],
                        "Strat %": r["Net %"],
                        "B&H %":   r["B&H %"],
                    } for r in sell_stocks])
                    st.dataframe(
                        sell_tbl.style.map(cp, subset=["Strat %","B&H %"]),
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No SELL signals.")

            # ---- WATCHLIST ----
            if st.session_state.watchlist:
                st.markdown("---")
                st.markdown("### My Watchlist")
                wl_rows = []
                for t in st.session_state.watchlist:
                    match = next((r for r in period_data if r["Ticker"] == t), None)
                    if match:
                        wl_rows.append({
                            "Ticker":  t.replace(".NS","").replace("-USD",""),
                            "Market":  match["Market"],
                            "Price":   match["Price"],
                            "Signal":  match["Signal"],
                            "Strat %": match["Net %"],
                            "B&H %":   match["B&H %"],
                        })
                if wl_rows:
                    def cs(v):
                        if v == "BUY":  return "background-color:#1a3a1a;color:#3fb950;font-weight:bold"
                        if v == "SELL": return "background-color:#3a1a1a;color:#f85149;font-weight:bold"
                        return ""
                    wl_df = pd.DataFrame(wl_rows)
                    st.dataframe(
                        wl_df.style.map(cs, subset=["Signal"]).map(cp, subset=["Strat %","B&H %"]),
                        use_container_width=True, hide_index=True
                    )
                # Remove from watchlist
                st.markdown("**Remove from Watchlist:**")
                rm_cols = st.columns(min(len(st.session_state.watchlist), 4))
                for j, t in enumerate(st.session_state.watchlist):
                    label_t = t.replace(".NS","").replace("-USD","")
                    if rm_cols[j % 4].button(f"- {label_t}", key=f"wl_rm_{period_label}_{j}"):
                        st.session_state.watchlist.remove(t)
                        st.rerun()

            # ---- SEARCH & ADD AFTER BACKTEST ----
            st.markdown("---")
            st.markdown("### Search & Add Any Stock to Results")
            sc1, sc2, sc3 = st.columns([2, 1, 1])
            with sc1:
                search_ticker = st.text_input(
                    "Ticker",
                    placeholder="Type any ticker e.g. AAPL, RELIANCE, BTC",
                    key=f"post_search_{period_label}",
                    label_visibility="collapsed"
                )
            with sc2:
                search_market = st.selectbox(
                    "Market",
                    ["US", "India (NSE)", "Crypto"],
                    key=f"post_market_{period_label}",
                    label_visibility="collapsed"
                )
            with sc3:
                search_btn = st.button("Search & Add to Results", key=f"post_btn_{period_label}", use_container_width=True)

            if search_btn and search_ticker.strip():
                raw = search_ticker.strip().upper().replace(" ", "")
                if search_market == "India (NSE)" and not raw.endswith(".NS"):
                    t_try = raw + ".NS"
                elif search_market == "Crypto" and not raw.endswith("-USD"):
                    t_try = raw + "-USD"
                else:
                    t_try = raw

                # Check not already in results
                already = any(r["Ticker"] == t_try for r in res.get(period_label, []))
                if already:
                    st.info(f"{t_try} already in results.")
                else:
                    with st.spinner(f"Fetching & backtesting {t_try}..."):
                        try:
                            new_rows = backtest_single(t_try, strategy_name, selected_periods, capital)
                            if new_rows and period_label in new_rows:
                                st.session_state.results[period_label].append(new_rows[period_label])
                                st.session_state.results[period_label].sort(key=lambda x: x["Net %"], reverse=True)
                                st.success(f"Added {t_try} — Signal: {new_rows[period_label]['Signal']} | Strategy: {new_rows[period_label]['Net %']}%")
                                st.rerun()
                            else:
                                st.error(f"Could not fetch data for '{t_try}'. Check ticker.")
                        except Exception as e:
                            st.error(f"Error: {e}")

            st.markdown("---")

            # ---- FULL LEADERBOARD ----
            st.subheader("Full Leaderboard")
            mkt_filter = st.radio("Filter:", ["All","US","India","Crypto"],
                                   horizontal=True, key=f"mkt_{period_label}")
            filtered = period_data if mkt_filter == "All" else [r for r in period_data if r["Market"] == mkt_filter]

            if filtered:
                disp = pd.DataFrame([{
                    "Ticker":       r["Ticker"].replace(".NS","").replace("-USD",""),
                    "Market":       r["Market"],
                    "Price":        r["Price"],
                    "Signal":       r["Signal"],
                    "Strategy %":   r["Net %"],
                    "Buy & Hold %": r["B&H %"],
                    "Win Rate %":   r["Win Rate"],
                    "Trades":       r["Trades"],
                    "End Value":    r["End Value"],
                } for r in filtered])

                def csig(v):
                    if v == "BUY":  return "background-color:#1a3a1a;color:#3fb950;font-weight:bold"
                    if v == "SELL": return "background-color:#3a1a1a;color:#f85149;font-weight:bold"
                    return ""
                def cpct(v):
                    try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                    except: return ""

                st.dataframe(
                    disp.style.map(csig, subset=["Signal"]).map(cpct, subset=["Strategy %","Buy & Hold %"]),
                    use_container_width=True, hide_index=True
                )

            st.markdown("---")

            # ---- CHART & TRADE LOG ----
            st.subheader("Chart & Trade Log")
            ticker_choices = [r["Ticker"] for r in filtered] if filtered else []
            if not ticker_choices:
                st.info("No tickers to display.")
                continue

            selected_ticker = st.selectbox(
                "Select asset:",
                options=ticker_choices,
                format_func=lambda x: x.replace(".NS","").replace("-USD",""),
                key=f"sel_{period_label}"
            )
            row = next((r for r in filtered if r["Ticker"] == selected_ticker), None)

            if row:
                df_plot = row["_df"]
                log     = row["_log"]
                curr    = "INR" if selected_ticker.endswith(".NS") else "USD"

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Signal",   row["Signal"])
                m2.metric("Strategy", f"{row['Net %']}%")
                m3.metric("B&H",      f"{row['B&H %']}%")
                m4.metric("Win Rate", f"{row['Win Rate']}%")
                m5.metric("End Val",  f"{curr} {row['End Value']:,.0f}")

                tf_choice = st.radio("View:", ["1M","3M","6M","1Y","Full"], index=4,
                                     horizontal=True, key=f"tf_{period_label}_{selected_ticker}")
                tf_map  = {"1M":30,"3M":90,"6M":180,"1Y":365}
                df_view = df_plot if tf_choice == "Full" else \
                          df_plot[df_plot.index >= df_plot.index.max() - timedelta(days=tf_map[tf_choice])]

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Close"],
                                          name="Price", line=dict(color="white", width=1.5)))
                s = strategy_name
                if s in ["Triple SMA Ribbon (20/50/200)", "Mean Reversion - Dip Buy"]:
                    for col_n, color, nm in [("SMA20","cyan","SMA 20"),("SMA50","gold","SMA 50"),("SMA200","magenta","SMA 200")]:
                        if col_n in df_view.columns:
                            fig.add_trace(go.Scatter(x=df_view.index, y=df_view[col_n], name=nm, line=dict(color=color, width=1)))
                elif s == "LuxAlgo ATR Channel" and "Band" in df_view.columns:
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Band"], name="ATR Band", line=dict(color="lime", width=1.5, dash="dot")))
                elif s == "MACD Momentum" and "MACD" in df_view.columns:
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACD"],    name="MACD",   line=dict(color="cyan",    width=1)))
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACDSig"], name="Signal", line=dict(color="magenta", width=1, dash="dot")))
                elif s == "EMA 9/21 Ribbon" and "EMA9" in df_view.columns:
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA9"],  name="EMA 9",  line=dict(color="lime",   width=1)))
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA21"], name="EMA 21", line=dict(color="orange", width=1)))
                elif s == "Bollinger Band Squeeze" and "BBUp" in df_view.columns:
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBUp"],  name="BB Upper", line=dict(color="orange", width=1, dash="dot")))
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBLow"], name="BB Lower", line=dict(color="orange", width=1, dash="dot")))
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBMid"], name="BB Mid",   line=dict(color="gray",   width=1)))

                buy_dates   = [t["Entry Date"] for t in log]
                buy_prices  = [t["Entry Price"] for t in log]
                sell_dates  = [t["Exit Date"]  for t in log if t["Status"] == "CLOSED"]
                sell_prices = [t["Exit Price"] for t in log if t["Status"] == "CLOSED"]
                if buy_dates:
                    fig.add_trace(go.Scatter(x=buy_dates,  y=buy_prices,  mode="markers",
                                              name="BUY",  marker=dict(symbol="triangle-up",   color="lime", size=10)))
                if sell_dates:
                    fig.add_trace(go.Scatter(x=sell_dates, y=sell_prices, mode="markers",
                                              name="SELL", marker=dict(symbol="triangle-down", color="red",  size=10)))

                fig.update_layout(template="plotly_dark", height=450,
                                   margin=dict(l=20,r=20,t=30,b=20),
                                   legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Trade Log")
                if log:
                    log_df = pd.DataFrame(log)
                    log_df.rename(columns={"Portfolio": f"Portfolio ({curr})"}, inplace=True)
                    def cr(v):
                        try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                        except: return ""
                    def cst(v):
                        if v == "OPEN":   return "color:#3fb950;font-weight:bold"
                        if v == "CLOSED": return "color:#8b949e"
                        return ""
                    st.dataframe(
                        log_df.style.map(cr, subset=["Return %"]).map(cst, subset=["Status"]),
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No trades triggered.")

else:
    st.markdown("---")
    st.info("Add stocks in the search boxes above, then click a Run button in the sidebar.")