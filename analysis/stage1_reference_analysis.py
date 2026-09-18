"""Stage 1: Reference analysis of fajr.json and maghrib.json.

Read-only. Inspects structure, label vocabulary, temporal segments, transitions,
and data quality. No predictions are produced and Label Studio is not contacted.
"""
import json
import collections
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FILES = {
    "fajr": os.path.join(ROOT, "fajr.json"),
    "maghrib": os.path.join(ROOT, "maghrib.json"),
}

KP = ["nose", "left_eye", "right_eye", "left_ear", "right_ear",
      "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
      "left_wrist", "right_wrist", "left_hip", "right_hip",
      "left_knee", "right_knee", "left_ankle", "right_ankle"]


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def frame_number(item):
    return item["attr"].get("frame")


def label_of(item):
    """First annotation label; for duplicate annotations we verify agreement."""
    anns = item["annotations"]
    if not anns:
        return None
    labels = {a["attributes"].get("salaa-fagir") for a in anns}
    return anns[0]["attributes"].get("salaa-fagir") if len(labels) == 1 else None


def build_segments(items):
    """Contiguous runs of identical labels, ordered by frame number."""
    ordered = sorted(items, key=frame_number)
    segs = []
    for it in ordered:
        fr = frame_number(it)
        lab = label_of(it)
        if segs and segs[-1]["label"] == lab:
            segs[-1]["end"] = fr
            segs[-1]["n_frames"] += 1
        else:
            segs.append({"label": lab, "start": fr, "end": fr, "n_frames": 1})
    return segs


def analyze(name, path):
    d = load(path)
    items = d["items"]
    report = {"name": name, "path": os.path.basename(path), "n_items": len(items)}

    keysets = collections.Counter(tuple(sorted(it.keys())) for it in items)
    report["item_keysets"] = {" | ".join(k): v for k, v in keysets.items()}

    frames = [frame_number(it) for it in items]
    report["frame_min"] = min(frames)
    report["frame_max"] = max(frames)
    report["frame_unique"] = len(set(frames))
    report["frames_contiguous_from_zero"] = frames == list(range(len(frames)))
    report["frames_sorted"] = frames == sorted(frames)

    sizes = collections.Counter(tuple(it["image"]["size"]) for it in items)
    report["image_sizes"] = {"x".join(str(v) for v in k): c for k, c in sizes.items()}
    # CVAT stores image size as [height, width]; confirmed against coordinate extents.
    report["size_interpretation"] = "height,width (CVAT convention)"

    ann_counts = collections.Counter(len(it["annotations"]) for it in items)
    report["annotations_per_item"] = {str(k): v for k, v in ann_counts.items()}

    dups = [it for it in items if len(it["annotations"]) != 1]
    dup_report = {"n_frames": len(dups), "frames": sorted(frame_number(it) for it in dups),
                  "identical": 0, "differing": 0, "label_conflicts": 0}
    for it in dups:
        anns = it["annotations"]
        pairs_ok = all(a["points"] == anns[0]["points"] for a in anns)
        labels = {a["attributes"].get("salaa-fagir") for a in anns}
        if len(labels) > 1:
            dup_report["label_conflicts"] += 1
        dup_report["identical" if pairs_ok else "differing"] += 1
    report["duplicate_annotations"] = dup_report

    lab_counter = collections.Counter()
    for it in items:
        for a in it["annotations"]:
            lab_counter[a["attributes"].get("salaa-fagir")] += 1
    report["labels"] = lab_counter.most_common()

    akeys = collections.Counter()
    for it in items:
        for a in it["annotations"]:
            akeys[tuple(sorted(a["attributes"].keys()))] += 1
    report["attribute_keys"] = {" | ".join(k): v for k, v in akeys.items()}

    plen = collections.Counter(len(a["points"]) for it in items for a in it["annotations"])
    report["points_array_lengths"] = {str(k): v for k, v in plen.items()}

    pa_keys = collections.Counter()
    for it in items:
        for a in it["annotations"]:
            for pa in a.get("points_attributes", []):
                pa_keys[tuple(sorted(pa.keys()))] += 1
    report["point_attribute_keys"] = {" | ".join(k): v for k, v in pa_keys.items()}

    segs = build_segments(items)
    report["segments"] = segs
    report["n_segments"] = len(segs)

    # duration statistics per label (purely descriptive; NOT a timing template)
    durs = collections.defaultdict(list)
    for s in segs:
        durs[s["label"]].append(s["n_frames"])
    report["segment_duration_stats"] = {
        lab: {"count": len(v), "min": min(v), "max": max(v),
              "mean": round(sum(v) / len(v), 1)}
        for lab, v in sorted(durs.items())
    }
    report["label_appears_as_segment"] = len(durs)

    # rapid label flips (instability indicator)
    labs = [label_of(it) for it in sorted(items, key=frame_number)]
    report["label_flips"] = sum(1 for i in range(1, len(labs)) if labs[i] != labs[i - 1])
    report["min_segment_frames"] = min(s["n_frames"] for s in segs)

    trans = collections.Counter()
    for a, b in zip(segs, segs[1:]):
        trans[(a["label"], b["label"])] += 1
    report["transitions"] = {"%s -> %s" % (a, b): c for (a, b), c in trans.items()}

    vis_counter = collections.Counter()
    missing_counter = 0
    per_kp_low = collections.Counter()
    coords_out_of_bounds = 0
    for it in items:
        h, w = it["image"]["size"]  # CVAT convention: [height, width]
        for a in it["annotations"]:
            pts = a["points"]
            for i in range(17):
                x, y, v = pts[i * 3], pts[i * 3 + 1], pts[i * 3 + 2]
                vis_counter[v] += 1
                if x == 0 and y == 0:
                    missing_counter += 1
                if v == 0:
                    per_kp_low[KP[i]] += 1
                if x < 0 or y < 0 or x > w or y > h:
                    coords_out_of_bounds += 1
    report["visibility_distribution"] = dict(vis_counter)
    report["missing_xy_count"] = missing_counter
    report["coords_out_of_bounds"] = coords_out_of_bounds
    report["low_visibility_by_keypoint"] = per_kp_low.most_common()

    paths = collections.Counter(it["image"]["path"].split("/")[0] for it in items)
    report["image_path_prefixes"] = dict(paths)
    report["sample_image_path"] = items[0]["image"]["path"]
    report["sample_item_id"] = items[0]["id"]

    # occluded flag
    occ = collections.Counter()
    kf = collections.Counter()
    for it in items:
        for a in it["annotations"]:
            occ[a["attributes"].get("occluded")] += 1
            kf[a["attributes"].get("keyframe")] += 1
    report["occluded_flag"] = dict(occ)
    report["keyframe_flag"] = dict(kf)

    return report


def print_report(r):
    print("=" * 78)
    print("REFERENCE ANALYSIS:", r["name"].upper(), "(", r["path"], ")")
    print("=" * 78)
    print("items (frames):", r["n_items"])
    print("frame range:", r["frame_min"], "->", r["frame_max"],
          "| unique:", r["frame_unique"],
          "| contiguous from 0:", r["frames_contiguous_from_zero"],
          "| sorted:", r["frames_sorted"])
    print("image sizes:", r["image_sizes"])
    print("annotations per item:", r["annotations_per_item"])
    print("item key-sets:", r["item_keysets"])
    print("attribute keys:", r["attribute_keys"])
    print("points array lengths:", r["points_array_lengths"])
    print("point attribute keys:", r["point_attribute_keys"])
    print("image size interpretation:", r["size_interpretation"])
    print("duplicate-annotation frames:", r["duplicate_annotations"])
    print("occluded flag:", r["occluded_flag"], "| keyframe flag:", r["keyframe_flag"])
    print("label flips:", r["label_flips"], "| segments:", r["n_segments"],
          "| distinct labels used as segments:", r["label_appears_as_segment"],
          "| min segment:", r["min_segment_frames"], "frames")
    print()
    print("LABEL VOCABULARY (label -> frame count):")
    for lab, c in r["labels"]:
        print("   %-42s %6d" % (lab, c))
    print()
    print("VISIBILITY DISTRIBUTION (0=absent,1=occluded,2=visible):",
          r["visibility_distribution"])
    print("missing (x==0 and y==0) keypoint readings:", r["missing_xy_count"])
    print("coords out of image bounds:", r["coords_out_of_bounds"])
    print("low-visibility (v==0) by keypoint (top):")
    for kp, c in r["low_visibility_by_keypoint"][:8]:
        print("   %-18s %6d" % (kp, c))
    print()
    print("SEGMENTS (ordered, %d):" % len(r["segments"]))
    print("   %-4s %-42s %8s %8s %8s" % ("#", "label", "start", "end", "frames"))
    for i, s in enumerate(r["segments"]):
        print("   %-4d %-42s %8s %8s %8d" %
              (i, s["label"], s["start"], s["end"], s["n_frames"]))
    print()
    print("TRANSITIONS (from -> to : count):")
    for k, c in sorted(r["transitions"].items()):
        print("   %-70s : %d" % (k, c))
    print()


def main():
    reports = {}
    for name, path in FILES.items():
        reports[name] = analyze(name, path)
        print_report(reports[name])
    out = os.path.join(HERE, "reference_analysis.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(reports, fh, ensure_ascii=False, indent=2)
    print("saved:", out)


if __name__ == "__main__":
    main()
