"""E1b, the user's example: the present active indicative by person and number, with and without an explicit subject:
the share of BSB head words with the suffix +s (found by the vocabulary, not known), and the commonest words before it."""
import collections, json, os, engine as E, cells as CL
C = E.Corpus(); cl = CL.Cells(C, C.split("train"))
tab = collections.defaultdict(lambda: [0, 0, collections.Counter(), collections.Counter()])
for t, pre, core, post, cx in cl.rows:
    if t["class"] != "verb" or (t["tense"], t["voice"], t["mood"]) != ("present", "active", "indicative"):
        continue
    if cx["q"]:
        continue
    k = (t["person"], t["number"], "subject in clause" if cx["subj"] else "no subject")
    d = tab[k]; s = CL.lemmatize(CL.head(t, core))[1]
    d[0] += 1; d[1] += s == "+s"; d[2][" ".join(pre) or "–"] += 1; d[3][s] += 1
lines = ["| person | number | subject | n | +s | suffixes | words before |", "|---|---|---|---|---|---|---|"]
for k in sorted(tab):
    n, s, pre, suf = tab[k]
    lines.append(f"| {k[0]} | {k[1]} | {k[2]} | {n} | {s / n:.0%} | {', '.join(f'{a} {b}' for a, b in suf.most_common(3))} | {', '.join(f'{a} {b}' for a, b in pre.most_common(3))} |")
open(os.path.join(E.PRIV, "results/person_present.md"), "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
