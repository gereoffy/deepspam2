#!/usr/bin/env python3
# elteresek okanak felderitese: a levelek reszei (ctyp / charset / cte), csoportositva
#   python3 diag.py fuzz.mbox py.out rs.out
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from bench_py import split_mbox
from compare_out import load  # noqa
import eml2str as E
msgs = split_mbox(open(sys.argv[1], 'rb').read())
a, b = load(sys.argv[2]), load(sys.argv[3])
so = sys.stdout; sys.stdout = open(os.devnull, 'w')
rows = []
for i in sorted(a):
    if a[i] == b[i]: continue
    e = E.parse_eml(msgs[i], decode=True)
    def walk(x):
        if x["parts"]:
            for p in x["parts"]: yield from walk(p)
        else: yield x
    leaves = [(p["ctyp"], p["charset"], p["encoding"]) for p in walk(e) if p["ctyp"].startswith('text/') or p["ctyp"] in ('application/ics', 'application/rtf')]
    rows.append((i, leaves))
sys.stdout = so
cnt = collections.Counter()
for i, l in rows:
    for x in l: cnt[x[1]] += 1
print(cnt.most_common())
iso = [r for r in rows if any((x[1] or '').startswith('iso-2022') for x in r[1])]
print('iso-2022 reszt tartalmazo: %d, egyeb: %d' % (len(iso), len(rows) - len(iso)))
for i, l in [r for r in rows if r not in iso][:40]: print(i, l)
