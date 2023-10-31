#! /usr/bin/python3

import os
import sys
import time
import random

import gensim
from gensim.models import word2vec, keyedvectors

import logging
logging.basicConfig(filename='gensim.log',level=logging.INFO)

#sentences=[]
#for line in open("sentences.txt","r"):
#    sentences.append(line.strip().split(" "))

# iter=500 x 256k sentences ->  82 min
# iter=5 x 1.5m senteces x edim=300 -> 15 min (3min/iter?)  4 thread
# iter=15 x 1.5m senteces x edim=300 -> 35 min   8 thread
#    2639960  373380768 2448033125 sentences.txt    78m7.744s  iter=10 w=7 s=300 cpu=32
#    win=5 cpu=16 iter=30  real    204m4.699s 

sentences = word2vec.LineSentence('all.spm')
#sentences = word2vec.LineSentence('all5.txt.TOK')
#sentences = word2vec.PathLineSentences('TOK/')

#help(word2vec.Word2Vec)

model = word2vec.Word2Vec(sentences, vector_size=256, window=10, min_count=1, workers=8, epochs=25, sg=1, hs=1, sample=0)
# model = word2vec.Word2Vec(sentences, size=300, window=5, min_count=10, workers=32, iter=5, sample=0)
#model = word2vec.Word2Vec(sentences, size=300, window=10, min_count=20, workers=8, iter=30, sample=0)

#model = word2vec.Word2Vec(sentences, vector_size=256, window=5, min_count=20, workers=12, epochs=30, sample=0)

#model.save("all12sg.save")
model.wv.save_word2vec_format("spm5.wv")
#model.wv.save_word2vec_format("all12sg.wvbin", binary=True)

#print(model.wv['kedves'])
