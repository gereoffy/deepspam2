#! /usr/bin/python3

import os
import sys
import time
import random
import logging

import gensim
from gensim.models import word2vec, keyedvectors
from gensim.models.callbacks import CallbackAny2Vec

class EpochSaver(CallbackAny2Vec):
    '''Callback to save model after each epoch.'''
    def __init__(self, path_prefix):
        self.path_prefix = path_prefix
        self.epoch = 0

    def on_epoch_end(self, model):
#        output_path = get_tmpfile('{}_epoch{}.model'.format(self.path_prefix, self.epoch))
#        model.save(self.path_prefix+"-%d"%(self.epoch))
        model.wv.save_word2vec_format(self.path_prefix+"-%d.wv"%(self.epoch))
        self.epoch+=1

logging.basicConfig(filename='gensim.log',level=logging.INFO)

saver = EpochSaver("checkpoint")

#model = Word2Vec(common_texts, iter=5, size=10, min_count=0, seed=42, callbacks=[saver])

sentences = word2vec.LineSentence('all.spm')
#sentences = word2vec.LineSentence('all5.txt.TOK')
#sentences = word2vec.PathLineSentences('TOK2x/hu/1_comm.txt.TOK2x')

#help(word2vec.Word2Vec)

model = word2vec.Word2Vec(sentences, vector_size=256, window=10, min_count=1, workers=8, epochs=25, sg=1, hs=1, sample=0, callbacks=[saver])
# model = word2vec.Word2Vec(sentences, size=300, window=5, min_count=10, workers=32, iter=5, sample=0)
#model = word2vec.Word2Vec(sentences, size=300, window=10, min_count=20, workers=8, iter=30, sample=0)

#model = word2vec.Word2Vec(sentences, vector_size=256, window=5, min_count=20, workers=12, epochs=30, sample=0)

#model.save("all12sg.save")
model.wv.save_word2vec_format("spm6.wv")
#model.wv.save_word2vec_format("all12sg.wvbin", binary=True)
#print(model.wv['kedves'])
