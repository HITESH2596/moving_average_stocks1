import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Global Multi-Market Backtester")
st.title("📈 Global Multi-Market Strategy Dashboard")

# --- 1. LIVE TICKER FETCHING ENGINES ---
@st.cache_data
def get_sp500_tickers():
    # Scraping the current live S&P 500 list from Wikipedia
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    table = pd.read_html(url)
    df = table[0]
    tickers = df['Symbol'].tolist()
    # Clean tickers for yfinance compatibility (replace dots with dashes)
    return [t.replace('.', '-') for t in tickers]

@st.cache_data
def get_nifty50_tickers():
    # Scraping the current live Nifty 50 list from Wikipedia
    url = "https://en.wikipedia.org/wiki/NIFTY_50"
    table = pd.read_html(url)
    df = table[2] # Target the constituents table
    tickers = df['Symbol'].tolist()
    # Add the required '.NS' suffix for National Stock Exchange of India
    return [f"{t}.NS" for t in tickers]

# --- 2. SIDEBAR PARAMETERS ---
st.sidebar.header("⚙️ Strategy Parameters")
market_type = st.sidebar.selectbox("Select Target Market", ["US Markets (S&P 500)", "Indian Markets (Nifty 50)"])

# Load full asset rosters dynamically
if "US Markets" in market_type:
    full_ticker_pool = get_sp500_tickers()
    currency = "USD"
    default_selection = ["AAPL", "NVDA", "MSFT"]
else:
    full_ticker_pool = get_nifty50_tickers()
    currency = "INR"
    default_selection = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

# You can now select ANY or ALL shares from the entire index dropdown
selected_tickers = st.sidebar.multiselect(
    "Choose Assets to Analyze (Leave blank to run all)", 
    options=full_ticker_pool, 
    default=default_selection
)

initial_capital = st.sidebar.number_input("Starting Capital per Asset", min_value=1000, value=10000, step=1000)
start_date = st.sidebar.date_input("Backtest Start Date", pd.to_datetime("2023-01-01"))
end_date = st.sidebar.date_input("Backtest End Date", pd.to_datetime("2026-01-01"))

# --- 3. ANALYTICS & STRATEGY RETURN CALCULATION ---
def run_analytics(tickers, start, end, capital):
    summary_data = []
    detailed_dfs = {}
    
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start, end=end, progress=False)
            if df.empty or len(df) < 200:
                continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            # Moving Average Ribbons
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()
            
            # Position Assignment
            df['Signal'] = 0
            buy_condition = (df['SMA_20'] > df['SMA_50']) & (df['SMA_50'] > df['SMA_200'])
            sell_condition = (df['SMA_20'] < df['SMA_50']) | (df['Close'] < df['SMA_200'])
            
            df['Signal'] = np.where(buy_condition, 1, np.where(sell_condition, -1, 0))
            df['Signal'] = df['Signal'].replace(0, np.nan).ffill().fillna(-1)
            
            # Math behind Strategy Return
            df['Asset_Return'] = df['Close'].pct_change()
            df['Strategy_Return'] = df['Asset_Return'] * df['Signal'].shift(1)
            
            # Compounding Performance Over Time
            cumulative_strat = (1 + df['Strategy_Return'].fillna(0)).cumprod()
            cumulative_bh = (1 + df['Asset_Return'].fillna(0)).cumprod()
            
            final_strat_pct = (cumulative_strat.iloc[-1] - 1) * 100
            final_bh_pct = (cumulative_bh.iloc[-1] - 1) * 100
            ending_val = capital * cumulative_strat.iloc[-1]
            
            latest_sig = df['Signal'].iloc[-1]
            status = "🟢 BUY" if latest_sig == 1 else "🔴 SELL / AVOID"
            
            summary_data.append({
                "Ticker": ticker,
                "Current Price": round(df['Close'].iloc[-1], 2),
                "Live Condition": status,
                "Strategy Return (%)": round(final_strat_pct, 2),
                "Ending Value": f"{round(ending_val, 2)} {currency}",
                "Buy & Hold (%)": round(final_bh_pct, 2)
            })
            detailed_dfs[ticker] = df
            
        except Exception:
            pass # Keep processing other stocks cleanly if one ticker fails
            
    return pd.DataFrame(summary_data), detailed_dfs

# --- 4. DISPLAY UI WORKSPACE ---
targets = selected_tickers if selected_tickers else full_ticker_pool

if targets:
    with st.spinner("Analyzing full market data arrays..."):
        summary_df, asset_charts = run_analytics(targets, start_date, end_date, initial_capital)
    
    st.subheader("📊 Live Strategy Screener Matrix")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("🔍 Technical Chart & History Workspace")
    active_tab_ticker = st.selectbox("Select an asset to view its moving average chart structure:", summary_df['Ticker'].tolist())
    
    if active_tab_ticker in asset_charts:
        plot_df = asset_charts[active_tab_ticker]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Close'], name='Stock Price', line=dict(color='white', width=1.5)))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA_20'], name='20 SMA', line=dict(color='cyan', width=1)))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA_50'], name='50 SMA', line=dict(color='gold', width=1)))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['SMA_200'], name='200 SMA', line=dict(color='magenta', width=1.5)))
        
        fig.update_layout(template="plotly_dark", height=500, xaxis_title="Timeline", yaxis_title=f"Price ({currency})")
        st.plotly_chart(fig, use_container_width=True)
