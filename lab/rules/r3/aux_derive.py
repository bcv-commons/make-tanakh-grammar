"""Auxiliaries derived from the alignment, with no knowledge of the target: a target word that, in the renderings of verbs,
stands beside another content word in at least half of its occurrences, across at least MIN_LEMMAS different verb lemmas
(Vamvas «θέλω» + verb for the future). Written as FUNC_FILE + the auxiliaries -> data/<name>_func_aux.txt.
    OT_DB=data/vamvas_ot.db FUNC_FILE=data/vamvas_func.txt python aux_derive.py vamvas"""
import collections, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../engine"))
import engine as E, heb_run as HR  # noqa: E402
MIN_LEMMAS = int(os.environ.get("MIN_LEMMAS", "30"))
H = HR.HebCorpus()
base = set(E.FUNC); aux = set()
for rnd in range(5):   # iterate: once the articles are function words, «του κυρίου» no longer makes κυρίου look like one
    E.FUNC.clear(); E.FUNC.update(base | aux)
    lem = collections.defaultdict(set); with_other = collections.Counter(); alone = collections.Counter()
    for ref in H.split("train"):
        for t in H.tok[ref]:
            if os.environ.get("CLASSES", "verb") != "all" and t["class"] != "verb":
                continue
            g = H.rendering(ref, t)
            if not g:
                continue
            gl = [x.lower() for x in g]
            for w in {x for x in gl if x not in base}:
                if any(x != w and x not in E.FUNC for x in gl):   # another content word beside it
                    with_other[w] += 1; lem[w].add(t["lemma"])
                else:
                    alone[w] += 1
    new = {w for w in lem if len(lem[w]) >= MIN_LEMMAS and with_other[w] >= alone[w]}
    print("round", rnd, "->", len(new), file=sys.stderr)
    if new == aux:
        break
    aux = new
aux = sorted(aux)
for w in sorted(aux, key=lambda w: -with_other[w]):
    print(f"{w}\t{with_other[w]} with another content word, {alone[w]} alone, {len(lem[w])} lemmas")
name = sys.argv[1] + ("_all" if os.environ.get("CLASSES") == "all" else "")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"../data/{name}_func_aux.txt"), "w", encoding="utf-8").write("\n".join(sorted(set(base) | set(aux))) + "\n")
