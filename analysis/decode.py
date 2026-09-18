"""Segmental decoder over the canonical prayer state sequence.

Decoding happens in SKELETON space (rak'ah-agnostic state names like
"سجود أول - الركعة <R>"), because pose geometry cannot distinguish rak'ah
numbers. The rak'ah number is then attached by position in the decoded
sequence, which is exactly the temporal-context reasoning required.

Aligning the whole video to the canonical ORDERED state list makes illegal
jumps structurally impossible, chooses the rak'ah count from temporal
evidence, and suppresses jitter via a minimum segment duration while still
allowing genuinely short transition states (skippable at a penalty, never
merged into neighbours).

dp[t][p] = best score when canonical state p covers frames [s..t] and states
0..p-1 cover [0..s-1] in order. Backtracking gives contiguous, gap-free output.
"""
import re

import numpy as np

ORDINALS = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة"}
NEG = -1e18
R = "<R>"

# Rak'ah-agnostic state names (as produced by the classifier).
S_QIYAM = "القيام-الركعة %s" % R
S_BEND = "انحناء للركوع - الركعة %s" % R
S_RUKU = "ركوع - الركعة %s" % R
S_RISE_RUKU = "الرفع من الركوع - الركعة %s" % R
S_ITIDAL = "اعتدال-الركعة %s" % R
S_DOWN = "نزول للسجود - الركعة %s" % R
S_SUJUD1 = "سجود أول - الركعة %s" % R
S_RISE_SUJUD = "الرفع من السجود - الركعة %s" % R
S_JALSA = "جلسة بين السجدتين - الركعة %s" % R
S_DOWN2 = "نزول للسجدة الثانية - الركعة %s" % R
S_SUJUD2 = "سجود ثاني - الركعة %s" % R

OPENING = "رفع اليدين لتكبيرة الإحرام"
STAND_2ND = "النهوض من السجود الثاني إلى القيام -للركعة الثانية"
TASH_FIRST = "الجلوس للتشهد الأول"
TASH_LAST = "الجلوس للتشهد الأخير"
TASLEEM = "التسليم"
RISE2_TMPL = "الرفع من السجود الثاني-الركعة %s" % R
STAND_3RD = "النهوض للقيام-الركعة %s" % R
# "rising to stand FOR rak'ah N" names the rak'ah being entered, so its <R>
# resolves against counter+1 rather than the current counter.
NEXT_RAKAH_STATES = {STAND_3RD}

CYCLE = [S_QIYAM, S_BEND, S_RUKU, S_RISE_RUKU, S_ITIDAL, S_DOWN, S_SUJUD1,
         S_RISE_SUJUD, S_JALSA, S_DOWN2, S_SUJUD2]

# Core postures must appear in every rak'ah: they are the structural anchors of
# the prayer and can never be skipped. Brief transitional states physically do
# occur but may be too short for the classifier to catch, so they are skippable
# at a modest cost rather than being forced.
CORE_STATES = {S_QIYAM, S_RUKU, S_ITIDAL, S_SUJUD1, S_JALSA, S_SUJUD2,
               TASH_FIRST, TASH_LAST, TASLEEM}
SKIPPABLE_COST = 12.0
CORE_SKIP_COST = 1e6


def state_skip_cost(label):
    return SKIPPABLE_COST if label not in CORE_STATES else CORE_SKIP_COST


def canonical_sequence(n_rakah):
    """Ordered skeleton-level state list for an n-rak'ah prayer."""
    seq = [OPENING]
    for r in range(1, n_rakah + 1):
        seq.extend(CYCLE)
        if r == 1:
            seq.append(STAND_2ND)
        else:
            seq.append(RISE2_TMPL)
            if r < n_rakah:
                seq.append(TASH_FIRST)
                seq.append(STAND_3RD)
    seq.append(TASH_LAST)
    seq.append(TASLEEM)
    return seq


def _sub_rakah(skel, rakah):
    return re.sub(re.escape(R), ORDINALS[rakah], skel)


def resolve_rakah_sequence(path_labels, n_rakah):
    """Attach rak'ah numbers from position in the decoded state sequence.

    The rak'ah counter advances exactly once per entry into a standing state
    (القيام), not once per frame: a standing pose persists for many frames and
    must not be counted repeatedly. This is purely temporal reasoning — the
    pose itself cannot reveal the rak'ah number.
    """
    out, counter, prev = [], 0, None
    for lab in path_labels:
        if lab == S_QIYAM and prev != S_QIYAM:
            counter = min(counter + 1, n_rakah)
        prev = lab
        if R in lab:
            r = counter + 1 if lab in NEXT_RAKAH_STATES else counter
            r = min(max(r, 1), n_rakah)
            out.append(_sub_rakah(lab, r))
        else:
            out.append(lab)
    return out


def decode_segmental(cols, states=None, min_len=6, skip_penalty=12.0,
                     state_penalty=2.0):
    """Optimal constrained segmentation into the ordered canonical states.

    Formulation. Let pre[s] = best score for states 0..p-1 covering frames
    [0..s-1] with state p-1 ending exactly at s-1, minus the cost of starting
    state p at frame s. Then

        dp[t][p] = csum[t+1][p] - csum[s][p] + pre[s] - state_penalty

    maximised over every s with s >= 1 and a segment length of at least
    min_len, i.e. s <= t - min_len + 1. A running maximum over s makes this
    O(N) per state instead of O(N^2).

    Skipping canonical state r (jumping from q to p > q+1) costs the skip price
    of each bypassed state. Core postures cost CORE_SKIP_COST, so they are
    effectively mandatory; only genuine transitional states may be skipped.

    Returns (path, segments, score); segments = [(start, end, state_index)].
    """
    N, P = cols.shape
    csum = np.zeros((N + 1, P))
    csum[1:] = np.cumsum(cols, axis=0)

    if states is not None:
        costs = np.array([state_skip_cost(s) for s in states])
    else:
        costs = np.full(P, skip_penalty)

    dp = np.full((N, P), NEG)
    bp_q = np.full((N, P), -1, dtype=np.int64)
    bp_s = np.full((N, P), -1, dtype=np.int64)

    # canonical state 0 may start at frame 0 (video could open mid-prayer)
    for t in range(min_len - 1, N):
        dp[t, 0] = csum[t + 1, 0] - state_penalty
        bp_s[t, 0] = 0

    # penalty[q, p] = total cost of the states skipped when jumping q -> p
    skip = np.zeros((P, P))
    for p in range(P):
        for q in range(p):
            skip[q, p] = costs[q + 1:p].sum() if p > q + 1 else 0.0

    for p in range(1, P):
        pre = np.full(N, NEG)
        pre_q = np.zeros(N, dtype=np.int64)
        if N > 1:
            s_ar = np.arange(1, N)
            cs_p = csum[s_ar, p]
            for q in range(p):
                cand = dp[s_ar - 1, q] - skip[q, p] - cs_p
                better = cand > pre[s_ar]
                pre[s_ar] = np.where(better, cand, pre[s_ar])
                pre_q[s_ar] = np.where(better, q, pre_q[s_ar])
        # running maximum of pre over s' <= s, tracking the argmax
        run = np.full(N, NEG)
        arg = np.full(N, -1, dtype=np.int64)
        cur, cur_arg = NEG, -1
        for s in range(N):
            if pre[s] > cur:
                cur, cur_arg = pre[s], s
            run[s], arg[s] = cur, cur_arg
        for t in range(min_len - 1, N):
            s_max = t - min_len + 1
            if s_max < 1:
                continue
            bs = arg[s_max]
            if bs < 1 or run[s_max] <= NEG / 2:
                continue
            dp[t, p] = csum[t + 1, p] + run[s_max] - state_penalty
            bp_q[t, p] = pre_q[bs]
            bp_s[t, p] = bs

    end_p = int(np.argmax(dp[N - 1]))
    score = float(dp[N - 1, end_p])
    segs = []
    p, t = end_p, N - 1
    while True:
        s = int(bp_s[t, p])
        if s < 0:
            s = 0
        segs.append((s, t, p))
        if p == 0 or int(bp_q[t, p]) < 0:
            break
        q = int(bp_q[t, p])
        t, p = s - 1, q
        if t < 0:
            break
    segs.reverse()

    path = np.zeros(N, dtype=np.int32)
    for (s, e, pi) in segs:
        path[s:e + 1] = pi
    return path, segs, score


def decode_best(M, index, candidate_counts=(2, 3, 4), anchors=None, **kw):
    """Try several rak'ah hypotheses on skeleton emissions; return the best.

    `anchors` is an optional list of (start0, end0) frame ranges (0-based,
    inclusive) where prostration is known to occur from the motion signal.
    Frames outside every anchored range cannot be assigned a sujud state, which
    resolves the otherwise-identical "sitting between the two sujuds" versus
    "sitting for tashahhud" ambiguity by sequence position.
    """
    results = []
    N = M.shape[0]
    for n in candidate_counts:
        states = canonical_sequence(n)
        if any(lab not in index for lab in states):
            continue
        cols = np.full((N, len(states)), -20.0)
        for j, lab in enumerate(states):
            cols[:, j] = M[:, index[lab]]
        if anchors:
            mask = np.zeros(N, dtype=bool)
            for (a, b) in anchors:
                a2, b2 = max(0, a), min(N - 1, b)
                if b2 >= a2:
                    mask[a2:b2 + 1] = True
            for j, lab in enumerate(states):
                if lab.startswith("سجود"):
                    cols[~mask, j] = -1e6
        path, segs, score = decode_segmental(cols, states=states, **kw)
        results.append((score, n, states, path, segs))
    if not results:
        return None
    results.sort(key=lambda r: -r[0])
    best = results[0]
    return {"score": best[0], "n_rakah": best[1], "states": best[2],
            "path": best[3], "segments": best[4],
            "all_scores": [(round(s, 1), nn) for s, nn, *_ in results]}
