import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="NSE Total Market Backtester")
st.title("🇮🇳 Total Indian Market Index Backtester Pro")
st.markdown("Select an entire market index block to instantly backtest win rates, transaction counts, and returns over a 1 to 10-year period.")

# Initialize memory storage (Session State)
if "summary_df" not in st.session_state:
    st.session_state.summary_df = None
if "asset_charts" not in st.session_state:
    st.session_state.asset_charts = {}

# --- 1. DYNAMIC INDEX ROSTER FETCHING ENGINE ---
@st.cache_data(ttl=86400)
def fetch_entire_index_pool(index_type):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if index_type == "Nifty 50 (Top Bluechips)":
        url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
    elif index_type == "Nifty Next 50 (Mid-Caps)":
        url = "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv"
    elif index_type == "Nifty 100 (Top 100 Stocks)":
        url = "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"
    else:
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            lines = response.text.split('\n')
            tickers = []
            for line in lines[1:]:
                columns = line.split(',')
                if len(columns) > 2 and columns[2].strip():
                    tickers.append(columns[2].strip())
            return [t for t in tickers if t and t != "Symbol"]
    except Exception:
        pass
    return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "HINDUNILVR", "LT"]

# --- 2. SIDEBAR PARAMETERS ---
st.sidebar.header("⚙️ Market Range Settings")

index_selection = st.sidebar.selectbox(
    "Select Target Index Block",
    options=["Nifty 50 (Top Bluechips)", "Nifty Next 50 (Mid-Caps)", "Nifty 100 (Top 100 Stocks)"]
)

time_option = st.sidebar.selectbox(
    "Select Backtest Horizon",
    options=["10 Years", "5 Years", "3 Years", "1 Year"]
)

initial_capital = st.sidebar.number_input("Starting Capital per Stock (₹)", min_value=1000, value=10000, step=1000)

today_dt = datetime.now()
if time_option == "10 Years":
    start_date = (today_dt - timedelta(days=10*365)).date()
elif time_option == "5 Years":
    start_date = (today_dt - timedelta(days=5*365)).date()
elif time_option == "3 Years":
    start_date = (today_dt - timedelta(days=3*365)).date()
else:
    start_date = (today_dt - timedelta(days=365)).date()
end_date = today_dt.date()

raw_nse_symbols = fetch_entire_index_pool(index_selection)
processed_tickers = [f"{sym}.NS" for sym in raw_nse_symbols if sym]

# --- 3. QUANTITATIVE ANALYSIS BACKTEST ENGINE ---
def run_mass_backtest(tickers, start, end, capital):
    summary_rows = []
    charts_cache = {}
    
    progress_bar = st.progress(0)
    total_count = len(tickers)
    
    extended_start = pd.to_datetime(start) - timedelta(days=365)
    
    for idx, ticker in enumerate(tickers):
        clean_name = ticker.replace(".NS", "")
        progress_bar.progress((idx + 1) / total_count)
        
        try:
            df = yf.download(ticker, start=extended_start, end=end, progress=False)
            if df.empty or len(df) < 200:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            
            df['Signal'] = 0
            buy_rule = (df['SMA_20'] > df['SMA_50']) & (df['SMA_50'] > df['SMA_200'])
            sell_rule = (df['SMA_20'] < df['SMA_50']) | (df['Close'] < df['SMA_200'])
            
            df['Signal'] = np.where(buy_rule, 1, np.where(sell_rule, -1, 0))
            df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
            
            metric_df = df[df.index >= pd.to_datetime(start)].copy()
            if metric_df.empty:
                continue
                
            total_trades = 0
            winning_trades = 0
            position_active = False
            entry_price = 0.0
            
            for index, row in metric_df.iterrows():
                current_sig = row['Signal']
                if current_sig == 1 and not position_active:
                    position_active = True
                    entry_price = float(row['Close'])
                    total_trades += 1
                elif current_sig == -1 and position_active:
                    position_active = False
                    exit_price = float(row['Close'])
                    if exit_price > entry_price:
                        winning_trades += 1
                        
            win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            
            metric_df['Asset_Return'] = metric_df['Close'].pct_change()
            metric_df['Strategy_Return'] = metric_df['Asset_Return'] * metric_df['Signal'].shift(1)
            
            cum_strategy = (1 + metric_df['Strategy_Return'].fillna(0)).cumprod()
            cum_bh = (1 + metric_df['Asset_Return'].fillna(0)).cumprod()
            
            strat_pct = (cum_strategy.iloc[-1] - 1) * 100
            bh_pct = (cum_bh.iloc[-1] - 1) * 100
            ending_cash = capital * cum_strategy.iloc[-1]
            
            summary_rows.append({
                "Ticker": clean_name,
                "Last Price": round(float(metric_df['Close'].iloc[-1]), 2),
                "Condition": "🟢 BUY" if metric_df['Signal'].iloc[-1] == 1 else "🔴 SELL",
                "Strategy Return": f"{round(float(strat_pct), 2)}%",
                "Buy & Hold Return": f"{round(float(bh_pct), 2)}%",
                "Trades": int(total_trades),
                "Success Win Rate": f"{round(win_rate_pct, 1)}%",
                "Ending Value": f"₹{round(float(ending_cash), 2)}"
            })
            charts_cache[clean_name] = df
            
        except Exception:
            pass
            
    progress_bar.empty()
    return pd.DataFrame(summary_rows), charts_cache

# --- 4. RENDER DATA ARCHITECTURE TO UI ---
if st.sidebar.button("🚀 Run Complete Index Backtest", type="primary"):
    with st.spinner(f"Downloading data tables for all assets in {index_selection}..."):
        res_df, res_charts = run_mass_backtest(processed_tickers, start_date, end_date, initial_capital)
        st.session_state.summary_df = res_df
        st.session_state.asset_charts = res_charts

if st.session_state.summary_df is not None and not st.session_state.summary_df.empty:
    st.subheader(f"📊 Live Strategy Screener Matrix ({index_selection})")
    st.dataframe(st.session_state.summary_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("🔍 Individual Technical Chart Analytics")
    
    col1, col2 = st.columns([2, 3])
    with col1:
        chart_options = list(st.session_state.asset_charts.keys())
        selected_chart = st.selectbox("Select a stock to inspect:", options=chart_options)
    
    with col2:
        chart_timeframe = st.radio(
            "Chart Timeframe View:",
            options=["1 Month", "3 Months", "6 Months", "1 Year", "Full Backtest Horizon"],
            index=3,
            horizontal=True
        )
        
    # --- ADDED: NEW LIVE DYNAMIC CARD BLOCK BELOW SPECIFIC ASSET DROPDOWN ---
    if selected_chart in st.session_state.asset_charts:
        # Pull matching data subset row from our stored dataframe match matrix
        match_row = st.session_state.summary_df[st.session_state.summary_df["Ticker"] == selected_chart]
        
        if not match_row.empty:
            st.markdown(f"#### 📈 {selected_chart} Key Metrics Summary")
            m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
            
            with m_col1:
                st.metric(label="Last Market Price", value=f"₹{match_row['Last Price'].values[0]}")
            with m_col2:
                st.metric(label="Strategy Return", value=match_row['Strategy Return'].values[0])
            with m_col3:
                st.metric(label="Success Win Rate", value=match_row['Success Win Rate'].values[0])
            with m_col4:
                st.metric(label="Total Trade Cycles", value=str(match_row['Trades'].values[0]))
            with m_col5:
                st.metric(label="Ending Portfolio Value", value=match_row['Ending Value'].values[0])
        
        st.markdown("<br>", unsafe_allow_html=True) # Adds a clean visual spacing divider
        
        # --- PLOTLY GRAPH DRAWING ---
        raw_df = st.session_state.asset_charts[selected_chart]
        max_available_date = raw_df.index.max()
        
        if chart_timeframe == "1 Month":
            graph_start = max_available_date - timedelta(days=30)
        elif chart_timeframe == "3 Months":
            graph_start = max_available_date - timedelta(days=90)
        elif chart_timeframe == "6 Months":
            graph_start = max_available_date - timedelta(days=180)
        elif chart_timeframe == "1 Year":
            graph_start = max_available_date - timedelta(days=365)
        else:
            graph_start = pd.to_datetime(start_date)
            
        pdf = raw_df[(raw_df.index >= graph_start) & (raw_df.index <= max_available_date)]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], name='Stock Close Price', line=dict(color='white', width=1.5)))
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_20'], name='20 Day Fast SMA', line=dict(color='cyan', width=1)))
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_50'], name='50 Day Medium SMA', line=dict(color='gold', width=1)))
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_200'], name='200 Day Macro Floor', line=dict(color='magenta', width=1.5)))
        
        fig.update_layout(template="plotly_dark", height=500, xaxis_title="Timeline", yaxis_title="Price (INR ₹)")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"💡 Click the blue button in the sidebar to run the strategy across all stocks listed in the {index_selection}.")
