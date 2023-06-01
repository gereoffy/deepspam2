
import time
import torch
import sentencepiece

class DeepSpam_model(torch.nn.Module):

    def __init__(self, ndim, filter_sizes=[2, 3, 4, 5], num_classes=2, dropout=0.5, filters=128, hidden=64):
        super().__init__()
        self.convl = torch.nn.ModuleList([ torch.nn.Conv1d(in_channels=ndim, out_channels=filters, kernel_size=k, padding="valid") for k in filter_sizes ])
        self.l_dr2 = torch.nn.Dropout(dropout,inplace=True)
        self.l_hid = torch.nn.Linear(len(filter_sizes)*filters, hidden)
        self.l_fc = torch.nn.Linear(hidden, num_classes)

    def forward(self, x):
        x=x.permute(0, 2, 1) # reorder embedding->conv1d
        x_conv = [ torch.max( torch.nn.functional.relu( conv(x) ), dim=2).values for conv in self.convl ] # Conv1D + ReLU + GlobalMaxPooling
        x=torch.cat(x_conv,dim=1)
        x = self.l_dr2(x) # drop 0.5
        x = torch.nn.functional.relu(self.l_hid(x))  # linear 512->64 + ReLU
        x = self.l_fc(x)   # linear 64->2
        return x



class DeepSpam:

######## Example: ############
# from model import DeepSpam
# ds=DeepSpam()   # load model
# result=ds(text) # use model

  def __init__(self,path="model/",device="cpu",load="deepspam.pt"):
    self.device=device

    # load pretrained tokernizer:
    self.tokenizer = sentencepiece.SentencePieceProcessor(model_file=path+'spm.model')

    # load pretrained embeddings:
    embedding_tensors=torch.load(path+"embeddings.pt",map_location=device)
    embedding_tensors.requires_grad=False
    num_words,num_dim=embedding_tensors.size()
    embedding_tensors[0]*=0 # token #0 = mask/padding
    self.embedding = torch.nn.Embedding.from_pretrained(embedding_tensors,freeze=True)

    # create classification model:
    self.model=DeepSpam_model(num_dim)
    self.model.to(device)
    if load:
        self.model.load_state_dict(torch.load(path+load,map_location=device))
        self.model.eval()

    # print summary:
    print(self.model)
    all_params = sum([p.numel() for p in self.model.parameters()])
    print("MODEL: vocab=%d  embed=%d  params=%d"%(num_words,num_dim,all_params))


  def tokenize(self,texts,max_len=None):
    # tokenize array of texts to input_ids & optional truncating / padding:
    data = []
    for d in self.tokenizer.encode(texts):
        if max_len:
            d=d[:max_len] # truncate
            d+=[0]*(max_len-len(d)) # add padding
        data.append(d)
    return data


  def __call__(self,text,max_len=None):
    with torch.no_grad():
        input_ids=torch.tensor(self.tokenize([text],max_len),dtype=torch.int,device=self.device)
        logits=self.model(self.embedding(input_ids))
        res=logits[0].sigmoid() # get probs
        res=res[0]*100.0/(res[0]+res[1])
    return res.item() # 0.0 ... 100.0 %

  def save(self,path="model/"):
    torch.save(self.model.state_dict(), path+'deepspam.pt')

  def train(self,texts,label_ids,num_train,epochs=50,batch_size=256,max_len=256,dropwords=10,savebest=True):

    # prepare dataset (array of texts and label_ids -> tokenized/onehot tensors):
    data=self.tokenize(texts,max_len)
    data=torch.tensor(data,dtype=torch.int,device=self.device)
    labels=torch.nn.functional.one_hot(torch.tensor(label_ids),2).float().to(self.device)
    print('Shape of data tensor:', data.shape)    #Shape of data tensor: (118952, 100)
    print('Shape of label tensor:', labels.shape) #Shape of label tensor: (118952, 2)

    # for word dropout:
    masks=[]
    for i in range(max_len):
        m=[1]*max_len
        m[i]=0
        masks.append(m)
    masks=torch.tensor(masks).to(self.device)

    #loss_fn=torch.nn.CrossEntropyLoss()
    #loss_fn=torch.nn.BCELoss()
    loss_fn=torch.nn.BCEWithLogitsLoss()

    #optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001, betas=(0.9, 0.999), eps=1e-07) # keras defaults
    optimizer = torch.optim.AdamW(self.model.parameters(), lr=1e-4,  weight_decay=1e-1, betas=(0.9, 0.95) )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs, 1e-5, verbose=False) # 2x jobb a final loss/acc vele mint nelkule!
#    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)

    ep_size=num_train//batch_size
    val_loss=0
    val_acc=0
    best_acc=0

    for ep in range(epochs):

        t0=time.time()

        # train 1 epoch:

        t_loss=0.0
        t_acc=0

        self.model.train()
        for step in range(ep_size):

            # get batch
            ix = torch.randint(num_train-batch_size, (batch_size,))
            x = data[ix]
            y = labels[ix]

            # word-level dropout
            for j in range(dropwords): x*=masks[torch.randint(0,max_len,(batch_size,))]

            # forward & backpropagation
            optimizer.zero_grad()
            logits=self.model(self.embedding(x))
            loss = loss_fn(logits, y)
            loss.backward()
            optimizer.step()

            t_loss+=loss.item()

            # calc accuracy
            _, acc_pred = logits.max(dim=1)
            _, acc_good = y.max(dim=1)
            t_acc+= (acc_good == acc_pred).sum().item()

        t_lr=scheduler.get_last_lr()[0]
        scheduler.step()

        t_loss/=ep_size
        t_acc/=ep_size*batch_size

        t1=time.time()

        # eval

        test_ham=0
        test_hamcnt=0
        test_spam=0
        test_spamcnt=0
        test_fp=0
        test_fn=0

        self.model.eval()
        with torch.no_grad():
            val_acc=0.0
            val_loss=0.0
            i=num_train
            while i<len(data):
                eval_batch_size=batch_size*8
                if i+eval_batch_size>len(data): eval_batch_size=len(data)-i
                x=data[i:i+eval_batch_size]
                y=labels[i:i+eval_batch_size]

                logits=self.model(self.embedding(x))
                val_loss+=loss_fn(logits,y).item()*eval_batch_size
                probs=logits.softmax(dim=1)

                _, acc_pred = probs.max(dim=1)
                _, acc_good = y.max(dim=1)
                acc=(acc_good == acc_pred).sum()
                val_acc+=acc.item()

                for res in probs:
                    if label_ids[i]==0: test_spamcnt+=1 # 0=negative (spam)
                    else: test_hamcnt+=1                # 1=positive (ham)
                    if res[1]>0.9: # ham detected
                        if label_ids[i]==1: test_ham+=1
                        else: test_fn+=1
                    elif res[0]>0.9: # spam detected
                        if label_ids[i]==0: test_spam+=1
                        else: test_fp+=1
                    i+=1

            i-=num_train
            val_acc/=i
            val_loss/=i

        # custom metrics for spam filtering:
        test_acc=(1.0-test_spam/test_spamcnt) + test_fn/test_spam + 3.0*test_fp/test_ham # ratio of non-detected spam + ratio of FNs + 3x ratio of FPs

        if ep<epochs/5:
            is_best='.' # warmup :)
            best_acc=test_acc
        elif test_acc<best_acc-0.0002:
            best_acc=test_acc
            is_best='*'
            if savebest: self.save()
        else: is_best=' '

        print("%3d:  loss=%6.4f acc=%6.4f  val: %6.4f / %6.4f / %6.4f %s (%5.2f+%4.2f sec) lr:%10.8f  HAM:%6.2f/%5.3f%%  SPAM:%6.2f/%5.3f%% "%
            (ep+1, t_loss,t_acc, val_loss,val_acc,test_acc, is_best, t1-t0, time.time()-t1, t_lr,
            100.0*test_ham/test_hamcnt, 100.0*test_fp/test_ham, 100.0*test_spam/test_spamcnt, 100.0*test_fn/test_spam ) )


