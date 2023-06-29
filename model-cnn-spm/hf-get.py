#! /usr/bin/python3

#name="bert-base-multilingual-cased"
#name="distilbert-base-multilingual-uncased"
#name='NYTK/PULI-BERT-Large'
#name="sentence-transformers/distiluse-base-multilingual-cased-v2"  # OOM lesz mindig...
#name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" # 79.9%
#name="xlm-mlm-100-1280" # 0.8542
#name="xlm-mlm-17-1280" # 0.7941
name="xlm-roberta-large" # https://arxiv.org/abs/1911.02116    58GB hu
#name="xlm-roberta-base" # https://arxiv.org/abs/1911.02116    58GB hu    83.5% @ 5 epoch 16x32 batch

id2label = {0: "NEGATIVE", 1: "POSITIVE"}
label2id = {"NEGATIVE": 0, "POSITIVE": 1}

import os
import torch

from transformers import AutoTokenizer,BertTokenizer,LlamaTokenizer
from transformers import AutoModelForSequenceClassification, TrainingArguments, Trainer

#tokenizer = AutoTokenizer.from_pretrained("distilbert-base-multilingual-cased")
tokenizer = AutoTokenizer.from_pretrained(name, do_lower_case=False)
tokenizer.save_pretrained("temp")
tokenizer.save_vocabulary("temp")
os.rename("temp/sentencepiece.bpe.model","spm.model")

model = AutoModelForSequenceClassification.from_pretrained(name, num_labels=len(id2label), id2label=id2label, label2id=label2id)
print(model)
print(model.parameters())
print(model.num_parameters())

#num_params = sum([p.numel() for p in model.parameters() if p.requires_grad])
#print(f"Number of trainable parameters: {num_params}")

w=model.roberta.embeddings.word_embeddings.weight
print(w.size())
print(w)
torch.save(w,"embeddings.pt")


