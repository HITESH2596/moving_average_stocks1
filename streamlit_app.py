
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Global Multi-Market Backtester Pro")
st.title("Global Multi-Market Backtester Pro")
st.markdown("6 Strategies · 1Y / 5Y / 10Y Periods · Live BUY/SELL Screener · Trade Ledger")

# ---------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------
if "results" not in st.session_state:
    st.session_state.results = {}
if "charts" not in st.session_state:
    st.session_state.charts = {}

# ---------------------------------------------------------------
# MARKET DEFINITIONS
# ---------------------------------------------------------------
MARKETS = {
    "US Tech & Bluechips": {
        "tickers": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD", "NFLX", "V", "JPM", "MS"],
        "currency": "USD"
    },
    "Indian Markets (NSE)": {
        "tickers": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
                    "AXISBANK.NS", "WIPRO.NS", "BAJFINANCE.NS", "SBIN.NS", "LT.NS"],
        "currency": "INR"
    },
    "Crypto Majors": {
        "tickers": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "LINK-USD"],
        "currency": "USD"
    },
    "Global Commodities": {
        "tickers": ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F"],
        "currency": "USD"
    },
}

STRATEGIES = [
    "Triple SMA Ribbon (20/50/200)",
    "LuxAlgo ATR Channel",
    "MACD Momentum",
    "Mean Reversion - Dip Buy",
    "EMA 9/21 Ribbon",
    "Bollinger Band Squeeze",
]

PERIODS = {
    "1 Year":  365,
    "5 Years": 1825,
    "10 Years": 3650,
}

# ---------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------
st.sidebar.header("Strategy Parameters")

market_name = st.sidebar.selectbox("Select Market", list(MARKETS.keys()))
currency = MARKETS[market_name]["currency"]
tickers = MARKETS[market_name]["tickers"]

strategy_name = st.sidebar.selectbox("Select Strategy", STRATEGIES)

st.sidebar.markdown("**Backtest Periods**")
use_1y  = st.sidebar.checkbox("1 Year",   value=True)
use_5y  = st.sidebar.checkbox("5 Years",  value=True)
use_10y = st.sidebar.checkbox("10 Years", value=True)

selected_periods = {}
if use_1y:  selected_periods["1Y"]  = 365
if use_5y:  selected_periods["5Y"]  = 1825
if use_10y: selected_periods["10Y"] = 3650

capital = st.sidebar.number_input("Starting Capital per Asset", min_value=1000, value=100000, step=5000)

run_btn = st.sidebar.button("Run Backtest", type="primary")

# ---------------------------------------------------------------
# INDICATOR FUNCTIONS
# ---------------------------------------------------------------
def compute_sma(series, window):
    return series.rolling(window=window).mean()

def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def compute_atr(df, period=14):
    hl  = df["High"] - df["Low"]
    hcp = (df["High"] - df["Close"].shift(1)).abs()
    lcp = (df["Low"]  - df["Close"].shift(1)).abs()
    tr  = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def compute_bb(series, window=20, num_std=2):
    mid   = series.rolling(window).mean()
    std   = series.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower

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
        mid   = (df["High"] + df["Low"]) / 2
        tf    = mid - 3.0 * df["ATR"]
        tc    = mid + 3.0 * df["ATR"]
        floor  = [0.0] * len(df)
        ceil_v = [0.0] * len(df)
        signals = [0] * len(df)
        closes  = df["Close"].values
        tf_v    = tf.values
        tc_v    = tc.values
        for i in range(1, len(df)):
            floor[i]  = max(tf_v[i], floor[i-1])  if closes[i-1] > floor[i-1]  else tf_v[i]
            ceil_v[i] = min(tc_v[i], ceil_v[i-1]) if closes[i-1] < ceil_v[i-1] else tc_v[i]
            if   closes[i] > ceil_v[i]:  signals[i] =  1
            elif closes[i] < floor[i]:   signals[i] = -1
            else:                         signals[i] =  signals[i-1]
        df["Signal"] = signals
        df["Band"]   = np.where(df["Signal"] == 1,
                                pd.Series(floor,  index=df.index),
                                pd.Series(ceil_v, index=df.index))

    elif strategy == "MACD Momentum":
        df["EMA12"]    = compute_ema(df["Close"], 12)
        df["EMA26"]    = compute_ema(df["Close"], 26)
        df["MACD"]     = df["EMA12"] - df["EMA26"]
        df["MACDSig"]  = compute_ema(df["MACD"], 9)
        df["Signal"]   = np.where(df["MACD"] > df["MACDSig"], 1, -1)

    elif strategy == "Mean Reversion - Dip Buy":
        df["SMA20"]  = compute_sma(df["Close"], 20)
        df["SMA50"]  = compute_sma(df["Close"], 50)
        df["SMA200"] = compute_sma(df["Close"], 200)
        buy  = (df["SMA200"] > df["SMA50"]) & (df["SMA50"] > df["SMA20"]) & (df["Close"] < df["SMA20"])
        sell = (df["Close"] > df["SMA50"])
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    elif strategy == "EMA 9/21 Ribbon":
        df["EMA9"]  = compute_ema(df["Close"], 9)
        df["EMA21"] = compute_ema(df["Close"], 21)
        df["Signal"] = np.where(df["EMA9"] > df["EMA21"], 1, -1)

    elif strategy == "Bollinger Band Squeeze":
        df["SMA20"] = compute_sma(df["Close"], 20)
        df["RSI"]   = compute_rsi(df["Close"], 14)
        df["BBUp"], df["BBMid"], df["BBLow"] = compute_bb(df["Close"], 20, 2)
        buy  = (df["Close"] < df["BBLow"])  & (df["RSI"] < 35)
        sell = (df["Close"] > df["BBUp"])   | (df["RSI"] > 65)
        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)

    return df

# ---------------------------------------------------------------
# BACKTEST ENGINE
# ---------------------------------------------------------------
def run_backtest(df, capital):
    trades_log  = []
    in_position = False
    entry_price = 0.0
    entry_date  = None
    portfolio   = float(capital)
    wins        = 0
    total       = 0

    signals = df["Signal"].values
    closes  = df["Close"].values
    dates   = df.index

    for i in range(len(df)):
        sig   = signals[i]
        price = float(closes[i])
        date  = dates[i].strftime("%Y-%m-%d")

        if sig == 1 and not in_position:
            in_position = True
            entry_price = price
            entry_date  = date
            total += 1

        elif sig == -1 and in_position:
            in_position = False
            ret         = (price - entry_price) / entry_price
            portfolio  *= (1 + ret)
            if price > entry_price:
                wins += 1
            trades_log.append({
                "Type":          "CLOSED",
                "Entry Date":    entry_date,
                "Entry Price":   round(entry_price, 4),
                "Exit Date":     date,
                "Exit Price":    round(price, 4),
                "Trade Return":  round(ret * 100, 2),
                "Portfolio Val": round(portfolio, 2),
            })
            entry_price = 0.0

    if in_position:
        price  = float(closes[-1])
        ret    = (price - entry_price) / entry_price
        portfolio *= (1 + ret)
        if price > entry_price:
            wins += 1
        trades_log.append({
            "Type":          "OPEN",
            "Entry Date":    entry_date,
            "Entry Price":   round(entry_price, 4),
            "Exit Date":     "Present",
            "Exit Price":    round(price, 4),
            "Trade Return":  round(ret * 100, 2),
            "Portfolio Val": round(portfolio, 2),
        })

    win_rate  = (wins / total * 100) if total > 0 else 0.0
    net_pct   = (portfolio / capital - 1) * 100

    first_valid = df[df["Signal"].notna()]["Close"].iloc[0] if not df[df["Signal"].notna()].empty else closes[0]
    bh_pct = (float(closes[-1]) / float(first_valid) - 1) * 100

    return {
        "net_pct":    round(net_pct, 2),
        "bh_pct":     round(bh_pct, 2),
        "end_val":    round(portfolio, 2),
        "win_rate":   round(win_rate, 1),
        "trades":     total,
        "log":        trades_log,
        "last_sig":   int(signals[-1]),
        "last_price": round(float(closes[-1]), 4),
    }

# ---------------------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------------------
def run_engine(tickers, strategy, periods, capital):
    results  = {p: [] for p in periods}
    charts   = {}
    max_days = max(periods.values()) + 250

    progress = st.progress(0)
    total    = len(tickers)

    for idx, ticker in enumerate(tickers):
        progress.progress((idx + 1) / total)
        try:
            end_dt   = datetime.now()
            start_dt = end_dt - timedelta(days=max_days)
            raw = yf.download(ticker, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 60:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            charts[ticker] = raw

            for label, days in periods.items():
                cutoff = end_dt - timedelta(days=days)
                slice_df = raw[raw.index >= pd.to_datetime(cutoff)].copy()
                if len(slice_df) < 50:
                    continue
                enriched = generate_signals(slice_df, strategy)
                bt = run_backtest(enriched, capital)
                results[label].append({
                    "Ticker":     ticker,
                    "Price":      bt["last_price"],
                    "Signal":     "BUY" if bt["last_sig"] == 1 else "SELL",
                    "Net %":      bt["net_pct"],
                    "B&H %":      bt["bh_pct"],
                    "Win Rate":   bt["win_rate"],
                    "Trades":     bt["trades"],
                    "End Value":  bt["end_val"],
                    "_log":       bt["log"],
                    "_df":        enriched,
                })

        except Exception as e:
            st.warning(f"Skipped {ticker}: {e}")
            continue

    progress.empty()

    for label in results:
        results[label].sort(key=lambda x: x["Net %"], reverse=True)

    return results, charts

# ---------------------------------------------------------------
# RUN
# ---------------------------------------------------------------
if run_btn:
    if not selected_periods:
        st.warning("Please select at least one period.")
    else:
        with st.spinner("Running backtest across all assets..."):
            res, chts = run_engine(tickers, strategy_name, selected_periods, capital)
            st.session_state.results = res
            st.session_state.charts  = chts

# ---------------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------------
if st.session_state.results:
    res = st.session_state.results

    # Period tab selector
    available_periods = [p for p in res if res[p]]
    if not available_periods:
        st.error("No results. Try different settings.")
        st.stop()

    period_tabs = st.tabs(available_periods)

    for tab, period_label in zip(period_tabs, available_periods):
        with tab:
            period_data = res[period_label]

            # BUY / SELL signal lists
            buy_list  = [r["Ticker"].replace(".NS","") for r in period_data if r["Signal"] == "BUY"]
            sell_list = [r["Ticker"].replace(".NS","") for r in period_data if r["Signal"] == "SELL"]

            col_b, col_s = st.columns(2)
            with col_b:
                st.success("BUY Signals: " + ("  |  ".join(buy_list) if buy_list else "None"))
            with col_s:
                st.error("SELL / CASH: " + ("  |  ".join(sell_list) if sell_list else "None"))

            st.markdown("---")

            # Leaderboard table
            st.subheader("Strategy Leaderboard")
            display_df = pd.DataFrame([{
                "Ticker":         r["Ticker"].replace(".NS",""),
                "Price":          r["Price"],
                "Signal":         r["Signal"],
                f"Strategy %":    r["Net %"],
                "Buy & Hold %":   r["B&H %"],
                "Win Rate %":     r["Win Rate"],
                "Total Trades":   r["Trades"],
                f"End Value ({currency})": r["End Value"],
            } for r in period_data])

            def color_signal(val):
                if val == "BUY":  return "background-color: #1a3a1a; color: #3fb950; font-weight: bold"
                if val == "SELL": return "background-color: #3a1a1a; color: #f85149; font-weight: bold"
                return ""

            def color_pct(val):
                try:
                    v = float(val)
                    return "color: #3fb950" if v >= 0 else "color: #f85149"
                except:
                    return ""

            styled = display_df.style \
                .map(color_signal, subset=["Signal"]) \
                .map(color_pct, subset=[f"Strategy %", "Buy & Hold %"])

            st.dataframe(styled, use_container_width=True, hide_index=True)

            st.markdown("---")

            # Chart + Trade Log section
            st.subheader("Technical Chart & Trade Log")
            ticker_choices = [r["Ticker"] for r in period_data]
            selected_ticker = st.selectbox(
                "Select asset to inspect:",
                options=ticker_choices,
                format_func=lambda x: x.replace(".NS",""),
                key=f"ticker_select_{period_label}"
            )

            selected_row = next((r for r in period_data if r["Ticker"] == selected_ticker), None)

            if selected_row:
                df_plot = selected_row["_df"]
                log     = selected_row["_log"]

                # Metrics
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Signal",          selected_row["Signal"])
                m2.metric("Strategy Return", f"{selected_row['Net %']}%")
                m3.metric("Buy & Hold",      f"{selected_row['B&H %']}%")
                m4.metric("Win Rate",        f"{selected_row['Win Rate']}%")
                m5.metric("End Value",       f"{currency} {selected_row['End Value']:,.0f}")

                # Chart timeframe selector
                tf_choice = st.radio(
                    "Chart View:",
                    ["1M", "3M", "6M", "1Y", "Full"],
                    index=4,
                    horizontal=True,
                    key=f"tf_{period_label}_{selected_ticker}"
                )
                tf_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
                if tf_choice != "Full":
                    cutoff_dt = df_plot.index.max() - timedelta(days=tf_map[tf_choice])
                    df_view   = df_plot[df_plot.index >= cutoff_dt]
                else:
                    df_view   = df_plot

                # Build chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_view.index, y=df_view["Close"],
                    name="Price", line=dict(color="white", width=1.5)
                ))

                strat = strategy_name
                if strat == "Triple SMA Ribbon (20/50/200)" or strat == "Mean Reversion - Dip Buy":
                    for col, color, name in [("SMA20","cyan","SMA 20"), ("SMA50","gold","SMA 50"), ("SMA200","magenta","SMA 200")]:
                        if col in df_view.columns:
                            fig.add_trace(go.Scatter(x=df_view.index, y=df_view[col], name=name, line=dict(color=color, width=1)))

                elif strat == "LuxAlgo ATR Channel":
                    if "Band" in df_view.columns:
                        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Band"], name="ATR Band", line=dict(color="lime", width=1.5, dash="dot")))

                elif strat == "MACD Momentum":
                    if "MACD" in df_view.columns:
                        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACD"],    name="MACD",   line=dict(color="cyan",    width=1)))
                        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACDSig"], name="Signal", line=dict(color="magenta", width=1, dash="dot")))

                elif strat == "EMA 9/21 Ribbon":
                    if "EMA9" in df_view.columns:
                        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA9"],  name="EMA 9",  line=dict(color="lime",   width=1)))
                        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA21"], name="EMA 21", line=dict(color="orange", width=1)))

                elif strat == "Bollinger Band Squeeze":
                    if "BBUp" in df_view.columns:
                        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBUp"],  name="BB Upper", line=dict(color="orange", width=1, dash="dot")))
                        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBLow"], name="BB Lower", line=dict(color="orange", width=1, dash="dot")))
                        fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBMid"], name="BB Mid",   line=dict(color="gray",   width=1)))

                # Buy/Sell markers from trade log
                buy_dates  = [t["Entry Date"] for t in log]
                buy_prices = [t["Entry Price"] for t in log]
                sell_dates  = [t["Exit Date"]  for t in log if t["Type"] == "CLOSED"]
                sell_prices = [t["Exit Price"] for t in log if t["Type"] == "CLOSED"]

                if buy_dates:
                    fig.add_trace(go.Scatter(
                        x=buy_dates, y=buy_prices, mode="markers",
                        name="BUY Entry", marker=dict(symbol="triangle-up", color="lime", size=10)
                    ))
                if sell_dates:
                    fig.add_trace(go.Scatter(
                        x=sell_dates, y=sell_prices, mode="markers",
                        name="SELL Exit", marker=dict(symbol="triangle-down", color="red", size=10)
                    ))

                fig.update_layout(
                    template="plotly_dark",
                    height=450,
                    margin=dict(l=20, r=20, t=30, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

                # Trade Log
                st.subheader("Trade Log")
                if log:
                    log_df = pd.DataFrame(log)
                    log_df.rename(columns={
                        "Type":         "Status",
                        "Trade Return": "Return %",
                        "Portfolio Val": f"Portfolio ({currency})"
                    }, inplace=True)

                    def color_trade(val):
                        try:
                            v = float(val)
                            return "color: #3fb950" if v >= 0 else "color: #f85149"
                        except:
                            return ""

                    def color_status(val):
                        if val == "OPEN":   return "color: #3fb950; font-weight: bold"
                        if val == "CLOSED": return "color: #8b949e"
                        return ""

                    log_styled = log_df.style \
                        .map(color_trade,  subset=["Return %"]) \
                        .map(color_status, subset=["Status"])
                    st.dataframe(log_styled, use_container_width=True, hide_index=True)
                else:
                    st.info("No trades triggered in this period.")

else:
    st.info("Configure your parameters in the sidebar and click Run Backtest.")