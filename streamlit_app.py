import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="NSE Strategy Platform")
st.title("🇮🇳 Indian Market Strategy Screener & Backtester")
st.markdown("Track trends, see live buy/sell conditions, and backtest performance with percentage returns for NSE equities using Yahoo Finance.")

# --- 1. CLEAN HARDCODED POOL OF TOP INDIAN NSE ASSETS ---
NIFTY_TRACKER_POOL = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "BHARTIARTL.NS", "SBIN.NS", "ITC.NS", "HINDUNILVR.NS", "LT.NS", 
    "AXISBANK.NS", "KOTAKBANK.NS", "MARUTI.NS", "BAJAJFINSV.NS", "TITAN.NS"
]

# --- 2. SIDEBAR PARAMETERS ---
st.sidebar.header("⚙️ Strategy Settings")
selected_tickers = st.sidebar.multiselect(
    "Choose Stocks to Analyze (Leave blank to run all loaded)", 
    options=NIFTY_TRACKER_POOL, 
    default=["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]
)

initial_capital = st.sidebar.number_input("Starting Capital per Stock (₹)", min_value=1000, value=10000, step=1000)
start_date = st.sidebar.date_input("Backtest Start Date", pd.to_datetime("2023-01-01"))
end_date = st.sidebar.date_input("Backtest End Date", pd.to_datetime("2026-01-01"))

# --- 3. ANALYTICS ENGINE (YAHOO FINANCE) ---
def run_backtest(tickers, start, end, capital):
    summary_rows = []
    asset_charts = {}  # Fixed variable storage name
    
    targets = tickers if tickers else NIFTY_TRACKER_POOL
    
    for ticker in targets:
        try:
            # Fetch historical data via yfinance
            df = yf.download(ticker, start=start, end=end, progress=False)
            if df.empty:
                continue
                
            # Flatten columns if generated as multi-index by yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            if len(df) < 200: # Ensure we have enough data points for the 200 SMA
                continue
                
            # Calculate Moving Averages (20, 50, 200)
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            
            # Formulate Buy/Sell Conditions
            df['Signal'] = 0
            buy_rule = (df['SMA_20'] > df['SMA_50']) & (df['SMA_50'] > df['SMA_200'])
            sell_rule = (df['SMA_20'] < df['SMA_50']) | (df['Close'] < df['SMA_200'])
            
            df['Signal'] = np.where(buy_rule, 1, np.where(sell_rule, -1, 0))
            df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
            
            # Compute Strategy Percentage Returns
            df['Asset_Return'] = df['Close'].pct_change()
            df['Strategy_Return'] = df['Asset_Return'] * df['Signal'].shift(1)
            
            cum_strategy = (1 + df['Strategy_Return'].fillna(0)).cumprod()
            cum_bh = (1 + df['Asset_Return'].fillna(0)).cumprod()
            
            strat_pct = (cum_strategy.iloc[-1] - 1) * 100
            bh_pct = (cum_bh.iloc[-1] - 1) * 100
            ending_cash = capital * cum_strategy.iloc[-1]
            
            current_status = "🟢 BUY" if df['Signal'].iloc[-1] == 1 else "🔴 SELL"
            
            summary_rows.append({
                "NSE Ticker": ticker.replace(".NS", ""),
                "Last Price (₹)": round(float(df['Close'].iloc[-1]), 2),
                "Signal Condition": current_status,
                "Strategy Return (%)": f"{round(float(strat_pct), 2)}%",
                "Ending Value": f"₹{round(float(ending_cash), 2)}",
                "Buy & Hold Return (%)": f"{round(float(bh_pct), 2)}%"
            })
            asset_charts[ticker] = df
            
        except Exception as e:
            pass # Move to next stock seamlessly if a single download glitches
            
    return pd.DataFrame(summary_rows), asset_charts

# --- 4. RENDER DATA TO DASHBOARD UI ---
if selected_tickers or NIFTY_TRACKER_POOL:
    with st.spinner("Fetching Yahoo Finance tables and rendering backtests..."):
        summary_df, asset_charts = run_backtest(selected_tickers, start_date, end_date, initial_capital)
        
    if not summary_df.empty:
        st.subheader("📊 Live NSE Strategy Screener Matrix")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("🔍 Interactive Technical Chart Workspace")
        
        # Clean dropdown picker options matching keys
        chart_options = list(asset_charts.keys())
        selected_chart = st.selectbox("Pick an asset to inspect historical ribbon lines:", options=chart_options)
        
        if selected_chart in asset_charts:
            pdf = asset_charts[selected_chart]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['Close'], name='Stock Close Price', line=dict(color='white', width=1.5)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_20'], name='20 Day Fast SMA', line=dict(color='cyan', width=1)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_50'], name='50 Day Medium SMA', line=dict(color='gold', width=1)))
            fig.add_trace(go.Scatter(x=pdf.index, y=pdf['SMA_200'], name='200 Day Macro Floor', line=dict(color='magenta', width=1.5)))
            
            fig.update_layout(template="plotly_dark", height=500, xaxis_title="Timeline", yaxis_title="Price (INR ₹)")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Could not fetch data. Please adjust your dates or asset selection.")
