# RE Credit Monitor: pulls free public data into data/market.json. Failures are logged, never fatal.
import csv,io,json,os,time,datetime as dt,urllib.request
UA={"User-Agent":"Mozilla/5.0 (RE Credit Monitor research; ncohen@asg-capital.com)"}
TODAY=dt.date.today(); S={}; ERR=[]
def get(u):
  for i in range(2):
    try:
      with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=25) as r: return r.read().decode("utf-8","replace")
    except Exception as e: last=e; time.sleep(3)
  raise last
def thin(o):  # daily for last 5y, month-end before
  cut=(TODAY-dt.timedelta(days=1826)).isoformat(); out=[]
  for d,v in o:
    if d<cut and out and out[-1][0][:7]==d[:7]: out[-1]=[d,v]
    else: out.append([d,v])
  return out
def add(k,name,freq,grp,src,url,obs): S[k]={"name":name,"freq":freq,"group":grp,"source":src,"url":url,"obs":thin(obs) if freq=="D" else obs}
FRED="""DFF|Effective fed funds rate|D|rates
DFEDTARU|Fed funds target, upper|D|rates
DFEDTARL|Fed funds target, lower|D|rates
SOFR|SOFR|D|rates
SOFR30DAYAVG|SOFR 30-day average|D|rates
DPRIME|Bank prime rate|D|rates
DGS3MO|3M Treasury|D|rates
DGS1|1Y Treasury|D|rates
DGS2|2Y Treasury|D|rates
DGS5|5Y Treasury|D|rates
DGS7|7Y Treasury|D|rates
DGS10|10Y Treasury|D|rates
DGS30|30Y Treasury|D|rates
T10Y2Y|10Y minus 2Y|D|rates
DFII10|10Y TIPS real yield|D|rates
T10YIE|10Y breakeven inflation|D|rates
MORTGAGE30US|30Y fixed mortgage rate|W|rates
BAMLC0A0CM|IG corporate OAS|D|credit
BAMLC0A4CBBB|BBB corporate OAS|D|credit
BAMLH0A0HYM2|High-yield OAS|D|credit
CREACBW027SBOG|CRE loans, all commercial banks ($bn)|W|credit
DRCRELEXFACBS|CRE delinquency rate ex farmland, all banks|Q|credit
SUBLPDRCSC|SLOOS net % tightening: construction & land|Q|credit
SUBLPDRCSM|SLOOS net % tightening: multifamily|Q|credit
SUBLPDRCSN|SLOOS net % tightening: nonfarm nonresidential|Q|credit
SUBLPDRCDC|SLOOS net % stronger demand: construction & land|Q|credit
SUBLPDRCDM|SLOOS net % stronger demand: multifamily|Q|credit
RRVRUSQ156N|US rental vacancy rate|Q|space
HOUST5F|Starts, 5+ units (SAAR, k)|M|space
PERMIT5|Permits, 5+ units (SAAR, k)|M|space
UNDCON5MUSA|Under construction, 5+ units (k)|M|space
COMPU5MUSA|Completions, 5+ units (SAAR, k)|M|space
CUSR0000SEHA|CPI rent of primary residence, US|M|space
CPIAUCSL|CPI all items, US|M|macro
CUURA101SEHA|CPI rent, New York metro|M|space
CUURA320SEHA|CPI rent, Miami metro|M|space
BAA10Y|Moody's Baa corporate yield minus 10Y|D|credit
T10Y3M|10Y minus 3M Treasury|D|rates
PAYEMS|Payrolls, US (k)|M|macro
UNRATE|Unemployment rate, US|M|macro
COMREPUSQ159N|Commercial RE prices, US (YoY %)|Q|pricing"""
METRO={"New York, NY":"NEWY636","Miami, FL":"MIAM112","Tampa, FL":"TAMP312","Orlando, FL":"ORLA712","Atlanta, GA":"ATLA013","Charlotte, NC":"CHAR737","Nashville, TN":"NASH947","Dallas, TX":"DALL148","Houston, TX":"HOUS448","Austin, TX":"AUST448","Phoenix, AZ":"PHOE004","Chicago, IL":"CHIC917","Los Angeles, CA":"LOSA106","Washington, DC":"WASH911"}
for m,c in METRO.items():
  FRED+=f"\n{c}NA|Payrolls, {m} metro (k)|M|metro\n{c}BPPRIV|Housing permits, {m} metro (units)|M|metro"
for line in FRED.splitlines():
  sid,name,freq,grp=line.split("|")
  try:
    rows=list(csv.reader(io.StringIO(get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2000-01-01"))))[1:]
    obs=[[r[0],round(float(r[1]),4)] for r in rows if len(r)>1 and r[1] not in ("",".")]
    if not obs: raise ValueError("no data")
    add(sid,name,freq,grp,"FRED, Federal Reserve Bank of St. Louis",f"https://fred.stlouisfed.org/series/{sid}",obs)
  except Exception as e: ERR.append(f"FRED {sid}: {e}")
TK={"ARI":"Apollo Commercial RE Finance","BXMT":"Blackstone Mortgage Trust","LADR":"Ladder Capital","KREF":"KKR Real Estate Finance","TRTX":"TPG RE Finance Trust","ACR":"ACRES Commercial Realty","STWD":"Starwood Property Trust","REM":"iShares Mortgage RE ETF","VNQ":"Vanguard Real Estate ETF","KRE":"SPDR Regional Banking ETF"}
for t,n in TK.items():
  try:
    r=json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=10y&interval=1d"))["chart"]["result"][0]
    obs=[[dt.datetime.utcfromtimestamp(a).date().isoformat(),round(b,3)] for a,b in zip(r["timestamp"],r["indicators"]["quote"][0]["close"]) if b is not None]
    add("PX_"+t,f"{n} ({t}) close","D","listed","Yahoo Finance",f"https://finance.yahoo.com/quote/{t}",obs)
  except Exception as e: ERR.append(f"Yahoo {t}: {e}")
CIK={"ARI":"0001467760","BXMT":"0001061630","LADR":"0001577670","KREF":"0001631596","TRTX":"0001630472","ACR":"0001332551","STWD":"0001465128"}
def bydate(a):
  d={}
  for x in a:
    if x.get("form","")[:4] in ("10-Q","10-K"): d[x["end"]]=x["val"]
  return sorted(d.items())
for t,c in CIK.items():
  try:
    f=json.loads(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c}.json"))["facts"]
    g=f["us-gaap"]; u=lambda t:g.get(t,{}).get("units",{}).get("USD",[])
    eq=bydate(u("StockholdersEquity") or u("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"))
    pf=dict(bydate(u("PreferredStockLiquidationPreferenceValue") or u("PreferredStockValue")))
    eq=[(d,v-pf.get(d,0)) for d,v in eq]
    sh=bydate(f.get("dei",{}).get("EntityCommonStockSharesOutstanding",{}).get("units",{}).get("shares",[]))
    bv=[[d,round(v/s[0],3)] for d,v in eq[-24:] for s in [[sv for sd,sv in sh if sd>=d]] if s]
    add("BVPS_"+t,f"{t} book value per common share (equity less preferred, / shares)","Q","listed","SEC EDGAR XBRL",f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={c}",bv)
  except Exception as e: ERR.append(f"SEC {t}: {e}")
M=["New York, NY","Miami, FL","Tampa, FL","Orlando, FL","Atlanta, GA","Charlotte, NC","Nashville, TN","Dallas, TX","Houston, TX","Austin, TX","Phoenix, AZ","Chicago, IL","Los Angeles, CA","Washington, DC","United States"]
try:
  rd=csv.reader(io.StringIO(get("https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv"))); h=next(rd)
  dc=[i for i,x in enumerate(h) if len(x)==10 and x[4]=="-"]
  for r in rd:
    if r[2] in M: add("ZORI_"+r[2],f"Zillow Observed Rent Index, {r[2]}","M","space","Zillow Research","https://www.zillow.com/research/data/",[[h[i],round(float(r[i]),1)] for i in dc if r[i]])
except Exception as e: ERR.append(f"Zillow: {e}")
os.makedirs("data",exist_ok=True)
json.dump({"generated_utc":dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),"count":len(S),"errors":ERR,"series":S},open("data/market.json","w"),separators=(",",":"))
print(f"{len(S)} series, {len(ERR)} errors"); [print(" ERR",e) for e in ERR]
