import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="NSE Total Market Backtester")
st.title("🇮🇳 Total Indian Market Index Backtester Pro")
st.markdown("Select an entire market index block to run macro metrics, then use the workspace below to zoom into localized timeframes with a cumulative compounding ₹1 Lakh strategy.")

# Initialize session memory cache arrays
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
        return ["RELIANCE", "TCS", "HDFCBANK"]

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
index_selection = st.sidebar.selectbox("Select Target Index Block", options=["Nifty 50 (Top Bluechips)", "Nifty Next 50 (Mid-Caps)", "Nifty 100 (Top 100 Stocks)"])
time_option = st.sidebar.selectbox("Select Core Backtest Horizon", options=["10 Years", "5 Years", "3 Years", "1 Year"])
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
            # FIXED STRATEGY EXIT RULE: Using Close < SMA_50 to fix the early shakeout problem
            sell_rule = (df['Close'] < df['SMA_50']) | (df['Close'] < df['SMA_200'])
            
            df['Signal'] = np.where(buy_rule, 1, np.where(sell_rule, -1, 0))
            df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
            
            metric_df = df[df.index >= pd.to_datetime(start)].copy()
            if metric_df.empty:
                continue
                
            summary_rows.append({
                "Ticker": clean_name,
                "Last Price": round(float(metric_df['Close'].iloc[-1]), 2),
                "Condition": "🟢 BUY" if metric_df['Signal'].iloc[-1] == 1 else "🔴 SELL"
            })
            charts_cache[clean_name] = df
            
        except Exception:
            pass
            
    progress_bar.empty()
    return pd.DataFrame(summary_rows), charts_cache

# --- 4. RENDER DATA ARCHITECTURE TO UI ---
if st.sidebar.button("🚀 Run Complete Index Backtest", type="primary"):
    with st.spinner(f"Downloading metrics for all assets in {index_selection}..."):
        res_df, res_charts = run_mass_backtest(processed_tickers, start_date, end_date, initial_capital)
        st.session_state.summary_df = res_df
        st.session_state.asset_charts = res_charts

if st.session_state.summary_df is not None and not st.session_state.summary_df.empty:
    st.subheader(f"📊 Market Overview Overview ({index_selection})")
    st.dataframe(st.session_state.summary_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("🔍 Localized Timeframe Workspace (₹1,00,000 Total Cumulative Simulation)")
    
    col1, col2 = st.columns([2, 3])
    with col1:
        chart_options = list(st.session_state.asset_charts.keys())
        selected_chart = st.selectbox("Select a stock to evaluate:", options=chart_options)
    with col2:
        chart_timeframe = st.radio(
            "Select Timeframe View:",
            options=["1 Month", "3 Months", "6 Months", "1 Year", "Full Backtest Horizon"],
            index=3,
            horizontal=True
        )
        
    if selected_chart in st.session_state.asset_charts:
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
            
        pdf = raw_df[(raw_df.index >= graph_start) & (raw_df.index <= max_available_date)].copy()
        
        # --- CUMULATIVE MULTI-TRADE TIMEFRAME CALCULATOR ---
        local_trades_log = []
        total_trades = 0
        winning_trades = 0
        position_active = False
        entry_price = 0.0
        entry_date = None
        
        running_portfolio_capital = 100000.0  # Starts with exactly ₹1 Lakh
        
        # Check if the stock starts the timeframe already inside an active buy signal
        if not pdf.empty and pdf['Signal'].iloc[0] == 1:
            position_active = True
            entry_price = float(pdf['Close'].iloc[0])
            entry_date = pdf.index[0].strftime('%Y-%m-%d')
            total_trades += 1

        for index, row in pdf.iterrows():
            current_sig = row['Signal']
            current_close = float(row['Close'])
            
            # Action: Trigger Buy Setup
            if current_sig == 1 and not position_active:
                position_active = True
                entry_price = current_close
                entry_date = index.strftime('%Y-%m-%d')
                total_trades += 1
            
            # Action: Trigger Sell Setup (Realized profit/loss recalculates the running portfolio total)
            elif current_sig == -1 and position_active:
                position_active = False
                exit_price = current_close
                exit_date = index.strftime('%Y-%m-%d')
                
                trade_return_pct = ((exit_price - entry_price) / entry_price)
                trade_profit_loss = running_portfolio_capital * trade_return_pct
                # Update the running wallet total with the compounded results of this trade
                running_portfolio_capital = running_portfolio_capital + trade_profit_loss
                
                if exit_price > entry_price:
                    winning_trades += 1
                    
                local_trades_log.append({
                    "Action": "🔄 COMPLETED TRADE",
                    "Entry Date": entry_date,
                    "Entry Price": f"₹{round(entry_price, 2)}",
                    "Exit Date": exit_date,
                    "Exit Price": f"₹{round(exit_price, 2)}",
                    "Trade Return": f"{round(trade_return_pct * 100, 2)}%",
                    "Compounded Portfolio Value": f"₹{round(running_portfolio_capital, 2)}"
                })
        
        # Handle open positions running up into the final day of the selected timeframe
        if position_active:
            exit_price = float(pdf['Close'].iloc[-1])
            trade_return_pct = ((exit_price - entry_price) / entry_price)
            trade_profit_loss = running_portfolio_capital * trade_return_pct
            running_portfolio_capital = running_portfolio_capital + trade_profit_loss
            
            if exit_price > entry_price:
                winning_trades += 1
                
            local_trades_log.append({
                "Action": "🟢 ACTIVE OPEN POSITION",
                "Entry Date": entry_date,
                "Entry Price": f"₹{round(entry_price, 2)}",
                "Exit Date": "Present Day",
                "Exit Price": f"₹{round(exit_price, 2)}",
                "Trade Return": f"{round(trade_return_pct * 100, 2)}%",
                "Compounded Portfolio Value": f"₹{round(running_portfolio_capital, 2)}"
            })

        win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        net_strategy_timeframe_pct = ((running_portfolio_capital - 100000.0) / 100000.0) * 100

        # --- DISPLAY THE UPDATED TIMEFRAME KPI CARDS ---
        st.markdown(f"#### 📈 Cumulative Performance Metrics for {selected_chart} inside this {chart_timeframe} Window")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric(label="Total Strategy Return (This Window)", value=f"{round(net_strategy_timeframe_pct, 2)}%")
        with m_col2:
            st.metric(label="Timeframe Success Win Rate", value=f"{round(win_rate_pct, 1)}%")
        with m_col3:
            st.metric(label="Total Executed Trades Here", value=str(total_trades))
        with m_col4:
            st.metric(
                label="Total Portfolio Value (From ₹1L Start)", 
                value=f"₹{round(running_portfolio_capital, 2)}", 
                delta=f"{round(net_strategy_timeframe_pct, 2)}% net change"
            )
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- RENDER THE PLOTLY GRAPH ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], name='Stock Close Price', line=dict(color='white', width=1.5)))
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_20'], name='20 Day Fast SMA', line=dict(color='cyan', width=1)))
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_50'], name='50 Day Medium SMA', line=dict(color='gold', width=1)))
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_200'], name='200 Day Macro Floor', line=dict(color='magenta', width=1.5)))
        fig.update_layout(template="plotly_dark", height=450, xaxis_title="Timeline", yaxis_title="Price (INR ₹)", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        # --- DISPLAY COMPOUNDED TRANSACTIONS LEDGER ---
        st.markdown("#### 📝 Cumulative Compounding Transaction Ledger")
        if len(local_trades_log) > 0:
            log_df = pd.DataFrame(local_trades_log)
            st.dataframe(log_df, use_container_width=True, hide_index=True)
        else:
            st.info("No active strategy crossover signals were triggered inside this specific isolated window.")
else:
    st.info(f"💡 Click the blue button in the sidebar to run the strategy across all stocks listed in the {index_selection}.")
