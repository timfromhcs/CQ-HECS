# Raw local evidence

This directory contains command logs captured during the v2.4/next-stable investigation. Each log is tied to the baseline or source SHA and exact command recorded in `../TEST_MATRIX.md` and `../EXECUTION_LOG.md`. Logs must not contain credentials or sensitive environment dumps.

## Raw upstream dumps kept out of git

`openai_math_tree.json` (15 MB, truncated GitHub tree API response; not used for any count) and the two `*.b64` transfer encodings of the already-tracked `openai_math_CONTENTS.md` / `openai_math_formalization.yaml` are intentionally not committed. They remain in the working tree of the machine that captured them. SHA-256:

- `openai_math_tree.json`: 3297460b6cf6dff60ad41b041412eb7840943b616a3d7d4f709981b8a6c5649d
- `openai_math_contents.b64`: b1ff4369cb68d0d143cb9e688972b7ea73ca3bff3487f59c2bf9219fb92ad147
- `openai_math_formalization.b64`: 4c828da15d5e41554039982dd650730716dae3b073db01e939db53b6e70a5f75
