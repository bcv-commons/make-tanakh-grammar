"""rung 4: the reflexive possessive measured directly: held-out B tokens whose Danish rendering holds sin/sit/sine or
hans/hendes/dets/dens/deres, and whether E5 (with or without REFL) writes the same possessive"""
import collections, json, os, random, sqlite3, sys
LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PRIV = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules")   # corpora and run outputs, never in git (env.sh)
os.environ.update(OT_DB="data/dan_ot.db", FUNC_FILE="data/dan_func.txt")
if len(sys.argv) > 1 and sys.argv[1] == "refl":
    os.environ.update(REFL="1", CTX_EXTRA="pron.gov,noun.after_cstr,det.poss,noun.refl")
sys.path.insert(0, os.path.join(LAB, "eng_v10"))
import engine as E, cells as CL, heb_run as HR, final_eval as FE  # noqa: E402
CL.contexts = HR.heb_contexts
common = None
for d in ("data/dan_ot.db", "data/ot.db", "data/vamvas_ot.db"):
    s_ = {r for (r,) in sqlite3.connect(os.path.join(PRIV, d)).execute("select ref from verse")}
    common = s_ if common is None else common & s_
H = HR.HebCorpus(); tr = sorted(r for r in H.split("train") if r in common)
B = random.Random(8).sample(tr, 800); train = [r for r in tr if r not in set(B)]
eng = FE.build(H, train, os.environ.get("STAGE", "e5"))
REF = {"sin", "sit", "sine"}; NON = {"hans", "hendes", "dets", "dens", "deres"}
c = collections.Counter()
for ref in B:
    for t in H.tok[ref]:
        g = H.rendering(ref, t)
        if not g:
            continue
        g = {x.lower() for x in g}
        kind = "refl" if g & REF else "non" if g & NON else None
        if not kind:
            continue
        w, _ = eng.render(t); w = {x.lower() for x in w}
        got = "refl" if w & REF else "non" if w & NON else "none"
        c[(kind, got)] += 1
print(sys.argv[1:] or ["base"], dict(sorted(c.items())))
