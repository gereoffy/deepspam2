#! /usr/bin/python3
# Token-level explanation of DeepSpam2 decisions, colored output (see DeepSpam.explain)
#
# usage: ./explain.py [-m model/deepspam.pt] [--html out.html] [--top 8] [Junk.txt ...]

import sys,argparse,html
from model import DeepSpam

ap=argparse.ArgumentParser()
ap.add_argument("files",nargs="*",default=["Junk.txt"])
ap.add_argument("-m","--model",default="model/deepspam.pt")
ap.add_argument("--html",help="write colored HTML report to this file")
ap.add_argument("--top",type=int,default=8,help="number of top token groups to list")
args=ap.parse_args()

ds=DeepSpam(device="cpu",load=None,ds1=False)
ds.load(args.model)

def rgb(v,scale):
    a=min(1.0,abs(v)/scale)**0.6 if scale>0 else 0.0
    if v>0: return (255,int(255*(1-a)),int(255*(1-a)))  # red = spam
    return (int(255*(1-a)),255,int(255*(1-a)*0.9))      # green = ham

def ansi_line(r):
    scale=max(abs(t) for t in r["tok"])
    s=""
    for i,pc in enumerate(r["pieces"]):
        if i<r["n"]:
            c=rgb(r["tok"][i],scale)
            s+="\x1b[38;2;0;0;0;48;2;%d;%d;%dm%s"%(*c,pc)
        else: s+="\x1b[0;2m"+pc                       # truncated: model never saw it
    return s+"\x1b[0m"

out=[]
for fn in args.files:
    for line in open(fn,"rt"):
        line=line.rstrip("\n")
        if not line: continue
        r=ds.explain(line.split("|",1))
        if not r: continue
        col=91 if r["score"]>=80 else 92 if r["score"]<=20 else 93
        print("\n\x1b[1;%dm%7.3f%%\x1b[0m  logit diff=%+.2f  (tokens sum=%+.2f)"%(col,r["score"],r["diff"],sum(r["tok"])))
        print(ansi_line(r))
        g=r["groups"]
        print("  spam ->", " | ".join("\x1b[91m%+.2f\x1b[0m %s"%(c,t) for s,c,t in g[:args.top] if c>0))
        print("  ham  ->", " | ".join("\x1b[92m%+.2f\x1b[0m %s"%(c,t) for s,c,t in g[::-1][:args.top//2] if c<0))
        out.append(r)

if args.html:
    with open(args.html,"wt") as h:
        h.write("<!doctype html><meta charset=utf-8><title>DeepSpam explain</title>"
                "<style>body{font:14px/1.7 sans-serif;max-width:1100px;margin:auto;padding:16px}"
                "div.t{margin:18px 0;padding-top:8px;border-top:1px solid #ccc}span{white-space:pre-wrap}"
                ".tr{color:#aaa}b{font-size:16px}</style>\n")
        for r in out:
            scale=max(abs(t) for t in r["tok"])
            h.write("<div class=t><b>%.3f%%</b> &nbsp; logit diff %+.2f<br>"%(r["score"],r["diff"]))
            for i,pc in enumerate(r["pieces"]):
                if i<r["n"]: h.write('<span style="background:rgb(%d,%d,%d)" title="%+.3f">%s</span>'%(*rgb(r["tok"][i],scale),r["tok"][i],html.escape(pc)))
                else: h.write('<span class=tr>%s</span>'%html.escape(pc))
            h.write("</div>\n")
    print("\nHTML written:",args.html)
