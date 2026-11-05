# Run from the scratchpad: needs fund_check.py / nobtc.py / weightopt.py there (see tools/fast_preset_test.py).
# With the room cap: add new dip markets / split BTC risk with ETH, on top of the fast preset.
import sys, numpy as np, pandas as pd, itertools
exec(open('fund_check.py').read().split("C = [")[0])
XK = ["eth1h", "sol1h", "silver1h", "gold1h144", "btc1h144"]
RMX = np.vstack([RM] + [SER[k][0] for k in XK]); LMX = np.vstack([LM] + [SER[k][1] for k in XK])
base = SETS["8|btc0.75|x1.25"]
def addset(name, btc, scale, extra):
    w = np.concatenate([base * scale, np.zeros(len(XK))]); w[0] = btc
    for k, v in extra.items(): w[len(KEYS) + XK.index(k)] = v
    RB[name] = ((RMX * w[:, None]).sum(0), (LMX * w[:, None]).sum(0)); return name
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1)
cands = []
for btc in (0.5, 0.625, 0.75):
    for scale in (1.0, 1.1, 1.2):
        cands.append(addset(f"btc{btc}|s{scale}|-", btc, scale, {}))
        for k in XK:
            for v in (0.1, 0.2, 0.3):
                cands.append(addset(f"btc{btc}|s{scale}|{k}={v}", btc, scale, {k: v}))
        for k1, k2 in itertools.combinations(["eth1h", "silver1h", "gold1h144", "sol1h"], 2):
            cands.append(addset(f"btc{btc}|s{scale}|{k1}=0.15,{k2}=0.15", btc, scale, {k1: 0.15, k2: 0.15}))
exec("dst =" + open('fund_check.py').read().split("dst =")[1].split("with Pool")[0])
if __name__ == "__main__":
    dA = pd.read_pickle("addon2_A.pkl")
    if False: A = p.map(ev, [(c, RULE, "A") for c in cands], chunksize=4)
    
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    print("reference:", dA[dA.set == "btc0.75|s1.0|-"].round(1).to_string(index=False), flush=True)
    ok = dA[(dA.breach == 0) & (dA.pass_ >= 93)].sort_values("days")
    print(f"{len(ok)} of {len(dA)} kept >=93% pass, 0 breaches on 2020-22 (weekly starts)", flush=True)
    print(ok.head(30).round(1).to_string(index=False), flush=True)
    pick = [("btc0.75|s1.0|-", RULE, "reference fast preset")] + [(x, RULE, x) for x in list(ok.set.head(12)) + ["btc0.625|s1.0|-", "btc0.625|s1.0|eth1h=0.2", "btc0.5|s1.0|eth1h=0.2", "btc0.5|s1.0|eth1h=0.3", "btc0.5|s1.0|btc1h144=0.3", "btc0.625|s1.0|btc1h144=0.1"] if x != "btc0.75|s1.0|-"]
    with Pool(4) as p: rows = p.map(job, pick)
    print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)
