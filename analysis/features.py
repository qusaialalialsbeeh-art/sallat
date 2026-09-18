"""Pose feature extraction: interpretable, scale/translation invariant features.

Shared by reference training and new-video inference so both see identical
representation. Nothing here depends on absolute frame numbers or image size.
"""
import numpy as np

# COCO-17 order (identical in CVAT reference export and YOLO output).
KP_NAMES = ["nose", "left_eye", "right_eye", "left_ear", "right_ear",
            "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
            "left_wrist", "right_wrist", "left_hip", "right_hip",
            "left_knee", "right_knee", "left_ankle", "right_ankle"]
KI = {n: i for i, n in enumerate(KP_NAMES)}

NOSE, LEYE, REYE, LEAR, REAR, LSHO, RSHO, LELB, RELB, LWRI, RWRI, \
    LHIP, RHIP, LKNE, RKNE, LANK, RANK = range(17)

# Body joints that actually matter for prayer posture (face/ears are often
# occluded and must NEVER drive uncertainty on their own).
CORE_JOINTS = [LSHO, RSHO, LELB, RELB, LWRI, RWRI, LHIP, RHIP,
               LKNE, RKNE, LANK, RANK]


def _angle(a, b, c):
    """Angle at b, in degrees, between rays b->a and b->c."""
    v1 = a - b
    v2 = c - b
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return np.nan
    cosv = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosv)))


def extract_frame_features(kps_xy, kps_conf):
    """Geometric features for a single frame, robust to position and scale.

    kps_xy: (17,2) floats, image pixel coords.
    kps_conf: (17,) floats in [0,1].
    Returns dict of named scalar features (may contain NaN).
    """
    p = np.asarray(kps_xy, dtype=np.float64)
    c = np.asarray(kps_conf, dtype=np.float64)
    f = {}

    # --- visibility / confidence aggregation over BODY joints only ---
    f["conf_core_mean"] = float(np.mean(c[CORE_JOINTS]))
    f["conf_core_min"] = float(np.min(c[CORE_JOINTS]))
    f["conf_torso_mean"] = float(np.mean(c[[LSHO, RSHO, LHIP, RHIP]]))
    f["conf_legs_mean"] = float(np.mean(c[[LKNE, RKNE, LANK, RANK]]))

    # --- normalization frame: hip centre (root) + torso scale ---
    sho_c = (p[LSHO] + p[RSHO]) / 2.0
    hip_c = (p[LHIP] + p[RHIP]) / 2.0
    ank_c = (p[LANK] + p[RANK]) / 2.0
    kne_c = (p[LKNE] + p[RKNE]) / 2.0
    root = hip_c
    torso_vec = sho_c - hip_c
    torso_len = float(np.linalg.norm(torso_vec))
    if torso_len < 1e-3:
        torso_len = np.nan
    f["torso_len"] = torso_len

    # --- torso orientation relative to image vertical (0 = upright) ---
    if not np.isnan(torso_len):
        f["torso_tilt_deg"] = float(np.degrees(
            np.arctan2(abs(torso_vec[0]), abs(torso_vec[1]) + 1e-9)))
        # signed tilt: direction of lean, discriminates motion direction
        f["torso_tilt_signed"] = float(np.degrees(
            np.arctan2(torso_vec[0], abs(torso_vec[1]) + 1e-9)))
    else:
        f["torso_tilt_deg"] = np.nan
        f["torso_tilt_signed"] = np.nan

    # --- vertical ratios (normalized by torso length => body-scale free) ---
    if not np.isnan(torso_len):
        f["hip_above_ankle"] = float((ank_c[1] - hip_c[1]) / torso_len)
        f["knee_above_ankle"] = float((ank_c[1] - kne_c[1]) / torso_len)
        f["shoulder_above_ankle"] = float((ank_c[1] - sho_c[1]) / torso_len)
        f["hip_to_knee"] = float(np.linalg.norm(hip_c - kne_c) / torso_len)
        f["knee_to_ankle"] = float(np.linalg.norm(kne_c - ank_c) / torso_len)
        f["shoulder_hip_ratio"] = float(
            np.linalg.norm(sho_c - hip_c) / torso_len)
        # shoulder width also normalized (scale-free)
        f["shoulder_width"] = float(
            np.linalg.norm(p[LSHO] - p[RSHO]) / torso_len)
        f["hip_width"] = float(np.linalg.norm(p[LHIP] - p[RHIP]) / torso_len)
        # ankle-cantered body extent (proxy for standing vs prostrating)
        f["body_height"] = float(
            (ank_c[1] - min(p[NOSE, 1], sho_c[1])) / torso_len)

    # --- relative coordinates of key joints wrt root, scale-normalized ---
    if not np.isnan(torso_len):
        for idx, nm in [(NOSE, "nose"), (LSHO, "lsho"), (RSHO, "rsho"),
                        (LELB, "lelb"), (RELB, "relb"), (LWRI, "lwri"),
                        (RWRI, "rwri"), (LKNE, "lkne"), (RKNE, "rkne"),
                        (LANK, "lank"), (RANK, "rank")]:
            rel = (p[idx] - root) / torso_len
            f["rel_%s_y" % nm] = float(rel[1])
            f["rel_%s_x" % nm] = float(rel[0])

    # --- joint angles (scale-free by construction) ---
    f["elbow_l"] = _angle(p[LSHO], p[LELB], p[LWRI])
    f["elbow_r"] = _angle(p[RSHO], p[RELB], p[RWRI])
    f["knee_l"] = _angle(p[LHIP], p[LKNE], p[LANK])
    f["knee_r"] = _angle(p[RHIP], p[RKNE], p[RANK])
    f["hip_l"] = _angle(p[LSHO], p[LHIP], p[LKNE])
    f["hip_r"] = _angle(p[RSHO], p[RHIP], p[RKNE])
    f["shoulder_l"] = _angle(p[LELB], p[LSHO], p[LHIP])
    f["shoulder_r"] = _angle(p[RELB], p[RSHO], p[RHIP])

    # --- wrist proximity to knees/head: very discriminative for sujud ---
    if not np.isnan(torso_len):
        f["wrist_knee_dist"] = float(min(
            np.linalg.norm(p[LWRI] - p[LKNE]), np.linalg.norm(p[RWRI] - p[RKNE])
        ) / torso_len)
        f["wrist_ankle_dist"] = float(min(
            np.linalg.norm(p[LWRI] - p[LANK]), np.linalg.norm(p[RWRI] - p[RANK])
        ) / torso_len)
        f["nose_ankle_dist"] = float(
            np.linalg.norm(p[NOSE] - ank_c) / torso_len)
        f["nose_hip_dist"] = float(np.linalg.norm(p[NOSE] - hip_c) / torso_len)
        # hip height above the lowest body point (sitting vs standing)
        lowest = float(np.max([ank_c[1], kne_c[1], hip_c[1], sho_c[1]]))
        f["hip_above_lowest"] = float((lowest - hip_c[1]) / torso_len)

    return f


def feature_names(sample):
    return sorted(sample.keys())


def to_matrix(feat_dicts, names):
    """Stack feature dicts into an (N, D) float array; NaN -> 0."""
    X = np.full((len(feat_dicts), len(names)), np.nan, dtype=np.float64)
    for i, fd in enumerate(feat_dicts):
        for j, n in enumerate(names):
            v = fd.get(n, np.nan)
            X[i, j] = v if v is not None else np.nan
    return X


def add_temporal_features(X, window=7):
    """Append causal velocity/acceleration + short-window displacement.

    Uses only past & current frames (causal) so inference never peeks ahead.
    """
    N, D = X.shape
    Xc = np.nan_to_num(X, nan=0.0)
    feats = [Xc]
    for w in (1, 3, window):
        d = np.zeros_like(Xc)
        if N > w:
            d[w:] = Xc[w:] - Xc[:-w]
        feats.append(d)
    # acceleration at lag 1
    acc = np.zeros_like(Xc)
    if N > 1:
        vel = Xc[1:] - Xc[:-1]
        acc[2:] = vel[1:] - vel[:-1]
    feats.append(acc)
    # short-window mean displacement direction magnitude over window
    w = max(2, window)
    disp = np.zeros_like(Xc)
    if N > w:
        disp[w:] = (Xc[w:] - Xc[:-w])
    feats.append(disp)
    return np.concatenate(feats, axis=1)
