import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Global Multi-Market Backtester Pro")
st.title("Global Multi-Market Backtester Pro")

# ---------------------------------------------------------------
# DEFAULT TICKERS
# ---------------------------------------------------------------
DEFAULT_US = ["AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","AMD","NFLX","V","JPM","MS"]
DEFAULT_IN = ["RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","WIPRO.NS","BAJFINANCE.NS","SBIN.NS","LT.NS","TATAMOTORS.NS"]
DEFAULT_CR = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD"]

# ---------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------
if "results"   not in st.session_state: st.session_state.results   = {}
if "run_label" not in st.session_state: st.session_state.run_label = ""
if "watchlist" not in st.session_state: st.session_state.watchlist = []

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
    "Smart Money Concepts (SMC)",
]

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
run_us  = st.sidebar.button("Run US Stocks",     type="primary", use_container_width=True)
run_in  = st.sidebar.button("Run Indian Stocks", type="primary", use_container_width=True)
run_cr  = st.sidebar.button("Run Crypto",        type="primary", use_container_width=True)
run_all = st.sidebar.button("Run ALL Markets",   use_container_width=True)

# ---------------------------------------------------------------
# INDICATORS
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
# SIGNALS
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

    elif strategy == "Smart Money Concepts (SMC)":
        # HTF trend
        sma50  = compute_sma(df["Close"], 50)
        sma200 = compute_sma(df["Close"], 200)

        # Average body
        body     = (df["Close"] - df["Open"]).abs()
        avg_body = body.rolling(14).mean()
        strong_up = (df["Close"] > df["Open"]) & (body > avg_body * 1.5)
        strong_dn = (df["Close"] < df["Open"]) & (body > avg_body * 1.5)

        # Order Blocks
        ob_bull_top = df["High"].shift(1).where(strong_up, np.nan).ffill()
        ob_bull_bot = df["Low"].shift(1).where(strong_up, np.nan).ffill()
        ob_bear_top = df["High"].shift(1).where(strong_dn, np.nan).ffill()
        ob_bear_bot = df["Low"].shift(1).where(strong_dn, np.nan).ffill()
        in_bull_ob  = (df["Close"] >= ob_bull_bot) & (df["Close"] <= ob_bull_top)
        in_bear_ob  = (df["Close"] >= ob_bear_bot) & (df["Close"] <= ob_bear_top)

        # Fair Value Gap
        bull_fvg = df["Low"] > df["High"].shift(2)
        bear_fvg = df["High"] < df["Low"].shift(2)

        # Break of Structure
        swing_hi = df["High"].rolling(20).max()
        swing_lo = df["Low"].rolling(20).min()
        bos_bull = df["Close"] > swing_hi.shift(1)
        bos_bear = df["Close"] < swing_lo.shift(1)

        # CHoCH — structure shift
        choch_bull = (df["Close"] > sma50) & (df["Close"].shift(1) <= sma50.shift(1))
        choch_bear = (df["Close"] < sma50) & (df["Close"].shift(1) >= sma50.shift(1))

        # Liquidity Sweep — KEY signal, weighted highest
        prev_hi    = df["High"].rolling(20).max().shift(1)
        prev_lo    = df["Low"].rolling(20).min().shift(1)
        bull_sweep = (df["Low"] < prev_lo) & (df["Close"] > prev_lo) & (df["Close"] > df["Open"])
        bear_sweep = (df["High"] > prev_hi) & (df["Close"] < prev_hi) & (df["Close"] < df["Open"])

        # Demand / Supply zones using recent swing lows/highs
        near_demand = df["Close"] <= (prev_lo * 1.05)   # within 5% of swing low
        near_supply = df["Close"] >= (prev_hi * 0.95)   # within 5% of swing high

        # Score — bull sweep + CHoCH weighted heavily
        bull_score = (
            in_bull_ob.astype(int) * 1 +
            bull_fvg.astype(int)   * 1 +
            bull_sweep.astype(int) * 3 +   # strongest signal
            choch_bull.astype(int) * 2 +   # structure shift
            bos_bull.astype(int)   * 2 +
            near_demand.astype(int)* 1
        )
        bear_score = (
            in_bear_ob.astype(int) * 1 +
            bear_fvg.astype(int)   * 1 +
            bear_sweep.astype(int) * 3 +
            choch_bear.astype(int) * 2 +
            bos_bear.astype(int)   * 2 +
            near_supply.astype(int)* 1
        )

        # Also use 200 SMA as macro trend filter
        macro_bull = df["Close"] > sma200
        macro_bear = df["Close"] < sma200

        # Final signal — need score >= 3 AND macro trend alignment
        buy  = (bull_score >= 3) & (bull_score > bear_score)
        sell = (bear_score >= 3) & (bear_score > bull_score) & macro_bear

        df["Signal"] = np.where(buy, 1, np.where(sell, -1, 0))
        df["Signal"] = df["Signal"].replace(0, np.nan).ffill().fillna(-1)
        df["SMC_Bull"] = bull_score
        df["SMC_Bear"] = bear_score

    return df

# ---------------------------------------------------------------
# BACKTEST
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
            log.append({"Status":"CLOSED","Entry Date":entry_date,"Entry Price":round(entry,4),
                         "Exit Date":date,"Exit Price":round(price,4),
                         "Return %":round(ret*100,2),"Portfolio":round(portfolio,2)})
    if in_pos:
        price = float(closes[-1])
        ret   = (price - entry) / entry
        portfolio *= (1 + ret)
        if price > entry: wins += 1
        log.append({"Status":"OPEN","Entry Date":entry_date,"Entry Price":round(entry,4),
                     "Exit Date":"Present","Exit Price":round(price,4),
                     "Return %":round(ret*100,2),"Portfolio":round(portfolio,2)})
    win_rate = wins / total * 100 if total > 0 else 0.0
    first_cl = df[df["Signal"].notna()]["Close"].iloc[0] if not df[df["Signal"].notna()].empty else closes[0]
    bh_pct   = (float(closes[-1]) / float(first_cl) - 1) * 100
    return {"net_pct":round((portfolio/capital-1)*100,2),"bh_pct":round(bh_pct,2),
            "end_val":round(portfolio,2),"win_rate":round(win_rate,1),
            "trades":total,"log":log,"last_sig":int(signals[-1]),"last_price":round(float(closes[-1]),4)}

# ---------------------------------------------------------------
# PROCESS ONE TICKER
# ---------------------------------------------------------------
def process_ticker(ticker, strategy, periods, capital):
    max_days = max(periods.values()) + 250
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=max_days)
    raw = yf.download(ticker, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
    if raw.empty or len(raw) < 60:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    mkt = "India" if ticker.endswith(".NS") else "Crypto" if ticker.endswith("-USD") else "US"
    result = {}
    for label, days in periods.items():
        cutoff   = end_dt - timedelta(days=days)
        slice_df = raw[raw.index >= pd.to_datetime(cutoff)].copy()
        if len(slice_df) < 50:
            continue
        enriched = generate_signals(slice_df, strategy)
        bt       = run_backtest(enriched, capital)
        result[label] = {
            "Ticker":ticker,"Market":mkt,"Price":bt["last_price"],
            "Signal":"BUY" if bt["last_sig"]==1 else "SELL",
            "Net %":bt["net_pct"],"B&H %":bt["bh_pct"],"Win Rate":bt["win_rate"],
            "Trades":bt["trades"],"End Value":bt["end_val"],"_log":bt["log"],"_df":enriched,
        }
    return result

# ---------------------------------------------------------------
# FULL ENGINE
# ---------------------------------------------------------------
def run_engine(tickers, strategy, periods, capital):
    results = {p: [] for p in periods}
    prog    = st.progress(0)
    status  = st.empty()
    for idx, ticker in enumerate(tickers):
        prog.progress((idx+1)/len(tickers))
        status.caption(f"Processing {ticker} ({idx+1}/{len(tickers)})...")
        try:
            rows = process_ticker(ticker, strategy, periods, capital)
            if rows:
                for label, row in rows.items():
                    results[label].append(row)
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
if run_us and selected_periods:
    with st.spinner("Running US Stocks..."):
        st.session_state.results   = run_engine(DEFAULT_US, strategy_name, selected_periods, capital)
        st.session_state.run_label = "US Stocks"
elif run_in and selected_periods:
    with st.spinner("Running Indian Stocks..."):
        st.session_state.results   = run_engine(DEFAULT_IN, strategy_name, selected_periods, capital)
        st.session_state.run_label = "Indian Stocks"
elif run_cr and selected_periods:
    with st.spinner("Running Crypto..."):
        st.session_state.results   = run_engine(DEFAULT_CR, strategy_name, selected_periods, capital)
        st.session_state.run_label = "Crypto"
elif run_all and selected_periods:
    with st.spinner("Running ALL Markets..."):
        st.session_state.results   = run_engine(DEFAULT_US+DEFAULT_IN+DEFAULT_CR, strategy_name, selected_periods, capital)
        st.session_state.run_label = "All Markets"

# ---------------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------------
if st.session_state.results:
    res       = st.session_state.results
    run_label = st.session_state.run_label
    st.markdown(f"## Results — {run_label} · {strategy_name}")

    available_periods = [p for p in res if res[p]]
    if not available_periods:
        st.error("No results. Try a longer period.")
        st.stop()

    period_tabs = st.tabs(available_periods)

    for tab, period_label in zip(period_tabs, available_periods):
        with tab:
            period_data = res[period_label]

            def pct_color(v):
                try: return "color:#3fb950" if float(v) >= 0 else "color:#f85149"
                except: return ""

            def sig_color(v):
                if v == "BUY":  return "background-color:#1a3a1a;color:#3fb950;font-weight:bold"
                if v == "SELL": return "background-color:#3a1a1a;color:#f85149;font-weight:bold"
                return ""

            buy_stocks  = [r for r in period_data if r["Signal"] == "BUY"]
            sell_stocks = [r for r in period_data if r["Signal"] == "SELL"]

            # BUY / SELL tables
            st.markdown("### Signal Summary")
            col_b, col_s = st.columns(2)

            with col_b:
                st.success(f"BUY Signals — {len(buy_stocks)} stocks")
                if buy_stocks:
                    buy_df = pd.DataFrame([{
                        "Ticker":   r["Ticker"].replace(".NS","").replace("-USD",""),
                        "Market":   r["Market"],
                        "Price":    r["Price"],
                        "Strat %":  r["Net %"],
                        "B&H %":    r["B&H %"],
                        "Win Rate": r["Win Rate"],
                    } for r in buy_stocks])
                    st.dataframe(buy_df.style.map(pct_color, subset=["Strat %","B&H %"]),
                                 use_container_width=True, hide_index=True)
                else:
                    st.info("No BUY signals.")

            with col_s:
                st.error(f"SELL / CASH — {len(sell_stocks)} stocks")
                if sell_stocks:
                    sell_df = pd.DataFrame([{
                        "Ticker":   r["Ticker"].replace(".NS","").replace("-USD",""),
                        "Market":   r["Market"],
                        "Price":    r["Price"],
                        "Strat %":  r["Net %"],
                        "B&H %":    r["B&H %"],
                        "Win Rate": r["Win Rate"],
                    } for r in sell_stocks])
                    st.dataframe(sell_df.style.map(pct_color, subset=["Strat %","B&H %"]),
                                 use_container_width=True, hide_index=True)
                else:
                    st.info("No SELL signals.")

            # WATCHLIST
            if st.session_state.watchlist:
                st.markdown("---")
                st.markdown("### My Watchlist")
                wl_rows = [r for r in period_data if r["Ticker"] in st.session_state.watchlist]
                if wl_rows:
                    wl_df = pd.DataFrame([{
                        "Ticker":  r["Ticker"].replace(".NS","").replace("-USD",""),
                        "Market":  r["Market"],
                        "Price":   r["Price"],
                        "Signal":  r["Signal"],
                        "Strat %": r["Net %"],
                        "B&H %":   r["B&H %"],
                    } for r in wl_rows])
                    st.dataframe(
                        wl_df.style.map(sig_color, subset=["Signal"]).map(pct_color, subset=["Strat %","B&H %"]),
                        use_container_width=True, hide_index=True
                    )

            st.markdown("---")

            # FULL LEADERBOARD
            st.subheader("Full Leaderboard")
            mkt_filter = st.radio("Filter:", ["All","US","India","Crypto"],
                                   horizontal=True, key=f"mkt_{period_label}")
            filtered = period_data if mkt_filter == "All" else [r for r in period_data if r["Market"] == mkt_filter]

            if filtered:
                disp_df = pd.DataFrame([{
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
                st.dataframe(
                    disp_df.style.map(sig_color, subset=["Signal"]).map(pct_color, subset=["Strategy %","Buy & Hold %"]),
                    use_container_width=True, hide_index=True
                )

            st.markdown("---")

            # CHART & TRADE LOG — single search with suggestions
            st.subheader("Chart & Trade Log")

            ch1, ch2 = st.columns([3, 1])
            with ch1:
                chart_search = st.text_input(
                    "Stock",
                    placeholder="Type ticker or company name e.g. USAR, Apple, Reliance...",
                    label_visibility="collapsed",
                    key=f"chart_search_{period_label}"
                )
            with ch2:
                chart_mkt = st.selectbox(
                    "Mkt", ["US", "India (NSE)", "Crypto"],
                    label_visibility="collapsed",
                    key=f"chart_mkt_{period_label}"
                )

            # Live suggestions as user types
            final_ticker = None
            if chart_search.strip() and len(chart_search.strip()) >= 2:
                try:
                    sq = yf.Search(chart_search.strip(), max_results=7).quotes
                    suggestions = [
                        f"{q.get('symbol','')} — {q.get('shortname') or q.get('longname','')}"
                        for q in sq if q.get("symbol")
                    ]
                    if suggestions:
                        chosen = st.selectbox(
                            "Pick:",
                            suggestions,
                            key=f"suggest_{period_label}",
                            label_visibility="collapsed"
                        )
                        if chosen:
                            final_ticker = chosen.split(" — ")[0].strip()
                except Exception:
                    pass

            chart_go = st.button("Search & View Chart",
                                  key=f"chart_go_{period_label}",
                                  use_container_width=True,
                                  type="primary")

            if chart_go:
                if final_ticker:
                    raw_t = final_ticker
                elif chart_search.strip():
                    raw_t = chart_search.strip().upper().replace(" ", "")
                    if chart_mkt == "India (NSE)" and not raw_t.endswith(".NS"):
                        raw_t = raw_t + ".NS"
                    elif chart_mkt == "Crypto" and not raw_t.endswith("-USD"):
                        raw_t = raw_t + "-USD"
                else:
                    raw_t = None

                if raw_t:
                    st.session_state[f"chart_sel_{period_label}"] = raw_t
                    if not any(r["Ticker"] == raw_t for r in period_data):
                        with st.spinner(f"Fetching & backtesting {raw_t}..."):
                            try:
                                new_rows = process_ticker(raw_t, strategy_name, selected_periods, capital)
                                if new_rows and period_label in new_rows:
                                    st.session_state.results[period_label].append(new_rows[period_label])
                                    st.session_state.results[period_label].sort(key=lambda x: x["Net %"], reverse=True)
                                    st.rerun()
                                else:
                                    st.error(f"No data for '{raw_t}'. Check ticker.")
                                    st.session_state[f"chart_sel_{period_label}"] = None
                            except Exception as e:
                                st.error(f"Error: {e}")
                                st.session_state[f"chart_sel_{period_label}"] = None
                    else:
                        st.rerun()

            # Determine which stock to show
            sel_ticker = st.session_state.get(f"chart_sel_{period_label}")
            row = None
            if sel_ticker:
                row = next((r for r in period_data if r["Ticker"] == sel_ticker), None)
            if row is None and period_data:
                row = period_data[0]
                sel_ticker = row["Ticker"]

            if row:
                df_plot = row["_df"]
                log     = row["_log"]
                curr    = "INR" if sel_ticker.endswith(".NS") else "USD"
                lbl     = sel_ticker.replace(".NS","").replace("-USD","")
                in_wl   = sel_ticker in st.session_state.watchlist

                st.markdown(f"#### {lbl} — {row['Market']}")
                m1, m2, m3, m4, m5 = st.columns(5)
                sig_col = "#3fb950" if row["Signal"] == "BUY" else "#f85149"
                m1.markdown(f"**Signal**<br><span style='color:{sig_col};font-size:20px;font-weight:bold'>{row['Signal']}</span>", unsafe_allow_html=True)
                m2.metric("Strategy",  f"{row['Net %']}%")
                m3.metric("B&H",       f"{row['B&H %']}%")
                m4.metric("Win Rate",  f"{row['Win Rate']}%")
                m5.metric("End Value", f"{curr} {row['End Value']:,.0f}")

                if in_wl:
                    if st.button(f"Remove {lbl} from Watchlist", key=f"wl_chart_{period_label}"):
                        st.session_state.watchlist.remove(sel_ticker)
                        st.rerun()
                else:
                    if st.button(f"Add {lbl} to Watchlist", key=f"wl_chart_{period_label}", type="primary"):
                        st.session_state.watchlist.append(sel_ticker)
                        st.rerun()

                tf_choice = st.radio("View:", ["1M","3M","6M","1Y","Full"], index=4,
                                     horizontal=True, key=f"tf_{period_label}_{sel_ticker}")
                tf_map  = {"1M":30,"3M":90,"6M":180,"1Y":365}
                df_view = df_plot if tf_choice == "Full" else \
                          df_plot[df_plot.index >= df_plot.index.max() - timedelta(days=tf_map[tf_choice])]

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Close"],
                                          name="Price", line=dict(color="white", width=1.5)))
                s = strategy_name
                if s in ["Triple SMA Ribbon (20/50/200)", "Mean Reversion - Dip Buy"]:
                    for c_n, color, nm in [("SMA20","cyan","SMA 20"),("SMA50","gold","SMA 50"),("SMA200","magenta","SMA 200")]:
                        if c_n in df_view.columns:
                            fig.add_trace(go.Scatter(x=df_view.index, y=df_view[c_n], name=nm, line=dict(color=color, width=1)))
                elif s == "LuxAlgo ATR Channel" and "Band" in df_view.columns:
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["Band"], name="ATR Band",
                                              line=dict(color="lime", width=1.5, dash="dot")))
                elif s == "MACD Momentum" and "MACD" in df_view.columns:
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACD"],    name="MACD",
                                              line=dict(color="cyan", width=1)))
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["MACDSig"], name="Signal",
                                              line=dict(color="magenta", width=1, dash="dot")))
                elif s == "EMA 9/21 Ribbon" and "EMA9" in df_view.columns:
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA9"],  name="EMA 9",
                                              line=dict(color="lime", width=1)))
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["EMA21"], name="EMA 21",
                                              line=dict(color="orange", width=1)))
                elif s == "Smart Money Concepts (SMC)":
                    try:
                        sma50_v = compute_sma(df_view["Close"], min(50, len(df_view)))
                        fig.add_trace(go.Scatter(
                            x=df_view.index, y=sma50_v,
                            name="SMA 50", line=dict(color="orange", width=1, dash="dot")
                        ))
                        sma200_v = compute_sma(df_view["Close"], min(200, len(df_view)))
                        fig.add_trace(go.Scatter(
                            x=df_view.index, y=sma200_v,
                            name="SMA 200", line=dict(color="magenta", width=1.5, dash="dot")
                        ))
                        # Mark liquidity sweeps
                        roll_n = min(20, len(df_view) - 1)
                        if roll_n > 2:
                            prev_lo = df_view["Low"].rolling(roll_n).min().shift(1)
                            bull_sweep_mask = (
                                (df_view["Low"] < prev_lo) &
                                (df_view["Close"] > df_view["Open"])
                            ).fillna(False)
                            sweep_dates  = df_view.index[bull_sweep_mask].tolist()
                            sweep_prices = df_view["Low"][bull_sweep_mask].tolist()
                            if sweep_dates:
                                fig.add_trace(go.Scatter(
                                    x=sweep_dates[-10:], y=sweep_prices[-10:],
                                    mode="markers", name="Liq Sweep",
                                    marker=dict(symbol="triangle-up", color="lime", size=12)
                                ))
                    except Exception:
                        pass
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBUp"],  name="BB Upper",
                                              line=dict(color="orange", width=1, dash="dot")))
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBLow"], name="BB Lower",
                                              line=dict(color="orange", width=1, dash="dot")))
                    fig.add_trace(go.Scatter(x=df_view.index, y=df_view["BBMid"], name="BB Mid",
                                              line=dict(color="gray", width=1)))

                buy_dates   = [t["Entry Date"] for t in log]
                buy_prices  = [t["Entry Price"] for t in log]
                sell_dates  = [t["Exit Date"]   for t in log if t["Status"] == "CLOSED"]
                sell_prices = [t["Exit Price"]  for t in log if t["Status"] == "CLOSED"]
                if buy_dates:
                    fig.add_trace(go.Scatter(x=buy_dates, y=buy_prices, mode="markers",
                                              name="BUY", marker=dict(symbol="triangle-up", color="lime", size=10)))
                if sell_dates:
                    fig.add_trace(go.Scatter(x=sell_dates, y=sell_prices, mode="markers",
                                              name="SELL", marker=dict(symbol="triangle-down", color="red", size=10)))

                fig.update_layout(template="plotly_dark", height=450,
                                   margin=dict(l=20,r=20,t=30,b=20),
                                   legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Trade Log")
                if log:
                    log_df = pd.DataFrame(log)
                    log_df.rename(columns={"Portfolio": f"Portfolio ({curr})"}, inplace=True)
                    def cr(v):
                        try: return "color:#3fb950" if float(v) >= 0 else "color:#f85149"
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
    st.info("Select a strategy and click a Run button in the sidebar to start.")