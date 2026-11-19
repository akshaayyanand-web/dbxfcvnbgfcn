# Add new-lab components to the 21-EA book and run FTMO 2-Step (+10%/+5%, 5% daily, 10% static, 80% split, no consistency rule)
# and FTMO 1-Step (+10%, 3% daily, 10% EOD-trailing, reset on payout, best-day 50%, 90% split).
import os, sys, pickle, numpy as np, pandas as pd
ARGV = list(sys.argv)
NOVA = open("nova2.py").read(); exec(NOVA[:NOVA.index("\nif __name__")])
from multiprocessing import Pool
TR = pickle.load(open("newlab_trades.pkl", "rb"))
NEWSEL = {"gnight": ("H1 gold Asia-session drift", "XAUUSD", "long 23->03 UTC all"),
          "fomc": ("H5 pre-FOMC drift", "USATECHIDXUSD", "long 14:00 ET day before -> 14:00 ET FOMC day")}
extra = [a for a in sys.argv[1:] if a in globals().get("EXTRA", {})]
def comp_from_trades(trs, w):
    R = np.zeros(len(idx)); L = np.zeros(len(idx)); F = np.zeros(len(idx))
    for et, xt, r, path in trs:
        opn = 0.0
        for k, (b, inc, lo) in enumerate(path):
            pass
        # path holds bar indices of the market, re-map with times
    return R, L, F
def comp_from_paths(trs, times, w):
    R = np.zeros(len(idx)); L = np.zeros(len(idx)); F = np.zeros(len(idx))
    for et, xt, r, path in trs:
        if et < idx[0] or xt > idx[-1]: continue
        opn = 0.0; n = len(path)
        for k, (tb, inc, lo) in enumerate(path):
            h = idx.searchsorted(tb)
            if h >= len(idx): break
            R[h] += w * inc; L[h] += w * lo
            if k < n - 1: F[h] += w * inc; opn += w * inc
            else: F[h] -= opn
    return [R, L, F]
def load_new(name):
    key = NEWSEL[name]; trs = TR[key]
    # convert bar indices in path to timestamps: entry bar = et, consecutive hourly bars
    out = []
    for et, xt, r, path in trs:
        b0 = path[0][0]; t0 = pd.Timestamp(et)
        out.append((t0, pd.Timestamp(xt), r, [(t0 + pd.Timedelta(hours=int(b - b0)), inc, lo) for b, inc, lo in path]))
    return out
def add_components(names, mult=1.0):
    TRN_D = {}
    tgt = np.median([PORT["21"][c] * pd.Series(COMP[c][0], idx).groupby(idx.normalize()).sum().loc["2020-09-01":"2022-12-31"].std() for c in NAMES])
    for nm in names:
        unit = comp_from_paths(load_new(nm), None, 1.0)
        sd = pd.Series(unit[0], idx).groupby(idx.normalize()).sum().loc["2020-09-01":"2022-12-31"].std()
        w = tgt / sd; COMP[nm] = [w * a for a in unit]; PORT["21"][nm] = mult; BASE[nm] = 0.1
        if nm not in NAMES: NAMES.append(nm)
        print(f"{nm}: unit risk per trade {100*w:.3f}% of equity (equal-risk to the median EA)", flush=True)
def daily_sharpe(names):
    build({c: PORT["21"].get(c, 0) if c in names else 0.0 for c in NAMES})
    d = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum(); d = d[d.index.weekday < 5]
    a, b = d[:"2022-12-31"], d["2023-01-01":]
    return round(a.mean() / a.std() * np.sqrt(252), 2), round(b.mean() / b.std() * np.sqrt(252), 2), round(100 * d.sum() / ((idx[-1] - idx[0]).days / 365.25), 1)

def acct(h0, scale, names, target=None, days=None, DL=0.05, ML=0.10, G=0.04, trailing=False, reset=False, cons=None, buf=0.0, every=14, split=0.8):
    build({c: (min(PORT["21"][c] * scale, 1.0 / BASE[c]) if c in names else 0.0) for c in NAMES})
    eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 1 - ML; peak = 1.0; pays = []; dstart = 1.0; ref = 1.0; dp = []; Z = ML * 0.8
    end = min(h0 + (days or 900) * 24, len(EQ_R)); nextpay = h0 + every * 24
    for i in range(h0, end):
        if DAYN[i] != day:
            bal = eq - opn
            if day != -1:
                dp.append(bal - dstart)
                if trailing: peak = max(peak, bal); floor = max(floor, peak - ML)
            prof = sum(dp); best = max(dp) if dp else 0
            if target and bal >= 1 + target and len(dp) >= 2 and (cons is None or best <= cons * prof): return "pass", (i - h0) / 24, i, pays
            if days and i >= nextpay:
                w = min(bal, eq) - 1 - buf
                if w > 0.005 and (cons is None or best <= cons * max(prof, 1e-9)):
                    pays.append(w); dp = []; nextpay = i + every * 24
                    if reset: eq = 1.0; opn = 0.0; bal = 1.0; peak = 1.0; floor = 1 - ML
                    else: eq -= w; bal = eq - opn
                else: nextpay = i + 24
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - G: eq = min(after, max(low, ref - G - 0.003)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - DL: return "breached", (i - h0) / 24, i, pays
        else: opn += eq * mm * D_FLT[i]; eq = after
        if eq <= floor: return "breached", (i - h0) / 24, i, pays
    return ("open" if target else "kept"), (end - h0) / 24, end, pays

def two_step(a):
    h0, es, fs, names = a
    p, d1, i1, _ = acct(h0, es, names, target=0.10)
    if p != "pass": return (p, None, None, 0.0)
    p, d2, i2, _ = acct(i1 + 1, es, names, target=0.05)
    if p != "pass": return (p + "2", None, None, 0.0)
    o, _, _, pays = acct(i2 + 48, fs, names, days=365, buf=0.02)
    return ("pass", d1 + d2, o, 0.8 * sum(pays))
def one_step(a):
    h0, es, fs, names = a
    p, d1, i1, _ = acct(h0, es, names, target=0.10, DL=0.03, G=0.022, trailing=True, cons=0.5)
    if p != "pass": return (p, None, None, 0.0)
    o, _, _, pays = acct(i1 + 48, fs, names, days=365, DL=0.03, G=0.022, trailing=True, reset=True, cons=0.5)
    return ("pass", d1, o, 0.9 * sum(pays))
def table(fn, names, es_list, fs_list, starts, label):
    rows = []
    for es in es_list:
        for fs in fs_list:
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(fn, [(h, es, fs, names) for h in starts]), columns=["ev", "days", "o", "pct"])
            ok = d[d.ev == "pass"]
            rows.append(dict(book=label, eval_x=es, funded_x=fs, passed=round(100 * len(ok) / len(d)), med_days=ok.days.median(), p25=ok.days.quantile(.25), p75=ok.days.quantile(.75),
                             funded_kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1), yr_p25=round(100 * ok.pct.quantile(.25), 1)))
            print(rows[-1], flush=True)
    return rows
if __name__ == "__main__":
    mode = ARGV[1]; new = [x for x in ARGV[2].split(",") if x] if len(ARGV) > 2 else []
    add_components(list(NEWSEL))
    base = [c for c in NAMES if c not in NEWSEL]; book = base + new
    print("Sharpe 2020-22 / 2023-26 / %/yr at x1  base:", daily_sharpe(base), " with", new, ":", daily_sharpe(book), flush=True)
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    lab = "21 EAs" + "".join(" + " + x for x in new)
    ES = tuple(float(x) for x in ARGV[3].split(",")) if len(ARGV) > 3 else (2.0, 2.5, 3.0)
    FS = tuple(float(x) for x in ARGV[4].split(",")) if len(ARGV) > 4 else (2.0, 2.5, 3.0)
    if mode == "two": rows = table(two_step, book, ES, FS, st, lab)
    else: rows = table(one_step, book, (2.5,), (1.5, 2.0), st, lab)
    pd.DataFrame(rows).to_csv(f"combo10_{mode}_{'_'.join(new) or 'base'}_{len(ARGV)}_{ARGV[-1]}.csv", index=False)
