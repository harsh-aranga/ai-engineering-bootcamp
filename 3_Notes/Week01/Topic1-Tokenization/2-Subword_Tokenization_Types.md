Following are the tokenization types used under subword tokenization.
### BPE
* Check [[3-Byte_Pair_Encoding]]
### WordPiece
- **Used by:** BERT, DistilBERT, ELECTRA
- **Difference from BPE:** Chooses merges by likelihood score, not frequency
- **Marker:** Uses `##` prefix for non-starting subwords (`un##hap##py`)
- **Status:** Legacy (BERT-era 2018), modern LLMs use BPE

### SentencePiece
- **What it is:** Library (not an algorithm) that implements BPE/Unigram
- **Key feature:** Language-agnostic, no pre-tokenization needed
- **Used by:** T5, LLaMA, Mistral, multilingual models
- **Marker:** Uses `▁` to mark spaces (`▁Hello▁world`)
- **Why it matters:** Handles languages without spaces (Chinese, Japanese)

### Unigram
- **Used by:** T5, XLNet, ALBERT (via SentencePiece)
- **Approach:** Starts with huge vocab, prunes down (opposite of BPE)
- **Status:** Niche use, BPE dominates

### What You Need to Remember
- **Production reality:** 90% of modern LLMs use BPE (GPT, Claude, LLaMA)
- **BERT models:** Use WordPiece (legacy)
- **Multilingual models:** Often use SentencePiece library with BPE
- **For interviews:** "BPE merges by frequency, WordPiece by likelihood, SentencePiece is a library"