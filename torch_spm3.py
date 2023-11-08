#! /usr/bin/python3

import time,os
from model import DeepSpam


print('Processing text dataset')
texts = []  # list of text samples
labels_index = ["spam","ham"]  # dictionary mapping label name to numeric id
labels = []  # list of label ids

def loadtext(path,label_id):
    for t in open("data/"+path,"r"):
        if len(t)<10: continue # too short
        texts.append(t[:1024].split("|",1))
        labels.append(label_id)

loadtext("SPAM.mbox.txt",0)
loadtext("HAM.mbox.txt",1)
num_train=len(texts)
loadtext("SPAM-test.txt",0)
loadtext("HAM-test.txt",1)
num_all=len(texts)
num_val=num_all-num_train
print('Found %d texts. (%d+%d)' % (num_all,num_train,num_val))

ds=DeepSpam(device="cuda",load=None,ds1=False,logfile=open("model/deepspam.log","at"))
t0=time.time()
data=ds.tokenize(ds.preprocess(texts),ds.MAX_BLOCK)
print("Tokenized %d samples (%3.1f sec)"%(len(data),time.time()-t0))

#from sklearn.utils import shuffle
#texts,labels = shuffle(texts,labels,random_state=1978)
#num_train=int(0.5*num_all)

#####################################################################################################

#  def train(self,texts,label_ids,num_train,epochs=50,batch_size=1024,max_len=MAX_BLOCK,dropwords=10,savebest=True,lr1=0.0001):

#for bs in [8,16,32,64,128,256,512,1024,2048]:
#for bs in [512,256,192,128,96,64,48,32,24,16,12,8,4]:
for bs in [64,48,32,24,16,12,8]:
#    for lr in [0.0002,0.0001,0.00005,0.00002,0.00001]:
    for lr in [0.01,0.005,0.003,0.002,0.001,0.0005,0.0002,0.0001]:
        # train new model
        ds.reset()
        t0=time.time()
        fn=ds.train(data,labels,num_train,batch_size=bs,lr1=lr)
        print("Total TIME: %5.3f sec   File:"%(time.time()-t0),fn)
        try:
            if fn: ds.load(fn) # rollback to last saved checkpoint (if any)
            for text in open("Junk.txt","rt"):
                res=ds(text.split("|",1))
                print("%6.3f%%"%res,text[:128])
        except Exception as e: print(repr(e))
