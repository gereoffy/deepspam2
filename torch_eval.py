#! /usr/bin/python3

import time,os,sys,glob
from model import DeepSpam

eval_bs=1024
samples=None

texts = []  # list of text samples
labels = []  # list of label ids
data = None

def loadtext(path,label_id):
    for t in open("data/"+path,"r"):
        if len(t)<10: continue # too short
        texts.append(t[:1024].split("|",1))
        labels.append(label_id)

loadtext("SPAM-test.txt",0)
loadtext("HAM-test.txt",1)

ds=DeepSpam(device="cuda",load=None,ds1=False)

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
    if not data: data=ds.tokenize(ds.preprocess(texts),ds.MAX_BLOCK)
    t0=time.time()
    val_loss,val_acc,test_acc,spam_stat=ds.test(data,labels)
    t=time.time()-t0
    print("%5.3f\t%5.3f\t(%d/%d)\t%s [%s]  %4.2fs"%(test_acc,a/n, bad,ok, spam_stat,  fnev, t))

