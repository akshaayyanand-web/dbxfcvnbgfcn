"""SHA-256 manifest of every raw data file used (path relative to $RSCRATCH, bytes, sha256). Writes repro/data_manifest.csv."""
import os, hashlib, csv
S = os.environ.get("RSCRATCH", "/tmp/claude-0/-home-user-dbxfcvnbgfcn/0ea82c59-9b45-5b6c-b663-efd40f90c87c/scratchpad")
DIRS = ["kh", "kf", "fut", "fut1m", "eu1m", "fx1m", "cdata/um", "cdata/prem", "cdata/met", "cdata/cm", "cdata/misc", "mdata/agg", "mdata/depth", "mdata/k1", "indep/cb", "indep/bs", "rdata/fred", "rdata/french", "rdata/cboe"]
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_manifest.csv"); n = 0; tot = 0
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["path", "bytes", "sha256"])
    for d in DIRS:
        p = os.path.join(S, d)
        if not os.path.isdir(p): continue
        for fn in sorted(os.listdir(p)):
            fp = os.path.join(p, fn)
            if not os.path.isfile(fp) or fn.endswith((".pkl", ".txt", ".done")): continue
            h = hashlib.sha256()
            with open(fp, "rb") as g:
                for chunk in iter(lambda: g.read(1 << 20), b""): h.update(chunk)
            sz = os.path.getsize(fp); w.writerow([f"{d}/{fn}", sz, h.hexdigest()]); n += 1; tot += sz
print(n, "files", round(tot / 1e9, 2), "GB ->", out)
