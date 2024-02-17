# DeepSpam milter v2

Neural-network text classifier for SPAM-filtering witten in python3, using Milter API for MTA integration.
This is a complete rewrite of https://github.com/gereoffy/deepspam1 using PyTorch and SPM tokenizer.

Release contains pre-trained model for detecting Hungarian & English language spam emails.

# Project history:

1. deepspam1 tf2-keras model ported to pytorch
2. new model using SentencePiece and embedding from pretrained XLM
3. new metrics for model eval, optimized for spam filtering
4. dataset found to be wrong, requires a full review and cleanup :(
5. old mailer3 unable to handle dataset properly (utf8, bad html etc)
6. mailer3 ported to python3 -> mailer4 initial version (same ui/keys)
7. wide unicode display issues -> wcwidth/widechars added/implemented...
8. old html2txt used in deepspam1 found to be wrong... new html parser developed!
9. python's mime email parser found to be sloooow and sometimes broken -> implemented my own
10. mailer4: integrated deepspam model evaluation, see Screenshot-mailer4-diffmode.png
11. mailer4: added search, selection, deduplication, tagging features - tested on real data
12. better charmap filtering (charfilter6.py & unicodes6x.map) to remove unicode shit...
13. XML's embedding replaced by custom multi-language word2vec pretrained vectors & spm6 model
14. hyperparameter search implemented (bs/lr), new model eval code to find best training result
15. re-implemented the milter API from scratch using native asyncio -> deepspam4.py
16. first stable/public release! (after testing in production for a week)
17. visualization (asciiart/matplotlib) of the model weights (trainging & testing processes)
18. email parser: refactor/rewrite hdrdecode & parse_from functions of old hdrdecode.py

# Tools included:

- torch_emb.py: direct rewrite of deepspam1's model train code to pytorch
- torch_spm3.py: new model trainer, uses py class from model/ dir
- torch_eval.py: model eval & compare
- maildedup3.py: email deduplication and parsing, from mbox to txt
- mailer4.py: Python3 version of my old email reader, used primarily for spam-dataset preparation & model eval

# Libraries included:

- eml2str.py: all of my mime email parser and html2txt converter functions
- ttykeymap.py: python version of my old getch2.c, console i/o functions and text UI
- widechars.py: wide unicode utilities, based on https://github.com/jquast/wcwidth
- striprtf.py: rtf to txt converter, from https://github.com/joshy/striprtf
