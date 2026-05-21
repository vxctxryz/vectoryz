# Models directory

This directory holds runtime ML-models (FastText language-id, etc.).

On first run, vectoryz fetches `lid.176.ftz` (~917KB) from Meta's CDN
into this directory. Subsequent runs use the cached file.

To pre-fetch manually:

```bash
curl -sSL -o lid.176.ftz \
    https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz
```
