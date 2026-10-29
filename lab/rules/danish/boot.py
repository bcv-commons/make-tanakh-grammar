"""paired bootstrap (1,000 resamples over verses) of chrF between two hypothesis dumps of danish/run.py (DUMP=...): B - A
    python danish/boot.py A.json B.json"""
import json, random, sys
import sacrebleu
a, b = (json.load(open(f)) for f in sys.argv[1:3])
assert a["refs"] == b["refs"]
R = a["words"]; rnd = random.Random(11); d = []
for _ in range(1000):
    idx = [rnd.randrange(len(R)) for _ in R]
    x = sacrebleu.corpus_chrf([a["hyps"][i] for i in idx], [[R[i] for i in idx]]).score
    y = sacrebleu.corpus_chrf([b["hyps"][i] for i in idx], [[R[i] for i in idx]]).score
    d.append(y - x)
d.sort(); print(sys.argv[2], "-", sys.argv[1], round(sum(d) / 1000, 2), [round(d[25], 2), round(d[975], 2)])
