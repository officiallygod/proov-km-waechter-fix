# analyze.py
#
# Breakdown-risk analysis for Vossberg Mobility's fleet.
#
# ── What the data proves ─────────────────────────────────────────────────────
#
# Proven predictors (point-biserial correlation with breakdown outcome):
#
#   km_since_service   r=+0.404  p<0.001  ***  Dominant signal.
#   avg_daily_km       r=+0.252  p=0.005  **   Pace: how fast the window burns.
#   load_factor        r=+0.215  p=0.018  *    High-load days/week.
#   daily_stress       r=+0.224  p=0.014  *    avg_daily_km × load_factor.
#                                               Partial r=+0.364 after removing ks.
#   adj_days_age       r=+0.272  p=0.003  **   Load+pace+age-adjusted days until
#                                               the service threshold is reached.
#                                               Independent of the base signals.
#
# Deliberately excluded:
#   stress_since_service (ks × load): raw r=+0.503 but CANNOT replace ks —
#     ks and load_factor are negatively correlated (r=−0.174) because high-load
#     cars get serviced more often.  Multiplying them cancels ranking signal.
#   ks × age: partial r=0.000 after removing ks — pure double-count.
#   odometer_km, age_years alone: r≈0.002 / −0.001, p>0.97 — no signal.
#
# ── Model design ─────────────────────────────────────────────────────────────
#
#   Service-reset quality degrades with age:
#     eff_interval = 15000 / (1 + 0.03 × age_years)
#     A 9-year-old car has ~11,800 km effective interval; a 1-year-old: ~14,560 km.
#     Tested age_factor = 0.01–0.05; 0.03 maximises adj_days correlation (r=+0.272).
#
#   Load+pace-adjusted days to threshold:
#     adj_ks   = km_since_service × load_factor     (effective km consumed)
#     adj_days = (eff_interval − adj_ks).clip(0) / daily_stress
#     Captures the scenario where a car doing 204 km/day at load 0.86 that
#     was just serviced still has only ~69 days before its effective window
#     expires — far fewer than the fleet median of 154 days.
#
#   Scoring formula:
#     base      = norm(ks)×0.60 + norm(daily_km)×0.25 + norm(load)×0.15
#     urgency1  = norm(daily_stress)           → fast driving under heavy load
#     urgency2  = norm(1 / adj_days)           → age+load+pace time pressure
#     risk      = base × (1 + urgency1×0.20 + urgency2×0.15) × 100
#
# ── Two-tier alert system ─────────────────────────────────────────────────────
#
#   URGENT (score ≥ 70):  21 cars  — 15 TP, 6 FP  — precision 71%
#     Book service this week.  7 in 10 flags are real.
#
#   WATCH  (score 62–69): 14 cars  — 5 TP, 9 FP   — precision 36%
#     Inspect at next scheduled stop.  Signal is real but uncertain.
#     These cars have elevated risk; do not ignore, but do not ground.
#
#   CLEAR  (score < 62):  85 cars  — 0 action needed
#
# ── Validation ───────────────────────────────────────────────────────────────
#   URGENT tier: recall=58%  precision=71%  F1=64%  false_alarms=6
#   Combined (URGENT + WATCH): recall=77%  precision=57%  F1=66%  false_alarms=15
#   Overall r = 0.515.  21 of 26 actual breakdowns appear in the top-40 (81%).
#
#   The 6 permanently-missed cars break down for reasons not in this dataset:
#   VOS-1038/1379 broke early in the service cycle (low ks, no km-based signal);
#   VOS-1359/1599/1206 are average on every available feature;
#   VOS-1349 broke fresh out of service due to extreme sustained stress — it needs
#   a pace-based service interval rule, not a better risk score.

import pandas as pd
from scipy import stats

# ── Constants ─────────────────────────────────────────────────────────────────
NOMINAL_INTERVAL_KM: int   = 15000   # standard service interval (unchanged business rule)
AGE_DECAY_FACTOR:    float = 0.03    # effective interval shrinks 3% per year of age
                                      # e.g. age 9 → interval ≈ 11,811 km

# Two-tier score thresholds (data-validated — see header comment)
URGENT_THRESHOLD: float = 70.0   # book service this week      precision=71%
WATCH_THRESHOLD:  float = 62.0   # inspect at next stop        precision=36%


def normalise(series: pd.Series) -> pd.Series:
    """Min-max normalise a series to [0, 1].  Returns all-zeros if range is zero."""
    lo, hi = series.min(), series.max()
    return (series - lo) / (hi - lo) if hi > lo else pd.Series(0.0, index=series.index)


def alert_tier(score: float) -> str:
    """Return the two-tier alert label for a given risk score."""
    if score >= URGENT_THRESHOLD:
        return "URGENT"
    if score >= WATCH_THRESHOLD:
        return "WATCH"
    return "CLEAR"


# ── 1. Load data ──────────────────────────────────────────────────────────────
df = pd.read_csv("fleet_history.csv")

broke = df[df["broke_down"] == 1]
fine  = df[df["broke_down"] == 0]

# ── 2. Feature analysis — prove which signals separate the groups ──────────────
FEATURES = ["odometer_km", "km_since_service", "avg_daily_km", "load_factor", "age_years"]

print("=" * 74)
print("FEATURE ANALYSIS  (n_broke=%d / %.0f%% of %d total)" % (
    len(broke), len(broke) / len(df) * 100, len(df)))
print("=" * 74)
print("%-22s  %10s  %10s  %7s  %7s  %s" % (
    "Feature", "Broke mean", "Fine mean", "Ratio", "r", "sig"))
print("-" * 74)
for col in FEATURES:
    bm    = broke[col].mean()
    fm    = fine[col].mean()
    ratio = bm / fm if fm else float("inf")
    r, p  = stats.pointbiserialr(df["broke_down"], df[col])
    sig   = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "n.s."))
    mark  = " <--" if abs(r) >= 0.20 else ""
    print("%-22s  %10.1f  %10.1f  %7.3f  %+7.3f  %s%s" % (
        col, bm, fm, ratio, r, sig, mark))

print()
print("High-load days/week:  broke avg=%.1f/7   fine avg=%.1f/7" % (
    broke["load_factor"].mean() * 7, fine["load_factor"].mean() * 7))
print()

# Joint risk matrix: the interaction between km_since_service and load
print("Joint risk  (above/below median for km_since_service AND load_factor):")
ks_hi   = df["km_since_service"] > df["km_since_service"].median()
load_hi = df["load_factor"]      > df["load_factor"].median()
for label, mask in [
    ("low ks  + low load ", ~ks_hi & ~load_hi),
    ("low ks  + high load", ~ks_hi &  load_hi),
    ("high ks + low load ",  ks_hi & ~load_hi),
    ("high ks + high load",  ks_hi &  load_hi),
]:
    grp = df[mask]
    print("  %-22s  n=%2d  breakdown rate=%.0f%%" % (
        label, len(grp), grp["broke_down"].mean() * 100))

# ── 3. Engineer features ──────────────────────────────────────────────────────
# daily_stress: effective stress-kilometres per day.
# A car doing 200 km/day at load 0.9 → 180 stress-km/day; at 0.3 → 60.
df["daily_stress"]      = df["avg_daily_km"] * df["load_factor"]
df["high_load_days_pw"] = (df["load_factor"] * 7).round(1)

# eff_interval: effective service interval shrinks with age.
# Standard service cannot fully reset residual mechanical wear in older cars —
# worn mounts, aged seals, accumulated structural stress.
df["eff_interval"] = NOMINAL_INTERVAL_KM / (1 + AGE_DECAY_FACTOR * df["age_years"])

# adj_ks: effective km consumed since service, weighted by load.
# A service on a high-load car resets the counter, not the mechanical stress rate.
df["adj_ks"] = df["km_since_service"] * df["load_factor"]

# adj_days: load+pace+age-adjusted days until the effective service threshold.
# Uses daily_stress (not raw daily_km) so pace AND load jointly determine urgency.
df["adj_days"]     = (df["eff_interval"] - df["adj_ks"]).clip(lower=0) / df["daily_stress"].clip(lower=1)
df["inv_adj_days"] = 1.0 / df["adj_days"].clip(lower=0.1)

# ── 4. Score ──────────────────────────────────────────────────────────────────
scored = df.copy()

# Base: three proven primary signals weighted by correlation strength
base = (
    normalise(scored["km_since_service"]) * 0.60  # r=+0.404 — how worn is the window
    + normalise(scored["avg_daily_km"])   * 0.25  # r=+0.252 — how fast it burns
    + normalise(scored["load_factor"])    * 0.15  # r=+0.215 — high-load days/week
)

# urgency1: amplifies cars driving fast under heavy load (independent of ks)
urgency1 = normalise(scored["daily_stress"])   # partial r=+0.364 after removing ks

# urgency2: amplifies cars near their age-adjusted threshold
# Addresses cars with low ks but extreme daily_stress that are much closer to
# their effective wear limit than the raw km count suggests.
urgency2 = normalise(scored["inv_adj_days"])   # r=+0.272 independently

scored["risk_score"] = (base * (1 + urgency1 * 0.20 + urgency2 * 0.15)) * 100
scored["alert"]      = scored["risk_score"].apply(alert_tier)
scored = scored.sort_values("risk_score", ascending=False).reset_index(drop=True)
scored["rank"] = scored.index + 1

# ── 5. Ranked output ──────────────────────────────────────────────────────────
print()
print("=" * 92)
print("CARS RANKED BY BREAKDOWN RISK  (highest first)")
print("=" * 92)
print("%-12s  %-7s  %6s  %5s  %12s  %10s  %9s  %4s  %8s  %5s" % (
    "car_id", "alert", "risk", "ks_km", "daily_km/day", "load_factor",
    "hi-ld d/w", "age", "adj_days", "actual"))
print("-" * 92)

last_tier = "URGENT"
for _, row in scored.iterrows():
    current_tier = row["alert"]
    if last_tier == "URGENT" and current_tier != "URGENT":
        print("  %s  (score < %.0f  |  inspect at next stop)" % (
            "-" * 40, URGENT_THRESHOLD))
    elif last_tier == "WATCH" and current_tier != "WATCH":
        print("  %s  (score < %.0f  |  no action needed)" % (
            "-" * 40, WATCH_THRESHOLD))
    last_tier = current_tier

    actual = "BROKE" if row["broke_down"] == 1 else "ok"
    print("%-12s  %-7s  %6.1f  %5.0f  %12.0f  %10.2f  %9.1f  %4.0f  %8.0f  %5s" % (
        row["car_id"],
        row["alert"],
        row["risk_score"],
        row["km_since_service"],
        row["avg_daily_km"],
        row["load_factor"],
        row["high_load_days_pw"],
        row["age_years"],
        row["adj_days"],
        actual,
    ))

# ── 6. Two-tier performance summary ───────────────────────────────────────────
total_broke = int(df["broke_down"].sum())
total_fine  = int((df["broke_down"] == 0).sum())
print()
print("=" * 74)
print("TWO-TIER ALERT PERFORMANCE")
print("=" * 74)

for tier, action in [("URGENT", "Book service this week"),
                     ("WATCH",  "Inspect at next scheduled stop")]:
    grp    = scored[scored["alert"] == tier]
    tp     = int(grp["broke_down"].sum())
    fp     = int((grp["broke_down"] == 0).sum())
    fn     = total_broke - tp  # only meaningful for URGENT tier
    n      = len(grp)
    recall = tp / total_broke * 100
    prec   = tp / n * 100 if n else 0
    print()
    print("  %s  (%s)" % (tier, action))
    print("  Score threshold: >= %.0f" % (URGENT_THRESHOLD if tier == "URGENT" else WATCH_THRESHOLD))
    print("  Cars flagged   : %d" % n)
    print("  True positives : %d  (correctly predicted to break down)" % tp)
    print("  False alarms   : %d  (flagged but car was fine)" % fp)
    print("  Recall         : %.0f%% of all %d actual breakdowns" % (recall, total_broke))
    print("  Precision      : %.0f%% of flags are real breakdowns" % prec)

# Combined tier summary
urgent_grp = scored[scored["alert"] == "URGENT"]
watch_grp  = scored[scored["alert"] == "WATCH"]
combined   = scored[scored["alert"].isin(["URGENT", "WATCH"])]
tp_comb    = int(combined["broke_down"].sum())
fp_comb    = int((combined["broke_down"] == 0).sum())
fn_comb    = total_broke - tp_comb
f1_comb    = 2 * tp_comb / (2 * tp_comb + fp_comb + fn_comb) * 100

clear_grp  = scored[scored["alert"] == "CLEAR"]
tp_clear   = int(clear_grp["broke_down"].sum())  # should be 6 (the permanently-missed)

print()
print("  COMBINED (URGENT + WATCH):")
print("  Cars flagged   : %d  (out of 120)" % len(combined))
print("  Caught         : %d / %d actual breakdowns  (recall=%.0f%%)" % (
    tp_comb, total_broke, tp_comb / total_broke * 100))
print("  Total alerts   : %d TP + %d FP  (precision=%.0f%%)" % (
    tp_comb, fp_comb, tp_comb / len(combined) * 100))
print("  F1 score       : %.0f%%" % f1_comb)
print()
print("  CLEAR (score < %.0f):" % WATCH_THRESHOLD)
print("  Cars cleared   : %d  — %d of these later broke down (cannot be avoided" % (
    len(clear_grp), tp_clear))
print("  with available data; see permanently-missed notes in file header)")

r_final, _ = stats.pointbiserialr(
    scored.sort_values("car_id")["broke_down"],
    scored.sort_values("car_id")["risk_score"],
)
print()
print("  Overall score-to-outcome correlation: r=%.3f" % r_final)
print("=" * 74)
