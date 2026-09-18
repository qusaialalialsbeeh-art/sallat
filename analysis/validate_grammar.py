"""Validate that the grammar derived from the references reproduces both files.

Read-only. Confirms the transition graph and canonical sequences match the
hand-corrected Ground Truth exactly, so predictions can be constrained later.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prayer_grammar as g  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def segments(path):
    items = json.load(open(path, encoding="utf-8"))["items"]
    items.sort(key=lambda it: it["attr"]["frame"])
    segs = []
    for it in items:
        lab = it["annotations"][0]["attributes"].get("salaa-fagir")
        if segs and segs[-1] == lab:
            continue
        segs.append(lab)
    return segs


def main():
    ok = True
    for name, n_rakah in (("fajr", 2), ("maghrib", 3)):
        ref = segments(os.path.join(ROOT, name + ".json"))
        expected = g.build_expected_sequence(n_rakah)
        match = ref == expected
        ok &= match
        print("=" * 70)
        print("%s.json : %d segments, %d-rakah canonical sequence" %
              (name, len(ref), n_rakah))
        print("  grammar reproduces reference sequence exactly:", match)
        if not match:
            print("  --- reference (%d) ---" % len(ref))
            for x in ref:
                print("     ", x)
            print("  --- grammar (%d) ---" % len(expected))
            for x in expected:
                print("     ", x)

        # every observed transition must be legal in the graph
        illegal = [(a, b) for a, b in zip(ref, ref[1:]) if not g.is_legal(a, b)]
        print("  observed transitions illegal under graph:", illegal)
        ok &= not illegal

    print("=" * 70)
    print("TRANSITION GRAPH: %d legal pairs (incl. self-loops)" % len(g.TRANSITION_GRAPH))
    print("ALL CHECKS PASSED:", ok)


if __name__ == "__main__":
    main()
