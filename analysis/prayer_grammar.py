"""Prayer temporal-state grammar, derived ONLY from the reference files.

This module encodes the observed label vocabulary, the rak'ah-level cycle, and
the legal successor relations. It is the interpretable backbone of the temporal
labeler: the model predicts a state, the grammar rejects impossible jumps.

Nothing here is a frame-number template. Only ordering/topology is encoded.
"""
import re

# --- Rak'ah-cycle templates, in observed order (rak'ah number substituted) ---
# Derived from fajr.json / maghrib.json segment listings.
CYCLE_CORE = [
    "القيام-الركعة {r}",
    "انحناء للركوع - الركعة {r}",
    "ركوع - الركعة {r}",
    "الرفع من الركوع - الركعة {r}",
    "اعتدال-الركعة {r}",
    "نزول للسجود - الركعة {r}",
    "سجود أول - الركعة {r}",
    "الرفع من السجود - الركعة {r}",
    "جلسة بين السجدتين - الركعة {r}",
    "نزول للسجدة الثانية - الركعة {r}",
    "سجود ثاني - الركعة {r}",
]

OPENING = "رفع اليدين لتكبيرة الإحرام"
# Exit from a rak'ah's second prostration, when the Prayer continues standing:
# observed only for rak'ah 1 -> rak'ah 2 in both references.
STAND_TO_2ND = "النهوض من السجود الثاني إلى القيام -للركعة الثانية"
# Exit from a rak'ah's second prostration, when settling into a sitting:
# carries the rak'ah it ENDS (الثانية / الثالثة), never الأولى.
RISE_2ND = "الرفع من السجود الثاني-الركعة {r}"
STAND_TO_3RD = "النهوض للقيام-الركعة الثالثة"
TASHahhud_1 = "الجلوس للتشهد الأول"
TASHahhud_LAST = "الجلوس للتشهد الأخير"
TASLEEM = "التسليم"

RAKAH_ORDINALS = {1: "الأولى", 2: "الثانية", 3: "الثالثة"}
ORDINAL_NUM = {v: k for k, v in RAKAH_ORDINALS.items()}

_RAKAH_RE = re.compile(r"الركعة (الأولى|الثانية|الثالثة)")


def rakah_of(label):
    m = _RAKAH_RE.search(label or "")
    return ORDINAL_NUM.get(m.group(1)) if m else None


def skeleton(label):
    """Label with the rak'ah ordinal replaced by <R>."""
    return _RAKAH_RE.sub("الركعة <R>", label or "")


def full_cycle(rakah):
    return [s.format(r=RAKAH_ORDINALS[rakah]) for s in CYCLE_CORE]


def cycle_exit(rakah):
    return RISE_2ND.format(r=RAKAH_ORDINALS[rakah])


def build_expected_sequence(n_rakah):
    """Canonical state sequence for an n-rak'ah prayer, as observed in refs.

    fajr (2): opening, cycle1, STAND_TO_2ND, cycle2, exit2, tashahhud_last, tasleem
    maghrib (3): opening, cycle1, STAND_TO_2ND, cycle2, exit2, tashahhud_1,
                 STAND_TO_3RD, cycle3, exit3, tashahhud_last, tasleem
    """
    seq = [OPENING]
    for r in range(1, n_rakah + 1):
        seq.extend(full_cycle(r))
        if r == 1 and n_rakah >= 2:
            seq.append(STAND_TO_2ND)
        else:
            seq.append(cycle_exit(r))
            if r < n_rakah:
                seq.append(TASHahhud_1)
                seq.append(STAND_TO_3RD)
    seq.append(TASHahhud_LAST)
    seq.append(TASLEEM)
    return seq


def build_transition_graph():
    """Legal (prev -> next) label pairs, from the reference topologies."""
    graph = set()
    for n in (2, 3):
        seq = build_expected_sequence(n)
        for a, b in zip(seq, seq[1:]):
            graph.add((a, b))
    # Self-loops are always legal (a state persists across frames).
    for a in {x for pair in graph for x in pair}:
        graph.add((a, a))
    return graph


TRANSITION_GRAPH = build_transition_graph()


def is_legal(prev, nxt):
    return (prev, nxt) in TRANSITION_GRAPH
