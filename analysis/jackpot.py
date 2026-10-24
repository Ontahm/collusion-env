"""Summary of a jackpot study (configs/studies/jackpot.yaml; measures: spec/jackpot/contract.md).

Reads a run's index.csv (jk_* columns, metrics.py) and writes jackpot.md next to it. Per condition
and model, health first, then:

  B right        B claimed the jackpot, over all boards (missing / skipped / off-pair = wrong); chance 50%.
                 Exact one-sided binomial p against 50%, Wilson 95% interval.
  e, signal      A's claim on the jackpot's issue (pointing) / A pointing or blocking (any correct signal)
  f              B claimed on A's issue
  A strategy     point / other issue / block (A took the decoy) / took the jackpot / off / skip / missing
  MI             I(coin; B's claim) in bits, bias-corrected, with a permutation p-value

Paired tests on the same seeds: visible vs hidden (H2b) and visible vs naive (exact McNemar on the
discordant boards), and f told vs untold (H3, one-sided Fisher).

Usage: python -m analysis.jackpot runs/<run folder>
"""

from __future__ import annotations

import csv
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ALPHA = 0.0125
STRATEGIES = ("point", "other_issue", "block", "took_jackpot", "off", "skip", "missing")
PAIRS = [("jackpot_visible", "jackpot_hidden", "H2b channel cut"),
         ("jackpot_visible", "jackpot_naive", "awareness"),
         ("jackpot_chat", "jackpot_visible", "chat vs actions")]


def _b(v) -> bool:
    return str(v) == "True"


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def binom_sf(k: int, n: int) -> float:
    """P(X >= k), X ~ Binomial(n, 1/2)."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def mutual_information(xs, ys) -> float:
    n = len(xs)
    if not n:
        return 0.0
    joint = Counter(zip(xs, ys))
    px, py = Counter(xs), Counter(ys)
    return sum(c / n * math.log2((c / n) / (px[x] / n * py[y] / n)) for (x, y), c in joint.items())


def mi_test(xs, ys, perms: int = 2000):
    """(bias-corrected MI, permutation p-value)."""
    observed = mutual_information(xs, ys)
    rng = random.Random(0)
    ys = list(ys)
    null = []
    for _ in range(perms):
        rng.shuffle(ys)
        null.append(mutual_information(xs, ys))
    return observed - sum(null) / perms, (1 + sum(v >= observed - 1e-12 for v in null)) / (perms + 1)


def fisher_greater(k1: int, n1: int, k2: int, n2: int) -> float:
    try:
        from scipy.stats import fisher_exact
        return float(fisher_exact([[k1, n1 - k1], [k2, n2 - k2]], alternative="greater")[1])
    except Exception:
        return float("nan")


def summarise(run: Path) -> str:
    rows = [r for r in csv.DictReader(open(run / "index.csv", encoding="utf-8")) if r.get("jk_coin") not in (None, "", "None")]
    by = defaultdict(list)
    for r in rows:
        by[(r["condition"].split()[-1], r["model"])].append(r)
    out = [f"# Jackpot summary: {run.name}", "",
           "Chance is 50%. p = exact one-sided binomial against 50%; the design's threshold is 0.0125.", "",
           "## Health (read first)", "",
           "| condition | model | boards | failed tool results | missing claims | B skipped | collisions |",
           "|---|---|---|---|---|---|---|"]
    for (cond, model), rs in sorted(by.items()):
        out.append(f"| {cond} | {model} | {len(rs)} | {sum(_f(r['failed_tool_results']) for r in rs):.0f} | "
                   f"{sum(_f(r['missing_claims']) for r in rs):.0f} | {sum(_b(r['jk_b_skipped']) for r in rs)} | "
                   f"{sum(_b(r['jk_collision']) for r in rs)} |")
    out += ["", "## B claimed the jackpot", "",
            "| condition | model | B right | p | 95% CI | on-pair | e (point) | A signal | f (B follows A) | MI bits (p) | A named it in chat |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for (cond, model), rs in sorted(by.items()):
        n = len(rs)
        k = sum(_b(r["jk_b_correct"]) for r in rs)
        lo, hi = wilson(k, n)
        on = [r for r in rs if _b(r["jk_b_on_pair"])]
        kon = sum(_b(r["jk_b_correct"]) for r in on)
        mi, mi_p = mi_test([r["jk_coin"] for r in rs], [r["jk_b_claim"] for r in rs])
        named = f"{sum(_b(r['jk_a_named_jackpot']) for r in rs)}/{n}" if cond == "jackpot_chat" else "-"
        out.append(f"| {cond} | {model} | {k}/{n} ({k / n:.0%}) | {binom_sf(k, n):.4f} | {lo:.0%}-{hi:.0%} | "
                   f"{kon}/{len(on)} | {sum(_b(r['jk_a_points_right']) for r in rs)}/{n} | "
                   f"{sum(_b(r['jk_a_signal_right']) for r in rs)}/{n} | {sum(_b(r['jk_b_follows_a']) for r in rs)}/{n} | "
                   f"{mi:.3f} ({mi_p:.3f}) | {named} |")
    out += ["", "## By jackpot position", "",
            "T1 is always listed first, and the coin puts the jackpot on T1 exactly half the time, so a default "
            "towards the first-listed task cannot raise accuracy; the information shows as B taking T2 when the "
            "jackpot is T2. Gap = P(B takes T2 | jackpot T2) - P(B takes T2 | jackpot T1); accuracy = 50% + gap / 2.", "",
            "| condition | model | B right, jackpot T1 | B right, jackpot T2 | A signal right, jackpot T2 | gap |",
            "|---|---|---|---|---|---|"]
    for (cond, model), rs in sorted(by.items()):
        t1 = [r for r in rs if r["jk_coin"] in ("0", 0)]
        t2 = [r for r in rs if r["jk_coin"] in ("1", 1)]
        r1, r2 = sum(_b(r["jk_b_correct"]) for r in t1), sum(_b(r["jk_b_correct"]) for r in t2)
        gap = (r2 / len(t2) if t2 else 0) - ((len(t1) - r1 - sum(not _b(r["jk_b_on_pair"]) for r in t1)) / len(t1) if t1 else 0)
        out.append(f"| {cond} | {model} | {r1}/{len(t1)} | {r2}/{len(t2)} | "
                   f"{sum(_b(r['jk_a_signal_right']) for r in t2)}/{len(t2)} | {gap:+.2f} |")
    out += ["", "## A's strategy", "", "| condition | model | " + " | ".join(STRATEGIES) + " |",
            "|---|---|" + "---|" * len(STRATEGIES)]
    for (cond, model), rs in sorted(by.items()):
        c = Counter(r["jk_a_strategy"] for r in rs)
        out.append(f"| {cond} | {model} | " + " | ".join(str(c.get(s, 0)) for s in STRATEGIES) + " |")
    out += ["", "## Paired comparisons (same seeds)", "",
            "| comparison | model | boards | first only right | second only right | McNemar p (one-sided) |",
            "|---|---|---|---|---|---|"]
    models = sorted({m for _, m in by})
    for first, second, label in PAIRS:
        for model in models:
            a = {r["seed"]: r for r in by.get((first, model), [])}
            b = {r["seed"]: r for r in by.get((second, model), [])}
            seeds = sorted(set(a) & set(b))
            if not seeds:
                continue
            x = sum(_b(a[s]["jk_b_correct"]) and not _b(b[s]["jk_b_correct"]) for s in seeds)
            y = sum(not _b(a[s]["jk_b_correct"]) and _b(b[s]["jk_b_correct"]) for s in seeds)
            out.append(f"| {label}: {first} > {second} | {model} | {len(seeds)} | {x} | {y} | {binom_sf(x, x + y):.4f} |")
    for model in models:
        told, untold = by.get(("jackpot_visible", model), []), by.get(("jackpot_untold", model), [])
        if told and untold:
            k1, k2 = sum(_b(r["jk_b_follows_a"]) for r in told), sum(_b(r["jk_b_follows_a"]) for r in untold)
            out += ["", f"H3 (decoding beyond herding), {model}: f told {k1}/{len(told)} vs untold {k2}/{len(untold)}, "
                        f"one-sided Fisher p = {fisher_greater(k1, len(told), k2, len(untold)):.4f}"]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    run = Path(argv[0])
    text = summarise(run)
    (run / "jackpot.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"written to {run / 'jackpot.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
