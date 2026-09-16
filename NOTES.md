# What I checked, and what the agent got wrong

## What the agent got wrong

**1. `mileage_unit` was read but never used.**
The agent wired up `config_loader` to parse `mileage_unit` from `settings.cfg` but
`print_report` always printed miles regardless. I noticed because the setting existed in
the config with no effect. I pushed it to actually branch on the value: show km when the 
setting says km, miles when it says miles.

**2. `km_to_miles` used the wrong constant direction.**
`MILES_PER_KM = 1.609` is actually kilometres-per-mile, not miles-per-kilometre.
100 km was coming out as 160.9 "miles". I caught it by doing the mental check
100 km is about 62 miles, not 160. The number was obviously too large.

**3. Two sources of truth for the service rules.**
`km_wachter.py` had `SERVICE_INTERVAL_KM = 15000` hardcoded AND `settings.cfg` had the
same value. The 2016 comment literally said "nobody remembers which one wins."
The agent fixed several bugs but left both copies in place. I pushed it to load the
values from config at startup so there is exactly one place to change them. The module-level
names are kept as aliases so `verify.py` still passes without modification.

**4. Magic strings scattered across every file.**
`"last_service_km"`, `"odometer"`, `"id"` appeared as raw string literals in at least
four places. The agent did not flag this until I asked. One typo anywhere and the bug
is silent: no error, just wrong behaviour at runtime. I had it introduce a `CarField`
enum so every key access goes through one definition.

**5. `wear_percent` returned an unrounded float.**
`14900 / 15000 * 100` = `99.3333...`. The agent left this as a long float.
I pushed for rounding to 2 dp because floating-point drift can silently move a
`79.9999…%` car below the 80% threshold and leave it un-flagged. The test now asserts
exactly `99.33`, not a loose approximation.

**6. Empty fleet was not guarded.**
`fleet_summary([])` would divide by zero with no error message. The agent missed it.
I spotted it by reading `fleet_summary` top to bottom and asking: what happens if
`len(fleet)` is zero? I had it raise a `ValueError` with a descriptive message instead
of silently crashing.

**7. `car["odometer"]` was unguarded in two places.**
After fixing the `last_service_km` key crash the agent left `car["odometer"]` as a
hard key access. Same class of bug, different field. I found it by reading the fixed
code and asking "what other keys are still accessed without `.get()`?"

**8. The first risk model used `stress_since_service` as a replacement for `km_since_service`.**
The agent proposed multiplying `km_since_service × load_factor` as the dominant signal
because it had a higher raw correlation (r=0.503 vs 0.404). I asked it to prove this
actually improves recall before accepting it. It turned out the two features are
negatively correlated (r=−0.174) because high-load cars get serviced more often.
Replacing km_since_service with the product dropped top-30 recall from 73% to 54% :
exactly the opposite of better. The interaction belongs as a multiplier on top of the
base score, not as a replacement.

**9. The first model treated the score cutoff as rank-based (top-N) rather than score-based.**
Using "flag the top 35 cars" means the threshold shifts every time a new car joins
the fleet. I pushed for a fixed score threshold (≥ 70 for URGENT, ≥ 62 for WATCH)
so the same standard applies regardless of fleet size. This also naturally gives two
action levels rather than one undifferentiated list.

**10. Age was excluded entirely from the first model.**
The agent noted age_years had r=−0.001 and stopped there. I pushed it to think about
what age actually means mechanically an older car does not return to "as good as new"
after a service, residual wear in mounts, seals, and structural parts accumulates.
The right way to use age is to shrink the effective service interval, not to add it as
a standalone feature. Testing confirmed `eff_interval = 15000 / (1 + 0.03 × age)`
improves the adj_days correlation from 0.263 to 0.272.

## What I checked before I accepted its work

- Ran `python verify.py` after every batch of changes and read each PASS line
  individually, not just the final count.
- Confirmed `SERVICE_INTERVAL_KM == 15000` and `WARN_AT_PERCENT == 80` in the verify
  output, then traced them back to `settings.cfg` to make sure they were coming from
  config and not from leftover hardcoded literals in `km_wachter.py`.
- Checked `wear_percent(14900, 15000)` by hand: 14900 / 15000 = 0.9933, × 100 = 99.33.
  Verified the test asserts exactly `99.33`, not a loose float.
- Before accepting the risk model, I asked the agent to run a recall comparison between
  every candidate design and show me the numbers. I rejected the `stress_since_service`
  replacement after seeing it lose 19% of recall in the top-30. I only accepted the
  final formula after seeing it match or beat the baseline at every threshold level.
- Ran `python analyze.py` and read the full ranked output to check that the URGENT
  and WATCH tiers made intuitive sense : cars with high ks, high daily load, and short
  adj_days should appear at the top, and they do.
- Checked the permanently-missed cars individually to confirm the model was not simply
  broken: they genuinely have no distinguishing signal, which is a data limitation,
  not a scoring error.
- Ran the full test suite (`pytest -v`) after every round of changes to confirm no
  existing test regressed.

## What the data actually said

`km_since_service` is the strongest single predictor : cars that broke down averaged
11,678 km since their last service vs 7,261 km for cars that did not (ratio 1.61,
r=+0.404, p<0.001). `avg_daily_km` (r=+0.252) and `load_factor` (r=+0.215) also
genuinely separate the groups. Cars that broke down averaged 4.2 high-load days per
week vs 3.5 for fine cars.

The factors that were important was that age on its own is not such an important metric but with age 
the quality of service also differs. An old car will not become or act like a new one after
service, the quality will detoriate over time and that also contributes to the breakdown.

Factors like odometer reading and age is not important on its own but along with other factors 
combined they have a siginificant importance. Old cars are more detoriated and so are cars 
that have been driven way too lot.

The most instructive finding came from the joint risk matrix: cars with both high
km_since_service AND high load_factor break down at 52% : versus 4% for cars that are
low on both. That interaction is 13× the baseline rate and is exactly what the
urgency multiplier in the final model is designed to capture.

The paradox case (VOS-1349) was important: 1,086 km since service, 6 load-days per
week, 204 km/day : it broke almost immediately after a service. No km-based score
can catch this. The real fix for that car is a shorter service interval based on pace
and load, not a better risk formula. That is a business rule change, not a data
analysis result.

The two-tier alert system (URGENT ≥ 70, WATCH 62–69) came from measuring precision
at every score cutoff and picking thresholds that mean something actionable: URGENT
catches 15 of 26 breakdowns at 71% precision (7 in 10 flags are real), and the WATCH
tier catches 5 more at the cost of more uncertainty. 
The 6 permanently-missed cars broke down for reasons this dataset cannot explain: early-cycle failures and cars
that were average on every available feature.
