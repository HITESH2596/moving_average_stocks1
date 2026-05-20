import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Global Multi-Asset Backtester Pro")
st.title("🌎 Global Multi-Asset Quantitative Backtester")
st.markdown("### Pure Indicator-Driven Signal Panel")
st.markdown("This version holds all trades infinitely based **only** on strategy indicator exits. Fixed mathematical stop losses and profit targets are disabled.")

# Initialize session memory cache arrays
if "summary_df" not in st.session_state:
    st.session_state.summary_df = None
if "asset_charts" not in st.session_state:
    st.session_state.asset_charts = {}

# --- 1. GLOBAL INDEX ROSTER FETCHING ENGINE ---
@st.cache_data(ttl=86400)
def fetch_global_asset_pool(asset_selection):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    if asset_selection == "🇮🇳 Nifty 50 (India Bluechips)":
        url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                lines = response.text.split('\n')
                tickers = []
                for line in lines[1:]:
                    columns = line.split(',')
                    if len(columns) > 2 and columns[2].strip():
                        tickers.append(f"{columns[2].strip()}.NS")
                return [t for t in tickers if "Symbol" not in t]
        except Exception:
            pass
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "AXISBANK.NS"]

    elif asset_selection == "🇺🇸 US Tech & Bluechips":
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX", "AMD", "V", "MS", "JPM"]
        
    elif asset_selection == "🪙 Crypto Majors (vs USD)":
        return ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOT-USD", "LINK-USD", "DOGE-USD"]
        
    elif asset_selection == "🛢️ Global Commodities":
        return ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F"]
        
    return ["BTC-USD", "AAPL", "RELIANCE.NS"]

# --- 2. SIDEBAR PARAMETERS ---
st.sidebar.header("⚙️ Core Engine Settings")

asset_class = st.sidebar.selectbox(
    "1. Select Asset Class / Market", 
    options=[
        "🇺🇸 US Tech & Bluechips",
        "🪙 Crypto Majors (vs USD)",
        "🛢️ Global Commodities",
        "🇮🇳 Nifty 50 (India Bluechips)"
    ]
)

currency_symbol = "₹" if "India" in asset_class else "$"

selected_strategy = st.sidebar.selectbox(
    "2. Choose Backtest Strategy",
    options=[
        "LuxAlgo Style (Adaptive ATR Channel)",
        "MACD Momentum Breakthrough",
        "Triple SMA Ribbon Trend Follower",
        "Inverted Mean Reversion (Buy the Dip)"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("🎯 **Exit Logic Status:** Hard targets and risk stops are disabled. The strategy will buy and hold until a formal technical sell signal triggers.")
st.sidebar.markdown("---")

time_option = st.sidebar.selectbox(
    "3. Select Core Backtest Horizon", 
    options=["10 Years", "5 Years", "3 Years", "1 Year"]
)

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

processed_tickers = fetch_global_asset_pool(asset_class)

# --- 3. ADVANCED GLOBAL MASS-COMPOUNDING CALCULATION CORE ---
def run_mass_backtest(tickers, start, end, strategy_choice):
    summary_rows = []
    charts_cache = {}
    
    progress_bar = st.progress(0)
    total_count = len(tickers)
    extended_start = pd.to_datetime(start) - timedelta(days=365) 
    
    for idx, ticker in enumerate(tickers):
        progress_bar.progress((idx + 1) / total_count)
        
        try:
            df = yf.download(ticker, start=extended_start, end=end, progress=False)
            if df.empty or len(df) < 50:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Master indicator arrays
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            
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
                df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
                df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD_Line'] = df['EMA_12'] - df['EMA_26']
                df['Signal_Line'] = df['MACD_Line'].ewm(span=9, adjust=False).mean()
                df['Signal'] = np.where(df['MACD_Line'] > df['Signal_Line'], 1, -1)
                df['Visual_Band'] = df['Signal_Line']
                
            elif strategy_choice == "Inverted Mean Reversion (Buy the Dip)":
                buy_rule = (df['SMA_200'] > df['SMA_50']) & (df['SMA_50'] > df['SMA_20']) & (df['SMA_20'] > df['Close'])
                sell_rule = (df['Close'] > df['SMA_50'])
                df['Signal'] = np.where(buy_rule, 1, np.where(sell_rule, -1, 0))
                df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
                df['Visual_Band'] = df['SMA_20']
                
            else: # Triple SMA Ribbon Trend Follower
                buy_rule = (df['SMA_20'] > df['SMA_50']) & (df['SMA_50'] > df['SMA_200'])
                sell_rule = (df['Close'] < df['SMA_50']) | (df['Close'] < df['SMA_200'])
                df['Signal'] = np.where(buy_rule, 1, np.where(sell_rule, -1, 0))
                df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
                df['Visual_Band'] = df['SMA_50']

            pdf = df[df.index >= pd.to_datetime(start)].copy()
            if pdf.empty:
                continue
                
            total_trades = 0
            winning_trades = 0
            position_active = False
            entry_price = 0.0
            running_portfolio_capital = 100000.0  
            
            if pdf['Signal'].iloc[0] == 1:
                position_active = True
                entry_price = float(pdf['Close'].iloc[0])
                total_trades += 1

            for index, row in pdf.iterrows():
                current_sig = row['Signal']
                current_close = float(row['Close'])
                
                # Sells trigger ONLY when the technical strategy outputs a -1 signature change
                if current_sig == 1 and not position_active:
                    position_active = True
                    entry_price = current_close
                    total_trades += 1
                elif current_sig == -1 and position_active:
                    position_active = False
                    exit_price = current_close
                    trade_return_pct = ((exit_price - entry_price) / entry_price)
                    running_portfolio_capital += (running_portfolio_capital * trade_return_pct)
                    if exit_price > entry_price:
                        winning_trades += 1
            
            if position_active:
                exit_price = float(pdf['Close'].iloc[-1])
                trade_return_pct = ((exit_price - entry_price) / entry_price)
                running_portfolio_capital += (running_portfolio_capital * trade_return_pct)
                if exit_price > entry_price:
                    winning_trades += 1

            win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            net_return_pct = ((running_portfolio_capital - 100000.0) / 100000.0) * 100
            
            summary_rows.append({
                "Asset Ticker": ticker,
                "Current Status": "🟢 BUY" if pdf['Signal'].iloc[-1] == 1 else "🔴 CASH",
                "Last Price": f"{currency_symbol}{round(float(pdf['Close'].iloc[-1]), 2)}",
                "Total Trades": total_trades,
                "Win Rate (%)": f"{round(win_rate_pct, 1)}%",
                "Strategy Profit/Loss": f"{round(net_return_pct, 2)}%",
                "Final Balance (From 100k)": f"{currency_symbol}{round(running_portfolio_capital, 2)}",
                "Raw_Return_Num": net_return_pct  
            })
            charts_cache[ticker] = df
            
        except Exception:
            pass
            
    progress_bar.empty()
    out_df = pd.DataFrame(summary_rows)
    if not out_df.empty:
        out_df = out_df.sort_values(by="Raw_Return_Num", ascending=False).drop(columns=["Raw_Return_Num"])
    return out_df, charts_cache

# --- 4. RENDER DATA ARCHITECTURE TO UI ---
if st.sidebar.button("🚀 Run Complete Index Backtest", type="primary"):
    with st.spinner(f"Simulating mechanical indicators across all assets inside {asset_class}..."):
        res_df, res_charts = run_mass_backtest(processed_tickers, start_date, end_date, selected_strategy)
        st.session_state.summary_df = res_df
        st.session_state.asset_charts = res_charts

if st.session_state.summary_df is not None and not st.session_state.summary_df.empty:
    st.subheader(f"📊 Strategy Performance Leaderboard ({asset_class})")
    st.dataframe(st.session_state.summary_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("🔍 Localized Asset Technical Workspace")
    
    col1, col2 = st.columns([2, 3])
    with col1:
        chart_options = list(st.session_state.asset_charts.keys())
        selected_chart = st.selectbox("Select an asset to evaluate:", options=chart_options)
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
        
        # Local calculation loop matching table rows
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
                running_portfolio_capital += (running_portfolio_capital * trade_return_pct)
                if exit_price > entry_price: winning_trades += 1
                local_trades_log.append({
                    "Action": "🔄 STRATEGY EXIT", "Entry Date": entry_date, "Entry Price": f"{currency_symbol}{round(entry_price, 2)}",
                    "Exit Date": exit_date, "Exit Price": f"{currency_symbol}{round(exit_price, 2)}",
                    "Trade Return": f"{round(trade_return_pct * 100, 2)}%", "Portfolio Value": f"{currency_symbol}{round(running_portfolio_capital, 2)}"
                })
        
        if position_active:
            exit_price = float(pdf['Close'].iloc[-1])
            trade_return_pct = ((exit_price - entry_price) / entry_price)
            running_portfolio_capital += (running_portfolio_capital * trade_return_pct)
            if exit_price > entry_price: winning_trades += 1
            local_trades_log.append({
                "Action": "🟢 ACTIVE POSITION", "Entry Date": entry_date, "Entry Price": f"{currency_symbol}{round(entry_price, 2)}",
                "Exit Date": "Present Day", "Exit Price": f"{currency_symbol}{round(exit_price, 2)}",
                "Trade Return": f"{round(trade_return_pct * 100, 2)}%", "Portfolio Value": f"{currency_symbol}{round(running_portfolio_capital, 2)}"
            })

        win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        net_strategy_timeframe_pct = ((running_portfolio_capital - 100000.0) / 100000.0) * 100

        st.markdown(f"#### 📈 Strategy Crossover Breakdown: {selected_chart}")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1: st.metric("Selected Window Return", f"{round(net_strategy_timeframe_pct, 2)}%")
        with m_col2: st.metric("Calculated Win Rate", f"{round(win_rate_pct, 1)}%")
        with m_col3: st.metric("Signals Executed", str(total_trades))
        with m_col4: st.metric("Final Capital", f"{currency_symbol}{round(running_portfolio_capital, 2)}")

        # --- PLOT GRAPH ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], name='Asset Price', line=dict(color='white', width=1.5)))
        
        if selected_strategy == "LuxAlgo Style (Adaptive ATR Channel)":
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Visual_Band'], name='Volatility Line', line=dict(color='lime', width=1.5, dash='dot')))
        elif selected_strategy == "MACD Momentum Breakthrough":
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['MACD_Line'], name='MACD Line', line=dict(color='cyan', width=1)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Signal_Line'], name='Trigger Line', line=dict(color='magenta', width=1, dash='dot')))
        else: # Both SMA variations use standard SMA visualization tracking
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_20'], name='20 SMA', line=dict(color='cyan', width=1)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_50'], name='50 SMA', line=dict(color='gold', width=1.2)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_200'], name='200 SMA Floor', line=dict(color='magenta', width=1.5)))
            
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("#### 📝 Pure Indicator Transaction Ledger")
        if len(local_trades_log) > 0:
            st.dataframe(pd.DataFrame(local_trades_log), use_container_width=True, hide_index=True)
        else:
            st.info("No active strategy crossover signals triggered inside this specific window selection.")
else:
    st.info("💡 Select your parameters in the sidebar, then click 'Run Complete Index Backtest' to build the Global Leaderboard.")