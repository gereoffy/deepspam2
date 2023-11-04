#! /usr/bin/python3

import numpy as np

# SentencePiece training cmd:
# spm_train --input=all.out4 --vocab_size=262144 --max_sentencepiece_length=32 --model_prefix=spm5 --character_coverage=0.9999999 --max_sentence_length=65536 --remove_extra_whitespaces --train_extremely_large_corpus --hard_vocab_limit=true --num_threads=8 --shuffle_input_sentence=true
# spm_encode --model=spm5.model --input=all.out4 --output=all.spm

#import sentencepiece as spm
#sp = spm.SentencePieceProcessor(model_file='spm5.model')
#print(sp.encode_as_pieces(['This is a test', 'Hello world']))

vocab={}
numw=0
for line in open("spm6.vocab","rt"):
    w=line.split()[0]
#    vocab[w]=numw
    vocab[numw]=w
    numw+=1

print(vocab[3])

wcount=0
for line in open("spm6.wv","rt"):
    v=line.strip().split(" ")
    if len(v)<64:
        print(v)
#        embedding_matrix = np.zeros((int(v[0])+1, int(v[1])),dtype='float32')
        embedding_matrix = np.zeros((numw, int(v[1])),dtype='float32')
        continue
    wcount+=1

    i=int(v[0])
    embedding_matrix[i] = np.asarray(v[1:], dtype='float32')

    w=vocab[i]
    del vocab[i]

for w in vocab:
    print("Vocab-only:",w,vocab[w])


print('Words found: %d / %d'%(wcount,numw))


import torch
w=torch.from_numpy(embedding_matrix).float()#.to(device)
print(w.size())
print(w)
torch.save(w,"embeddings6.pt")

