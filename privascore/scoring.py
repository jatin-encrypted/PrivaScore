"""Scoring engine: Privacy Risk Index and Disclosure Quality score from per-flag evidence states.

Both scores are transparent, rule-based indices on a 0-100 scale. They are NOT probabilities
that a company misuses data. Inputs are the five evidence states:
  ED explicitly disclosed, CD conditionally disclosed, EE explicitly excluded,
  NS not stated (Absent), UN unclear.

Privacy Risk Index (0 = lowest risk, 100 = highest)
  Each applicable flag i with weight w_i contributes risk points r_i = f(state) * w_i:
      state          exposure flag    governance / readiness flag
      ED             1.0              0.0   (protection clearly present)
      CD             0.5              0.5
      EE             0.0              1.0   (protection explicitly denied)
      UN             0.5              0.5   (review needed)
      NS             0.0              0.0   (silence is never scored as risk)
  Risk Index = 100 * sum(r_i) / sum(w_i)    over applicable flags with w_i > 0

Disclosure Quality (0 = says nothing usable, 100 = every flag addressed clearly)
  q(ED) = q(EE) = 2.0, q(CD) = 1.5, q(UN) = 0.5, q(NS) = 0.0
  Quality = 100 * sum(q_i) / (2.0 * n)       over applicable flags with w_i > 0 (unweighted)

Applicability
  - Flags with weight 0 (DPDP4, informational) are reported but excluded from both scores.
  - AI2 (training opt-out) applies only when AI1 is ED or CD. Otherwise it is excluded from
    both scores instead of counting as a silent 0 (the Gemini draft kept it in the
    denominator, which shrank every risk score of a policy that does not train on user data).

Why NS adds no risk: a policy that omits a topic must not look safer *or* riskier on the
practice itself; the omission is penalised in Disclosure Quality instead. Report both scores
together; a low Risk Index with low Quality means "says little", not "safe".

Changes from the formula in the earlier Gemini draft gold set:
  1. Scores are computed in code, never typed (12 of its 15 Quality scores and 8 of 15 Risk
     scores did not match its own formula).
  2. Unclear is 0.5 * w for every flag (the draft's G4 row said 1.0 * w, contradicting its
     own general table).
  3. AI2 not applicable -> excluded from both denominators (see above).
  4. Unrounded values are kept; rounding happens only for display.
"""
from dataclasses import dataclass, field
from itertools import combinations
from typing import Mapping

from .flags import STATES, Flag

EXPOSURE_RISK = {"ED": 1.0, "CD": 0.5, "EE": 0.0, "UN": 0.5, "NS": 0.0}
PROTECTIVE_RISK = {"ED": 0.0, "CD": 0.5, "EE": 1.0, "UN": 0.5, "NS": 0.0}
QUALITY_POINTS = {"ED": 2.0, "EE": 2.0, "CD": 1.5, "UN": 0.5, "NS": 0.0}
MAX_QUALITY_POINTS = 2.0
SCORING_VERSION = "1.0"


@dataclass
class FlagScore:
    flag: str
    state: str
    weight: float
    applicable: bool
    reason: str               # why not applicable, or "" when applicable
    risk_points: float        # r_i (0 when not applicable)
    max_risk_points: float    # w_i when applicable, else 0
    quality_points: float     # q_i (0 when not applicable)


@dataclass
class ScoreResult:
    risk_index: float                  # unrounded, 0-100
    disclosure_quality: float          # unrounded, 0-100
    risk_points: float
    max_risk_points: float
    quality_points: float
    max_quality_points: float
    n_applicable: int
    n_not_stated: int
    per_flag: list = field(default_factory=list)
    version: str = SCORING_VERSION

    @property
    def risk_index_display(self) -> int:
        return round_half_up(self.risk_index)

    @property
    def disclosure_quality_display(self) -> int:
        return round_half_up(self.disclosure_quality)

    def to_dict(self):
        return {
            "scoring_version": self.version,
            "risk_index": round(self.risk_index, 4), "risk_index_display": self.risk_index_display,
            "disclosure_quality": round(self.disclosure_quality, 4),
            "disclosure_quality_display": self.disclosure_quality_display,
            "risk_points": self.risk_points, "max_risk_points": self.max_risk_points,
            "quality_points": self.quality_points, "max_quality_points": self.max_quality_points,
            "n_applicable": self.n_applicable, "n_not_stated": self.n_not_stated,
            "per_flag": [vars(f) for f in self.per_flag],
        }


def round_half_up(x: float) -> int:
    """Python's round() uses banker's rounding (round(42.5) == 42); display uses half-up."""
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def applicability(flag_id: str, states: Mapping[str, str]):
    if flag_id == "AI2":
        ai1 = states.get("AI1")
        if ai1 not in ("ED", "CD"):
            return False, f"not applicable: AI1={ai1}"
    return True, ""


def score(states: Mapping[str, str], flags: list, weights: Mapping[str, float] | None = None) -> ScoreResult:
    """Score one policy.

    states  : {flag_id: "ED"|"CD"|"EE"|"NS"|"UN"} for every flag in `flags`
    flags   : list of Flag (see privascore.flags.load_flags)
    weights : optional override {flag_id: weight}, used for sensitivity analysis
    """
    missing = [f.id for f in flags if f.id not in states]
    if missing:
        raise ValueError(f"missing states for flags: {missing}")
    bad = {k: v for k, v in states.items() if v not in STATES}
    if bad:
        raise ValueError(f"invalid states (allowed {STATES}): {bad}")

    per_flag, risk, max_risk, qual, n_app, n_ns = [], 0.0, 0.0, 0.0, 0, 0
    for f in flags:
        w = float(weights[f.id]) if weights and f.id in weights else f.weight
        st = states[f.id]
        ok, reason = applicability(f.id, states)
        if ok and w <= 0:
            ok, reason = False, "informational flag (weight 0)"
        if not ok:
            per_flag.append(FlagScore(f.id, st, w, False, reason, 0.0, 0.0, 0.0))
            continue
        table = PROTECTIVE_RISK if f.protective else EXPOSURE_RISK
        r = table[st] * w
        q = QUALITY_POINTS[st]
        per_flag.append(FlagScore(f.id, st, w, True, "", r, w, q))
        risk += r
        max_risk += w
        qual += q
        n_app += 1
        n_ns += st == "NS"
    max_q = MAX_QUALITY_POINTS * n_app
    return ScoreResult(
        risk_index=100.0 * risk / max_risk if max_risk else 0.0,
        disclosure_quality=100.0 * qual / max_q if max_q else 0.0,
        risk_points=risk, max_risk_points=max_risk, quality_points=qual, max_quality_points=max_q,
        n_applicable=n_app, n_not_stated=n_ns, per_flag=per_flag)


# ---------------------------------------------------------------- sensitivity analysis

def weight_sensitivity(states: Mapping[str, str], flags: list, delta: float = 1.0):
    """Risk Index when each scored flag's weight is moved by +/- delta (floor 0), one at a time,
    plus the equal-weights variant. Answers the viva question "what if your weights are wrong?"."""
    base = score(states, flags).risk_index
    rows = []
    for f in flags:
        if f.weight <= 0:
            continue
        for d in (-delta, +delta):
            w = max(0.0, f.weight + d)
            rows.append({"flag": f.id, "weight": w, "risk_index": score(states, flags, {f.id: w}).risk_index})
    equal = score(states, flags, {f.id: 1.0 for f in flags if f.weight > 0}).risk_index
    values = [r["risk_index"] for r in rows] + [base]
    return {"base": base, "min": min(values), "max": max(values), "equal_weights": equal, "variants": rows}


def kendall_tau(xs, ys) -> float:
    """Kendall's tau-b between two equal-length score lists (rank agreement, -1..1)."""
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("need two equal-length lists with at least 2 items")
    conc = disc = tx = ty = 0
    for i, j in combinations(range(len(xs)), 2):
        dx, dy = xs[i] - xs[j], ys[i] - ys[j]
        if dx == 0 and dy == 0:
            continue
        if dx == 0:
            tx += 1
        elif dy == 0:
            ty += 1
        elif (dx > 0) == (dy > 0):
            conc += 1
        else:
            disc += 1
    denom = ((conc + disc + tx) * (conc + disc + ty)) ** 0.5
    return (conc - disc) / denom if denom else 0.0


def ranking_stability(policy_states: Mapping[str, Mapping[str, str]], flags: list, delta: float = 1.0):
    """For a set of policies: Kendall tau between the base ranking and the ranking under each
    single-weight perturbation and under equal weights. Values near 1 mean the ranking of
    policies does not depend on the exact weights."""
    ids = sorted(policy_states)
    base = [score(policy_states[p], flags).risk_index for p in ids]
    out = []
    for f in flags:
        if f.weight <= 0:
            continue
        for d in (-delta, +delta):
            w = {f.id: max(0.0, f.weight + d)}
            alt = [score(policy_states[p], flags, w).risk_index for p in ids]
            out.append({"flag": f.id, "weight": w[f.id], "kendall_tau": kendall_tau(base, alt)})
    eq = {f.id: 1.0 for f in flags if f.weight > 0}
    equal_tau = kendall_tau(base, [score(policy_states[p], flags, eq).risk_index for p in ids])
    taus = [o["kendall_tau"] for o in out]
    return {"policies": ids, "min_tau": min(taus), "equal_weights_tau": equal_tau, "variants": out}


def states_from_labels(labels: list, policy_id: str) -> dict:
    """{flag: state} for one policy from validate_labels.py resolved output (or extractor output)."""
    return {x["flag"]: x["state"] for x in labels if x["policy_id"] == policy_id}


def flags_ids(flags: list[Flag]):
    return [f.id for f in flags]
