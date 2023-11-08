#! /usr/bin/python3

import time,os,sys,glob
from model import DeepSpam

eval_bs=1024
samples=None

ds=DeepSpam(device="cuda",load=None,ds1=False)

def loadtokens(path):
    texts=[]
    for t in open("data/"+path,"r"):
        if len(t)<10: continue # too short
        texts.append(t[:1024].split("|",1))
    return ds.tokenize(ds.preprocess(texts),ds.MAX_BLOCK)

for fnev in sys.argv[1:] if len(sys.argv)>1 else glob.glob('model/deepspam*.pt'):
    ds.load(fnev)
    a=0;n=0
    ok=bad=0
    for text in open("Junk.txt","rt"):
        a+=(res:=ds(text.split("|",1))) ; n+=1
        if len(sys.argv)==2: print("%6.3f%%"%res,text[:128])
        if res>80: ok+=1
        elif res<20: bad+=1
#    if len(sys.argv)>2:  print("%d/%d  avg: %5.3f  [%s]"%(bad,ok,a/n,fnev)); continue
    # eval
    if not samples: samples=[ loadtokens("SPAM-test.txt"), loadtokens("HAM-test.txt") ]
    t0=time.time()
    cnt={}
    for i in range(2):
        cnt[i]=[0,0,0,0] # count, sum, hamtag, spamtag
        x=0
        while x<len(samples[i]):
            for res in ds.evalbatch(samples[i][x:x+eval_bs],tokenized=True):
                cnt[i][0]+=1
                cnt[i][1]+=res
                if res<20: cnt[i][2]+=1
                if res>80: cnt[i][3]+=1
            x+=eval_bs
    t=time.time()-t0
    # results
    print("%5.3f\t(%d/%d)\tham: %5.2f/%4.2f (%5.3f)  spam: %5.2f/%4.2f (%5.3f)  [%s]  %4.2fs (%d+%d)"%(a/n, bad,ok, 
        100*cnt[1][2]/cnt[1][0],100*cnt[1][3]/cnt[1][0], cnt[1][1]/cnt[1][0],
        100*cnt[0][3]/cnt[0][0],100*cnt[0][2]/cnt[0][0], cnt[0][1]/cnt[0][0],   fnev, t, cnt[0][0],cnt[1][0]))
