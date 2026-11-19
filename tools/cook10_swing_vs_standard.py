exec(open("combo10.py").read().split('if __name__ == "__main__":')[0])
print("weekday-only share of each weekend-holding EA:", {k: round(float(v), 2) for k, v in WKD.items()}, flush=True)
FULL = dict(PORT["21"])
def funded(a):
    h0, fs, std = a
    for c in NAMES: PORT["21"][c] = FULL[c] * (WKD.get(c, 1.0) if std else 1.0)
    o, _, _, pays = acct(h0, fs, list(NAMES), days=365, buf=0.02); return (o, 0.8 * sum(pays))
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for fs in (2.0, 3.5):
        for std in (False, True):
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(funded, [(h, fs, std) for h in st]), columns=["o", "pct"])
            print(dict(account="Standard (no weekend holds)" if std else "Swing (weekend holds OK)", funded_x=fs, kept=round(100 * (d.o == "kept").mean()),
                       yr_median=round(100 * d.pct.median(), 1), yr_p10=round(100 * d.pct.quantile(.1), 1), yr_p25=round(100 * d.pct.quantile(.25), 1)), flush=True)
