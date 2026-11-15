exec(open("frontier3.py").read().split("for k, w in PORT.items()")[0])
w = PORT["21"]
print("RISK", {c: round(min(w[c] * 2.5, 1.0 / BASE[c]) * BASE[c], 2) for c in sorted(w, key=lambda c: -w[c] * BASE[c])})
