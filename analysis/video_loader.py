"""Load and preprocess the new YOLO JSONL video with temporal person tracking."""
import json
import os
import re

import numpy as np

import features as F
import tracking as T

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_JSONL = os.path.join(ROOT, "yolo_pose_results.jsonl")

_FRAME_NUM_RE = re.compile(r"(\d+)")


def frame_number_from_name(name):
    """Numeric (not lexical) frame order: frame_000010 -> 10."""
    m = _FRAME_NUM_RE.search(os.path.basename(name))
    return int(m.group(1)) if m else None


def load_video(path=DEFAULT_JSONL, verbose=False):
    """Returns dict with frames sorted numerically and tracked poses."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            num = frame_number_from_name(r["frame"])
            r["_num"] = num
            rows.append(r)
    rows.sort(key=lambda r: r["_num"])  # strict numeric ordering

    feats, confs, boxes, xy_all, meta = [], [], [], [], []
    track = None
    track_infos = []
    for k, r in enumerate(rows):
        dets = r.get("detections") or []
        idx, track, info = T.select_praying_person(
            dets, track, k, r["width"], r["height"])
        track_infos.append(info)
        if idx is None:
            feats.append(None)
            confs.append(None)
            xy_all.append(None)
            boxes.append(None)
        else:
            d = dets[idx]
            xy = np.asarray(d["keypoints_xy"], float)
            cf = np.asarray(d["keypoints_conf"], float)
            feats.append(F.extract_frame_features(xy, cf))
            confs.append(cf)
            xy_all.append(xy)
            boxes.append(np.asarray(d["box_xyxy"], float))
        meta.append({"num": r["_num"], "name": r["frame"],
                     "width": r["width"], "height": r["height"]})

    if verbose:
        n_multi = sum(1 for i in track_infos if i.get("n_candidates", 1) > 1)
        n_none = sum(1 for i in track_infos if i.get("reason") == "no_detection")
        print("frames:", len(rows), "| multi-detection frames:", n_multi,
              "| frames with no detection:", n_none)

    return {"features": feats, "confs": confs, "boxes": boxes, "xy": xy_all,
            "meta": meta, "track_infos": track_infos}


def to_matrix(video):
    sample = next(f for f in video["features"] if f is not None)
    names = F.feature_names(sample)
    raw = F.to_matrix([f if f is not None else {} for f in video["features"]], names)
    return raw, names


if __name__ == "__main__":
    v = load_video(verbose=True)
    raw, names = to_matrix(v)
    print("raw feature matrix:", raw.shape)
    print("first frames:", [m["name"] for m in v["meta"][:3]])
    print("last frames:", [m["name"] for m in v["meta"][-3:]])
