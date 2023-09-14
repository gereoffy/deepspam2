# deepspam2
DeepSpam milter v2 development

PyTorch implementation of various text classifier methods optimized for email SPAM filtering:

- Done:  CNN + SentencePiece cased (using embedding from pretrained XLM)
- TODO:  CNN + Word2vec uncased (DeepSpam v1 compatible)
- TODO:  Transformer variations (BERT, GPT2, LLaMA etc)

# Tools included:

- torch_emb.py: direct rewrite of deepspam1's model train code to pytorch
- torch_spm3.py: new model trainer, uses py class from model/ dir
- maildedup3.py: email deduplication and parsing, from mbox to txt
- mailer4.py: Python3 version of my old email reader, used primarily for spam-dataset preparation & model eval

# Libraries included:

- striprtf.py: rtf to txt converter, from https://github.com/joshy/striprtf
- eml2str.py: email parser and html to txt converter by me
- hdrdecode.py: email header parsers by me, from pymavis/spamwall project
- widechars.py: wide unicode utilities, tables from https://github.com/jquast/wcwidth
- ttykeymap.py: python version of my old getch2.c, console i/o functions, text UI
