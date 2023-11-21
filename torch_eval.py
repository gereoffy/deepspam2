#! /usr/bin/python3

import time,os,sys,glob
from model import DeepSpam

eval_bs=1024
samples=None

texts = []  # list of text samples
labels = []  # list of label ids
data = None

def draw_hist(w,wmin,wmax,col=128,row=8):
    ww=wmax-wmin
    data=[0]*col
    for x in w:
        c=(x-wmin)*col/ww
        if 0<=c<col: data[int(c)]+=1
#    for x in range(col): data[x]=col-x # test graphics
    wmax=max(x for x in data)
    for y in range(row):
        y0=(row-y-1)/row
        s=""
        for x in range(col):
            d=data[x]/wmax # 0..1
            s+=" " if d<y0 else chr(0x2581+min(int(8*(d-y0)*row),7)) # https://en.wikipedia.org/wiki/Block_Elements
        print(s,file=sys.stderr)

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

    ww=ds.model.l_hid.weight.view(-1)
#    ww=ds.model.l_fc.weight.view(-1)
    ws=ww.std().item()
    w=ww.tolist()
    wmid=[x for x in w if abs(x)<ws*0.1]
    draw_hist(w,-5*ws,5*ws)
    ds.plot(clear=True)

    a=0;n=0
    ok=bad=0
    for text in open("Junk.txt","rt"):
        a+=(res:=ds(text.split("|",1))) ; n+=1
        #if len(sys.argv)==2:
        print("%6.3f%%"%res,text[:128],file=sys.stderr)
        if res>80: ok+=1
        elif res<20: bad+=1
#    if len(sys.argv)>2:  print("%d/%d  avg: %5.3f  [%s]"%(bad,ok,a/n,fnev)); continue
    # eval
    if not data: data=ds.tokenize(ds.preprocess(texts),ds.MAX_BLOCK)
    t0=time.time()
    val_loss,val_acc,test_acc,spam_stat=ds.test(data,labels)
    t=time.time()-t0
    print("%5.3f\t%5.3f\t(%d/%d)\t%s [%s]  %4.2fs    %5.3f|%5.3f"%(test_acc,a/n, bad,ok, spam_stat,  fnev, t, ws,len(wmid)/len(w) ))

