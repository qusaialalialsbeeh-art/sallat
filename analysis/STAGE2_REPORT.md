# STAGE 2 — TEMPORAL LABELING RUN (NEW VIDEO)

## Input
`yolo_pose_results.jsonl` — 10,788 frames, 1 detection/frame, 17 COCO keypoints,
1920x1080, no malformed lines. Reference files `fajr.json` / `maghrib.json`
untouched (verified via `git diff`).

## Pipeline
1. `video_loader.py` — numeric frame ordering + temporal person tracking.
2. `features.py` — 51 scale/translation-invariant features (joint angles, torso
   tilt, vertical ratios, joint distances, velocities, confidence masks).
   Temporal windows (7 frames) via `dataset.add_temporal`.
3. `pipeline.train_classifier` — HistGradientBoosting with strong regularisation
   (`l2=10`, `min_samples_leaf=100`, `lr=0.05`) over view-invariant features.
   Raw `rel_*_x` coordinates, signed tilt and `conf_core_min` are dropped because
   they encode camera framing rather than pose.
4. `pipeline.count_rakahs` — prostration detected from motion
   (`tilt>55 & hip<0.9 & body<0.9`, median-smoothed); 2 sujud per rak'ah.
5. `decode.decode_best` — segmental DP aligning the whole video to the canonical
   ordered state list for the detected rak'ah count. Illegal jumps are
   structurally impossible; core postures are mandatory (huge skip cost) while
   brief transitions may be skipped cheaply; `min_len` suppresses jitter.
   Detected prostration episodes anchor the sujud states, resolving the
   "sitting between the two sujuds" vs "tashahhud" ambiguity by sequence
   position.
6. `decode.resolve_rakah_sequence` — rak'ah numbers attached from sequence
   position only (counter advances on entering القيام, never per frame).

## Results
- Rak'ah count from motion: **3** (6 prostration episodes).
- Output: **41 contiguous, gap-free segments** covering frames 1..10,788.
- Rak'ah sequence: الأولى → الثانية → (التشهد الأول) → الثالثة → التشهد الأخير → التسليم.

## Validation
- In-sample round-trip on both references: frame agreement **0.999**, segment
  counts exactly 27 (fajr) and 41 (maghrib), matching ground truth.
- Leave-one-prayer-out is deliberately reported for honesty: fajr 0.587 /
  maghrib 0.124 frame accuracy, showing frame-level classification alone is not
  reliable — which is exactly why grammar-constrained decoding is used.
- 19 low-confidence boundary bands reported for manual review.

## Label Studio
Host `185.237.15.215:8080` is **unreachable from this sandbox** (all ports
time out; general internet works). `PROJECT_ID` is also not set in the
environment. No write was attempted or performed.

`push.py` is ready: it performs a safe GET first, validates on a single task,
then writes new annotations only — never deleting tasks/annotations and never
touching keypoints or boxes. Run once the host is reachable:

    PROJECT_ID=<id> python3 push.py --dry-run
    PROJECT_ID=<id> python3 push.py

## Artifacts
`segments.json`, `inferences.txt`, `labelstudio_payload.json`.
