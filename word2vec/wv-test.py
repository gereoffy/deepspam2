#! /usr/bin/python3

from gensim.models.keyedvectors import KeyedVectors
import sentencepiece as spm

text="Kedves hölgyeim és uraim! Hello minden macska es beka! Ich bin wieder hier, bei dir... Hasta la vista, baby"

sp = spm.SentencePieceProcessor(model_file='spm5.model')
ids=sp.encode_as_pieces([text.lower()])[0]
print(ids)

wv=KeyedVectors.load_word2vec_format('spm5sg.wv', binary=False)
for w in ids:
        print(w+":", ", ".join(w for w,p in wv.most_similar(w)) )
