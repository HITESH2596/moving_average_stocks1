import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="TradeSignal Pro")

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

DEFAULT_US = ["AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","AMD","NFLX","V","JPM","MS"]

DEFAULT_IN_50 = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
    "WIPRO.NS","BAJFINANCE.NS","SBIN.NS","LT.NS","TATAMOTORS.NS",
    "HINDUNILVR.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS",
    "ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS","NTPC.NS","ONGC.NS",
    "COALINDIA.NS","HCLTECH.NS","TECHM.NS","AXISBANK.NS","KOTAKBANK.NS",
    "INDUSINDBK.NS","BHARTIARTL.NS","ITC.NS","DRREDDY.NS","CIPLA.NS",
    "DIVISLAB.NS","EICHERMOT.NS","HEROMOTOCO.NS","BAJAJ-AUTO.NS","BPCL.NS",
    "GRASIM.NS","HINDALCO.NS","JSWSTEEL.NS","TATASTEEL.NS","TATACONSUM.NS",
    "UPL.NS","APOLLOHOSP.NS","ADANIENT.NS","ADANIGREEN.NS","ADANIPORTS.NS",
    "BAJAJFINSV.NS","BRITANNIA.NS","SBILIFE.NS","HDFCLIFE.NS","M&M.NS",
]

DEFAULT_IN = DEFAULT_IN_50 + [
    # Nifty Next 50
    "AMBUJACEM.NS","AUROPHARMA.NS","BANDHANBNK.NS","BERGEPAINT.NS","BEL.NS",
    "BOSCHLTD.NS","CANBK.NS","CHOLAFIN.NS","COLPAL.NS","DABUR.NS",
    "DLF.NS","GAIL.NS","GODREJCP.NS","HAVELLS.NS","HINDPETRO.NS",
    "ICICIGI.NS","ICICIPRULI.NS","INDUSTOWER.NS","IRCTC.NS","JUBLFOOD.NS",
    "LICHSGFIN.NS","LUPIN.NS","MARICO.NS","MCDOWELL-N.NS","MUTHOOTFIN.NS",
    "NAUKRI.NS","NMDC.NS","OFSS.NS","PAGEIND.NS","PIDILITIND.NS",
    "PNB.NS","RECLTD.NS","SAIL.NS","SHREECEM.NS","SIEMENS.NS",
    "SRF.NS","TORNTPHARM.NS","TRENT.NS","VEDL.NS","VOLTAS.NS",
    "ZOMATO.NS","DMART.NS","PIIND.NS","ALKEM.NS","BALKRISIND.NS",
    "BIOCON.NS","CONCOR.NS","INDIGO.NS","MFSL.NS","MOTHERSON.NS",
    # Nifty Midcap 100
    "ABCAPITAL.NS","ABFRL.NS","AJANTPHARM.NS","APOLLOTYRE.NS","ASHOKLEY.NS",
    "ASTRAL.NS","ATUL.NS","AUBANK.NS","BAJAJHLDNG.NS",
    "BATAINDIA.NS","BHEL.NS","BLUEDART.NS","CEATLTD.NS","CROMPTON.NS",
    "CUMMINSIND.NS","CYIENT.NS","DEEPAKNTR.NS","DIXON.NS","ELGIEQUIP.NS",
    "ESCORTS.NS","EXIDEIND.NS","FEDERALBNK.NS","FLUOROCHEM.NS",
    "GLENMARK.NS","GMRINFRA.NS","GNFC.NS","GODREJPROP.NS","GRANULES.NS",
    "GSPL.NS","GUJGASLTD.NS","HAL.NS","HFCL.NS","HONAUT.NS",
    "IDFCFIRSTB.NS","IEX.NS","INDHOTEL.NS","INDIANB.NS",
    "JKCEMENT.NS","JSL.NS","JUBLINGREA.NS","KAJARIACER.NS","KANSAINER.NS",
    "KEC.NS","LALPATHLAB.NS","LAURUSLABS.NS","LTTS.NS",
    "LUXIND.NS","MANAPPURAM.NS","MAXHEALTH.NS","MCX.NS",
    "METROPOLIS.NS","MRF.NS","NATCOPHARM.NS",
    "NAVINFLUOR.NS","NBCC.NS","NLCINDIA.NS","OBEROIRLTY.NS",
    "PERSISTENT.NS","PETRONET.NS","PFIZER.NS","PHOENIXLTD.NS","POLYCAB.NS",
    "PRAJIND.NS","PTC.NS","RAMCOCEM.NS",
    "RVNL.NS","SBICARD.NS","SCHAEFFLER.NS","SKFINDIA.NS","SOBHA.NS",
    "SONACOMS.NS","STARHEALTH.NS","SUMICHEM.NS","SUNDARMFIN.NS","SUNDRMFAST.NS",
    "SUPREMEIND.NS","SYNGENE.NS","TATACHEM.NS","TATACOMM.NS","TATAELXSI.NS",
    "TATAPOWER.NS","THERMAX.NS","TIMKEN.NS","TTKPRESTIG.NS",
    "TVSMOTOR.NS","UBLLTD.NS","UNIONBANK.NS",
    "VBL.NS","WHIRLPOOL.NS","ZEEL.NS","ZYDUSLIFE.NS",
]

DEFAULT_CR = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD"]
DEFAULT_CM = ["GC=F","SI=F","CL=F","NG=F","HG=F","PL=F"]
COMMODITY_NAMES = {"GC=F":"Gold","SI=F":"Silver","CL=F":"Crude Oil","NG=F":"Natural Gas","HG=F":"Copper","PL=F":"Platinum"}

STRATEGIES = [
    "Triple SMA Ribbon (20/50/200)",
    "LuxAlgo ATR Channel",
    "MACD Momentum",
    "EMA 9/21 Ribbon",
    "Smart Money Concepts (SMC)",
    "Supertrend",
    "VWAP + RSI",
    "Ichimoku Cloud",
]

STRATEGY_TF = {
    "Triple SMA Ribbon (20/50/200)": "1d",
    "LuxAlgo ATR Channel":           "4h",
    "MACD Momentum":                 "4h",
    "EMA 9/21 Ribbon":               "1h",
    "Smart Money Concepts (SMC)":    "4h",
    "Supertrend":                    "4h",
    "VWAP + RSI":                    "1h",
    "Ichimoku Cloud":                "1d",
}

MARKET_THRESHOLDS = {"US":5,"India":4,"Crypto":3,"Commodity":4}

BACKTEST_PERIODS = {
    "6 Months": 180,
    "1 Year":   365,
    "2 Years":  730,
    "5 Years":  1825,
    "10 Years": 3650,
}

CHART_INTERVALS = {
    "15 Minutes": "15m",
    "1 Hour":     "1h",
    "4 Hours":    "4h",
    "1 Day":      "1d",
}

for k, v in [("bt_results",[]),("bt_label",""),("bot_bt",[]),
              ("bot_bt_label",""),("watchlist",[]),("bot_log",[])]:
    if k not in st.session_state:
        st.session_state[k] = v

def get_market(t):
    if t.endswith(".NS"):  return "India"
    if t.endswith("-USD"): return "Crypto"
    if t.endswith("=F"):   return "Commodity"
    return "US"

def ticker_label(t):
    if t in COMMODITY_NAMES: return COMMODITY_NAMES[t]
    return t.replace(".NS","").replace("-USD","")

def get_min_votes(t): return MARKET_THRESHOLDS.get(get_market(t), 4)

def fmt(v, suffix=""):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    if suffix == "" and isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, float):
        return f"{v:.2f}{suffix}"
    return f"{v}{suffix}"

def sig_color(v):
    if v=="BUY":  return "background-color:#1a3a1a;color:#3fb950;font-weight:bold"
    if v=="SELL": return "background-color:#3a1a1a;color:#f85149;font-weight:bold"
    if v=="HOLD": return "color:#e3b341"
    return ""

def pct_col(v):
    try: return "color:#3fb950" if float(str(v).replace("%",""))>=0 else "color:#f85149"
    except: return ""

def compute_sma(s,w): return s.rolling(w).mean()
def compute_ema(s,span): return s.ewm(span=span,adjust=False).mean()

def compute_atr(df,p=14):
    hl=df["High"]-df["Low"]
    hcp=(df["High"]-df["Close"].shift(1)).abs()
    lcp=(df["Low"]-df["Close"].shift(1)).abs()
    return pd.concat([hl,hcp,lcp],axis=1).max(axis=1).rolling(p).mean()

def compute_rsi(s,p=14):
    d=s.diff(); g=d.clip(lower=0).rolling(p).mean(); l=(-d.clip(upper=0)).rolling(p).mean()
    return 100-(100/(1+g/l.replace(0,np.nan)))

def compute_bb(s,w=20,n=2):
    mid=s.rolling(w).mean(); std=s.rolling(w).std()
    return mid+n*std, mid, mid-n*std

def clean_df(raw):
    if isinstance(raw.columns,pd.MultiIndex):
        raw.columns=["_".join([str(c) for c in col]).strip() for col in raw.columns]
        rmap={}
        for col in raw.columns:
            for std in ["Close","Open","High","Low","Volume"]:
                if col.startswith(std): rmap[col]=std
        raw.rename(columns=rmap,inplace=True)
    raw.columns=[str(c).strip() for c in raw.columns]
    raw.index=pd.to_datetime(raw.index)
    if "Close" in raw.columns: raw=raw.dropna(subset=["Close"])
    return raw

def fetch_data(ticker,interval="1d",days=400):
    try:
        end_dt=datetime.now()
        max_days=min(days,59) if interval in ["1h","15m"] else min(days,729) if interval=="4h" else days
        start_dt=end_dt-timedelta(days=max_days)
        raw=yf.download(ticker,start=start_dt,end=end_dt,interval=interval,
                        progress=False,auto_adjust=True,group_by="column")
        if raw is None or raw.empty: return None
        raw=clean_df(raw)
        if "Close" not in raw.columns or len(raw)<20: return None
        return raw
    except Exception: return None

def generate_signals(df,strategy):
    df=df.copy()
    if len(df)<20: return df

    if strategy=="Triple SMA Ribbon (20/50/200)":
        df["SMA20"]=compute_sma(df["Close"],min(20,len(df)))
        df["SMA50"]=compute_sma(df["Close"],min(50,len(df)))
        df["SMA200"]=compute_sma(df["Close"],min(200,len(df)))
        buy=(df["SMA20"]>df["SMA50"])&(df["SMA50"]>df["SMA200"])
        sell=(df["Close"]<df["SMA50"])|(df["Close"]<df["SMA200"])
        df["Signal"]=np.where(buy,1,np.where(sell,-1,0))
        df["Signal"]=df["Signal"].replace(0,np.nan).ffill().fillna(-1)

    elif strategy=="LuxAlgo ATR Channel":
        df["ATR"]=compute_atr(df,14)
        mid=(df["High"]+df["Low"])/2
        tf_v=(mid-3.0*df["ATR"]).values; tc_v=(mid+3.0*df["ATR"]).values
        closes=df["Close"].values
        floor,ceil_v,signals=[0.0]*len(df),[0.0]*len(df),[0]*len(df)
        for i in range(1,len(df)):
            floor[i]=max(tf_v[i],floor[i-1]) if closes[i-1]>floor[i-1] else tf_v[i]
            ceil_v[i]=min(tc_v[i],ceil_v[i-1]) if closes[i-1]<ceil_v[i-1] else tc_v[i]
            if closes[i]>ceil_v[i]: signals[i]=1
            elif closes[i]<floor[i]: signals[i]=-1
            else: signals[i]=signals[i-1]
        df["Signal"]=signals
        df["Band"]=np.where(df["Signal"]==1,pd.Series(floor,index=df.index),pd.Series(ceil_v,index=df.index))

    elif strategy=="MACD Momentum":
        df["EMA12"]=compute_ema(df["Close"],12); df["EMA26"]=compute_ema(df["Close"],26)
        df["MACD"]=df["EMA12"]-df["EMA26"]; df["MACDSig"]=compute_ema(df["MACD"],9)
        df["Signal"]=np.where(df["MACD"]>df["MACDSig"],1,-1)

    elif strategy=="EMA 9/21 Ribbon":
        df["EMA9"]=compute_ema(df["Close"],9); df["EMA21"]=compute_ema(df["Close"],21)
        df["Signal"]=np.where(df["EMA9"]>df["EMA21"],1,-1)

    elif strategy=="Smart Money Concepts (SMC)":
        sma50=compute_sma(df["Close"],min(50,len(df))); sma200=compute_sma(df["Close"],min(200,len(df)))
        body=(df["Close"]-df["Open"]).abs(); avg_body=body.rolling(min(14,len(df))).mean()
        su=(df["Close"]>df["Open"])&(body>avg_body*1.5); sd=(df["Close"]<df["Open"])&(body>avg_body*1.5)
        obt=df["High"].shift(1).where(su,np.nan).ffill(); obb=df["Low"].shift(1).where(su,np.nan).ffill()
        obt2=df["High"].shift(1).where(sd,np.nan).ffill(); obb2=df["Low"].shift(1).where(sd,np.nan).ffill()
        ibo=(df["Close"]>=obb)&(df["Close"]<=obt); ibo2=(df["Close"]>=obb2)&(df["Close"]<=obt2)
        n=min(20,len(df)//2)
        bfvg=df["Low"]>df["High"].shift(2); bfvg2=df["High"]<df["Low"].shift(2)
        shi=df["High"].rolling(n).max(); slo=df["Low"].rolling(n).min()
        bb2=df["Close"]>shi.shift(1); bb3=df["Close"]<slo.shift(1)
        cb=(df["Close"]>sma50)&(df["Close"].shift(1)<=sma50.shift(1))
        cb2=(df["Close"]<sma50)&(df["Close"].shift(1)>=sma50.shift(1))
        phi=df["High"].rolling(n).max().shift(1); plo=df["Low"].rolling(n).min().shift(1)
        bsw=(df["Low"]<plo)&(df["Close"]>plo)&(df["Close"]>df["Open"])
        bsw2=(df["High"]>phi)&(df["Close"]<phi)&(df["Close"]<df["Open"])
        nd=df["Close"]<=(plo*1.05); ns=df["Close"]>=(phi*0.95)
        bsc=ibo.astype(int)+bfvg.astype(int)+bsw.astype(int)*3+cb.astype(int)*2+bb2.astype(int)*2+nd.astype(int)
        bsc2=ibo2.astype(int)+bfvg2.astype(int)+bsw2.astype(int)*3+cb2.astype(int)*2+bb3.astype(int)*2+ns.astype(int)
        mb=df["Close"]<sma200
        buy=(bsc>=3)&(bsc>bsc2); sell=(bsc2>=3)&(bsc2>bsc)&mb
        df["Signal"]=np.where(buy,1,np.where(sell,-1,0))
        df["Signal"]=df["Signal"].replace(0,np.nan).ffill().fillna(-1)

    elif strategy=="Supertrend":
        atr_v=compute_atr(df,10); mult=3.0
        hl2=(df["High"]+df["Low"])/2
        upper=(hl2+mult*atr_v).copy(); lower=(hl2-mult*atr_v).copy()
        sig_arr=np.zeros(len(df))
        for i in range(1,len(df)):
            lower.iloc[i]=lower.iloc[i] if lower.iloc[i]>lower.iloc[i-1] or df["Close"].iloc[i-1]<lower.iloc[i-1] else lower.iloc[i-1]
            upper.iloc[i]=upper.iloc[i] if upper.iloc[i]<upper.iloc[i-1] or df["Close"].iloc[i-1]>upper.iloc[i-1] else upper.iloc[i-1]
            if df["Close"].iloc[i]>upper.iloc[i-1]: sig_arr[i]=1
            elif df["Close"].iloc[i]<lower.iloc[i-1]: sig_arr[i]=-1
            else: sig_arr[i]=sig_arr[i-1]
        df["Signal"]=sig_arr; df["ST_Upper"]=upper; df["ST_Lower"]=lower

    elif strategy=="VWAP + RSI":
        typ=(df["High"]+df["Low"]+df["Close"])/3
        vol=df["Volume"] if "Volume" in df.columns else pd.Series(1,index=df.index)
        df["VWAP"]=(typ*vol).rolling(20).sum()/vol.rolling(20).sum()
        df["RSI"]=compute_rsi(df["Close"],14)
        df["BBUp"],df["BBMid"],df["BBLow"]=compute_bb(df["Close"],20,2)
        buy=((df["Close"]>df["VWAP"])&(df["RSI"]>50)&(df["RSI"]<70))|((df["Close"]<df["BBLow"])&(df["RSI"]<35))
        sell=((df["Close"]<df["VWAP"])&(df["RSI"]<50)&(df["RSI"]>30))|((df["Close"]>df["BBUp"])&(df["RSI"]>65))
        df["Signal"]=np.where(buy,1,np.where(sell,-1,0))
        df["Signal"]=df["Signal"].replace(0,np.nan).ffill().fillna(-1)

    elif strategy=="Ichimoku Cloud":
        n1,n2,n3=min(9,len(df)//3),min(26,len(df)//2),min(52,len(df)-1)
        df["Tenkan"]=(df["High"].rolling(n1).max()+df["Low"].rolling(n1).min())/2
        df["Kijun"]=(df["High"].rolling(n2).max()+df["Low"].rolling(n2).min())/2
        df["SpanA"]=((df["Tenkan"]+df["Kijun"])/2).shift(n2)
        df["SpanB"]=((df["High"].rolling(n3).max()+df["Low"].rolling(n3).min())/2).shift(n2)
        ac=(df["Close"]>df["SpanA"])&(df["Close"]>df["SpanB"])
        bc=(df["Close"]<df["SpanA"])&(df["Close"]<df["SpanB"])
        tku=(df["Tenkan"]>df["Kijun"])&(df["Tenkan"].shift(1)<=df["Kijun"].shift(1))
        tkd=(df["Tenkan"]<df["Kijun"])&(df["Tenkan"].shift(1)>=df["Kijun"].shift(1))
        df["Signal"]=np.where(ac&tku,1,np.where(bc&tkd,-1,0))
        df["Signal"]=df["Signal"].replace(0,np.nan).ffill().fillna(-1)

    if "Signal" not in df.columns: df["Signal"]=0
    return df

def run_backtest(df,capital):
    log,in_pos,entry,portfolio,wins,total=[],False,0.0,float(capital),0,0
    entry_date=""
    signals=df["Signal"].values; closes=df["Close"].values; dates=df.index
    for i in range(len(df)):
        sig=signals[i]; price=closes[i]
        if price is None or (isinstance(price,float) and np.isnan(price)): continue
        price=float(price); date=str(dates[i])[:16]
        if sig==1 and not in_pos:
            in_pos,entry,entry_date,total=True,price,date,total+1
        elif sig==-1 and in_pos:
            in_pos=False; ret=(price-entry)/entry; portfolio*=(1+ret)
            if price>entry: wins+=1
            log.append({"Status":"CLOSED","Entry Date":entry_date,"Entry Price":round(entry,4),
                         "Exit Date":date,"Exit Price":round(price,4),"Return %":round(ret*100,2),"Portfolio":round(portfolio,2)})
    if in_pos:
        last_v=next((closes[i] for i in range(len(closes)-1,-1,-1)
                     if closes[i] is not None and not(isinstance(closes[i],float) and np.isnan(closes[i]))),entry)
        price=float(last_v); ret=(price-entry)/entry; portfolio*=(1+ret)
        if price>entry: wins+=1
        log.append({"Status":"OPEN","Entry Date":entry_date,"Entry Price":round(entry,4),
                     "Exit Date":"Present","Exit Price":round(price,4),"Return %":round(ret*100,2),"Portfolio":round(portfolio,2)})
    win_rate=wins/total*100 if total>0 else 0.0
    last_price=float(next((closes[i] for i in range(len(closes)-1,-1,-1)
                            if closes[i] is not None and not(isinstance(closes[i],float) and np.isnan(closes[i]))),0))
    valid=df[df["Close"].notna()]
    first_cl=float(valid["Close"].iloc[0]) if not valid.empty else last_price
    bh_pct=round((last_price/first_cl-1)*100,2) if first_cl>0 else 0.0
    return {"net_pct":round((portfolio/capital-1)*100,2),"bh_pct":bh_pct,"end_val":round(portfolio,2),
            "win_rate":round(win_rate,1),"trades":total,"log":log,
            "last_sig":int(signals[-1]),"last_price":last_price}

def run_bot_backtest_engine(df,capital,min_votes):
    closes=df["Close"].values; dates=df.index; n=len(df)
    all_sigs=[]
    for strat in STRATEGIES:
        try:
            e=generate_signals(df.copy(),strat); all_sigs.append(e["Signal"].values)
        except: all_sigs.append(np.zeros(n))
    log,in_pos,entry,portfolio,wins,total=[],False,0.0,float(capital),0,0
    entry_date=""; last_buy_v=last_sell_v=0
    for i in range(n):
        price=closes[i]
        if price is None or(isinstance(price,float) and np.isnan(price)): continue
        price=float(price); date=str(dates[i])[:16]
        buy_v=sum(1 for s in all_sigs if i<len(s) and s[i]==1)
        sell_v=sum(1 for s in all_sigs if i<len(s) and s[i]==-1)
        last_buy_v,last_sell_v=buy_v,sell_v
        sig=1 if(buy_v>=min_votes and buy_v>sell_v) else -1 if(sell_v>=min_votes and sell_v>buy_v) else 0
        if sig==1 and not in_pos:
            in_pos,entry,entry_date,total=True,price,date,total+1
        elif sig==-1 and in_pos:
            in_pos=False; ret=(price-entry)/entry; portfolio*=(1+ret)
            if price>entry: wins+=1
            log.append({"Status":"CLOSED","Entry Date":entry_date,"Entry Price":round(entry,4),
                         "Exit Date":date,"Exit Price":round(price,4),"Return %":round(ret*100,2),
                         "Portfolio":round(portfolio,2),"Buy Votes":buy_v,"Sell Votes":sell_v})
    if in_pos:
        last_v=next((closes[i] for i in range(n-1,-1,-1)
                     if closes[i] is not None and not(isinstance(closes[i],float) and np.isnan(closes[i]))),entry)
        price=float(last_v); ret=(price-entry)/entry; portfolio*=(1+ret)
        if price>entry: wins+=1
        log.append({"Status":"OPEN","Entry Date":entry_date,"Entry Price":round(entry,4),
                     "Exit Date":"Present","Exit Price":round(price,4),"Return %":round(ret*100,2),
                     "Portfolio":round(portfolio,2),"Buy Votes":last_buy_v,"Sell Votes":last_sell_v})
    win_rate=wins/total*100 if total>0 else 0.0
    last_price=float(next((closes[i] for i in range(n-1,-1,-1)
                            if closes[i] is not None and not(isinstance(closes[i],float) and np.isnan(closes[i]))),0))
    valid=df[df["Close"].notna()]
    first_cl=float(valid["Close"].iloc[0]) if not valid.empty else last_price
    bh_pct=round((last_price/first_cl-1)*100,2) if first_cl>0 else 0.0
    last_sig=1 if(last_buy_v>=min_votes and last_buy_v>last_sell_v) else -1 if(last_sell_v>=min_votes and last_sell_v>last_buy_v) else 0
    return {"net_pct":round((portfolio/capital-1)*100,2),"bh_pct":bh_pct,"end_val":round(portfolio,2),
            "win_rate":round(win_rate,1),"trades":total,"log":log,"last_price":last_price,
            "last_sig":last_sig,"last_buy_v":last_buy_v,"last_sell_v":last_sell_v}

def get_multi_tf_consensus(ticker):
    buy_v=sell_v=0; detail={}; tf_cache={}
    for strat in STRATEGIES:
        tf=STRATEGY_TF.get(strat,"1d")
        if tf not in tf_cache:
            try:
                raw=fetch_data(ticker,interval=tf,days=200)
                tf_cache[tf]=raw if raw is not None and len(raw)>=20 else fetch_data(ticker,interval="1d",days=200)
            except: tf_cache[tf]=None
    for strat in STRATEGIES:
        tf=STRATEGY_TF.get(strat,"1d"); raw=tf_cache.get(tf)
        if raw is None: detail[strat]={"signal":0,"tf":tf}; continue
        try:
            e=generate_signals(raw.copy(),strat); sig=int(e["Signal"].iloc[-1])
            buy_v+=1 if sig==1 else 0; sell_v+=1 if sig==-1 else 0
            detail[strat]={"signal":sig,"tf":tf}
        except: detail[strat]={"signal":0,"tf":tf}
    return buy_v,sell_v,detail

def process_ticker(ticker,strategy,days,capital,interval):
    try:
        raw=fetch_data(ticker,interval=interval,days=days+50)
        if raw is None: return None
        cutoff=datetime.now()-timedelta(days=days)
        sl=raw[raw.index>=pd.to_datetime(cutoff)].copy()
        if len(sl)<20: return None
        en=generate_signals(sl,strategy); bt=run_backtest(en,capital)
        return {"Ticker":ticker,"Market":get_market(ticker),"Label":ticker_label(ticker),
                "Price":round(bt["last_price"],2),"Signal":"BUY" if bt["last_sig"]==1 else "SELL",
                "Net %":bt["net_pct"],"B&H %":bt["bh_pct"],"Win Rate":bt["win_rate"],
                "Trades":bt["trades"],"End Value":bt["end_val"],"_log":bt["log"],"_df":en}
    except: return None

def process_bot_ticker_bt(ticker,days,capital):
    try:
        min_votes=get_min_votes(ticker)
        raw=fetch_data(ticker,interval="1d",days=days+50)
        if raw is None: return None
        cutoff=datetime.now()-timedelta(days=days)
        sl=raw[raw.index>=pd.to_datetime(cutoff)].copy()
        if len(sl)<30: return None
        bt=run_bot_backtest_engine(sl,capital,min_votes)
        sig_txt="BUY" if bt["last_sig"]==1 else "SELL" if bt["last_sig"]==-1 else "HOLD"
        return {"Ticker":ticker,"Market":get_market(ticker),"Label":ticker_label(ticker),
                "Price":round(bt["last_price"],2),"Signal":sig_txt,"Min Votes":min_votes,
                "Buy Votes":bt["last_buy_v"],"Sell Votes":bt["last_sell_v"],
                "Net %":bt["net_pct"],"B&H %":bt["bh_pct"],"Win Rate":bt["win_rate"],
                "Trades":bt["trades"],"End Value":bt["end_val"],"_log":bt["log"],"_df":sl}
    except: return None

def run_engine(tickers,strategy,days,capital,interval):
    results=[]; prog=st.progress(0); status=st.empty()
    for idx,ticker in enumerate(tickers):
        prog.progress((idx+1)/len(tickers))
        status.caption(f"Processing {ticker_label(ticker)} ({idx+1}/{len(tickers)})...")
        row=process_ticker(ticker,strategy,days,capital,interval)
        if row: results.append(row)
    prog.empty(); status.empty()
    results.sort(key=lambda x:x["Net %"] if x["Net %"] is not None and not(isinstance(x["Net %"],float) and np.isnan(x["Net %"])) else -999,reverse=True)
    return results

def draw_chart(df_view,log,strategy_name):
    df_view=df_view.copy()
    if isinstance(df_view.index,pd.MultiIndex): df_view.index=df_view.index.get_level_values(0)
    df_view.index=pd.to_datetime(df_view.index)
    fig=go.Figure()
    try: fig.add_trace(go.Scatter(x=df_view.index,y=df_view["Close"],name="Price",line=dict(color="white",width=1.5)))
    except: pass
    s=strategy_name
    try:
        if s=="Triple SMA Ribbon (20/50/200)":
            for col,color,nm in [("SMA20","#00FFFF","SMA 20"),("SMA50","#FFD700","SMA 50"),("SMA200","#FF00FF","SMA 200")]:
                if col in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index,y=df_view[col],name=nm,line=dict(color=color,width=1)))
        elif s=="LuxAlgo ATR Channel":
            if "Band" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index,y=df_view["Band"],name="ATR Band",line=dict(color="lime",width=1.5,dash="dot")))
        elif s=="MACD Momentum":
            if "MACD" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index,y=df_view["MACD"],name="MACD",line=dict(color="#00FFFF",width=1)))
            if "MACDSig" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index,y=df_view["MACDSig"],name="Signal",line=dict(color="#FF00FF",width=1,dash="dot")))
        elif s=="EMA 9/21 Ribbon":
            if "EMA9" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index,y=df_view["EMA9"],name="EMA 9",line=dict(color="#00FF88",width=1)))
            if "EMA21" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index,y=df_view["EMA21"],name="EMA 21",line=dict(color="#FF8800",width=1)))
        elif s=="Supertrend":
            if "ST_Upper" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index,y=df_view["ST_Upper"],name="ST Resist",line=dict(color="#FF4444",width=1.5,dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index,y=df_view["ST_Lower"],name="ST Support",line=dict(color="#44FF44",width=1.5,dash="dot")))
        elif s=="VWAP + RSI":
            if "VWAP" in df_view.columns: fig.add_trace(go.Scatter(x=df_view.index,y=df_view["VWAP"],name="VWAP",line=dict(color="#FFD700",width=1.5)))
            if "BBUp" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index,y=df_view["BBUp"],name="BB Upper",line=dict(color="#FF8800",width=1,dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index,y=df_view["BBLow"],name="BB Lower",line=dict(color="#FF8800",width=1,dash="dot")))
        elif s=="Ichimoku Cloud":
            if "SpanA" in df_view.columns:
                fig.add_trace(go.Scatter(x=df_view.index,y=df_view["SpanA"],name="Span A",line=dict(color="#00FF88",width=1)))
                fig.add_trace(go.Scatter(x=df_view.index,y=df_view["SpanB"],name="Span B",line=dict(color="#FF4444",width=1)))
                fig.add_trace(go.Scatter(x=df_view.index,y=df_view["Tenkan"],name="Tenkan",line=dict(color="#00FFFF",width=1,dash="dot")))
                fig.add_trace(go.Scatter(x=df_view.index,y=df_view["Kijun"],name="Kijun",line=dict(color="#FF00FF",width=1,dash="dot")))
        elif s=="Smart Money Concepts (SMC)":
            dv=df_view.reset_index(); dc=dv.columns[0]; n=len(dv)
            if "Close" in dv.columns:
                fig.add_trace(go.Scatter(x=dv[dc],y=dv["Close"].rolling(min(50,n)).mean(),name="SMA 50",line=dict(color="#FF8800",width=1,dash="dot")))
                fig.add_trace(go.Scatter(x=dv[dc],y=dv["Close"].rolling(min(200,n)).mean(),name="SMA 200",line=dict(color="#FF00FF",width=1.5,dash="dot")))
    except: pass
    try:
        bd=[t["Entry Date"] for t in log]; bp=[t["Entry Price"] for t in log]
        sd=[t["Exit Date"] for t in log if t["Status"]=="CLOSED"]; sp=[t["Exit Price"] for t in log if t["Status"]=="CLOSED"]
        if bd: fig.add_trace(go.Scatter(x=bd,y=bp,mode="markers",name="BUY",marker=dict(symbol="triangle-up",color="lime",size=10)))
        if sd: fig.add_trace(go.Scatter(x=sd,y=sp,mode="markers",name="SELL",marker=dict(symbol="triangle-down",color="red",size=10)))
    except: pass
    fig.update_layout(template="plotly_dark",height=450,margin=dict(l=20,r=20,t=30,b=20),
                       legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
    return fig

def show_performance(log_t, row, curr, capital):
    m1,m2,m3,m4,m5=st.columns(5)
    sc="#3fb950" if row["Signal"]=="BUY" else "#f85149" if row["Signal"]=="SELL" else "#e3b341"
    m1.markdown(f"**Signal**<br><span style='color:{sc};font-size:20px;font-weight:bold'>{row['Signal']}</span>",unsafe_allow_html=True)
    m2.metric("Strategy Return",fmt(row["Net %"],"%"))
    m3.metric("Buy & Hold",fmt(row["B&H %"],"%"))
    m4.metric("Win Rate",fmt(row["Win Rate"],"%"))
    m5.metric("Total Trades",str(row["Trades"]))
    if log_t:
        rets=[t["Return %"] for t in log_t]
        wins_l=[r for r in rets if r>0]; losses_l=[r for r in rets if r<0]
        avg_w=round(sum(wins_l)/len(wins_l),2) if wins_l else 0
        avg_l=round(sum(losses_l)/len(losses_l),2) if losses_l else 0
        best=round(max(rets),2) if rets else 0; worst=round(min(rets),2) if rets else 0
        rr=round(abs(avg_w/avg_l),2) if avg_l!=0 else "∞"
        gp=sum(r for r in rets if r>0); gl=abs(sum(r for r in rets if r<0))
        pf=round(gp/gl,2) if gl>0 else "∞"
        pvs=[t["Portfolio"] for t in log_t]; peak=pvs[0] if pvs else capital; mdd=0
        for pv in pvs:
            if pv>peak: peak=pv
            dd=(peak-pv)/peak*100
            if dd>mdd: mdd=dd
        mdd=round(mdd,2)
        n2,n3,n4,n5,n6,n7=st.columns(6)
        n2.metric("Capital",f"{curr} {capital:,.0f}")
        n3.metric("End Value",f"{curr} {row['End Value']:,.0f}" if row["End Value"] else "—")
        n4.metric("Avg Win",f"+{avg_w}%"); n5.metric("Avg Loss",f"{avg_l}%")
        n6.metric("Best Trade",f"+{best}%"); n7.metric("Worst Trade",f"{worst}%")
        d1,d2,d3=st.columns(3)
        d1.metric("Risk/Reward",str(rr))
        d2.metric("Profit Factor",str(pf),help=">1 profitable · >2 excellent")
        d3.metric("Max Drawdown",f"-{mdd}%",delta="lower is better",delta_color="inverse")
        score=sum([
            bool(row["Win Rate"] and row["Win Rate"]>=50),
            bool(row["Net %"] and row["Net %"]>0),
            pf!="∞" and pf>=1.5, mdd<20, rr!="∞" and rr>=1.5
        ])
        rm={5:"⭐⭐⭐⭐⭐ Excellent",4:"⭐⭐⭐⭐ Good",3:"⭐⭐⭐ Average",2:"⭐⭐ Below Average",1:"⭐ Poor",0:"❌ Very Poor"}
        rc="#3fb950" if score>=4 else "#e3b341" if score>=2 else "#f85149"
        st.markdown(f"**Strategy Rating:** <span style='color:{rc};font-size:18px'>{rm.get(score,'⭐⭐⭐')}</span> &nbsp; Score: {score}/5",unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════
st.sidebar.header("Backtest Settings")
strategy_name=st.sidebar.selectbox("Strategy",STRATEGIES)
rec_tf=STRATEGY_TF.get(strategy_name,"1d")
st.sidebar.caption(f"Recommended timeframe: `{rec_tf}`")
tf_label=st.sidebar.selectbox("Chart Timeframe",list(CHART_INTERVALS.keys()),
    index=list(CHART_INTERVALS.values()).index(rec_tf) if rec_tf in CHART_INTERVALS.values() else 3)
interval=CHART_INTERVALS[tf_label]
period_label=st.sidebar.selectbox("Backtest Period",list(BACKTEST_PERIODS.keys()),index=1)
bt_days=BACKTEST_PERIODS[period_label]
capital=st.sidebar.number_input("Capital per Asset",min_value=1000,value=100000,step=5000)
st.sidebar.markdown("---")
run_us=st.sidebar.button("🇺🇸 Run US Stocks (12)",type="primary",use_container_width=True)
run_in50=st.sidebar.button("🇮🇳 Run Nifty 50 (Fast)",use_container_width=True)
run_in=st.sidebar.button("🇮🇳 Run Nifty 200 (5–8 mins)",type="primary",use_container_width=True)
run_cr=st.sidebar.button("🪙 Run Crypto",type="primary",use_container_width=True)
run_cm=st.sidebar.button("🛢️ Run Commodities",type="primary",use_container_width=True)
run_all=st.sidebar.button("🌍 Run ALL Markets",use_container_width=True)
st.sidebar.caption("⚠️ Nifty 200 & All Markets scans take 5–8 mins")
st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Bot Consensus Backtest")
st.sidebar.caption("Same logic as the live bot — all 8 strategies, market-specific thresholds")
st.sidebar.markdown("🇺🇸 US=5/8 · 🇮🇳 India=4/8 · 🪙 Crypto=3/8 · 🛢️ Comm=4/8")
bot_bt_market=st.sidebar.selectbox("Market",["US Stocks","Nifty 50","Nifty 200","Crypto","Commodities","All Markets"],key="bot_bt_market")
run_bot_bt=st.sidebar.button("Run Bot Backtest",use_container_width=True,key="run_bot_bt")

# ═══════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════
tab_bt, tab_bot = st.tabs(["📊 Backtester", "🤖 Paper Trading Bot"])

# ── TRIGGER RUNS ───────────────────────────────────────────────
def do_run(tickers,label):
    with st.spinner(f"Running {label}... ({len(tickers)} assets)"):
        res=run_engine(tickers,strategy_name,bt_days,capital,interval)
        st.session_state.bt_results=res
        st.session_state.bt_label=f"{label} · {strategy_name} · {tf_label} · {period_label}"
        st.session_state.bot_bt=[]
        st.rerun()

if run_us:    do_run(DEFAULT_US,"US Stocks")
elif run_in50: do_run(DEFAULT_IN_50,"Nifty 50")
elif run_in:  do_run(DEFAULT_IN,"Nifty 200")
elif run_cr:  do_run(DEFAULT_CR,"Crypto")
elif run_cm:  do_run(DEFAULT_CM,"Commodities")
elif run_all: do_run(DEFAULT_US+DEFAULT_IN+DEFAULT_CR+DEFAULT_CM,"All Markets")
elif run_bot_bt:
    mkt_map={
        "US Stocks":DEFAULT_US,
        "Nifty 50":DEFAULT_IN_50,
        "Nifty 200":DEFAULT_IN,
        "Crypto":DEFAULT_CR,
        "Commodities":DEFAULT_CM,
        "All Markets":DEFAULT_US+DEFAULT_IN+DEFAULT_CR+DEFAULT_CM
    }
    bt_tickers=mkt_map[bot_bt_market]
    with st.spinner(f"Running Bot Backtest — {bot_bt_market} — {period_label}... ({len(bt_tickers)} assets)"):
        bot_rows=[]; prog=st.progress(0); status_txt=st.empty()
        for idx,ticker in enumerate(bt_tickers):
            prog.progress((idx+1)/len(bt_tickers))
            status_txt.caption(f"Bot backtest: {ticker_label(ticker)} ({idx+1}/{len(bt_tickers)}) threshold={get_min_votes(ticker)}/8")
            row=process_bot_ticker_bt(ticker,bt_days,capital)
            if row: bot_rows.append(row)
        prog.empty(); status_txt.empty()
        bot_rows.sort(key=lambda x:x["Net %"] if x["Net %"] is not None and not(isinstance(x["Net %"],float) and np.isnan(x["Net %"])) else -999,reverse=True)
        st.session_state.bot_bt=bot_rows
        st.session_state.bot_bt_label=f"Bot Consensus · {bot_bt_market} · {period_label}"
        st.session_state.bt_results=[]
        st.rerun()

# ═══════════════════════════════════════════════════════════════
# TAB 1 — BACKTESTER
# ═══════════════════════════════════════════════════════════════
with tab_bt:
    st.title("Global Multi-Market Backtester Pro")

    results=st.session_state.get("bt_results",[])
    bot_rows=st.session_state.get("bot_bt",[])

    if results:
        st.markdown(f"## {st.session_state.get('bt_label','Results')}")
        buy_stocks=[r for r in results if r["Signal"]=="BUY"]
        sell_stocks=[r for r in results if r["Signal"]=="SELL"]

        st.markdown("### Signal Summary")
        col_b,col_s=st.columns(2)
        with col_b:
            st.success(f"🟢 BUY — {len(buy_stocks)} stocks")
            if buy_stocks:
                st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                    "Price":fmt(r["Price"]),"Strat %":fmt(r["Net %"],"%"),
                    "B&H %":fmt(r["B&H %"],"%"),"Win Rate":fmt(r["Win Rate"],"%")}
                    for r in buy_stocks]),use_container_width=True,hide_index=True)
            else: st.info("No BUY signals.")
        with col_s:
            st.error(f"🔴 SELL — {len(sell_stocks)} stocks")
            if sell_stocks:
                st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                    "Price":fmt(r["Price"]),"Strat %":fmt(r["Net %"],"%"),
                    "B&H %":fmt(r["B&H %"],"%"),"Win Rate":fmt(r["Win Rate"],"%")}
                    for r in sell_stocks]),use_container_width=True,hide_index=True)
            else: st.info("No SELL signals.")

        if st.session_state.watchlist:
            st.markdown("---"); st.markdown("### ★ My Watchlist")
            wl_rows=[r for r in results if r["Ticker"] in st.session_state.watchlist]
            if wl_rows:
                st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                    "Price":fmt(r["Price"]),"Signal":r["Signal"],
                    "Strat %":fmt(r["Net %"],"%"),"B&H %":fmt(r["B&H %"],"%")}
                    for r in wl_rows]).style.map(sig_color,subset=["Signal"]),
                    use_container_width=True,hide_index=True)

        st.markdown("---"); st.subheader("Full Leaderboard")
        mf=st.radio("Filter:",["All","US","India","Crypto","Commodity"],horizontal=True,key="mf")
        fd=results if mf=="All" else [r for r in results if r["Market"]==mf]
        if fd:
            st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],
                "Price":fmt(r["Price"]),"Signal":r["Signal"],
                "Strategy %":fmt(r["Net %"],"%"),"B&H %":fmt(r["B&H %"],"%"),
                "Win Rate":fmt(r["Win Rate"],"%"),"Trades":r["Trades"],"End Value":fmt(r["End Value"])}
                for r in fd]).style.map(sig_color,subset=["Signal"]),
                use_container_width=True,hide_index=True)

        st.markdown("---"); st.subheader("Chart & Trade Log")
        ch1,ch2=st.columns([3,1])
        with ch1:
            chart_search=st.text_input("Search",placeholder="AAPL, RELIANCE, BTC, Gold...",
                label_visibility="collapsed",key="chart_search")
        with ch2:
            chart_mkt=st.selectbox("Market",["US","India (NSE)","Crypto","Commodity"],
                label_visibility="collapsed",key="chart_mkt")
        final_ticker=None
        if chart_search.strip() and len(chart_search.strip())>=2:
            try:
                sq=yf.Search(chart_search.strip(),max_results=7).quotes
                sugg=[f"{q.get('symbol','')} — {q.get('shortname') or q.get('longname','')}" for q in sq if q.get("symbol")]
                if sugg:
                    chosen=st.selectbox("Pick:",sugg,key="chart_sugg",label_visibility="collapsed")
                    if chosen: final_ticker=chosen.split(" — ")[0].strip()
            except: pass
        if st.button("Search & View Chart",key="chart_go",use_container_width=True,type="primary"):
            if final_ticker:
                raw_t=final_ticker
                if chart_mkt=="India (NSE)" and not raw_t.endswith(".NS"): raw_t+=".NS"
                elif chart_mkt=="Crypto" and not raw_t.endswith("-USD"): raw_t+="-USD"
            elif chart_search.strip():
                raw_t=chart_search.strip().upper().replace(" ","")
                if chart_mkt=="India (NSE)" and not raw_t.endswith(".NS"): raw_t+=".NS"
                elif chart_mkt=="Crypto" and not raw_t.endswith("-USD"): raw_t+="-USD"
            else: raw_t=None
            if raw_t:
                st.session_state["chart_sel"]=raw_t
                if not any(r["Ticker"]==raw_t for r in results):
                    with st.spinner(f"Fetching {raw_t}..."):
                        nr=process_ticker(raw_t,strategy_name,bt_days,capital,interval)
                        if nr:
                            st.session_state.bt_results.append(nr)
                            st.session_state.bt_results.sort(key=lambda x:x["Net %"] if x["Net %"] is not None and not(isinstance(x["Net %"],float) and np.isnan(x["Net %"])) else -999,reverse=True)
                            st.rerun()
                        else: st.error(f"No data for '{raw_t}'.")
                else: st.rerun()

        sel_ticker=st.session_state.get("chart_sel")
        row=None
        if sel_ticker: row=next((r for r in results if r["Ticker"]==sel_ticker),None)
        if row is None and results: row=results[0]; sel_ticker=row["Ticker"]
        if row:
            df_plot=row["_df"]; log_t=row["_log"]
            curr="INR" if sel_ticker.endswith(".NS") else "USD"
            lbl=row["Label"]; in_wl=sel_ticker in st.session_state.watchlist
            st.markdown(f"#### {lbl} — {row['Market']} · {tf_label} · {period_label}")
            st.markdown("### Performance Summary")
            show_performance(log_t,row,curr,capital)
            st.markdown("---")
            if in_wl:
                if st.button(f"Remove {lbl} from Watchlist",key="wl_rm"): st.session_state.watchlist.remove(sel_ticker); st.rerun()
            else:
                if st.button(f"★ Add {lbl} to Watchlist",key="wl_add",type="primary"): st.session_state.watchlist.append(sel_ticker); st.rerun()
            tf2=st.radio("View:",["1W","1M","3M","6M","1Y","Full"],index=5,horizontal=True,key="chart_tf")
            tfm={"1W":7,"1M":30,"3M":90,"6M":180,"1Y":365}
            dfv=df_plot if tf2=="Full" else df_plot[df_plot.index>=df_plot.index.max()-timedelta(days=tfm[tf2])]
            st.plotly_chart(draw_chart(dfv,log_t,strategy_name),use_container_width=True)
            st.subheader("Trade Log")
            if log_t:
                ldf=pd.DataFrame(log_t); ldf.rename(columns={"Portfolio":f"Portfolio ({curr})"},inplace=True)
                def cr(v):
                    try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                    except: return ""
                def cst(v):
                    if v=="OPEN": return "color:#3fb950;font-weight:bold"
                    if v=="CLOSED": return "color:#8b949e"
                    return ""
                st.dataframe(ldf.style.map(cr,subset=["Return %"]).map(cst,subset=["Status"]),use_container_width=True,hide_index=True)
            else: st.info("No trades triggered.")

    elif bot_rows:
        bot_label=st.session_state.get("bot_bt_label","Bot Consensus Backtest")
        st.markdown(f"## 🤖 {bot_label}")
        st.caption("Exact same logic as the live bot — all 8 strategies, market-specific thresholds.")
        buy_bt=[r for r in bot_rows if r["Signal"]=="BUY"]
        sell_bt=[r for r in bot_rows if r["Signal"]=="SELL"]
        hold_bt=[r for r in bot_rows if r["Signal"]=="HOLD"]
        b1,b2,b3=st.columns(3)
        b1.success(f"🟢 BUY — {len(buy_bt)}"); b2.error(f"🔴 SELL — {len(sell_bt)}"); b3.info(f"⚪ HOLD — {len(hold_bt)}")
        if buy_bt:
            st.markdown("### Top BUY Signals")
            st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],"Price":fmt(r["Price"]),
                "Threshold":f"{r['Min Votes']}/8","Buy Votes":r["Buy Votes"],
                "Strategy %":fmt(r["Net %"],"%"),"B&H %":fmt(r["B&H %"],"%"),
                "Win Rate":fmt(r["Win Rate"],"%"),"Trades":r["Trades"],"End Value":fmt(r["End Value"])}
                for r in buy_bt]),use_container_width=True,hide_index=True)
        st.markdown("### Full Bot Leaderboard")
        mf=st.radio("Filter:",["All","US","India","Crypto","Commodity"],horizontal=True,key="bot_bt_mkt")
        fd=bot_rows if mf=="All" else [r for r in bot_rows if r["Market"]==mf]
        if fd:
            st.dataframe(pd.DataFrame([{"Asset":r["Label"],"Market":r["Market"],"Price":fmt(r["Price"]),
                "Signal":r["Signal"],"Threshold":f"{r['Min Votes']}/8",
                "Buy V":r["Buy Votes"],"Sell V":r["Sell Votes"],
                "Strategy %":fmt(r["Net %"],"%"),"B&H %":fmt(r["B&H %"],"%"),
                "Win Rate":fmt(r["Win Rate"],"%"),"Trades":r["Trades"]}
                for r in fd]).style.map(sig_color,subset=["Signal"]),use_container_width=True,hide_index=True)
        st.markdown("### Bot Trade Log")
        if fd:
            sel_bot=st.selectbox("Select asset:",
                [r["Ticker"] for r in fd],format_func=ticker_label,key="bot_bt_sel")
            sbr=next((r for r in fd if r["Ticker"]==sel_bot),None)
            if sbr:
                curr="INR" if sel_bot.endswith(".NS") else "USD"
                st.markdown("### Performance Summary")
                show_performance(sbr["_log"],sbr,curr,capital)
                st.markdown("---")
                dfv=sbr["_df"]; log_b=sbr["_log"]
                fig=go.Figure()
                try:
                    fig.add_trace(go.Scatter(x=dfv.index,y=dfv["Close"],name="Price",line=dict(color="white",width=1.5)))
                    bd=[t["Entry Date"] for t in log_b]; bp=[t["Entry Price"] for t in log_b]
                    sd=[t["Exit Date"] for t in log_b if t["Status"]=="CLOSED"]
                    sp=[t["Exit Price"] for t in log_b if t["Status"]=="CLOSED"]
                    if bd: fig.add_trace(go.Scatter(x=bd,y=bp,mode="markers",name="BUY",marker=dict(symbol="triangle-up",color="lime",size=10)))
                    if sd: fig.add_trace(go.Scatter(x=sd,y=sp,mode="markers",name="SELL",marker=dict(symbol="triangle-down",color="red",size=10)))
                except: pass
                fig.update_layout(template="plotly_dark",height=400,margin=dict(l=20,r=20,t=30,b=20),
                                   legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
                st.plotly_chart(fig,use_container_width=True)
                if log_b:
                    ldf=pd.DataFrame(log_b)
                    def cr2(v):
                        try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                        except: return ""
                    def cs3(v):
                        if v=="OPEN": return "color:#3fb950;font-weight:bold"
                        if v=="CLOSED": return "color:#8b949e"
                        return ""
                    st.dataframe(ldf.style.map(cr2,subset=["Return %"]).map(cs3,subset=["Status"]),use_container_width=True,hide_index=True)
                else: st.info("No trades triggered.")
    else:
        st.info("Choose a strategy and period → click a Run button in the sidebar.")
        st.markdown("**Nifty 50** for a quick scan · **Nifty 200** for a full India scan (5–8 mins)")
        st.markdown("**Or** click **Run Bot Backtest** to test the consensus bot logic.")

# ═══════════════════════════════════════════════════════════════
# TAB 2 — PAPER TRADING BOT
# ═══════════════════════════════════════════════════════════════
with tab_bot:
    st.title("🤖 Paper Trading Bot")
    st.markdown("Each strategy runs on its optimal timeframe. Votes tallied across all 8.")
    if not ALPACA_AVAILABLE:
        st.error("Add `alpaca-py` to requirements.txt"); st.code("alpaca-py"); st.stop()
    default_key=st.secrets.get("ALPACA_KEY",""); default_secret=st.secrets.get("ALPACA_SECRET","")
    if default_key and default_secret:
        st.success("Alpaca keys loaded from Streamlit Secrets.")
        api_key=default_key; api_secret=default_secret
    else:
        b1,b2=st.columns(2)
        with b1: api_key=st.text_input("Alpaca API Key",type="password",key="bot_key")
        with b2: api_secret=st.text_input("Alpaca API Secret",type="password",key="bot_secret")
    if not api_key or not api_secret:
        st.info("Enter Alpaca Paper Trading keys above.")
        st.markdown("1. Go to [alpaca.markets](https://alpaca.markets)\n2. Paper Trading → API Keys → Generate\n3. Or add to Streamlit Secrets:\n```\nALPACA_KEY = 'your_key'\nALPACA_SECRET = 'your_secret'\n```")
    else:
        try:
            bot_client=TradingClient(api_key,api_secret,paper=True)
            acct=bot_client.get_account()
            st.markdown("### Account")
            a1,a2,a3,a4=st.columns(4)
            a1.metric("Portfolio",f"${float(acct.portfolio_value):,.0f}")
            a2.metric("Cash",f"${float(acct.cash):,.0f}")
            a3.metric("P&L Today",f"${float(acct.equity)-float(acct.last_equity):+,.0f}")
            a4.metric("Buying Power",f"${float(acct.buying_power):,.0f}")
            st.markdown("---"); st.markdown("### Bot Settings")
            s1,s2,s3=st.columns(3)
            with s1: trade_mode=st.radio("Size Mode",["Fixed $","% of Portfolio"],key="trade_mode",horizontal=True)
            with s2:
                if trade_mode=="Fixed $": fixed_amt=st.number_input("Amount ($)",min_value=10,max_value=10000,value=500,step=50,key="fixed_amt")
                else: bot_cap_pct=st.slider("Capital %",1,25,2,key="bot_cap")
            with s3: max_pos=st.slider("Max positions",1,10,5,key="max_pos")
            allow_short=st.toggle("Allow Short Selling (US Stocks only)",value=False,key="allow_short")
            if allow_short: st.warning("Short selling only works for US stocks on Alpaca.")
            st.info("**Thresholds:** 🇺🇸 US=5/8 · 🇮🇳 India=4/8 · 🪙 Crypto=3/8 · 🛢️ Commodities=4/8")
            bot_tickers=st.multiselect("Assets to scan",DEFAULT_US+DEFAULT_CR+DEFAULT_CM,
                default=["AAPL","NVDA","MSFT","BTC-USD","GC=F"],format_func=ticker_label,key="bot_tickers")
            st.markdown("---")
            c1,c2=st.columns(2)
            with c1: auto_trade=st.toggle("Enable Auto Trading",value=False,key="auto_trade")
            with c2: scan_interval=st.selectbox("Scan every",["5 mins","15 mins","30 mins","1 hour"],key="scan_iv")
            iv_map={"5 mins":300,"15 mins":900,"30 mins":1800,"1 hour":3600}
            iv_sec=iv_map[scan_interval]
            if auto_trade:
                st.success(f"Auto trading ON — scanning every {scan_interval}")
                import streamlit.components.v1 as components
                components.html(f"<script>setTimeout(()=>window.location.reload(),{iv_sec*1000});</script>",height=0)
                scan_btn=True
            else:
                scan_btn=st.button("🔍 Scan All Timeframes & Execute Trades",type="primary",use_container_width=True)
            if scan_btn and bot_tickers:
                positions={}
                try: positions={p.symbol:float(p.qty) for p in bot_client.get_all_positions()}
                except: pass
                pending=set()
                try:
                    oo=bot_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
                    pending={o.symbol for o in oo}
                except: pass
                port_val=float(bot_client.get_account().portfolio_value)
                st.markdown("### Live Multi-Timeframe Scan")
                prog=st.progress(0); rows=[]
                for i,ticker in enumerate(bot_tickers):
                    prog.progress((i+1)/len(bot_tickers))
                    try:
                        buy_v,sell_v,detail=get_multi_tf_consensus(ticker)
                        pdf=fetch_data(ticker,interval="1d",days=5)
                        if pdf is None: pdf=fetch_data(ticker,interval="1h",days=2)
                        price=float(pdf["Close"].iloc[-1]) if pdf is not None and len(pdf)>0 else 0.0
                        min_v=get_min_votes(ticker); action="—"; status="HOLD"
                        already_in=ticker in positions or ticker in pending
                        if buy_v>=min_v and buy_v>sell_v:
                            status="BUY"
                            pos_qty=positions.get(ticker,0)
                            if pos_qty<0:
                                try:
                                    bot_client.close_position(ticker); action="CLOSED SHORT"
                                    st.session_state.bot_log.append({"Time":datetime.now().strftime("%H:%M:%S"),"Asset":ticker_label(ticker),"Action":"CLOSE SHORT","Price":round(price,2),"Amount":"full","Votes":f"{buy_v}/8","Threshold":f"{min_v}/8"})
                                except Exception as e: action=f"Failed:{e}"
                            elif not already_in and len(positions)<max_pos:
                                try:
                                    qty_usd=float(fixed_amt) if trade_mode=="Fixed $" else port_val*(bot_cap_pct/100)
                                    bot_client.submit_order(MarketOrderRequest(symbol=ticker,notional=round(qty_usd,2),side=OrderSide.BUY,time_in_force=TimeInForce.DAY))
                                    action=f"BOUGHT ${qty_usd:.0f}"; positions[ticker]=1
                                    st.session_state.bot_log.append({"Time":datetime.now().strftime("%H:%M:%S"),"Asset":ticker_label(ticker),"Action":"BUY","Price":round(price,2),"Amount":f"${qty_usd:.0f}","Votes":f"{buy_v}/8","Threshold":f"{min_v}/8"})
                                except Exception as e: action=f"Failed:{e}"
                            elif already_in: action="Already holding/ordered"
                            else: action="Max positions reached"
                        elif sell_v>=min_v and sell_v>buy_v:
                            status="SELL"; mkt=get_market(ticker)
                            if ticker in positions:
                                pos_qty=positions[ticker]
                                if pos_qty>0:
                                    try:
                                        bot_client.close_position(ticker); action="CLOSED LONG"
                                        st.session_state.bot_log.append({"Time":datetime.now().strftime("%H:%M:%S"),"Asset":ticker_label(ticker),"Action":"CLOSE LONG","Price":round(price,2),"Amount":"full","Votes":f"{sell_v}/8","Threshold":f"{min_v}/8"})
                                    except Exception as e: action=f"Failed:{e}"
                                else: action="Already short"
                            elif allow_short and mkt=="US" and ticker not in pending and len(positions)<max_pos:
                                try:
                                    qty_usd=float(fixed_amt) if trade_mode=="Fixed $" else port_val*(bot_cap_pct/100)
                                    shares=max(1,int(qty_usd/price)) if price>0 else 1
                                    dollar_val=round(shares*price,2)
                                    bot_client.submit_order(MarketOrderRequest(
                                        symbol=ticker,qty=shares,
                                        side=OrderSide.SELL,time_in_force=TimeInForce.DAY))
                                    action=f"SHORT {shares} shares (${dollar_val:.0f})"
                                    positions[ticker]=-1
                                    st.session_state.bot_log.append({
                                        "Time":datetime.now().strftime("%H:%M:%S"),
                                        "Asset":ticker_label(ticker),
                                        "Action":"SHORT",
                                        "Price":round(price,2),
                                        "Amount":f"{shares} shares (~${dollar_val:.0f})",
                                        "Votes":f"{sell_v}/8",
                                        "Threshold":f"{min_v}/8"})
                                except Exception as e: action=f"Short failed:{e}"
                            elif allow_short and mkt!="US": action="Short N/A (US only)"
                            else: action="No long to close"
                        rows.append({"Asset":ticker_label(ticker),"Market":get_market(ticker),
                            "Price":round(price,2) if price>0 else "—","Signal":status,
                            "Threshold":f"{min_v}/8","Buy Votes":buy_v,"Sell Votes":sell_v,
                            "Action":action,"Holding":"Yes" if ticker in positions else "No"})
                    except Exception as e:
                        rows.append({"Asset":ticker_label(ticker),"Market":"—","Price":"—","Signal":"ERROR","Threshold":"—","Buy Votes":0,"Sell Votes":0,"Action":str(e),"Holding":"—"})
                prog.empty()
                if rows: st.dataframe(pd.DataFrame(rows).style.map(sig_color,subset=["Signal"]),use_container_width=True,hide_index=True)
            st.markdown("---"); st.subheader("Open Positions")
            try:
                pos_list=bot_client.get_all_positions()
                if pos_list:
                    def plc(v):
                        try: return "color:#3fb950" if float(v)>=0 else "color:#f85149"
                        except: return ""
                    st.dataframe(pd.DataFrame([{"Asset":p.symbol,"Qty":float(p.qty),"Avg":float(p.avg_entry_price),
                        "Current":float(p.current_price),"P&L $":round(float(p.unrealized_pl),2),
                        "P&L %":round(float(p.unrealized_plpc)*100,2)} for p in pos_list]).style.map(plc,subset=["P&L $","P&L %"]),
                        use_container_width=True,hide_index=True)
                    st.markdown("**Close individual position:**")
                    for p in pos_list:
                        c1,c2,c3=st.columns([2,2,1]); pnl=round(float(p.unrealized_pl),2)
                        c1.markdown(f"**{p.symbol}**"); c2.markdown(f"P&L: {'🟢' if pnl>=0 else '🔴'} ${pnl:+.2f}")
                        if c3.button("Close",key=f"close_pos_{p.symbol}",use_container_width=True):
                            bot_client.close_position(p.symbol); st.success(f"{p.symbol} closed!"); st.rerun()
                    st.markdown("---")
                    if st.button("🔴 Close ALL Positions",type="primary",use_container_width=True):
                        bot_client.close_all_positions(cancel_orders=True); st.success("All closed!"); st.rerun()
                else: st.info("No open positions.")
            except Exception as e: st.error(f"Positions error: {e}")
            st.markdown("---"); st.subheader("Pending Orders")
            try:
                open_orders=bot_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
                if open_orders:
                    st.dataframe(pd.DataFrame([{"Ticker":o.symbol,"Side":o.side.value.upper(),
                        "Amount":f"${float(o.notional):.0f}" if o.notional else str(o.qty),
                        "Status":o.status.value,"Time":o.created_at.strftime("%H:%M:%S")}
                        for o in open_orders]),use_container_width=True,hide_index=True)
                    st.markdown("**Cancel individual order:**")
                    for o in open_orders:
                        amt=f"${float(o.notional):.0f}" if o.notional else str(o.qty)
                        c1,c2,c3=st.columns([2,2,1])
                        c1.markdown(f"**{o.symbol}**"); c2.markdown(f"{o.side.value.upper()} {amt}")
                        if c3.button("❌",key=f"cancel_{o.id}",help=f"Cancel {o.symbol}"):
                            try: bot_client.cancel_order_by_id(o.id); st.success(f"{o.symbol} cancelled!"); st.rerun()
                            except Exception as e: st.error(f"Failed: {e}")
                    st.markdown("---")
                    if st.button("❌ Cancel ALL Pending Orders",use_container_width=True):
                        bot_client.cancel_orders(); st.success("All cancelled!"); st.rerun()
                else: st.info("No pending orders.")
            except Exception as e: st.error(f"Pending orders error: {e}")
            st.markdown("---"); st.subheader("Bot Trade Log")
            if st.session_state.bot_log:
                st.dataframe(pd.DataFrame(st.session_state.bot_log),use_container_width=True,hide_index=True)
            else: st.info("No trades this session.")
            st.markdown("---"); st.subheader("All Orders (Alpaca)")
            try:
                orders=bot_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL,limit=20))
                if orders:
                    st.dataframe(pd.DataFrame([{"Time":o.created_at.strftime("%Y-%m-%d %H:%M"),
                        "Ticker":o.symbol,"Side":o.side.value.upper(),
                        "Amount":o.notional or o.qty,"Status":o.status.value,
                        "Fill $":o.filled_avg_price or "—"} for o in orders]),use_container_width=True,hide_index=True)
                else: st.info("No orders yet.")
            except Exception as e: st.error(f"Error: {e}")
        except Exception as e: st.error(f"Could not connect to Alpaca: {e}")
