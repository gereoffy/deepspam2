#! /usr/bin/python3

import time
from model import DeepSpam

t0=time.time()

print('Processing text dataset')
texts = []  # list of text samples
labels_index = ["spam","ham"]  # dictionary mapping label name to numeric id
labels = []  # list of label ids

def loadtext(path,label_id):
    for t in open("data/"+path,"r"):
        if len(t)<10: continue # too short
        t="\n".join(t.split("|",1)) # subject + body
        texts.append(t[:1024])
        labels.append(label_id)
        #
        #texts.append(t[:1024].lower())
        #labels.append(label_id)

loadtext("SPAM.mbox.txt",0)
loadtext("HAM.mbox.txt",1)
num_train=len(texts)
loadtext("SPAM-test.txt",0)
loadtext("HAM-test.txt",1)
num_all=len(texts)
num_val=num_all-num_train
print('Found %d texts. (%d+%d)' % (num_all,num_train,num_val))

#from sklearn.utils import shuffle
#texts,labels = shuffle(texts,labels,random_state=1978)
#num_train=int(0.5*num_all)

#####################################################################################################

# train new model
ds=DeepSpam(device="cuda",load=None)
ds.train(texts,labels,num_train)
##ds.save()

print("Total TIME: %5.3f sec"%(time.time()-t0))

# test
text="are you looking for a business loan personal loan home loan car loan student loan debt consolidation loan unsecured loan venture capital etc . or were you refused a loan by a bank or a financial setting for one or more reasons . you in the right place for your loan solutions ! email us right now at emailaddress this email and any files transmitted with it are confidential and intended solely for the use of the individual or entity to whom they are addressed . if you have received this email in error please notify the system manager . please note that any views or opinions presented in this email are solely those of the author and do not necessarily represent those of postal corporation of kenya . finally the recipient should check this email and any attachments for the presence of viruses . postal corporation of kenya accepts no liability for any damage caused by any virus transmitted by this email . postal corporation of kenya p . o box ##### ##### kenyatta avenue nairobi kenya domainname . ke"
res=ds(text)
print(res,text[:128])

