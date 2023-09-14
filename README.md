# deepspam2
DeepSpam milter v2 development

Project status:

1. deepspam1 ported to pytorch
2. new model using SentencePiece and embedding from pretrained XLM
3. new metrics for model eval, optimized for spam filtering
4. dataset found to be wrong, needs a full review and cleanup
5. old mailer3 unable to handle dataset properly (utf8, bad html etc)
6. mailer3 ported to python3 -> mailer4 initial version (same ui/keys)
7. old html2txt used in deepspam1 found to be wrong... new html parser developed!
8. wide unicode display issues -> wcwidth/widechars added/implemented...
9. python's mime email parser found to be sloooow and sometimes broken -> implemented my own
10. mailer4 missing search & tagging & export functions, TODO...

# Tools included:

- torch_emb.py: direct rewrite of deepspam1's model train code to pytorch
- torch_spm3.py: new model trainer, uses py class from model/ dir
- maildedup3.py: email deduplication and parsing, from mbox to txt
- mailer4.py: Python3 version of my old email reader, used primarily for spam-dataset preparation & model eval

# Libraries included:

- eml2str.py: my mime email parser and html2txt converter functions
- hdrdecode.py: my email header parser functions, from the pymavis/spamwall project
- ttykeymap.py: python version of my old getch2.c, console i/o functions and text UI
- widechars.py: wide unicode utilities, based on https://github.com/jquast/wcwidth
- striprtf.py: rtf to txt converter, from https://github.com/joshy/striprtf
