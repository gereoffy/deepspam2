#! /bin/bash

if test -f all.txt; then

    # filter unwanted chars (emoji, chinese etc) from all.txt -> all.out
    ./charfilter6.py

    # train SentencePiece tokenizer:
    spm_train --model_prefix=spm6 --input=all.out6 --input_sentence_size=5000000 --vocab_size=262144 --max_sentencepiece_length=16 --character_coverage=1 --max_sentence_length=65536 --remove_extra_whitespaces --train_extremely_large_corpus --hard_vocab_limit=true --num_threads=8 --shuffle_input_sentence=false

    # tokenize input:
    spm_encode --model=spm6.model --input=all.out6 --output=all.spm --output_format=id

    # train gensim's Word2vec on tokens:
    ./wordvec1.py

    # merge SPM vocab and WV vectors together, save as embeddings.pt
    ./merge.py

fi
