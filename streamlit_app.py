import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="NSE Total Market Backtester Pro")
st.title("🇮🇳 Total Indian Market Multi-Strategy Backtester")
st.markdown("Select an entire index block and your preferred algorithm to backtest win rates, trade frequency, and compounded capital performance.")

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
st.sidebar.header("⚙️ Core Engine Settings")

index_selection = st.sidebar.selectbox(
    "1. Select Target Index Block", 
    options=["Nifty 50 (Top Bluechips)", "Nifty Next 50 (Mid-Caps)", "Nifty 100 (Top 100 Stocks)"]
)

# --- ADDED: CORE STRATEGY SELECTOR DROPDOWN ---
selected_strategy = st.sidebar.selectbox(
    "2. Choose Backtest Strategy",
    options=[
        "LuxAlgo Style (Adaptive ATR Channel)",
        "MACD Momentum Breakthrough",
        "Triple SMA Ribbon Trend Follower"
    ]
)

time_option = st.sidebar.selectbox(
    "3. Select Core Backtest Horizon", 
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

# --- 3. UNIFIED MULTI-STRATEGY QUANT CORE ENGINE ---
def run_mass_backtest(tickers, start, end, strategy_choice):
    summary_rows = []
    charts_cache = {}
    
    progress_bar = st.progress(0)
    total_count = len(tickers)
    # Give a wide 365 day extra pad for lagging metrics calculations (like the 200 SMA)
    extended_start = pd.to_datetime(start) - timedelta(days=365) 
    
    for idx, ticker in enumerate(tickers):
        clean_name = ticker.replace(".NS", "")
        progress_bar.progress((idx + 1) / total_count)
        
        try:
            df = yf.download(ticker, start=extended_start, end=end, progress=False)
            if df.empty or len(df) < 50:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # --- STRATEGY MATHEMATICAL INJECTION LAYER ---
            if strategy_choice == "LuxAlgo Style (Adaptive ATR Channel)":
                atr_period = 14
                atr_multiplier = 3.0
                high_low = df['High'] - df['Low']
                high_cp = (df['High'] - df['Close'].shift(1)).abs()
                low_cp = (df['Low'] - df['Close'].shift(1)).abs()
                tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
                df['ATR'] = tr.rolling(window=atr_period).mean()
                df['Mid_Price'] = (df['High'] + df['Low']) / 2
                df['Trend_Floor'] = df['Mid_Price'] - (atr_multiplier * df['ATR'])
                df['Trend_Ceiling'] = df['Mid_Price'] + (atr_multiplier * df['ATR'])
                
                trend_floor, trend_ceiling = [0.0] * len(df), [0.0] * len(df)
                signals = [1] * len(df)
                for i in range(1, len(df)):
                    trend_floor[i] = max(df['Trend_Floor'].iloc[i], trend_floor[i-1]) if df['Close'].iloc[i-1] > trend_floor[i-1] else df['Trend_Floor'].iloc[i]
                    trend_ceiling[i] = min(df['Trend_Ceiling'].iloc[i], trend_ceiling[i-1]) if df['Close'].iloc[i-1] < trend_ceiling[i-1] else df['Trend_Ceiling'].iloc[i]
                    if df['Close'].iloc[i] > trend_ceiling[i]: signals[i] = 1
                    elif df['Close'].iloc[i] < trend_floor[i]: signals[i] = -1
                    else: signals[i] = signals[i-1]
                df['Signal'] = signals
                df['Visual_Band'] = np.where(df['Signal'] == 1, trend_floor, trend_ceiling)
                
            elif strategy_choice == "MACD Momentum Breakthrough":
                # Standard professional setup: Fast 12 day, Slow 26 day EMA lines
                df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
                df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD_Line'] = df['EMA_12'] - df['EMA_26']
                df['Signal_Line'] = df['MACD_Line'].ewm(span=9, adjust=False).mean()
                df['Signal'] = np.where(df['MACD_Line'] > df['Signal_Line'], 1, -1)
                df['Visual_Band'] = df['Signal_Line'] # Assigned for visualization maps later
                
            else: # Triple SMA Ribbon
                df['SMA_20'] = df['Close'].rolling(window=20).mean()
                df['SMA_50'] = df['Close'].rolling(window=50).mean()
                df['SMA_200'] = df['Close'].rolling(window=200).mean()
                buy_rule = (df['SMA_20'] > df['SMA_50']) & (df['SMA_50'] > df['SMA_200'])
                sell_rule = (df['Close'] < df['SMA_50']) | (df['Close'] < df['SMA_200'])
                df['Signal'] = np.where(buy_rule, 1, np.where(sell_rule, -1, 0))
                df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
                df['Visual_Band'] = df['SMA_50']

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
    with st.spinner(f"Scanning target assets using {selected_strategy}..."):
        res_df, res_charts = run_mass_backtest(processed_tickers, start_date, end_date, selected_strategy)
        st.session_state.summary_df = res_df
        st.session_state.asset_charts = res_charts

if st.session_state.summary_df is not None and not st.session_state.summary_df.empty:
    st.subheader(f"📊 Market Screening Matrix via {selected_strategy}")
    st.dataframe(st.session_state.summary_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("🔍 Localized Timeframe Workspace (₹1,00,000 Portfolio Compounding)")
    
    col1, col2 = st.columns([2, 3])
    with col1:
        chart_options = list(st.session_state.asset_charts.keys())
        selected_chart = st.selectbox("Select a stock to evaluate:", options=chart_options)
    with col2:
        chart_timeframe = st.radio(
            "Select Timeframe View:",
            options=["1 Month", "3 Months", "6 Months", "1 Year", "Full Backtest Horizon"],
            index=4, 
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
        
        # --- COMPOUNDING MULTI-TRADE TIMEFRAME SIMULATOR ---
        local_trades_log = []
        total_trades = 0
        winning_trades = 0
        position_active = False
        entry_price = 0.0
        entry_date = None
        
        running_portfolio_capital = 100000.0  
        
        if not pdf.empty and pdf['Signal'].iloc[0] == 1:
            position_active = True
            entry_price = float(pdf['Close'].iloc[0])
            entry_date = pdf.index[0].strftime('%Y-%m-%d')
            total_trades += 1

        for index, row in pdf.iterrows():
            current_sig = row['Signal']
            current_close = float(row['Close'])
            
            if current_sig == 1 and not position_active:
                position_active = True
                entry_price = current_close
                entry_date = index.strftime('%Y-%m-%d')
                total_trades += 1
            elif current_sig == -1 and position_active:
                position_active = False
                exit_price = current_close
                exit_date = index.strftime('%Y-%m-%d')
                
                trade_return_pct = ((exit_price - entry_price) / entry_price)
                trade_profit_loss = running_portfolio_capital * trade_return_pct
                running_portfolio_capital += trade_profit_loss
                
                if exit_price > entry_price:
                    winning_trades += 1
                    
                local_trades_log.append({
                    "Action": f"⚡ {selected_strategy[:10]} EXIT",
                    "Entry Date": entry_date,
                    "Entry Price": f"₹{round(entry_price, 2)}",
                    "Exit Date": exit_date,
                    "Exit Price": f"₹{round(exit_price, 2)}",
                    "Trade Return": f"{round(trade_return_pct * 100, 2)}%",
                    "Compounded Portfolio Value": f"₹{round(running_portfolio_capital, 2)}"
                })
        
        if position_active:
            exit_price = float(pdf['Close'].iloc[-1])
            trade_return_pct = ((exit_price - entry_price) / entry_price)
            trade_profit_loss = running_portfolio_capital * trade_return_pct
            running_portfolio_capital += trade_profit_loss
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

        # --- DISPLAY THE TIMEFRAME KPI CARDS ---
        st.markdown(f"#### 📈 {selected_strategy} Metrics for {selected_chart} ({chart_timeframe})")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric(label="Strategy Window Return", value=f"{round(net_strategy_timeframe_pct, 2)}%")
        with m_col2:
            st.metric(label="Algorithm Success Win Rate", value=f"{round(win_rate_pct, 1)}%")
        with m_col3:
            st.metric(label="Total Strategy Signals Triggered", value=str(total_trades))
        with m_col4:
            st.metric(label="Compounded Capital Result", value=f"₹{round(running_portfolio_capital, 2)}", delta=f"{round(net_strategy_timeframe_pct, 2)}% net change")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- RENDER THE PLOTLY GRAPH ACCORDING TO STRATEGY ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], name='Stock Close Price', line=dict(color='white', width=1.5)))
        
        if selected_strategy == "LuxAlgo Style (Adaptive ATR Channel)":
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Visual_Band'], name='LuxAlgo Volatility Band', line=dict(color='lime', width=1.5, dash='dot')))
        elif selected_strategy == "MACD Momentum Breakthrough":
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['MACD_Line'], name='MACD Line', line=dict(color='cyan', width=1)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Signal_Line'], name='MACD Signal Trigger', line=dict(color='magenta', width=1, dash='dot')))
        else:
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_20'], name='20 Day SMA', line=dict(color='cyan', width=1)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_50'], name='50 Day SMA', line=dict(color='gold', width=1.2)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_200'], name='200 Day Floor', line=dict(color='magenta', width=1.5)))
            
        fig.update_layout(template="plotly_dark", height=450, xaxis_title="Timeline", yaxis_title="Price/Indicator Scale", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        # --- DISPLAY COMPOUNDED TRANSACTIONS LEDGER ---
        st.markdown("#### 📝 Cumulative Compounding Transaction Ledger")
        if len(local_trades_log) > 0:
            log_df = pd.DataFrame(local_trades_log)
            st.dataframe(log_df, use_container_width=True, hide_index=True)
        else:
            st.info("No active strategy crossover signals were triggered inside this specific isolated window.")
else:
    st.info("💡 Select your target index and strategy in the sidebar, then click 'Run Complete Index Backtest'.")
