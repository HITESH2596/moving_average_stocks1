import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Global Multi-Market Backtester Pro")
st.title("Global Multi-Market Backtester Pro")
st.markdown("Search any stock · All markets in one backtest · BUY / SELL leaderboard · Watchlist")

# ---------------------------------------------------------------
# DEFAULT TICKERS (full lists)
# ---------------------------------------------------------------
DEFAULT_US = []
DEFAULT_IN = []
DEFAULT_CR = []

# ---------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------
def init_state():
    defaults = {
        "backtest_tickers": DEFAULT_US + DEFAULT_IN + DEFAULT_CR,
        "watchlist":        [],
        "results":          {},
        "run_label":        "",
        "run_currency":     "USD",
        "wl_us":            list(DEFAULT_US),
        "wl_in":            list(DEFAULT_IN),
        "wl_cr":            list(DEFAULT_CR),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ---------------------------------------------------------------
# STRATEGIES
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
# SIDEBAR
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
run_us   = st.sidebar.button("Run US Stocks",     type="primary", use_container_width=True)
run_in   = st.sidebar.button("Run Indian Stocks", type="primary", use_container_width=True)
run_cr   = st.sidebar.button("Run Crypto",        type="primary", use_container_width=True)
run_all  = st.sidebar.button("Run ALL Markets",   use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### Add Stocks to Backtest")
st.sidebar.caption("Search any stock from US, India or Crypto and add it to the backtest pool.")

wl_market = st.sidebar.selectbox("Market", ["US", "India (NSE)", "Crypto"], key="wl_market_sel")
wl_search  = st.sidebar.text_input(
    "Enter ticker",
    placeholder="e.g. AAPL / RELIANCE / BTC",
    key="wl_search_input"
)

if st.sidebar.button("Search & Add", use_container_width=True):
    raw = wl_search.strip().upper().replace(" ", "")
    if raw:
        if wl_market == "India (NSE)" and not raw.endswith(".NS"):
            ticker_try = raw + ".NS"
        elif wl_market == "Crypto" and not raw.endswith("-USD"):
            ticker_try = raw + "-USD"
        else:
            ticker_try = raw

        with st.spinner(f"Validating {ticker_try}..."):
            try:
                info  = yf.Ticker(ticker_try)
                price = info.fast_info.last_price
                name  = info.info.get("shortName", ticker_try)
                if price and float(price) > 0:
                    if wl_market == "US" and ticker_try not in st.session_state.wl_us:
                        st.session_state.wl_us.append(ticker_try)
                    elif wl_market == "India (NSE)" and ticker_try not in st.session_state.wl_in:
                        st.session_state.wl_in.append(ticker_try)
                    elif wl_market == "Crypto" and ticker_try not in st.session_state.wl_cr:
                        st.session_state.wl_cr.append(ticker_try)
                    if ticker_try not in st.session_state.watchlist:
                        st.session_state.watchlist.append(ticker_try)
                    st.sidebar.success(f"Added: {name} ({ticker_try}) @ {round(float(price),2)}")
                else:
                    st.sidebar.error(f"'{ticker_try}' not found. Check ticker.")
            except Exception:
                st.sidebar.error(f"Could not find '{ticker_try}'. Check ticker.")
    else:
        st.sidebar.warning("Please enter a ticker.")

st.sidebar.markdown("---")

# Show all added stocks with remove option
all_added = st.session_state.wl_us + st.session_state.wl_in + st.session_state.wl_cr
if all_added:
    st.sidebar.markdown("**Stocks added to backtest:**")
    for i, t in enumerate(all_added):
        c1, c2 = st.sidebar.columns([4, 1])
        mkt_tag = "🇮🇳" if t.endswith(".NS") else "🪙" if t.endswith("-USD") else "🇺🇸"
        c1.markdown(f"{mkt_tag} `{t.replace('.NS','').replace('-USD','')}`")
        if c2.button("✕", key=f"rm_all_{i}"):
            if t in st.session_state.wl_us:   st.session_state.wl_us.remove(t)
            if t in st.session_state.wl_in:   st.session_state.wl_in.remove(t)
            if t in st.session_state.wl_cr:   st.session_state.wl_cr.remove(t)
            if t in st.session_state.watchlist: st.session_state.watchlist.remove(t)
            st.rerun()
else:
    st.sidebar.info("No stocks added yet. Search above to add stocks.")

# ---------------------------------------------------------------
# DETERMINE WHAT TO RUN
# ---------------------------------------------------------------
run_tickers  = None
run_currency = "USD"
run_label    = ""

if run_us:
    run_tickers  = st.session_state.wl_us
    run_currency = "USD"
    run_label    = "US Stocks"
elif run_in:
    run_tickers  = st.session_state.wl_in
    run_currency = "INR"
    run_label    = "Indian Stocks"
elif run_cr:
    run_tickers  = st.session_state.wl_cr
    run_currency = "USD"
    run_label    = "Crypto"
elif run_all:
    run_tickers  = st.session_state.wl_us + st.session_state.wl_in + st.session_state.wl_cr
    run_currency = "USD"
    run_label    = "All Markets"
elif run_custom:
    run_tickers  = st.session_state.watchlist
    run_currency = "USD"
    run_label    = "My Watchlist"

# ---------------------------------------------------------------
# INDICATOR FUNCTIONS
# ---------------------------------------------------------------
def compute_sma(s, w):     return s.rolling(w).mean()
def compute_ema(s, span):  return s.ewm(span=span, adjust=False).mean()

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

    win_rate  = wins / total * 100 if total > 0 else 0.0
    first_cl  = df[df["Signal"].notna()]["Close"].iloc[0] if not df[df["Signal"].notna()].empty else closes[0]
    bh_pct    = (float(closes[-1]) / float(first_cl) - 1) * 100

    return {"net_pct": round((portfolio/capital-1)*100, 2), "bh_pct": round(bh_pct, 2),
            "end_val": round(portfolio, 2), "win_rate": round(win_rate, 1),
            "trades": total, "log": log, "last_sig": int(signals[-1]),
            "last_price": round(float(closes[-1]), 4)}

# ---------------------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------------------
def run_engine(tickers, strategy, periods, capital):
    results  = {p: [] for p in periods}
    max_days = max(periods.values()) + 250
    total    = len(tickers)
    prog     = st.progress(0)
    status   = st.empty()

    for idx, ticker in enumerate(tickers):
        prog.progress((idx + 1) / total)
        status.caption(f"Processing {ticker} ({idx+1}/{total})...")
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

                # Tag market
                if ticker.endswith(".NS"):   mkt = "India"
                elif ticker.endswith("-USD"): mkt = "Crypto"
                else:                         mkt = "US"

                results[label].append({
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
                })
        except Exception as e:
            status.caption(f"Skipped {ticker}: {e}")
            continue

    prog.empty()
    status.empty()
    for label in results:
        results[label].sort(key=lambda x: x["Net %"], reverse=True)
    return results

# ---------------------------------------------------------------
# RUN
# ---------------------------------------------------------------
if run_tickers is not None:
    if not run_tickers:
        st.warning("No stocks to backtest. Add stocks first.")
    elif not selected_periods:
        st.warning("Select at least one period.")
    else:
        with st.spinner(f"Running backtest for {run_label}..."):
            res = run_engine(run_tickers, strategy_name, selected_periods, capital)
            st.session_state.results     = res
            st.session_state.run_label   = run_label
            st.session_state.run_currency = run_currency

# ---------------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------------
if st.session_state.results:
    res       = st.session_state.results
    run_label = st.session_state.run_label

    st.markdown(f"## Results — {run_label} · {strategy_name}")

    available_periods = [p for p in res if res[p]]
    if not available_periods:
        st.error("No results returned.")
        st.stop()

    period_tabs = st.tabs(available_periods)

    for tab, period_label in zip(period_tabs, available_periods):
        with tab:
            period_data = res[period_label]

            # TOP BUY / TOP SELL lists ranked by Net %
            buy_stocks  = [r for r in period_data if r["Signal"] == "BUY"]
            sell_stocks = [r for r in period_data if r["Signal"] == "SELL"]

            # Top 10 of each
            top_buy  = buy_stocks[:10]
            top_sell = sell_stocks[:10]

            st.markdown("### Signal Summary")
            col_b, col_s = st.columns(2)

            with col_b:
                st.success(f"TOP BUY SIGNALS ({len(buy_stocks)} total)")
                if top_buy:
                    buy_df = pd.DataFrame([{
                        "Ticker":  r["Ticker"].replace(".NS","").replace("-USD",""),
                        "Market":  r["Market"],
                        "Price":   r["Price"],
                        "Strat %": r["Net %"],
                        "B&H %":   r["B&H %"],
                    } for r in top_buy])
                    st.dataframe(
                        buy_df.style.map(
                            lambda v: "color: #3fb950" if isinstance(v, (int,float)) and v >= 0
                                      else ("color: #f85149" if isinstance(v, (int,float)) else ""),
                            subset=["Strat %","B&H %"]
                        ),
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No BUY signals.")

            with col_s:
                st.error(f"TOP SELL / CASH ({len(sell_stocks)} total)")
                if top_sell:
                    sell_df = pd.DataFrame([{
                        "Ticker":  r["Ticker"].replace(".NS","").replace("-USD",""),
                        "Market":  r["Market"],
                        "Price":   r["Price"],
                        "Strat %": r["Net %"],
                        "B&H %":   r["B&H %"],
                    } for r in top_sell])
                    st.dataframe(
                        sell_df.style.map(
                            lambda v: "color: #3fb950" if isinstance(v, (int,float)) and v >= 0
                                      else ("color: #f85149" if isinstance(v, (int,float)) else ""),
                            subset=["Strat %","B&H %"]
                        ),
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No SELL signals.")

            st.markdown("---")

            # FULL LEADERBOARD
            st.subheader("Full Strategy Leaderboard")

            # Filter by market
            mkt_filter = st.radio(
                "Filter by market:",
                ["All", "US", "India", "Crypto"],
                horizontal=True,
                key=f"mkt_filter_{period_label}"
            )
            filtered = period_data if mkt_filter == "All" else [r for r in period_data if r["Market"] == mkt_filter]

            display_df = pd.DataFrame([{
                "Ticker":      r["Ticker"].replace(".NS","").replace("-USD",""),
                "Market":      r["Market"],
                "Price":       r["Price"],
                "Signal":      r["Signal"],
                "Strategy %":  r["Net %"],
                "Buy & Hold %":r["B&H %"],
                "Win Rate %":  r["Win Rate"],
                "Trades":      r["Trades"],
                "End Value":   r["End Value"],
            } for r in filtered])

            def color_signal(val):
                if val == "BUY":  return "background-color:#1a3a1a;color:#3fb950;font-weight:bold"
                if val == "SELL": return "background-color:#3a1a1a;color:#f85149;font-weight:bold"
                return ""

            def color_pct(val):
                try:    return "color:#3fb950" if float(val) >= 0 else "color:#f85149"
                except: return ""

            st.dataframe(
                display_df.style
                    .map(color_signal, subset=["Signal"])
                    .map(color_pct,    subset=["Strategy %","Buy & Hold %"]),
                use_container_width=True, hide_index=True
            )

            st.markdown("---")

            # CHART + TRADE LOG
            st.subheader("Chart & Trade Log")
            ticker_choices  = [r["Ticker"] for r in filtered]
            if not ticker_choices:
                st.info("No tickers to display.")
                continue

            selected_ticker = st.selectbox(
                "Select asset to inspect:",
                options=ticker_choices,
                format_func=lambda x: x.replace(".NS","").replace("-USD",""),
                key=f"sel_{period_label}"
            )
            selected_row = next((r for r in filtered if r["Ticker"] == selected_ticker), None)

            if selected_row:
                df_plot = selected_row["_df"]
                log     = selected_row["_log"]
                curr    = "INR" if selected_ticker.endswith(".NS") else "USD"

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Signal",   selected_row["Signal"])
                m2.metric("Strategy", f"{selected_row['Net %']}%")
                m3.metric("B&H",      f"{selected_row['B&H %']}%")
                m4.metric("Win Rate", f"{selected_row['Win Rate']}%")
                m5.metric("End Val",  f"{curr} {selected_row['End Value']:,.0f}")

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
                    for col, color, name in [("SMA20","cyan","SMA 20"),("SMA50","gold","SMA 50"),("SMA200","magenta","SMA 200")]:
                        if col in df_view.columns:
                            fig.add_trace(go.Scatter(x=df_view.index, y=df_view[col], name=name, line=dict(color=color, width=1)))
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
                sell_dates  = [t["Exit Date"]   for t in log if t["Status"] == "CLOSED"]
                sell_prices = [t["Exit Price"]  for t in log if t["Status"] == "CLOSED"]

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

                    def c_ret(v):
                        try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                        except: return ""
                    def c_stat(v):
                        if v == "OPEN":   return "color:#3fb950;font-weight:bold"
                        if v == "CLOSED": return "color:#8b949e"
                        return ""

                    st.dataframe(
                        log_df.style.map(c_ret, subset=["Return %"]).map(c_stat, subset=["Status"]),
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No trades triggered.")
else:
    st.info("Add stocks using the sidebar search, then click a Run button to start the backtest.")
    st.markdown("""
    **How to use:**
    1. In the sidebar, select market (US / India / Crypto)
    2. Type any ticker name and click **Search & Add**
    3. Add as many stocks as you want across any market
    4. Click **Run US Stocks**, **Run Indian Stocks**, **Run Crypto**, or **Run ALL Markets**
    5. Results show TOP BUY / SELL lists + full leaderboard + chart + trade log
    """)