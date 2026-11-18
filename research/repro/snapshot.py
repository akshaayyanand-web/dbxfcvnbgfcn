"""Export / import the processed datasets so the daily-frequency backtests can be reproduced without re-downloading.
export: research/repro/snapshot/*.csv.gz (daily panels, crypto derivatives panels, opening-range / FX-fix / microstructure tables, FRED/French/CBOE files)
import: rebuilds the cache files in $RSCRATCH/rdata that data.load(), crypto2.load(), intraday.tables() and micro.table() read."""
import os, sys, glob, gzip, shutil, pickle, pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); SNAP = os.path.join(H, "snapshot"); S = os.environ.get("RSCRATCH", "/tmp/claude-0/-home-user-dbxfcvnbgfcn/0ea82c59-9b45-5b6c-b663-efd40f90c87c/scratchpad"); R = f"{S}/rdata"
def _w(df, name): df.to_csv(os.path.join(SNAP, name + ".csv.gz"), compression="gzip")
def _r(name, **k): return pd.read_csv(os.path.join(SNAP, name + ".csv.gz"), index_col=0, parse_dates=True, **k)
def export():
    os.makedirs(SNAP, exist_ok=True); P = pickle.load(open(f"{R}/panels.pkl", "rb"))
    for k, v in P.items():
        if isinstance(v, pd.DataFrame): _w(v, f"panels__{k}")
        elif k == "macro": _w(pd.DataFrame(v), "panels__macro")
    C = pickle.load(open(f"{R}/crypto2.pkl", "rb"))
    for k, v in C.items():
        if isinstance(v, dict):
            for a, b in v.items(): _w(b, f"crypto2__{k}__{a}")
        else: _w(v.to_frame() if isinstance(v, pd.Series) else v, f"crypto2__{k}")
    for f in ("orb_tables", "micro_min", "fix_EURUSD", "fix_AUDCAD"):
        x = pickle.load(open(f"{R}/{f}.pkl", "rb"))
        if isinstance(x, dict):
            for a, b in x.items(): b.to_csv(os.path.join(SNAP, f"{f}__{a}.csv.gz"), compression="gzip")
        else: _w(x, f)
    for sub in ("fred", "cboe"):
        os.makedirs(f"{SNAP}/{sub}", exist_ok=True)
        for f in glob.glob(f"{R}/{sub}/*.csv"):
            with open(f, "rb") as a, gzip.open(f"{SNAP}/{sub}/{os.path.basename(f)}.gz", "wb") as b: shutil.copyfileobj(a, b)
    os.makedirs(f"{SNAP}/french", exist_ok=True)
    for f in glob.glob(f"{R}/french/*.csv"):
        with open(f, "rb") as a, gzip.open(f"{SNAP}/french/{os.path.basename(f)}.gz", "wb") as b: shutil.copyfileobj(a, b)
    print("exported", round(sum(os.path.getsize(x) for x in glob.glob(f"{SNAP}/**/*", recursive=True) if os.path.isfile(x)) / 1e6, 1), "MB")
def imp():
    os.makedirs(R, exist_ok=True)
    for sub in ("fred", "cboe", "french"):
        os.makedirs(f"{R}/{sub}", exist_ok=True)
        for f in glob.glob(f"{SNAP}/{sub}/*.gz"):
            with gzip.open(f, "rb") as a, open(f"{R}/{sub}/{os.path.basename(f)[:-3]}", "wb") as b: shutil.copyfileobj(a, b)
    P = {}
    for f in glob.glob(f"{SNAP}/panels__*.csv.gz"):
        k = os.path.basename(f)[8:-7]; df = pd.read_csv(f, index_col=0, parse_dates=True)
        P[k] = {c: df[c].dropna() for c in df.columns} if k == "macro" else df
    P["crypto_h"], P["cfd_h"] = {}, {}
    pickle.dump(P, open(f"{R}/panels.pkl", "wb"))
    C = {"metrics": {}, "cm": {}}
    for f in glob.glob(f"{SNAP}/crypto2__*.csv.gz"):
        parts = os.path.basename(f)[9:-7].split("__"); df = pd.read_csv(f, index_col=0, parse_dates=True)
        if len(parts) == 2: C[parts[0]][parts[1]] = df
        else: C[parts[0]] = df.iloc[:, 0] if df.shape[1] == 1 and parts[0] == "stable" else df
    pickle.dump(C, open(f"{R}/crypto2.pkl", "wb"))
    T = {os.path.basename(f)[12:-7]: pd.read_csv(f, index_col=0, parse_dates=["day"]) for f in glob.glob(f"{SNAP}/orb_tables__*.csv.gz")}
    pickle.dump(T, open(f"{R}/orb_tables.pkl", "wb"))
    for f in ("micro_min", "fix_EURUSD", "fix_AUDCAD"): pickle.dump(_r(f), open(f"{R}/{f}.pkl", "wb"))
    print("imported into", R)
if __name__ == "__main__": export() if sys.argv[1:] == ["export"] else imp()
