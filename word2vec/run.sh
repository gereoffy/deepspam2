#! /bin/bash

if test -f all.txt; then

    # filter unwanted chars (emoji, chinese etc) from all.txt -> all.out
    ./charfilter4.py

    # train SentencePiece tokenizer:
    spm_train --input=all.out --vocab_size=262144 --max_sentencepiece_length=32 --model_prefix=spm5 --character_coverage=0.9999999 --max_sentence_length=65536 --remove_extra_whitespaces --train_extremely_large_corpus --hard_vocab_limit=true --num_threads=8 --shuffle_input_sentence=true

    # tokenize input:
    spm_encode --model=spm5.model --input=all.out --output=all.spm

    # train gensim's Word2vec on tokens:
    ./wordvec1.py

    # merge SPM vocab and WV vectors together, save as embeddings.pt
    ./merge.py

fi
