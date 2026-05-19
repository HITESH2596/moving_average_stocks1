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

# --- 1. DYNAMIC INDEX ROSTER FETCHING ENGINE ---
@st.cache_data(ttl=86400) # Cache the list for 24 hours so it stays fast
def fetch_entire_index_pool(index_type):
    """
    Downloads raw CSV data pools directly from tracking hubs 
    to fetch the complete current list of active Indian tickers.
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    if index_type == "Nifty 50 (Top Bluechips)":
        url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
    elif index_type == "Nifty Next 50 (Mid-Caps)":
        url = "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv"
    elif index_type == "Nifty 100 (Top 100 Stocks)":
        url = "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"
    else: # Fallback to a predefined reliable list of active heavyweights if network times out
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "HINDUNILVR", "LT"]

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            lines = response.text.split('\n')
            df = pd.read_csv(pd.compat.StringIO(response.text)) if hasattr(pd, 'compat') else pd.read_csv(requests.utils.stream_decode_response_unicode(response.iter_content(chunk_size=1024)))
            # Fallback parsing method for standard strings
            tickers = []
            for line in lines[1:]: # Skip header
                columns = line.split(',')
                if len(columns) > 2 and columns[2].strip():
                    tickers.append(columns[2].strip())
            return [t for t in tickers if t and t != "Symbol"]
    except Exception:
        pass
        
    # Reliable hardcoded fallback array if NSE servers throttle the request
    return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "HINDUNILVR", "LT", "AXISBANK", "MARUTI", "ZOMATO", "TATAMOTORS", "COALINDIA"]

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

# Calculate Dates Programmatically based on current year 2026
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

# Fetch the tickers based on selection
raw_nse_symbols = fetch_entire_index_pool(index_selection)
processed_tickers = [f"{sym}.NS" for sym in raw_nse_symbols if sym]

# --- 3. QUANTITATIVE ANALYSIS BACKTEST ENGINE ---
def run_mass_backtest(tickers, start, end, capital):
    summary_rows = []
    asset_charts = {}
    
    # Visual progress bar for scanning large groups of stocks on mobile
    progress_bar = st.progress(0)
    total_count = len(tickers)
    
    for idx, ticker in enumerate(tickers):
        clean_name = ticker.replace(".NS", "")
        # Update progress bar status
        progress_bar.progress((idx + 1) / total_count)
        
        try:
            df = yf.download(ticker, start=start, end=end, progress=False)
            if df.empty or len(df) < 200:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            # Compute Exponential Ribbon Indicators
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            
            # Position Triggers
            df['Signal'] = 0
            buy_rule = (df['SMA_20'] > df['SMA_50']) & (df['SMA_50'] > df['SMA_200'])
            sell_rule = (df['SMA_20'] < df['SMA_50']) | (df['Close'] < df['SMA_200'])
            
            df['Signal'] = np.where(buy_rule, 1, np.where(sell_rule, -1, 0))
            df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
            
            # Calculate Total Trades and Success Win Rate
            total_trades = 0
            winning_trades = 0
            position_active = False
            entry_price = 0.0
            
            for index, row in df.iterrows():
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
            
            # Formulate Total Growth Returns
            df['Asset_Return'] = df['Close'].pct_change()
            df['Strategy_Return'] = df['Asset_Return'] * df['Signal'].shift(1)
            
            cum_strategy = (1 + df['Strategy_Return'].fillna(0)).cumprod()
            cum_bh = (1 + df['Asset_Return'].fillna(0)).cumprod()
            
            strat_pct = (cum_strategy.iloc[-1] - 1) * 100
            bh_pct = (cum_bh.iloc[-1] - 1) * 100
            ending_cash = capital * cum_strategy.iloc[-1]
            
            current_status = "🟢 BUY" if df['Signal'].iloc[-1] == 1 else "🔴 SELL"
            
            summary_rows.append({
                "Ticker": clean_name,
                "Last Price": round(float(df['Close'].iloc[-1]), 2),
                "Condition": current_status,
                "Strategy Return": f"{round(float(strat_pct), 2)}%",
                "Buy & Hold Return": f"{round(float(bh_pct), 2)}%",
                "Trades": int(total_trades),
                "Success Win Rate": f"{round(win_rate_pct, 1)}%",
                "Ending Value": f"₹{round(float(ending_cash), 2)}"
            })
            asset_charts[clean_name] = df
            
        except Exception:
            pass
            
    progress_bar.empty() # Clear out bar when finished
    return pd.DataFrame(summary_rows), asset_charts

# --- 4. RENDER DATA ARCHITECTURE TO UI ---
if st.sidebar.button("🚀 Run Complete Index Backtest", type="primary"):
    with st.spinner(f"Downloading historical market bars for all stocks in {index_selection}..."):
        summary_df, asset_charts = run_mass_backtest(processed_tickers, start_date, end_date, initial_capital)
        
    if not summary_df.empty:
        st.subheader(f"📊 Live Strategy Screener Matrix ({index_selection} over {time_option})")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("🔍 Individual Technical Chart Analytics")
        
        chart_options = list(asset_charts.keys())
        selected_chart = st.selectbox("Select a stock from the scanned index to check its ribbon graph layout:", options=chart_options)
        
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
        st.error("Data download timeout. Please click the button to try running the index strategy again.")
else:
    st.info(f"💡 Click the blue button in the sidebar to run the strategy across all stocks listed in the {index_selection}.")
