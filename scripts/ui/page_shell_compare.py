"""Vergleich gemeinsamer Elemente zwischen Seiten (Standardseiten vs. Ausnahmen)."""
import json, sys
from collections import defaultdict
EXC = {"home", "accounts/login/", "accounts/signup/", "accounts/password/reset/", "platform-report/"}
def edge(b, lang):  # Startkante (LTR links, RTL rechts)
    return None if not b else (round(b[0] + b[2], 1) if lang == "fa" else b[0])
def stats(path):
    rows = json.load(open(path)); g = defaultdict(list)
    for r in rows:
        if r["path"] not in EXC: g[(r["theme"], r["lang"], r["width"])].append(r)
    out = {}
    for k, rs in g.items():
        sp = lambda vals: (round(max(vals) - min(vals), 1) if vals else None)
        ce = [ (r["contentEdges"][1] if k[1]=="fa" else r["contentEdges"][0]) for r in rs if r["contentEdges"] and r["contentEdges"][0] > 0.5]
        out[k] = dict(
            logo=sp([edge(r["logo"], k[1]) for r in rs if r["logo"]]),
            back=sp([edge(r["back"], k[1]) for r in rs if r["back"]]),
            backY=sp([r["back"][1] for r in rs if r["back"]]),
            navH=sp([r["nav"][3] for r in rs if r["nav"]]),
            edge=sp(ce),
            headTop=sp([r["firstTextTop"] for r in rs if r.get("firstTextTop") is not None]),
            logoToEdge=(round(abs(edge(rs[0]["logo"], k[1]) - ce[0]), 1) if ce and rs[0]["logo"] else None),
            gutter=(round(min(ce), 1) if ce and k[1] != "fa" else None),
            overflow=sum(r["overflowX"] for r in rs), n=len(rs))
    return out
a = stats(sys.argv[1]); b = stats(sys.argv[2]) if len(sys.argv) > 2 else None
keys = ["logo", "back", "backY", "navH", "edge", "headTop", "logoToEdge", "gutter", "overflow"]
print("theme lang width |", " ".join(f"{k:>11}" for k in keys))
for k in sorted(a, key=lambda x: (x[0], x[1], x[2])):
    row = []
    for m in keys:
        v1 = a[k][m]; v2 = b[k][m] if b and k in b else None
        row.append(f"{str(v1)+('→'+str(v2) if b else ''):>11}")
    print(f"{k[0]:5} {k[1]} {k[2]:5} |", " ".join(row))
