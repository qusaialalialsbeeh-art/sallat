#!/bin/bash
set -e

echo "=========================================="
echo "FIX GITHUB + GIT LFS UPLOAD"
echo "=========================================="

cd /home/runner/workspace

echo "[1] Checking project files..."

for f in \
  models/yolo26l-pose.onnx \
  models/yolo26l-pose.pt \
  package.json \
  vite.config.ts \
  tsconfig.json
do
  if [ ! -f "$f" ]; then
    echo "ERROR: Missing $f"
    exit 1
  fi
  echo "OK: $f"
done

echo "[2] Checking Git LFS..."

git lfs install

echo "[3] Removing incorrect old LFS path..."

git lfs untrack "artifacts/yolo-pose/public/models/*.onnx" 2>/dev/null || true
git lfs untrack "artifacts/yolo-pose/public/models/*.pt" 2>/dev/null || true

echo "[4] Configuring correct LFS files..."

git lfs track "models/*.onnx"
git lfs track "models/*.pt"
git lfs track "ort/*.wasm"

echo "[5] Checking .gitattributes..."

cat .gitattributes

echo "[6] Checking repository..."

if [ ! -d .git ]; then
  git init
fi

git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/qusaialalialsbeeh-art/sallat.git

echo "[7] Git status..."

git status --short

echo "[8] Adding project..."

git add -A

echo "[9] Verifying LFS files..."

git lfs ls-files

echo "[10] Creating commit..."

if git diff --cached --quiet; then
  echo "Nothing new to commit."
else
  git commit -m "Upload prayer pose project"
fi

echo "[11] Setting branch..."

git branch -M main

echo "[12] Uploading to GitHub..."

git push -u origin main

echo "=========================================="
echo "UPLOAD COMPLETE"
echo "=========================================="

echo "Repository:"
echo "https://github.com/qusaialalialsbeeh-art/sallat"

echo ""
echo "LFS FILES:"
git lfs ls-files