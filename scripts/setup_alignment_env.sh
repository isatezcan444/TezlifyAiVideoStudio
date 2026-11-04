#!/usr/bin/env bash
# Stage 5.4 — build the isolated speech-alignment environment.
#
# The application venv stays Python 3.14 with no ML dependencies. The CTC
# aligner needs torch + transformers, which do not support 3.14, so they live in
# their own virtualenv and are reached by subprocess from
# backend/src/tezlify_studio/infrastructure/alignment/ctc_forced_alignment_impl.py.
#
# Downloads: ~1.3 GB of packages into tools/alignment-venv and ~1.3 GB of model
# weights into tools/hf-cache on first alignment. Both are gitignored.
# Nothing here sends user audio to a server; alignment runs on the local CPU.
#
# Usage:  bash scripts/setup_alignment_env.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/tools/alignment-venv"
CACHE_DIR="${REPO_ROOT}/tools/hf-cache"

# torch ships macOS arm64 wheels for 3.10-3.12; prefer the newest available.
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10; do
  if command -v "${candidate}" >/dev/null 2>&1; then
    PYTHON_BIN="${candidate}"
    break
  fi
done

if [ -z "${PYTHON_BIN}" ]; then
  echo "ERROR: need python3.10, 3.11 or 3.12 on PATH for the alignment environment." >&2
  echo "       (found: $(python3 -V 2>&1))" >&2
  exit 1
fi

echo "==> creating ${VENV_DIR} with ${PYTHON_BIN}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip

echo "==> installing torch (CPU) then transformers + ctc-segmentation"
"${VENV_DIR}/bin/pip" install torch --index-url https://download.pytorch.org/whl/cpu
"${VENV_DIR}/bin/pip" install transformers soundfile numpy ctc-segmentation librosa

mkdir -p "${CACHE_DIR}"

echo "==> verifying imports"
"${VENV_DIR}/bin/python" - <<'PY'
import importlib
missing = []
for name in ("torch", "transformers", "ctc_segmentation", "soundfile", "numpy"):
    try:
        importlib.import_module(name)
        print(f"  OK   {name}")
    except Exception as exc:
        missing.append(f"{name}: {exc}")
        print(f"  FAIL {name}: {exc}")
if missing:
    raise SystemExit(1)
PY

echo "==> verifying the alignment model is reachable (not downloading yet)"
HF_HOME="${CACHE_DIR}" "${VENV_DIR}/bin/python" - <<'PY'
from huggingface_hub import model_info
model_id = "Baybars/wav2vec2-xls-r-300m-cv8-turkish"
info = model_info(model_id)
print(f"  OK   {model_id} (license={info.cardData.get('license') if info.cardData else 'unknown'})")
PY

echo
echo "Alignment environment ready."
echo "The first render that needs it downloads ~1.3 GB of weights into ${CACHE_DIR}."
echo "Disable lip sync without uninstalling anything by setting LIP_SYNC_ENABLED=false in .env"
