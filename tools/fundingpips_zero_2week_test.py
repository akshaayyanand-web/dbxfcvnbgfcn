src = open("fpzero.py").read(); exec(src[:src.index("\nif __name__")])
def two(a):
    h0, sc = a
    build({c: min(PORT["21"][c] * sc, 1.0 / BASE[c]) * NOWK.get(c, WKD.get(c, 1.0)) for c in NAMES})
    eq = 1.0; opn = 0.0; day = -1; ref = 1.0; floor = 0.95; peak = 1.0
    for i in range(h0, min(h0 + 14 * 24, len(EQ_R))):
        if DAYN[i] != day: day = DAYN[i]; ref = max(eq - opn, eq)
        if EQ_R[i] == 0 and EQ_L[i] == 0: continue
        low = eq * (1 + EQ_L[i]); after = eq * (1 + EQ_R[i]); opn_new = opn + eq * D_FLT[i]
        if low <= floor or low <= ref - 0.03 or min(opn_new + (low - after), opn_new) <= -0.01: return "breached"
        opn = opn_new; eq = after; peak = max(peak, eq); floor = 1.0 if peak >= 1.05 else max(floor, peak - 0.05)
    return "500+" if eq - opn >= 1.13 else "alive, under 500"
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2026-10-01", freq="3D", tz="UTC")]
    for sc in (1, 2, 4, 8, 16):
        with Pool(os.cpu_count()) as p: R = pd.Series(p.map(two, [(h, sc) for h in st]))
        print(sc, (R.value_counts(normalize=True) * 100).round(1).to_dict())
