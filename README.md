# deepspam2
DeepSpam milter v2 development

PyTorch implementation of various text classifier methods optimized for email SPAM filtering:

- Done:  CNN + SentencePiece cased (using embedding from pretrained XLM)
- TODO:  CNN + Word2vec uncased (DeepSpam v1 compatible)
- TODO:  Transformer variations (BERT, GPT2, LLaMA etc)

# mailer4 included
Python3 version of my old email reader, used primarily for spam-dataset preparation & model eval. 
Includes hdrdecode.py from pymavis/spamwall and wide char tables from https://github.com/jquast/wcwidth
