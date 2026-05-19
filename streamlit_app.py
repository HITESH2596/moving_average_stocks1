import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="NSE Total Market Backtester Pro")
st.title("🇮🇳 Total Indian Market Multi-Strategy Backtester")
st.markdown("Analyze an entire market index block at once. The table below simulates a compounded ₹1,00,000 investment for every stock over your selected timeframe.")

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

selected_strategy = st.sidebar.selectbox(
    "2. Choose Backtest Strategy",
    options=[
        "LuxAlgo Style (Adaptive ATR Channel)",
        "MACD Momentum Breakthrough",
        "Triple SMA Ribbon Trend Follower"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Target & Risk Management")
target_pct = st.sidebar.slider("Profit Target (%)", min_value=2.0, max_value=50.0, value=15.0, step=0.5)
stop_pct = st.sidebar.slider("Stop Loss Guard (%)", min_value=1.0, max_value=25.0, value=5.0, step=0.5)
st.sidebar.markdown(f"**Risk/Reward Ratio:** {round(target_pct / stop_pct, 2)}:1")
st.sidebar.markdown("---")

time_option = st.sidebar.selectbox(
    "3. Select Core Backtest Horizon", 
    options=["10 Years", "5 Years", "3 Years", "1 Year"]
)

initial_capital = 100000.0 # Standardized to ₹1 Lakh baseline for all comparative tracking rows

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

# --- 3. ADVANCED MASS-COMPOUNDING CALCULATION CORE ---
def run_mass_backtest(tickers, start, end, strategy_choice, t_pct, s_pct):
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
            if df.empty or len(df) < 50:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Mathematical Technical indicators assignment
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
                
            else: # Triple SMA Ribbon
                df['SMA_20'] = df['Close'].rolling(window=20).mean()
                df['SMA_50'] = df['Close'].rolling(window=50).mean()
                df['SMA_200'] = df['Close'].rolling(window=200).mean()
                buy_rule = (df['SMA_20'] > df['SMA_50']) & (df['SMA_50'] > df['SMA_200'])
                sell_rule = (df['Close'] < df['SMA_50']) | (df['Close'] < df['SMA_200'])
                df['Signal'] = np.where(buy_rule, 1, np.where(sell_rule, -1, 0))
                df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
                df['Visual_Band'] = df['SMA_50']

            # Run Isolated Timeframe Performance Loop for the Summary Table metrics
            pdf = df[df.index >= pd.to_datetime(start)].copy()
            if pdf.empty:
                continue
                
            total_trades = 0
            winning_trades = 0
            position_active = False
            entry_price = 0.0
            live_target_price = 0.0
            live_stop_price = 0.0
            running_portfolio_capital = 100000.0  
            
            if pdf['Signal'].iloc[0] == 1:
                position_active = True
                entry_price = float(pdf['Close'].iloc[0])
                total_trades += 1

            for index, row in pdf.iterrows():
                current_sig = row['Signal']
                current_close = float(row['Close'])
                
                if position_active and live_target_price == 0.0:
                    live_target_price = entry_price * (1 + (t_pct / 100))
                    live_stop_price = entry_price * (1 - (s_pct / 100))

                if current_sig == 1 and not position_active:
                    position_active = True
                    entry_price = current_close
                    live_target_price = entry_price * (1 + (t_pct / 100))
                    live_stop_price = entry_price * (1 - (s_pct / 100))
                    total_trades += 1
                elif position_active:
                    hit_target = current_close >= live_target_price
                    hit_stop = current_close <= live_stop_price
                    indicator_exit = current_sig == -1
                    
                    if hit_target or hit_stop or indicator_exit:
                        position_active = False
                        exit_price = current_close
                        trade_return_pct = ((exit_price - entry_price) / entry_price)
                        running_portfolio_capital += (running_portfolio_capital * trade_return_pct)
                        if exit_price > entry_price:
                            winning_trades += 1
                        live_target_price = 0.0
                        live_stop_price = 0.0
            
            if position_active:
                exit_price = float(pdf['Close'].iloc[-1])
                trade_return_pct = ((exit_price - entry_price) / entry_price)
                running_portfolio_capital += (running_portfolio_capital * trade_return_pct)
                if exit_price > entry_price:
                    winning_trades += 1

            win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            net_return_pct = ((running_portfolio_capital - 100000.0) / 100000.0) * 100
            
            summary_rows.append({
                "Ticker": clean_name,
                "Current Status": "🟢 BUY" if pdf['Signal'].iloc[-1] == 1 else "🔴 CASH",
                "Last Price": f"₹{round(float(pdf['Close'].iloc[-1]), 2)}",
                "Total Trades": total_trades,
                "Win Rate (%)": f"{round(win_rate_pct, 1)}%",
                "Strategy Profit/Loss": f"{round(net_return_pct, 2)}%",
                "Final Balance (From ₹1L)": f"₹{round(running_portfolio_capital, 2)}",
                "Raw_Return_Num": net_return_pct  # Kept hidden for sorting power
            })
            charts_cache[clean_name] = df
            
        except Exception:
            pass
            
    progress_bar.empty()
    out_df = pd.DataFrame(summary_rows)
    if not out_df.empty:
        out_df = out_df.sort_values(by="Raw_Return_Num", ascending=False).drop(columns=["Raw_Return_Num"])
    return out_df, charts_cache

# --- 4. RENDER DATA ARCHITECTURE TO UI ---
if st.sidebar.button("🚀 Run Complete Index Backtest", type="primary"):
    with st.spinner(f"Simulating capital performance for all assets inside {index_selection}..."):
        res_df, res_charts = run_mass_backtest(processed_tickers, start_date, end_date, selected_strategy, target_pct, stop_pct)
        st.session_state.summary_df = res_df
        st.session_state.asset_charts = res_charts

if st.session_state.summary_df is not None and not st.session_state.summary_df.empty:
    st.subheader(f"📊 Strategy Performance Leaderboard ({index_selection})")
    st.markdown(f"Sorted automatically by highest compounding returns over the **{time_option}** horizon using **{selected_strategy}**.")
    st.dataframe(st.session_state.summary_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("🔍 Localized Technical Workspace")
    
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
        
        # Local logger calculation for details workspace matching table metrics
        local_trades_log = []
        total_trades = 0
        winning_trades = 0
        position_active = False
        entry_price = 0.0
        entry_date = None
        live_target_price = 0.0
        live_stop_price = 0.0
        running_portfolio_capital = 100000.0  
        
        if not pdf.empty and pdf['Signal'].iloc[0] == 1:
            position_active = True
            entry_price = float(pdf['Close'].iloc[0])
            entry_date = pdf.index[0].strftime('%Y-%m-%d')
            total_trades += 1

        for index, row in pdf.iterrows():
            current_sig = row['Signal']
            current_close = float(row['Close'])
            
            if position_active and live_target_price == 0.0:
                live_target_price = entry_price * (1 + (target_pct / 100))
                live_stop_price = entry_price * (1 - (stop_pct / 100))

            if current_sig == 1 and not position_active:
                position_active = True
                entry_price = current_close
                entry_date = index.strftime('%Y-%m-%d')
                live_target_price = entry_price * (1 + (target_pct / 100))
                live_stop_price = entry_price * (1 - (stop_pct / 100))
                total_trades += 1
            elif position_active:
                hit_target = current_close >= live_target_price
                hit_stop = current_close <= live_stop_price
                indicator_exit = current_sig == -1
                
                if hit_target or hit_stop or indicator_exit:
                    position_active = False
                    exit_price = current_close
                    exit_date = index.strftime('%Y-%m-%d')
                    trade_return_pct = ((exit_price - entry_price) / entry_price)
                    running_portfolio_capital += (running_portfolio_capital * trade_return_pct)
                    if exit_price > entry_price: winning_trades += 1
                    label = "🎯 TARGET" if hit_target else ("🛑 STOP LOSS" if hit_stop else "🔄 INDICATOR")
                    local_trades_log.append({
                        "Action": label, "Entry Date": entry_date, "Entry Price": f"₹{round(entry_price, 2)}",
                        "Exit Date": exit_date, "Exit Price": f"₹{round(exit_price, 2)}",
                        "Trade Return": f"{round(trade_return_pct * 100, 2)}%", "Portfolio Value": f"₹{round(running_portfolio_capital, 2)}"
                    })
                    live_target_price, live_stop_price = 0.0, 0.0
        
        if position_active:
            exit_price = float(pdf['Close'].iloc[-1])
            trade_return_pct = ((exit_price - entry_price) / entry_price)
            running_portfolio_capital += (running_portfolio_capital * trade_return_pct)
            if exit_price > entry_price: winning_trades += 1
            local_trades_log.append({
                "Action": "🟢 ACTIVE", "Entry Date": entry_date, "Entry Price": f"₹{round(entry_price, 2)}",
                "Exit Date": "Present Day", "Exit Price": f"₹{round(exit_price, 2)}",
                "Trade Return": f"{round(trade_return_pct * 100, 2)}%", "Portfolio Value": f"₹{round(running_portfolio_capital, 2)}"
            })

        win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        net_strategy_timeframe_pct = ((running_portfolio_capital - 100000.0) / 100000.0) * 100

        # KPI Workspace cards
        st.markdown(f"#### 📈 Granular Breakdown: {selected_chart}")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1: st.metric("Selected Window Return", f"{round(net_strategy_timeframe_pct, 2)}%")
        with m_col2: st.metric("Calculated Win Rate", f"{round(win_rate_pct, 1)}%")
        with m_col3: st.metric("Signals Executed", str(total_trades))
        with m_col4: st.metric("Final Capital", f"₹{round(running_portfolio_capital, 2)}")
            
        if position_active and live_target_price != 0.0:
            st.success(f"**📢 Live Target Projection:** Entry: **₹{round(entry_price,2)}** | Take Profit Level: **₹{round(live_target_price, 2)}** | Protective Stop Loss Level: **₹{round(live_stop_price, 2)}**")

        # --- PLOT GRAPH ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], name='Stock Price', line=dict(color='white', width=1.5)))
        if selected_strategy == "LuxAlgo Style (Adaptive ATR Channel)":
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Visual_Band'], name='Volatility Line', line=dict(color='lime', width=1.5, dash='dot')))
        elif selected_strategy == "MACD Momentum Breakthrough":
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['MACD_Line'], name='MACD', line=dict(color='cyan', width=1)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Signal_Line'], name='Trigger Line', line=dict(color='magenta', width=1, dash='dot')))
        else:
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_20'], name='20 SMA', line=dict(color='cyan', width=1)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_50'], name='50 SMA', line=dict(color='gold', width=1.2)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_200'], name='200 Floor', line=dict(color='magenta', width=1.5)))
            
        if position_active and live_target_price != 0.0:
            fig.add_hline(y=live_target_price, line_dash="dash", line_color="green")
            fig.add_hline(y=live_stop_price, line_dash="dash", line_color="red")
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("#### 📝 Transaction Ledger")
        if len(local_trades_log) > 0:
            st.dataframe(pd.DataFrame(local_trades_log), use_container_width=True, hide_index=True)
        else:
            st.info("No active crossover signals triggered inside this specific window selection.")
else:
    st.info("💡 Select your parameters in the sidebar, then click 'Run Complete Index Backtest' to build the Leaderboard.")
