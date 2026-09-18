"""Probe geometric separability of prayer states in the reference files.

Read-only. Shows that (a) the same pose recurs across rak'ah numbers, and
(b) transitional states overlap static states. This justifies the temporal
approach: history and movement direction are required, not a single frame.
"""
import json
import collections
import math
import statistics
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

KP = ["nose", "left_eye", "right_eye", "left_ear", "right_ear",
      "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
      "left_wrist", "right_wrist", "left_hip", "right_hip",
      "left_knee", "right_knee", "left_ankle", "right_ankle"]
IDX = {k: i for i, k in enumerate(KP)}


def probe_features(pts):
    def P(n):
        i = IDX[n]
        return pts[i * 3], pts[i * 3 + 1], pts[i * 3 + 2]

    ls, rs = P("left_shoulder"), P("right_shoulder")
    lh, rh = P("left_hip"), P("right_hip")
    la, ra = P("left_ankle"), P("right_ankle")
    sx, sy = (ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2
    hx, hy = (lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2
    ax, ay = (la[0] + ra[0]) / 2, (la[1] + ra[1]) / 2
    torso = math.hypot(sx - hx, sy - hy)
    angle = math.degrees(math.atan2(abs(sx - hx), abs(hy - sy) + 1e-6))
    hip_ratio = (ay - hy) / (torso + 1e-6)
    return angle, hip_ratio


def main():
    summary = {}
    for name in ("fajr", "maghrib"):
        d = json.load(open(os.path.join(ROOT, name + ".json"), encoding="utf-8"))
        by_lab = collections.defaultdict(list)
        for it in d["items"]:
            a = it["annotations"][0]
            by_lab[a["attributes"]["salaa-fagir"]].append(probe_features(a["points"]))
        rows = {}
        print("=" * 96)
        print("GEOMETRIC PROBE:", name.upper())
        print("%-46s %6s %12s %14s" % ("label", "n", "torso_deg", "hip_ratio"))
        for lab, v in sorted(by_lab.items(), key=lambda x: -len(x[1])):
            ang = statistics.median(t[0] for t in v)
            hip = statistics.median(t[1] for t in v)
            rows[lab] = {"n": len(v), "torso_deg_median": round(ang, 1),
                         "hip_ratio_median": round(hip, 2)}
            print("%-46s %6d %12.1f %14.2f" % (lab, len(v), ang, hip))
        summary[name] = rows
        print()
    out = os.path.join(HERE, "feature_probe.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print("saved:", out)


if __name__ == "__main__":
    main()
