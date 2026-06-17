import { useState, useCallback } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceLine, BarChart, Bar } from "recharts";

// ─── CONSTANTS ────────────────────────────────────────────────────────────────
const MARKETS = {
  "🇺🇸 US Tech": { tickers: ["AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","AMD","NFLX","V","JPM","MS"], currency: "USD" },
  "🇮🇳 Nifty 50": { tickers: ["RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","AXISBANK.NS","WIPRO.NS","BAJFINANCE.NS","SBIN.NS","LT.NS"], currency: "INR" },
  "🪙 Crypto": { tickers: ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD","LINK-USD"], currency: "USD" },
  "🛢️ Commodities": { tickers: ["GC=F","SI=F","CL=F","NG=F","HG=F"], currency: "USD" },
};

const PERIODS = { "1Y": 365, "5Y": 1825, "10Y": 3650 };

const STRATEGIES = [
  { id: "triple_sma",   label: "Triple SMA Ribbon",        color: "#58a6ff", desc: "BUY: SMA20>SMA50>SMA200 stack. SELL: price < SMA50 or SMA200." },
  { id: "lux_atr",      label: "LuxAlgo ATR Channel",      color: "#3fb950", desc: "Adaptive ATR trail. BUY: close crosses above floor. SELL: close drops below floor." },
  { id: "macd",         label: "MACD Momentum",            color: "#e3b341", desc: "BUY: MACD > Signal line. SELL: MACD < Signal line." },
  { id: "mean_rev",     label: "Mean Reversion (Dip Buy)", color: "#f78166", desc: "BUY: price dips below SMA20 in uptrend (SMA200>SMA50>SMA20). SELL: price reclaims SMA50." },
  { id: "ema_ribbon",   label: "EMA 9/21 Ribbon",          color: "#d2a8ff", desc: "BUY: EMA9 crosses above EMA21. SELL: EMA9 crosses below EMA21." },
  { id: "bb_squeeze",   label: "Bollinger Band Squeeze",   color: "#ffa657", desc: "BUY: close < lower BB + RSI<35. SELL: close > upper BB or RSI>65." },
];

// ─── MATH HELPERS ─────────────────────────────────────────────────────────────
const sma = (arr, w) => arr.map((_, i) => i < w - 1 ? null : arr.slice(i-w+1,i+1).reduce((a,b)=>a+b,0)/w);
const ema = (arr, span) => {
  const k = 2/(span+1), out = Array(arr.length).fill(null);
  let start = arr.findIndex(v=>v!=null);
  if (start<0) return out;
  out[start] = arr[start];
  for (let i=start+1;i<arr.length;i++) out[i] = arr[i]*k + out[i-1]*(1-k);
  return out;
};
const atr = (h,l,c,p=14) => {
  const tr = h.map((hi,i)=>i===0?hi-l[i]:Math.max(hi-l[i],Math.abs(hi-c[i-1]),Math.abs(l[i]-c[i-1])));
  return sma(tr,p);
};
const rsi = (closes, p=14) => {
  const out = Array(closes.length).fill(null);
  for (let i=p;i<closes.length;i++) {
    let g=0,ls=0;
    for (let j=i-p+1;j<=i;j++) { const d=closes[j]-closes[j-1]; if(d>0) g+=d; else ls-=d; }
    const avg_g=g/p, avg_l=ls/p;
    out[i] = avg_l===0 ? 100 : 100 - 100/(1+avg_g/avg_l);
  }
  return out;
};
const stddev = (arr, w) => arr.map((_,i) => {
  if (i<w-1) return null;
  const sl = arr.slice(i-w+1,i+1);
  const m = sl.reduce((a,b)=>a+b,0)/w;
  return Math.sqrt(sl.reduce((a,b)=>a+(b-m)**2,0)/w);
});

function computeSignals(rows, stratId) {
  const closes = rows.map(r=>r.close);
  const highs  = rows.map(r=>r.high||r.close);
  const lows   = rows.map(r=>r.low||r.close);
  const n = closes.length;
  let signals = Array(n).fill(0);

  if (stratId === "triple_sma") {
    const s20=sma(closes,20), s50=sma(closes,50), s200=sma(closes,200);
    for (let i=0;i<n;i++) {
      if (!s20[i]||!s50[i]||!s200[i]) continue;
      if (s20[i]>s50[i] && s50[i]>s200[i]) signals[i]=1;
      else if (closes[i]<s50[i] || closes[i]<s200[i]) signals[i]=-1;
      else signals[i] = signals[i-1]||0;
    }
    return rows.map((r,i)=>({...r,signal:signals[i],sma20:s20[i],sma50:s50[i],sma200:s200[i]}));
  }

  if (stratId === "lux_atr") {
    const atrV=atr(highs,lows,closes,14);
    const mid=rows.map((r,i)=>(highs[i]+lows[i])/2);
    let floor=Array(n).fill(0), ceil=Array(n).fill(0);
    for (let i=1;i<n;i++) {
      if (!atrV[i]) continue;
      const tf=mid[i]-3*atrV[i], tc=mid[i]+3*atrV[i];
      floor[i] = closes[i-1]>floor[i-1] ? Math.max(tf,floor[i-1]) : tf;
      ceil[i]  = closes[i-1]<ceil[i-1]  ? Math.min(tc,ceil[i-1])  : tc;
      if (closes[i]>ceil[i]) signals[i]=1;
      else if (closes[i]<floor[i]) signals[i]=-1;
      else signals[i]=signals[i-1]||0;
    }
    return rows.map((r,i)=>({...r,signal:signals[i],band:signals[i]===1?floor[i]:ceil[i]}));
  }

  if (stratId === "macd") {
    const e12=ema(closes,12), e26=ema(closes,26);
    const macdLine=e12.map((v,i)=>v&&e26[i]?v-e26[i]:null);
    const sigLine=ema(macdLine,9);
    for (let i=0;i<n;i++) {
      if (!macdLine[i]||!sigLine[i]) continue;
      signals[i] = macdLine[i]>sigLine[i] ? 1 : -1;
    }
    return rows.map((r,i)=>({...r,signal:signals[i],macd:macdLine[i],macdSig:sigLine[i]}));
  }

  if (stratId === "mean_rev") {
    const s20=sma(closes,20), s50=sma(closes,50), s200=sma(closes,200);
    for (let i=0;i<n;i++) {
      if (!s20[i]||!s50[i]||!s200[i]) { signals[i]=signals[i-1]||0; continue; }
      const buyRule  = s200[i]>s50[i] && s50[i]>s20[i] && closes[i]<s20[i];
      const sellRule = closes[i]>s50[i];
      if (buyRule) signals[i]=1;
      else if (sellRule) signals[i]=-1;
      else signals[i]=signals[i-1]||0;
    }
    return rows.map((r,i)=>({...r,signal:signals[i],sma20:s20[i],sma50:s50[i],sma200:s200[i]}));
  }

  if (stratId === "ema_ribbon") {
    const e9=ema(closes,9), e21=ema(closes,21);
    for (let i=1;i<n;i++) {
      if (!e9[i]||!e21[i]) continue;
      if (e9[i]>e21[i] && e9[i-1]<=e21[i-1]) signals[i]=1;
      else if (e9[i]<e21[i] && e9[i-1]>=e21[i-1]) signals[i]=-1;
      else signals[i]=signals[i-1]||0;
    }
    return rows.map((r,i)=>({...r,signal:signals[i],ema9:e9[i],ema21:e21[i]}));
  }

  if (stratId === "bb_squeeze") {
    const mid=sma(closes,20), sd=stddev(closes,20), rsiV=rsi(closes,14);
    const upper=mid.map((m,i)=>m&&sd[i]?m+2*sd[i]:null);
    const lower=mid.map((m,i)=>m&&sd[i]?m-2*sd[i]:null);
    for (let i=0;i<n;i++) {
      if (!upper[i]||!lower[i]||!rsiV[i]) { signals[i]=signals[i-1]||0; continue; }
      if (closes[i]<lower[i] && rsiV[i]<35) signals[i]=1;
      else if (closes[i]>upper[i] || rsiV[i]>65) signals[i]=-1;
      else signals[i]=signals[i-1]||0;
    }
    return rows.map((r,i)=>({...r,signal:signals[i],bbUpper:upper[i],bbLower:lower[i],bbMid:mid[i]}));
  }

  return rows.map(r=>({...r,signal:0}));
}

function backtest(rows, capital=100000) {
  let pos=false, entry=0, val=capital, wins=0, trades=0;
  const log=[];
  let entryDate="";
  for (let i=0;i<rows.length;i++) {
    const {signal,close,date}=rows[i];
    if (signal===1 && !pos) { pos=true; entry=close; entryDate=date; trades++; }
    else if (signal===-1 && pos) {
      pos=false;
      const ret=(close-entry)/entry;
      val*=(1+ret);
      if (close>entry) wins++;
      log.push({type:"EXIT",entryDate,entryPrice:entry,exitDate:date,exitPrice:close,ret:ret*100,val});
      entry=0;
    }
  }
  if (pos) {
    const last=rows[rows.length-1];
    const ret=(last.close-entry)/entry;
    val*=(1+ret);
    if (last.close>entry) wins++;
    log.push({type:"ACTIVE",entryDate,entryPrice:entry,exitDate:"Now",exitPrice:last.close,ret:ret*100,val});
  }
  const bh=(rows[rows.length-1].close/rows.find(r=>r.signal!==0)?.close-1)*100||0;
  return { val, trades, wins, winRate:trades?wins/trades*100:0, netPct:(val/capital-1)*100, bh, log };
}

// ─── DATA FETCH ───────────────────────────────────────────────────────────────
async function fetchYF(ticker, days) {
  const end=Math.floor(Date.now()/1000);
  const start=end-days*86400;
  const url=`https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?interval=1d&period1=${start}&period2=${end}`;
  try {
    const r=await fetch(`https://api.allorigins.win/get?url=${encodeURIComponent(url)}`);
    const j=await r.json();
    const d=JSON.parse(j.contents);
    const res=d?.chart?.result?.[0];
    if (!res) return null;
    const {timestamp,indicators:{quote:[{open,high,low,close}]}}=res;
    return timestamp.map((t,i)=>({
      date:new Date(t*1000).toISOString().split("T")[0],
      open:open[i],high:high[i],low:low[i],close:close[i]
    })).filter(x=>x.close!=null);
  } catch { return null; }
}

// ─── HELPERS ──────────────────────────────────────────────────────────────────
const fmtN=(v,d=2)=>v==null?"—":v.toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d});
const fmtP=v=>(v>=0?"+":"")+v.toFixed(2)+"%";
const C={bg:"#0d1117",surface:"#161b22",border:"#30363d",text:"#e6edf3",muted:"#8b949e",green:"#3fb950",red:"#f85149",blue:"#58a6ff",yellow:"#e3b341",purple:"#d2a8ff"};

export default function App() {
  const [market,setMarket]       = useState("🇺🇸 US Tech");
  const [stratId,setStratId]     = useState("triple_sma");
  const [periods,setPeriods]     = useState({"1Y":true,"5Y":true,"10Y":true});
  const [capital]                = useState(100000);
  const [loading,setLoading]     = useState(false);
  const [progress,setProgress]   = useState(0);
  const [results,setResults]     = useState(null); // { byPeriod, charts }
  const [active,setActive]       = useState(null);
  const [chartPeriod,setChartPeriod] = useState("1Y");
  const [tab,setTab]             = useState("leaderboard"); // leaderboard | chart | trades

  const {tickers,currency}=MARKETS[market];
  const selectedPeriods=Object.keys(periods).filter(p=>periods[p]);
  const strat=STRATEGIES.find(s=>s.id===stratId);

  const run = useCallback(async()=>{
    if (!selectedPeriods.length) return;
    setLoading(true); setProgress(0); setResults(null);
    const byPeriod={}, charts={};

    // fetch raw data for max period (10Y) once per ticker
    const maxDays=Math.max(...selectedPeriods.map(p=>PERIODS[p]));

    for (let i=0;i<tickers.length;i++) {
      const ticker=tickers[i];
      setProgress(Math.round((i/tickers.length)*100));
      const raw=await fetchYF(ticker, maxDays+200); // extra 200 for indicator warmup
      if (!raw||raw.length<60) continue;
      charts[ticker]=raw;

      for (const p of selectedPeriods) {
        const cutoff=new Date(); cutoff.setDate(cutoff.getDate()-PERIODS[p]);
        const slice=raw.filter(r=>new Date(r.date)>=cutoff);
        if (slice.length<50) continue;
        const enriched=computeSignals(slice,stratId);
        const bt=backtest(enriched,capital);
        if (!byPeriod[p]) byPeriod[p]=[];
        byPeriod[p].push({
          ticker, price:slice[slice.length-1].close,
          signal:enriched[enriched.length-1].signal,
          ...bt, enriched
        });
      }
    }

    // sort each period by netPct desc
    Object.keys(byPeriod).forEach(p=>{
      byPeriod[p].sort((a,b)=>b.netPct-a.netPct);
    });

    setResults({byPeriod,charts});
    const first=Object.values(byPeriod)[0]?.[0]?.ticker;
    setActive(first||null);
    setChartPeriod(selectedPeriods[selectedPeriods.length-1]);
    setLoading(false); setProgress(100);
  },[market,stratId,periods,capital]);

  // chart rows for active ticker + selected chart period
  const chartRows = (() => {
    if (!results||!active) return [];
    const pd=results.byPeriod[chartPeriod];
    if (!pd) return [];
    return pd.find(r=>r.ticker===active)?.enriched||[];
  })();

  const chartData = chartRows.slice(-Math.min(chartRows.length,500)).map(r=>({
    date:r.date, Price:r.close,
    ...(r.sma20!=null?{"SMA 20":r.sma20}:{}),
    ...(r.sma50!=null?{"SMA 50":r.sma50}:{}),
    ...(r.sma200!=null?{"SMA 200":r.sma200}:{}),
    ...(r.ema9!=null?{"EMA 9":r.ema9}:{}),
    ...(r.ema21!=null?{"EMA 21":r.ema21}:{}),
    ...(r.bbUpper!=null?{"BB Upper":r.bbUpper,"BB Lower":r.bbLower,"BB Mid":r.bbMid}:{}),
    ...(r.band!=null?{"ATR Band":r.band}:{}),
    ...(r.macd!=null?{}:{}),
    Signal:r.signal,
  }));

  const tradeLog = (() => {
    if (!results||!active) return [];
    const pd=results.byPeriod[chartPeriod];
    return pd?.find(r=>r.ticker===active)?.log||[];
  })();

  const activeStat = (() => {
    if (!results||!active) return null;
    const pd=results.byPeriod[chartPeriod];
    return pd?.find(r=>r.ticker===active);
  })();

  // BUY / SELL / HOLD lists
  const signalLists = (() => {
    if (!results) return {buy:[],sell:[]};
    const pd=results.byPeriod[chartPeriod]||[];
    return {
      buy: pd.filter(r=>r.signal===1).map(r=>r.ticker),
      sell: pd.filter(r=>r.signal===-1).map(r=>r.ticker),
    };
  })();

  const LINE_COLORS={"SMA 20":"#22d3ee","SMA 50":"#fbbf24","SMA 200":"#e879f9","EMA 9":"#34d399","EMA 21":"#f87171","BB Upper":"#fb923c","BB Lower":"#fb923c","BB Mid":"#94a3b8","ATR Band":"#4ade80","Price":"#ffffff"};

  const btn=(label,active,onClick,col="#58a6ff")=>(
    <button onClick={onClick} style={{padding:"5px 14px",borderRadius:6,border:`1px solid ${active?col:"#30363d"}`,
      background:active?col+"22":"transparent",color:active?col:"#8b949e",fontSize:12,cursor:"pointer",fontWeight:active?700:400}}>
      {label}
    </button>
  );

  return (
    <div style={{background:C.bg,minHeight:"100vh",color:C.text,fontFamily:"'Inter',sans-serif",display:"flex",flexDirection:"column"}}>
      {/* HEADER */}
      <div style={{background:"linear-gradient(135deg,#161b22,#1c2333)",borderBottom:`1px solid ${C.border}`,padding:"14px 24px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <div>
          <div style={{fontSize:20,fontWeight:800}}>🌎 Global Multi-Market Backtester Pro</div>
          <div style={{fontSize:11,color:C.muted,marginTop:2}}>6 strategies · 3 periods · live signal screener · trade ledger</div>
        </div>
        <div style={{fontSize:11,color:C.muted,textAlign:"right"}}>
          {strat && <span style={{color:strat.color}}>● {strat.label}</span>}
        </div>
      </div>

      <div style={{display:"flex",flex:1}}>
        {/* SIDEBAR */}
        <div style={{width:230,minWidth:230,background:C.surface,borderRight:`1px solid ${C.border}`,padding:"16px 14px",display:"flex",flexDirection:"column",gap:16}}>
          
          <div>
            <div style={{fontSize:10,color:C.muted,fontWeight:700,letterSpacing:1,marginBottom:6}}>MARKET</div>
            {Object.keys(MARKETS).map(m=>(
              <div key={m} onClick={()=>setMarket(m)} style={{padding:"6px 10px",borderRadius:6,cursor:"pointer",marginBottom:3,fontSize:12,
                background:market===m?"#1f6feb22":"transparent",border:`1px solid ${market===m?"#1f6feb66":"transparent"}`,
                color:market===m?C.blue:C.muted}}>
                {m}
              </div>
            ))}
          </div>

          <div>
            <div style={{fontSize:10,color:C.muted,fontWeight:700,letterSpacing:1,marginBottom:6}}>STRATEGY</div>
            {STRATEGIES.map(s=>(
              <div key={s.id} onClick={()=>setStratId(s.id)} style={{padding:"6px 10px",borderRadius:6,cursor:"pointer",marginBottom:3,fontSize:11,
                background:stratId===s.id?s.color+"22":"transparent",border:`1px solid ${stratId===s.id?s.color+"66":"transparent"}`,
                color:stratId===s.id?s.color:C.muted}}>
                {s.label}
              </div>
            ))}
            {strat && <div style={{marginTop:8,fontSize:10,color:C.muted,lineHeight:1.5,padding:"6px 8px",background:"#0d1117",borderRadius:6}}>{strat.desc}</div>}
          </div>

          <div>
            <div style={{fontSize:10,color:C.muted,fontWeight:700,letterSpacing:1,marginBottom:6}}>BACKTEST PERIODS</div>
            {Object.keys(PERIODS).map(p=>(
              <div key={p} onClick={()=>setPeriods(prev=>({...prev,[p]:!prev[p]}))}
                style={{padding:"5px 10px",borderRadius:6,cursor:"pointer",marginBottom:3,fontSize:12,display:"flex",alignItems:"center",gap:7,
                  background:periods[p]?"#238636"+"22":"transparent",border:`1px solid ${periods[p]?"#23863666":"transparent"}`,
                  color:periods[p]?C.green:C.muted}}>
                <span>{periods[p]?"✓":"○"}</span>{p}
              </div>
            ))}
          </div>

          <button onClick={run} disabled={loading||!selectedPeriods.length}
            style={{padding:"10px 0",borderRadius:8,border:"none",
              background:loading?"#21262d":"linear-gradient(135deg,#238636,#2ea043)",
              color:loading?C.muted:"#fff",fontWeight:800,fontSize:13,cursor:loading?"not-allowed":"pointer",marginTop:"auto"}}>
            {loading?`Running ${progress}%`:"▶ Run Backtest"}
          </button>
        </div>

        {/* MAIN */}
        <div style={{flex:1,padding:"20px 22px",overflow:"auto",minWidth:0}}>

          {results && (
            <>
              {/* SIGNAL SUMMARY BADGES */}
              <div style={{display:"flex",gap:12,marginBottom:18,flexWrap:"wrap"}}>
                <div style={{background:"#23863622",border:"1px solid #23863666",borderRadius:10,padding:"10px 18px"}}>
                  <div style={{fontSize:10,color:C.muted,marginBottom:4}}>🟢 BUY SIGNALS ({chartPeriod})</div>
                  <div style={{fontSize:12,color:C.green,fontWeight:700,lineHeight:1.8}}>
                    {signalLists.buy.length ? signalLists.buy.map(t=>t.replace(".NS","")).join(" · ") : "None"}
                  </div>
                </div>
                <div style={{background:"#f8516922",border:"1px solid #f8516966",borderRadius:10,padding:"10px 18px"}}>
                  <div style={{fontSize:10,color:C.muted,marginBottom:4}}>🔴 SELL / CASH ({chartPeriod})</div>
                  <div style={{fontSize:12,color:C.red,fontWeight:700,lineHeight:1.8}}>
                    {signalLists.sell.length ? signalLists.sell.map(t=>t.replace(".NS","")).join(" · ") : "None"}
                  </div>
                </div>
              </div>

              {/* PERIOD TABS */}
              <div style={{display:"flex",gap:6,marginBottom:14}}>
                <div style={{fontSize:12,color:C.muted,alignSelf:"center",marginRight:4}}>Period:</div>
                {selectedPeriods.map(p=>btn(p,chartPeriod===p,()=>setChartPeriod(p)))}
                <div style={{flex:1}}/>
                {["leaderboard","chart","trades"].map(t=>btn(t==="leaderboard"?"📊 Leaderboard":t==="chart"?"📈 Chart":"📝 Trade Log",tab===t,()=>setTab(t),C.blue))}
              </div>

              {/* LEADERBOARD */}
              {tab==="leaderboard" && results.byPeriod[chartPeriod] && (
                <div style={{overflowX:"auto"}}>
                  <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                    <thead>
                      <tr style={{background:C.surface,borderBottom:`1px solid ${C.border}`}}>
                        {["#","Ticker","Price","Signal","Trades","Win Rate","Strategy %","B&H %","End Value (100k)"].map(h=>(
                          <th key={h} style={{padding:"8px 10px",textAlign:h==="#"||h==="Ticker"?"left":"right",color:C.muted,fontWeight:600,whiteSpace:"nowrap"}}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {results.byPeriod[chartPeriod].map((r,i)=>(
                        <tr key={r.ticker} onClick={()=>setActive(r.ticker)}
                          style={{borderBottom:`1px solid #21262d`,cursor:"pointer",
                            background:active===r.ticker?"#1f6feb11":i%2===0?C.bg:C.surface,transition:"background 0.15s"}}>
                          <td style={{padding:"8px 10px",color:C.muted}}>{i+1}</td>
                          <td style={{padding:"8px 10px",fontWeight:700,color:C.text}}>
                            {r.ticker.replace(".NS","")}
                            {active===r.ticker&&<span style={{marginLeft:5,fontSize:9,color:C.blue}}>●</span>}
                          </td>
                          <td style={{padding:"8px 10px",textAlign:"right"}}>{fmtN(r.price)}</td>
                          <td style={{padding:"8px 10px",textAlign:"right"}}>
                            {r.signal===1
                              ? <span style={{color:C.green,fontWeight:700}}>🟢 BUY</span>
                              : <span style={{color:C.red,fontWeight:700}}>🔴 SELL</span>}
                          </td>
                          <td style={{padding:"8px 10px",textAlign:"right",color:C.muted}}>{r.trades}</td>
                          <td style={{padding:"8px 10px",textAlign:"right",color:r.winRate>=50?C.green:C.red}}>{fmtN(r.winRate)}%</td>
                          <td style={{padding:"8px 10px",textAlign:"right",color:r.netPct>=0?C.green:C.red,fontWeight:700}}>{fmtP(r.netPct)}</td>
                          <td style={{padding:"8px 10px",textAlign:"right",color:r.bh>=0?C.green:C.red}}>{fmtP(r.bh)}</td>
                          <td style={{padding:"8px 10px",textAlign:"right",color:C.blue,fontWeight:600}}>{currency} {fmtN(r.val)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* CHART */}
              {tab==="chart" && activeStat && (
                <>
                  {/* Stat cards */}
                  <div style={{display:"flex",gap:10,marginBottom:14,flexWrap:"wrap"}}>
                    {[
                      {label:"Signal",val:activeStat.signal===1?"🟢 BUY":"🔴 SELL",col:activeStat.signal===1?C.green:C.red},
                      {label:"Strategy Return",val:fmtP(activeStat.netPct),col:activeStat.netPct>=0?C.green:C.red},
                      {label:"Buy & Hold",val:fmtP(activeStat.bh),col:activeStat.bh>=0?C.green:C.red},
                      {label:"Win Rate",val:fmtN(activeStat.winRate)+"%",col:activeStat.winRate>=50?C.green:C.red},
                      {label:"Trades",val:activeStat.trades,col:C.muted},
                      {label:"End Value",val:currency+" "+fmtN(activeStat.val),col:C.blue},
                    ].map(b=>(
                      <div key={b.label} style={{background:C.surface,border:`1px solid ${C.border}`,borderRadius:8,padding:"7px 14px"}}>
                        <div style={{fontSize:10,color:C.muted}}>{b.label}</div>
                        <div style={{fontSize:14,fontWeight:700,color:b.col}}>{b.val}</div>
                      </div>
                    ))}
                  </div>

                  <div style={{background:C.surface,border:`1px solid ${C.border}`,borderRadius:10,padding:"14px 6px 6px"}}>
                    <div style={{fontSize:12,color:C.muted,paddingLeft:12,marginBottom:6}}>
                      {active?.replace(".NS","")} · {strat?.label} · {chartPeriod}
                    </div>
                    <ResponsiveContainer width="100%" height={320}>
                      <LineChart data={chartData} margin={{left:8,right:8}}>
                        <XAxis dataKey="date" tick={{fill:C.muted,fontSize:9}} interval={Math.floor(chartData.length/8)}
                          tickFormatter={d=>d.slice(2,7)}/>
                        <YAxis domain={["auto","auto"]} tick={{fill:C.muted,fontSize:9}} width={58}
                          tickFormatter={v=>v>=1000?(v/1000).toFixed(1)+"k":v.toFixed(2)}/>
                        <Tooltip contentStyle={{background:C.surface,border:`1px solid ${C.border}`,borderRadius:6,fontSize:10}}
                          labelStyle={{color:C.muted}} formatter={(v,n)=>[v!=null?fmtN(v):"—",n]}/>
                        <Legend wrapperStyle={{fontSize:10,paddingTop:6}}/>
                        {Object.keys(chartData[0]||{}).filter(k=>k!=="date"&&k!=="Signal").map(k=>(
                          <Line key={k} dataKey={k} stroke={LINE_COLORS[k]||"#888"} strokeWidth={k==="Price"?1.5:1}
                            dot={false} connectNulls strokeDasharray={k.includes("BB")||k.includes("ATR")?"4 2":undefined}/>
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Buy/Sell markers on mini equity bar */}
                  {tradeLog.length>0 && (
                    <div style={{marginTop:14,background:C.surface,border:`1px solid ${C.border}`,borderRadius:10,padding:"12px 14px"}}>
                      <div style={{fontSize:11,color:C.muted,marginBottom:8}}>📊 Equity Curve (per trade)</div>
                      <ResponsiveContainer width="100%" height={100}>
                        <BarChart data={tradeLog.map((t,i)=>({n:i+1,ret:t.ret}))}>
                          <XAxis dataKey="n" tick={{fill:C.muted,fontSize:9}}/>
                          <YAxis tick={{fill:C.muted,fontSize:9}} tickFormatter={v=>v.toFixed(0)+"%"}/>
                          <Tooltip contentStyle={{background:C.surface,border:`1px solid ${C.border}`,fontSize:10}} formatter={v=>[v.toFixed(2)+"%","Return"]}/>
                          <Bar dataKey="ret" fill={C.green} radius={2}
                            label={false}
                            isAnimationActive={false}
                            // color each bar by positive/negative
                            cells={undefined}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </>
              )}

              {/* TRADE LOG */}
              {tab==="trades" && (
                <div style={{overflowX:"auto"}}>
                  {tradeLog.length===0
                    ? <div style={{color:C.muted,padding:24,textAlign:"center"}}>No trades triggered in this window.</div>
                    : <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                        <thead>
                          <tr style={{background:C.surface,borderBottom:`1px solid ${C.border}`}}>
                            {["#","Type","Entry Date","Entry Price","Exit Date","Exit Price","Trade Return","Portfolio Value"].map(h=>(
                              <th key={h} style={{padding:"7px 10px",textAlign:h==="#"||h==="Type"?"left":"right",color:C.muted,fontWeight:600,whiteSpace:"nowrap"}}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {tradeLog.map((t,i)=>(
                            <tr key={i} style={{borderBottom:`1px solid #21262d`,background:i%2===0?C.bg:C.surface}}>
                              <td style={{padding:"7px 10px",color:C.muted}}>{i+1}</td>
                              <td style={{padding:"7px 10px"}}>
                                <span style={{color:t.type==="ACTIVE"?C.green:C.muted,fontWeight:700}}>
                                  {t.type==="ACTIVE"?"🟢 OPEN":"🔄 CLOSED"}
                                </span>
                              </td>
                              <td style={{padding:"7px 10px",textAlign:"right",color:C.muted}}>{t.entryDate}</td>
                              <td style={{padding:"7px 10px",textAlign:"right"}}>{fmtN(t.entryPrice)}</td>
                              <td style={{padding:"7px 10px",textAlign:"right",color:C.muted}}>{t.exitDate}</td>
                              <td style={{padding:"7px 10px",textAlign:"right"}}>{fmtN(t.exitPrice)}</td>
                              <td style={{padding:"7px 10px",textAlign:"right",fontWeight:700,color:t.ret>=0?C.green:C.red}}>{fmtP(t.ret)}</td>
                              <td style={{padding:"7px 10px",textAlign:"right",color:C.blue}}>{currency} {fmtN(t.val)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                  }
                </div>
              )}
            </>
          )}

          {!loading && !results && (
            <div style={{textAlign:"center",paddingTop:80,color:C.muted}}>
              <div style={{fontSize:48,marginBottom:14}}>🌎</div>
              <div style={{fontSize:17,fontWeight:700,color:C.text}}>Configure & Run Backtest</div>
              <div style={{fontSize:12,marginTop:8,maxWidth:400,margin:"8px auto 0"}}>
                Pick a market, select a strategy, toggle 1Y / 5Y / 10Y periods, then hit Run.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
        
