"""Temporal person tracking to lock onto the praying person across frames.

Selecting the highest-confidence detection independently per frame causes
identity flicker. We instead score each detection against a running track:
bbox IoU, body-centre continuity, pose-shape continuity and confidence.
"""
import numpy as np

CORE_JOINTS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]


def bbox_iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    ub = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = ua + ub - inter
    return inter / denom if denom > 1e-9 else 0.0


def pose_signature(kps_xy, kps_conf):
    """Scale/translation-invariant descriptor for identity comparison."""
    p = np.asarray(kps_xy, float)
    c = np.asarray(kps_conf, float)
    sho = (p[5] + p[6]) / 2.0
    hip = (p[11] + p[12]) / 2.0
    scale = np.linalg.norm(sho - hip)
    if scale < 1e-3:
        scale = max(np.linalg.norm(p[15] - p[0]), 1e-3)
    root = hip
    sig = (p[CORE_JOINTS] - root) / scale
    w = c[CORE_JOINTS]
    return sig, w


def select_praying_person(detections, prev_track, frame_idx, image_w, image_h):
    """Choose one detection per frame, consistent with the previous frame.

    detections: list of dicts with box_xyxy / keypoints_xy / keypoints_conf /
                confidence.
    prev_track: dict with 'box','center','sig','miss' or None.
    Returns (chosen_index, track_dict, info_dict).
    """
    if not detections:
        return None, prev_track, {"reason": "no_detection"}

    n = len(detections)
    if n == 1:
        d = detections[0]
        sig, w = pose_signature(d["keypoints_xy"], d["keypoints_conf"])
        box = list(map(float, d["box_xyxy"]))
        center = np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])
        track = {"box": box, "center": center, "sig": sig, "w": w,
                 "conf": float(d["confidence"]), "miss": 0}
        return 0, track, {"reason": "single_detection", "n_candidates": 1}

    diag = float(np.hypot(image_w, image_h))
    best_i, best_score, scores = 0, -1e9, []
    for i, d in enumerate(detections):
        box = list(map(float, d["box_xyxy"]))
        center = np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])
        area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
        conf = float(d["confidence"])
        score = 0.0

        if prev_track is not None:
            iou = bbox_iou(box, prev_track["box"])
            cdist = float(np.linalg.norm(center - prev_track["center"])) / diag
            sig, w = pose_signature(d["keypoints_xy"], d["keypoints_conf"])
            prev_sig = prev_track.get("sig")
            if prev_sig is not None and sig.shape == prev_sig.shape:
                pdist = float(np.mean(np.linalg.norm(sig - prev_sig, axis=1)))
                pdist = min(pdist / 3.0, 1.0)
            else:
                pdist = 1.0
            # continuity dominates; confidence is only a weak tie-breaker
            score = 3.0 * iou - 2.5 * cdist - 1.5 * pdist + 0.3 * conf
        else:
            # first frame: prefer larger, more confident, more central person
            score = area / (image_w * image_h + 1e-9) + 0.2 * conf
        scores.append(score)
        if score > best_score:
            best_score, best_i = score, i

    d = detections[best_i]
    box = list(map(float, d["box_xyxy"]))
    center = np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])
    sig, w = pose_signature(d["keypoints_xy"], d["keypoints_conf"])
    track = {"box": box, "center": center, "sig": sig, "w": w,
             "conf": float(d["confidence"]), "miss": 0}
    info = {"reason": "multi_detection", "n_candidates": n,
            "chosen_score": round(best_score, 4),
            "score_margin": round(best_score - sorted(scores, reverse=True)[1], 4)}
    return best_i, track, info
