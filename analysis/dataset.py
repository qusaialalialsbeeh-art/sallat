"""Label vocabulary, skeleton mapping and reference dataset construction.

The classifier predicts a RAK'AH-AGNOSTIC skeleton (e.g. "سجود أول" without
the rak'ah ordinal); the decoder later resolves which rak'ah it belongs to
from sequence position. This is what makes rak'ah tracking temporal rather
than geometric.
"""
import json
import os
import re

import numpy as np

import features as F

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_RAKAH_RE = re.compile(r"الركعة (الأولى|الثانية|الثالثة|الرابعة)")


def skeleton_of(label):
    """Strip the rak'ah ordinal so states generalise across rak'ah numbers."""
    return _RAKAH_RE.sub("الركعة <R>", label).strip()


def rakah_of(label):
    m = _RAKAH_RE.search(label)
    if not m:
        return None
    return {"الأولى": 1, "الثانية": 2, "الثالثة": 3, "الرابعة": 4}[m.group(1)]


def load_reference(name):
    """Read a reference file and return per-frame (features, label, conf)."""
    path = os.path.join(ROOT, name + ".json")
    d = json.load(open(path, encoding="utf-8"))
    items = sorted(d["items"], key=lambda it: it["attr"]["frame"])
    rows = []
    for it in items:
        ann = it["annotations"][0]
        pts = ann["points"]
        xy = np.array([[pts[i * 3], pts[i * 3 + 1]] for i in range(17)], float)
        # CVAT visibility: 2=visible,1=occluded,0=absent -> pseudo-confidence
        vis = np.array([pts[i * 3 + 2] for i in range(17)], float)
        conf = np.where(vis >= 2, 1.0, np.where(vis == 1, 0.5, 0.0))
        label = ann["attributes"]["salaa-fagir"]
        feat = F.extract_frame_features(xy, conf)
        feat["_label"] = label
        feat["_skeleton"] = skeleton_of(label)
        feat["_rakah"] = rakah_of(label)
        feat["_frame"] = it["attr"]["frame"]
        rows.append(feat)
    return rows


def build_reference_dataset(names=("fajr", "maghrib")):
    """Concatenate references; returns (X, skel_labels, groups, rakah, frames)."""
    all_rows, groups = [], []
    for gi, nm in enumerate(names):
        rows = load_reference(nm)
        all_rows.extend(rows)
        groups.extend([gi] * len(rows))
    sample = {k: v for k, v in all_rows[0].items() if not k.startswith("_")}
    names_f = F.feature_names(sample)
    raw = F.to_matrix(
        [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_rows],
        names_f)
    skel = [r["_skeleton"] for r in all_rows]
    rakah = np.array([r["_rakah"] if r["_rakah"] is not None else 0
                      for r in all_rows])
    frames = np.array([r["_frame"] for r in all_rows])
    return raw, names_f, skel, np.array(groups), rakah, frames


def add_temporal(raw, groups, window=7):
    """Temporal features computed WITHIN each video (no cross-video smearing)."""
    out = np.zeros((raw.shape[0], 0))
    for g in sorted(set(groups.tolist())):
        idx = np.where(groups == g)[0]
        blk = F.add_temporal_features(raw[idx], window=window)
        if out.shape[1] == 0:
            out = blk
        else:
            out = np.vstack([out, blk])
    order = np.concatenate([np.where(groups == g)[0] for g in sorted(set(groups.tolist()))])
    # restore original row order
    inv = np.argsort(order)
    return out[inv]


if __name__ == "__main__":
    raw, names_f, skel, groups, rakah, frames = build_reference_dataset()
    print("reference frames:", raw.shape[0], "raw features:", raw.shape[1],
          "temporal dims:", raw.shape[1] * 6)
    import collections
    print("distinct skeletons:", len(set(skel)))
    for s, c in collections.Counter(skel).most_common():
        print("   %-46s %6d" % (s, c))
