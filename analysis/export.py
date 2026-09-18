"""Produce the final Stage-2 labeling artifacts for the new video.

Writes, next to this script:
  * segments.json   - contiguous labeled segments with frames, label, confidence
  * inferences.txt  - human-readable report, including uncertain boundaries
  * labelstudio_payload.json - ready-to-POST result items (no credentials)

Run with --report to also print a summary to stdout.
"""
import json
import os
import sys

import numpy as np

import decode as DC
import pipeline as PL

HERE = os.path.dirname(os.path.abspath(__file__))

# a boundary between two segments is "uncertain" when either side sits below
UNCERTAIN_CONF = 0.55


def uncertainty_ranges(segments, conf, path, states, window=15):
    """Frame bands around decoded boundaries where the choice is genuinely weak.

    We judge each boundary by the MEAN confidence in a narrow band straddling
    it. A short transition can dip briefly without the boundary really being in
    doubt, so a mean over the band is a better signal than a single minimum.
    Reported ranges are for human review only; they do not change the labels.
    """
    out = []
    for s in segments[1:]:
        a = s["start_i"]
        lo, hi = max(0, a - window), min(len(conf) - 1, a + window)
        band = float(np.mean(conf[lo:hi + 1]))
        if band < UNCERTAIN_CONF:
            out.append((lo, hi, band))
    # merge bands that touch or overlap
    merged = []
    for (lo, hi, band) in out:
        if merged and lo <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi),
                          min(merged[-1][2], band))
        else:
            merged.append((lo, hi, band))
    return merged


def main():
    out = PL.run(verbose=True)
    segs = out["segments"]
    video = out["video"]
    res = out["res"]
    conf = out["conf"]

    metas = video["meta"]
    ranges = uncertainty_ranges(segs, conf, res["path"], res["states"])
    for s in segs:
        s["start_frame"] = metas[s["start_i"]]["num"]
        s["end_frame"] = metas[s["end_i"]]["num"]
        del s["start_i"], s["end_i"]

    uncertain = []
    for (a, b, band) in ranges:
        uncertain.append({
            "start_frame": metas[a]["num"],
            "end_frame": metas[b]["num"],
            "mean_confidence": float(band),
        })

    with open(os.path.join(HERE, "segments.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "n_rakah": out["n_rakah"],
            "total_frames": len(segs) and metas[-1]["num"],
            "sujud_episodes": [
                {"start_frame": a, "end_frame": b, "length": l}
                for (a, b, l) in out["sujud"]],
            "segments": segs,
            "uncertain_boundaries": uncertain,
        }, fh, ensure_ascii=False, indent=2)

    from labelstudio import build_timeline_result
    payload = build_timeline_result(segs, "temporal", "video")
    with open(os.path.join(HERE, "labelstudio_payload.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    lines = []
    lines.append("TEMPORAL LABELING RESULT - NEW VIDEO")
    lines.append("=" * 70)
    lines.append("frames: %d   rak'ahs: %d   segments: %d"
                 % (metas[-1]["num"], out["n_rakah"], len(segs)))
    lines.append("sujud episodes: %d" % len(out["sujud"]))
    lines.append("")
    lines.append("%-12s %-12s %-46s %s" %
                 ("start", "end", "label", "conf"))
    for s in segs:
        lines.append("%-12d %-12d %-46s %.2f" %
                     (s["start_frame"], s["end_frame"], s["label"],
                      s["confidence"]))
    lines.append("")
    lines.append("UNCERTAIN BOUNDARIES (review manually)")
    for u in uncertain:
        lines.append("  boundary approximately frames %d-%d (conf %.2f)"
                     % (u["start_frame"], u["end_frame"], u["mean_confidence"]))
    with open(os.path.join(HERE, "inferences.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\nwrote segments.json, inferences.txt, labelstudio_payload.json")
    print("uncertain ranges:", len(uncertain))


if __name__ == "__main__":
    main()
