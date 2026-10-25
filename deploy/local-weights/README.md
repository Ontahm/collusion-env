# deploy/local-weights/

Local model weights for `make local-server`. The `.gguf` files are git-ignored; `make models`
downloads them from pinned revisions and checks them against `SHA256SUMS`.

| File | Source (pinned revision) | Size | SHA-256 |
|---|---|---|---|
| `Qwen3-4B-Q4_K_M.gguf` | [Qwen/Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF) @ `bc640142c66e1fdd12af0bd68f40445458f3869b` | 2.5 GB | `7485fe6f…8534fdf5` |
| `Qwen3-4B-abliterated-q4_k_m.gguf` | [Mungert/Qwen3-4B-abliterated-GGUF](https://huggingface.co/Mungert/Qwen3-4B-abliterated-GGUF) @ `56175aed285a884480f49bb18d2a1b0e05a7749f` | 2.5 GB | `2638dc26…7ad57082` |

Qwen3-4B: Apache-2.0. The abliterated model is a refusal-removed variant of the same base model,
quantised by another packager (a small confound when comparing the two).

To add a model: its pinned download URL in the Makefile (`models` target), its SHA-256 here and in
`SHA256SUMS`, a server name (`--alias`), and a file in `configs/models/` with that name.
