#! /usr/bin/python3

from gensim.models.keyedvectors import KeyedVectors
import sentencepiece as spm

text="Kedves hölgyeim és uraim! Hello minden macska es beka! Ich bin wieder hier, bei dir... Hasta la vista, baby"

sp = spm.SentencePieceProcessor(model_file='spm6.model')
ids=sp.encode([text.lower()])[0]
print(ids)
print(sp.DecodeIds(ids))



wv=KeyedVectors.load_word2vec_format('spm6.wv', binary=False)
for i in ids:
    w=sp.IdToPiece(i)
    print(w+":", ", ".join(sp.IdToPiece(int(w)) for w,p in wv.most_similar(str(i))) )
