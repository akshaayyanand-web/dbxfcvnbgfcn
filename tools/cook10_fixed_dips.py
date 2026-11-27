import sys
exec(open("anticheat.py").read().split('\nif __name__ == "__main__":')[0])
for sym, rule, bh in (("BTC", "1h", 1), ("XAU", "4h", 4)):
    b = K.rs(m5(sym), rule).dropna(); tr = dip_core(b, sym, bh=bh, fix_lookahead=True); pd.DataFrame(tr, columns=["t", "tx", "R"]).to_pickle(f"fixed_DIP_{sym}_{rule}.pkl"); print(sym, rule, len(tr))
