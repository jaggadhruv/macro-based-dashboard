"""
Theme universes.

Each theme needs enough members that (a) breadth is a stable percentage and
(b) a "top 20 drivers" list is a real selection rather than just the whole list.
Target 25-32 names per theme. Below about 12, one stock crossing its moving
average swings breadth by 8+ points and the oscillator is mostly noise.

Tickers are Yahoo symbols. Indian names need .NS. After the first fetch, check
the coverage warnings -- a silently missing name shrinks a theme.
"""

INDIA_THEMES = {
    "Capital goods": [
        "ABB.NS", "SIEMENS.NS", "CGPOWER.NS", "THERMAX.NS", "LT.NS", "BHEL.NS",
        "KEI.NS", "POLYCAB.NS", "HAVELLS.NS", "TDPOWERSYS.NS", "GRINDWELL.NS",
        "AIAENG.NS", "CUMMINSIND.NS", "KSB.NS", "ELGIEQUIP.NS", "TIMKEN.NS",
        "SCHAEFFLER.NS", "SKFINDIA.NS", "TRITURBINE.NS", "APARINDS.NS",
        "HONAUT.NS", "BEML.NS", "ISGEC.NS", "PRAJIND.NS", "VOLTAS.NS",
        "BLUESTARCO.NS", "CARBORUNIV.NS", "FINCABLES.NS", "SUPREMEIND.NS",
        "RHIM.NS",
    ],
    "Power & utilities": [
        "NTPC.NS", "POWERGRID.NS", "TATAPOWER.NS", "JSWENERGY.NS", "TORNTPOWER.NS",
        "NHPC.NS", "SJVN.NS", "CESC.NS", "ADANIPOWER.NS", "IEX.NS",
        "POWERINDIA.NS", "INOXWIND.NS", "ADANIGREEN.NS", "SUZLON.NS",
        "NLCINDIA.NS", "GIPCL.NS", "KPIGREEN.NS", "WAAREEENER.NS",
        "PFC.NS", "RECLTD.NS", "IRENA.NS", "ORIENTGREEN.NS", "JPPOWER.NS",
        "TRIVENITURB.NS", "GENUSPOWER.NS",
    ],
    "Defence & rail": [
        "HAL.NS", "BEL.NS", "BDL.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "GRSE.NS",
        "DATAPATTNS.NS", "RVNL.NS", "IRCON.NS", "TITAGARH.NS", "RAILTEL.NS",
        "IRFC.NS", "ASTRAMICRO.NS", "ZENTEC.NS", "PARAS.NS", "SOLARINDS.NS",
        "MTARTECH.NS", "IRCTC.NS", "RITES.NS", "CONCOR.NS", "TEXRAIL.NS",
        "JWL.NS", "APOLLO.NS", "BEPL.NS", "IDEAFORGE.NS",
    ],
    "Pharma & chemicals": [
        "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "LUPIN.NS", "TORNTPHARM.NS",
        "DIVISLAB.NS", "LAURUSLABS.NS", "AARTIIND.NS", "NAVINFLUOR.NS",
        "DEEPAKNTR.NS", "SRF.NS", "PIIND.NS", "ALKYLAMINE.NS", "FINEORG.NS",
        "VINATIORGA.NS", "GLENMARK.NS", "ZYDUSLIFE.NS", "MANKIND.NS",
        "ABBOTINDIA.NS", "ALKEM.NS", "AJANTPHARM.NS", "IPCALAB.NS",
        "BIOCON.NS", "GRANULES.NS", "SYNGENE.NS", "ATUL.NS", "TATACHEM.NS",
        "CLEAN.NS", "GUJALKALI.NS", "BALAMINES.NS",
    ],
    "Banks & financials": [
        "HDFCBANK.NS", "ICICIBANK.NS", "AXISBANK.NS", "KOTAKBANK.NS", "SBIN.NS",
        "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "FEDERALBNK.NS",
        "IDFCFIRSTB.NS", "AUBANK.NS", "BAJFINANCE.NS", "CHOLAFIN.NS",
        "MUTHOOTFIN.NS", "SHRIRAMFIN.NS", "LICHSGFIN.NS", "BANKINDIA.NS",
        "UNIONBANK.NS", "INDIANB.NS", "KARURVYSYA.NS", "CUB.NS", "RBLBANK.NS",
        "M&MFIN.NS", "MANAPPURAM.NS", "PEL.NS", "SBICARD.NS", "POONAWALLA.NS",
        "IIFL.NS", "CREDITACC.NS",
    ],
    "Auto & ancillaries": [
        "MARUTI.NS", "M&M.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
        "TVSMOTOR.NS", "EICHERMOT.NS", "ASHOKLEY.NS", "BOSCHLTD.NS",
        "MOTHERSON.NS", "BALKRISIND.NS", "EXIDEIND.NS", "SONACOMS.NS",
        "ENDURANCE.NS", "UNOMINDA.NS", "BHARATFORG.NS", "MRF.NS", "APOLLOTYRE.NS",
        "CEATLTD.NS", "JKTYRE.NS", "AMARAJABAT.NS", "SUNDRMFAST.NS",
        "TIINDIA.NS", "CRAFTSMAN.NS", "SANSERA.NS", "ESCORTS.NS", "SUPRAJIT.NS",
        "LUMAXTECH.NS", "GABRIEL.NS", "SCHAEFFLER.NS",
    ],
    "IT & digital": [
        "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS", "LTIM.NS",
        "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "LTTS.NS", "KPITTECH.NS",
        "TATAELXSI.NS", "CYIENT.NS", "SONATSOFTW.NS", "BIRLASOFT.NS",
        "ZENSARTECH.NS", "MASTEK.NS", "HAPPSTMNDS.NS", "TATATECH.NS",
        "ECLERX.NS", "NEWGEN.NS", "INTELLECT.NS", "ZOMATO.NS", "PAYTM.NS",
        "POLICYBZR.NS", "NAUKRI.NS", "AFFLE.NS", "ROUTE.NS", "IDEAFORGE.NS",
        "CARTRADE.NS",
    ],
    "Metals & materials": [
        "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "JINDALSTEL.NS",
        "NMDC.NS", "SAIL.NS", "NATIONALUM.NS", "HINDZINC.NS", "APLAPOLLO.NS",
        "JSL.NS", "RATNAMANI.NS", "WELCORP.NS", "HINDCOPPER.NS", "MOIL.NS",
        "GRAVITA.NS", "SHYAMMETL.NS", "GPIL.NS", "KALYANKJIL.NS",
        "ULTRACEMCO.NS", "SHREECEM.NS", "AMBUJACEM.NS", "ACC.NS",
        "DALBHARAT.NS", "JKCEMENT.NS", "RAMCOCEM.NS", "BIRLACORPN.NS",
        "STARCEMENT.NS", "PRISMJOHNS.NS", "ORIENTCEM.NS",
    ],
}

US_THEMES = {
    "Semis & AI infra": [
        "NVDA", "AMD", "AVGO", "MU", "AMAT", "LRCX", "KLAC", "ADI", "TXN",
        "MRVL", "ON", "NXPI", "SNPS", "CDNS", "ARM", "VRT", "INTC", "QCOM",
        "TER", "ENTG", "MPWR", "SMCI", "ASML", "TSM", "WDC", "STX", "COHR",
        "ALAB", "CRDO", "NVT",
    ],
    "Software": [
        "MSFT", "CRM", "NOW", "ADBE", "INTU", "PANW", "CRWD", "SNOW", "DDOG",
        "MDB", "ZS", "TEAM", "WDAY", "HUBS", "ORCL", "SAP", "FTNT", "NET",
        "OKTA", "TWLO", "VEEV", "TYL", "ANSS", "PTC", "CFLT", "GTLB",
        "S", "ESTC", "DOCU", "BOX",
    ],
    "Banks & financials": [
        "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "SCHW",
        "BLK", "AXP", "COF", "FITB", "RF", "KEY", "CFG", "HBAN", "MTB",
        "ZION", "CMA", "ALLY", "SYF", "DFS", "NTRS", "STT", "BK", "FHN",
        "WAL", "EWBC",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "MPC", "VLO", "OXY", "HAL",
        "DVN", "FANG", "WMB", "KMI", "OKE", "BKR", "HES", "MRO", "APA",
        "CTRA", "EQT", "AR", "RRC", "SWN", "MTDR", "PR", "CHRD", "NOV",
        "FTI", "TRGP",
    ],
    "Industrials & defence": [
        "GE", "HON", "CAT", "DE", "ETN", "EMR", "PH", "ITW", "LMT", "RTX",
        "NOC", "GD", "LHX", "PWR", "URI", "MMM", "CMI", "ROK", "DOV", "IR",
        "AME", "FAST", "GWW", "SWK", "TT", "JCI", "CARR", "HWM", "TDG", "AXON",
    ],
    "Healthcare": [
        "UNH", "LLY", "JNJ", "ABBV", "MRK", "PFE", "TMO", "DHR", "ABT", "AMGN",
        "GILD", "VRTX", "REGN", "ISRG", "BMY", "CVS", "CI", "ELV", "HCA",
        "ZTS", "SYK", "BSX", "MDT", "EW", "BDX", "IQV", "A", "MCK", "COR",
        "HUM",
    ],
    "Consumer": [
        "AMZN", "HD", "MCD", "NKE", "SBUX", "TJX", "LOW", "BKNG", "CMG",
        "COST", "WMT", "PG", "KO", "PEP", "TGT", "ROST", "DG", "DLTR",
        "YUM", "DRI", "MAR", "HLT", "RCL", "CCL", "LULU", "ULTA", "ORLY",
        "AZO", "EBAY", "ETSY",
    ],
    "Materials & miners": [
        "LIN", "SHW", "FCX", "NEM", "ECL", "APD", "NUE", "STLD", "DOW", "PPG",
        "VMC", "MLM", "CF", "MOS", "ALB", "IFF", "LYB", "EMN", "CE", "RPM",
        "AVY", "PKG", "IP", "SEE", "AA", "X", "CLF", "RS", "CRS", "ATI",
    ],
}


def all_tickers(themes: dict) -> list[str]:
    seen, out = set(), []
    for names in themes.values():
        for t in names:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out
