"""Full temporal labeling pipeline for a new prayer video.

Steps
  1. load + temporally track the praying person,
  2. extract scale/translation-invariant pose features,
  3. classify each frame into a rak'ah-agnostic prayer state (temporal window),
  4. count rak'ahs from prostration episodes detected in the motion itself,
  5. decode the whole video against the canonical sequence for that rak'ah
     count (illegal jumps structurally impossible, jitter suppressed),
  6. attach rak'ah numbers from sequence position,
  7. compute per-frame confidence and group uncertain ranges.

Output: contiguous, gap-free segment list covering frame 1..N.
"""
import json
import os
import re

import numpy as np
from scipy.ndimage import median_filter
from sklearn.ensemble import HistGradientBoostingClassifier

import dataset as D
import decode as DC
import features as F
import video_loader as V

HERE = os.path.dirname(os.path.abspath(__file__))

DROP_PREFIX = ("rel_", "torso_tilt_signed", "conf_core_min")
CLF_PARAMS = dict(max_iter=150, learning_rate=0.05, max_depth=4,
                  l2_regularization=10.0, min_samples_leaf=100, random_state=0)

# prostrating torso: strongly tilted, hips low, body compressed
SUJUD_TILT = 55.0
SUJUD_HIP = 0.90
SUJUD_BODY = 0.90
SUJUD_SMOOTH = 21


def curated_indices(names):
    return [i for i, n in enumerate(names) if not n.startswith(DROP_PREFIX)]


def train_classifier(window=7):
    raw, names, skel, groups, rakah, frames = D.build_reference_dataset()
    cols = curated_indices(names)
    X = D.add_temporal(raw[:, cols], groups, window=window)
    vocab = sorted(set(skel))
    y = np.array([vocab.index(s) for s in skel])
    clf = HistGradientBoostingClassifier(**CLF_PARAMS).fit(X, y)
    return clf, vocab, names, cols, window


def classify_video(clf, vocab, cols, window, video):
    raw, _ = V.to_matrix(video)
    X = F.add_temporal_features(raw[:, cols], window=window)
    proba = clf.predict_proba(X)
    M = np.full((X.shape[0], len(vocab)), np.log(1e-12))
    for c, ci in enumerate(clf.classes_):
        M[:, ci] = np.log(np.clip(proba[:, c], 1e-12, 1.0))
    return M


def count_rakahs(video):
    """Detect prostration episodes from motion; 2 sujud per rak'ah."""
    raw, names = V.to_matrix(video)
    tilt = raw[:, names.index("torso_tilt_deg")]
    hip = raw[:, names.index("hip_above_ankle")]
    body = raw[:, names.index("body_height")]
    raw_det = np.nan_to_num((tilt > SUJUD_TILT) & (hip < SUJUD_HIP)
                            & (body < SUJUD_BODY)).astype(float)
    sm = median_filter(raw_det, size=SUJUD_SMOOTH)
    episodes, in_ep, start = [], False, 0
    for i, v in enumerate(sm):
        if v >= 0.5 and not in_ep:
            in_ep, start = True, i
        elif v < 0.5 and in_ep:
            in_ep = False
            episodes.append((start + 1, i, i - start))
    if in_ep:
        episodes.append((start + 1, len(sm), len(sm) - start))
    # merge episodes separated by a short gap: a gap inside one rak'ah's
    # sujud pair region is usually sitting-detection noise, not a boundary
    merged = []
    for ep in episodes:
        if merged and ep[0] - merged[-1][1] <= 30:
            prev = merged.pop()
            merged.append((prev[0], ep[1], ep[1] - prev[0]))
        else:
            merged.append(ep)
    merged.sort(key=lambda e: -e[2])
    keep = [e for e in merged if e[2] >= 60]
    keep.sort()
    return len(keep), keep, merged


def decode_video(M, vocab, n_rakah, sujud_episodes=None, min_len=10,
                 skip_penalty=12.0):
    index = {c: i for i, c in enumerate(vocab)}
    anchors = None
    if sujud_episodes:
        # episodes are 1-based inclusive frame numbers -> 0-based inclusive
        anchors = [(a - 1, b - 1) for (a, b, _len) in sujud_episodes]
    res = DC.decode_best(M, index, candidate_counts=(n_rakah,), anchors=anchors,
                         min_len=min_len, skip_penalty=skip_penalty)
    return res


def per_frame_confidence(M, res):
    """Per-frame confidence for the chosen state.

    Blends the chosen state's emission probability with its margin over the
    competing state, so genuinely ambiguous boundaries score low while solid
    postures score high. Face/ear occlusion never enters this: the classifier
    features exclude them.
    """
    P = np.exp(M - M.max(axis=1, keepdims=True))
    P = P / P.sum(axis=1, keepdims=True)
    pbest = np.zeros(M.shape[0])
    margin = np.zeros(M.shape[0])
    for t in range(M.shape[0]):
        order = np.argsort(-P[t])
        pbest[t] = P[t, order[0]]
        margin[t] = P[t, order[0]] - P[t, order[1]]
    return np.clip(0.6 * pbest + 0.4 * margin, 0, 1)


def build_segments(res, video, M):
    """Contiguous segments with frame numbers, labels and confidence."""
    metas = video["meta"]
    path = res["path"]
    states = res["states"]
    labels = DC.resolve_rakah_sequence([states[p] for p in path], res["n_rakah"])
    conf = per_frame_confidence(M, res)

    segs = []
    for i, lab in enumerate(labels):
        if segs and segs[-1]["label"] == lab:
            segs[-1]["end_i"] = i
            segs[-1]["confs"].append(conf[i])
        else:
            segs.append({"label": lab, "start_i": i, "end_i": i,
                         "confs": [conf[i]]})
    for s in segs:
        s["start_frame"] = metas[s["start_i"]]["num"]
        s["end_frame"] = metas[s["end_i"]]["num"]
        s["confidence"] = float(np.mean(s["confs"]))
        s["min_confidence"] = float(np.min(s["confs"]))
        s["length"] = s["end_i"] - s["start_i"] + 1
        s.pop("confs")
    return segs, labels, conf


def run(jsonl=None, verbose=True):
    video = V.load_video(jsonl) if jsonl else V.load_video()
    clf, vocab, names, cols, window = train_classifier()
    M = classify_video(clf, vocab, cols, window, video)
    n_ep, keep, merged = count_rakahs(video)
    n_rakah = max(1, n_ep // 2)
    if verbose:
        print("sujud episodes (kept):", len(keep))
        for e in keep:
            print("   %6d-%6d len=%5d" % e)
        print("=> rak'ah count from motion:", n_rakah)
    res = decode_video(M, vocab, n_rakah, sujud_episodes=keep)
    segs, labels, conf = build_segments(res, video, M)
    return {"video": video, "res": res, "segments": segs, "labels": labels,
            "conf": conf, "n_rakah": n_rakah, "sujud": keep,
            "all_episodes": merged}


if __name__ == "__main__":
    out = run()
    print("\n=== SEGMENTS: %d ===" % len(out["segments"]))
    for s in out["segments"]:
        print("  %6d-%6d  %-46s conf=%.2f" %
              (s["start_frame"], s["end_frame"], s["label"], s["confidence"]))
    print("\ntotal frames:", len(out["labels"]))