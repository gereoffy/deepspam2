#! /usr/bin/python3

TEXT_DATA_DIR = 'data'
MAX_SEQUENCE_LENGTH = 100

device="cuda"

import pickle
import time

#import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
#from torch.distribitutions.bernoulli import Bernoulli

class CNN_NLP(nn.Module):
    def __init__(self, pretrained_embedding, filter_sizes=[2, 3, 4, 5], num_classes=2, dropout=0.5, filters=128, hidden=32):
        super().__init__()
        self.l_emb = nn.Embedding.from_pretrained(embedding_tensors,freeze=True)
        self.embed_dim=len(embedding_tensors[0])
#        print("embed_dim:",self.embed_dim)
#        self.l_dr1 = torch.nn.Dropout(0.2)
#        self.l_dr1 = torch.nn.Dropout1d(0.5)
        self.convl = nn.ModuleList([ nn.Conv1d(in_channels=self.embed_dim, out_channels=filters, kernel_size=k, padding="valid") for k in filter_sizes ])
        self.l_dr2 = torch.nn.Dropout(dropout,inplace=True)
        self.l_hid = nn.Linear(len(filter_sizes)*filters, hidden)
        self.l_fc = nn.Linear(hidden, num_classes)

    def forward(self, input_ids): # x=input_ids[batch_size][maxseqlen]
        x=self.l_emb(input_ids)

#        print("---------------------------------")
#        print(x[7])
#        x=self.l_dr1(x) # drop
#        print(x[7])
#        print("---------------------------------")

        x=x.permute(0, 2, 1)
#        x_conv = [ torch.max(conv(x), dim=2).values for conv in self.convl ]
        x_conv = [ torch.max( F.relu( conv(x) ), dim=2).values for conv in self.convl ] # Conv1D + ReLU + GlobalMaxPooling
        x=torch.cat(x_conv,dim=1)
#    print(x.size()) # torch.Size([3, 512])
        #if self.training: 
        x = self.l_dr2(x) # drop 0.5
        x = F.relu(self.l_hid(x))  # linear 512->32 + ReLU
        x = self.l_fc(x)   # linear 32->2
#        return F.sigmoid(x)
        return x



t0=time.time()

print('Loading embedding_matrix')
wordmap,embedding_matrix = pickle.load(open("all12sg.pck32.1M", "rb"))

print(type(embedding_matrix))
print(type(embedding_matrix[0]))
#print(embedding_matrix[3])

num_words=len(embedding_matrix)
num_dim=len(embedding_matrix[0])
print('%d words found, dim=%d'%(num_words,num_dim))


embedding_tensors=torch.from_numpy(embedding_matrix).float()
print(embedding_tensors.size())

cnn_model=CNN_NLP(embedding_tensors)
cnn_model.to(device)
print(cnn_model)

for n,p in cnn_model.named_parameters(): print(n,p.numel(),p.requires_grad) # list weights
#for n,m in cnn_model.named_children(): print(n,m) # list sub-modules

all_params = sum([p.numel() for p in cnn_model.parameters()])
num_params = sum([p.numel() for p in cnn_model.parameters() if p.requires_grad])
print(f"Number of trainable parameters: {num_params}/{all_params}")


masks=[]
for i in range(MAX_SEQUENCE_LENGTH):
    m=[1]*MAX_SEQUENCE_LENGTH
    m[i]=0
    masks.append(m)

#print(masks)
masks=torch.tensor(masks).to(device)
print(masks)

#####################################################################################################




print('Processing text dataset')
texts = []  # list of text samples
labels_index = ["spam","ham"]  # dictionary mapping label name to numeric id
labels = []  # list of label ids

def loadtext(path,label_id):
    for t in open(TEXT_DATA_DIR+"/"+path,"r"):
        texts.append(t)
        labels.append(label_id)

loadtext("mail.neg",0)
loadtext("mail.pos",1)
num_train=len(texts)
loadtext("mail.negT",0)
loadtext("mail.posT",1)
num_all=len(texts)
num_val=num_all-num_train
print('Found %d texts. (%d+%d)' % (num_all,num_train,num_val))

data = []  #torch.zeros([num_all, MAX_SEQUENCE_LENGTH], dtype=torch.int32)  #torch.tensor(num_all, MAX_SEQUENCE_LENGTH), dtype='int32')
wcount_all=0
wcount_ok=0
for i in range(num_all):
    j=0
    d=[0]*MAX_SEQUENCE_LENGTH
    for w in texts[i].strip().split(" "):
        wcount_all+=1
        if w in wordmap:
#            if i==7: print(i,j,w,wordmap[w],data[7])
            wcount_ok+=1
            if j<MAX_SEQUENCE_LENGTH:
#                data[i][j]=wordmap[w]
                d[j]=wordmap[w]
                j+=1
    data.append(d)
print('%d tokens found (%d has embeddings)'%(wcount_all,wcount_ok))

#print(data[7], texts[7])
#print(data[8], texts[8])
#print(data[9], texts[9])
#exit()

data=torch.tensor(data).to(device)
labels=F.one_hot(torch.tensor(labels),2).float().to(device)

#Found 159388 texts. (143961+15427)
#40056712 tokens found (38577450 has embeddings)
#Shape of data tensor: torch.Size([159388, 100])

print('Shape of data tensor:', data.shape)
#Shape of data tensor: (118952, 100)

print('Shape of label tensor:', labels.shape)
#Shape of label tensor: (118952, 2)

print("TIME: %5.3f sec"%(time.time()-t0))

#####################################################################################################


batch_size=256
#loss_fn=nn.CrossEntropyLoss()
#loss_fn=nn.BCELoss()
loss_fn=nn.BCEWithLogitsLoss()
val_loss=0
val_acc=0

optimizer = torch.optim.Adam(cnn_model.parameters(), lr=0.001, betas=(0.9, 0.999), eps=1e-07) # keras defaults

#optimizer = torch.optim.AdamW(cnn_model.parameters(), lr=1e-3,  weight_decay=1e-1, betas=(0.9, 0.95) )


ep_size=num_train//batch_size

#lr=0.2
for ep in range(100):

    t0=time.time()

    t_loss=0.0
    t_acc=0

    cnn_model.train()

    for step in range(ep_size):

        optimizer.zero_grad()

        # get batch
        ix = torch.randint(num_train-batch_size, (batch_size,))
        x = data[ix]
        y = labels[ix]

#        rnd=torch.randint(0,MAX_SEQUENCE_LENGTH,(batch_size,10))  # gen. (batchsize * 10) random positions
#        for j in range(batch_size): x[j][rnd[j]]=0   # mask some words

        for j in range(10): x*=masks[torch.randint(0,MAX_SEQUENCE_LENGTH,(batch_size,))]

#        if step==0: print(x[3])


# 100:  loss=0.0198 acc=0.9929  val: 0.0102 / 0.9964   (4.620 sec)      20% word-drop
# 100:  loss=0.0146 acc=0.9948  val: 0.0080 / 0.9972   (4.608 sec)      10%
# 100:  loss=0.0091 acc=0.9970  val: 0.0164 / 0.9946   (2.593 sec)       0%

        logits=cnn_model(x)
        loss = loss_fn(logits, y)
        loss.backward()
        optimizer.step()

        t_loss+=loss.item()

        # calc acc
        _, acc_pred = logits.max(dim=1)
        _, acc_good = y.max(dim=1)
        t_acc+= (acc_good == acc_pred).sum().item()

    t_loss/=ep_size
    t_acc/=ep_size*batch_size

    # eval
    cnn_model.eval()
    with torch.no_grad():
            val=cnn_model(data[num_train:])
            val_loss=loss_fn(val,labels[num_train:]).item()
            _, acc_pred = val.max(dim=1)
            _, acc_good = labels[num_train:].max(dim=1)
            acc=(acc_good == acc_pred).sum() / len(acc_good)
            val_acc=acc.item()

    print("%3d:  loss=%6.4f acc=%6.4f  val: %6.4f / %6.4f   (%5.3f sec)"%(ep+1, t_loss,t_acc, val_loss,val_acc, time.time()-t0) )

torch.save(cnn_model.state_dict(), 'net.pt')
