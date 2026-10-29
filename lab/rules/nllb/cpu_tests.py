"""The NLLB instrument tests on CPU (2026-10-26; the GPU trains the nt model meanwhile). Model: grc-eng-bsb-nogospels; verses: the
dev chapters MRK 3, 9, 12 (held out for the model and the engine alike); all candidates without punctuation, as the engine writes.

  T1 judge:    per verse, NLLB's mean log-probability of the BSB reference and of eng_v5's E2 / E5 / E6 / E7 renderings: does
               it put the reference first, and does its order of the engine's stages follow chrF?
  T2 contrast: minimal edits of the reference (a tense: said -> says ...; an article dropped; a noun's number), scored with the
               Greek and with an empty source: does NLLB prefer the original, and is the preference the source's doing?
  T3 memory:   NLLB's translations of 127 training verses against its dev translations (chrF): how much is recall.

    ~/sil-study/.venv/bin/python -I lab/rules/nllb/cpu_tests.py [t1 t2 t3]   -> $MAKE_TANAKH_PRIVATE/rules/nllb/cpu_tests.json; nllb/cpu_tests.md"""
import json, os, random, re, sys, time
import torch, sacrebleu
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
torch.set_num_threads(int(os.environ.get("THREADS", "3")))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "rules", "nllb")   # run outputs, never in git (env.sh)
M = os.path.expanduser("~/models/nllb-finetuned/grc-eng-bsb-nogospels"); D = os.path.expanduser("~/bsb-nllb/rules-en/nogospels/data/")
tok = AutoTokenizer.from_pretrained(M, src_lang="ell_Grek", tgt_lang="eng_Latn"); model = AutoModelForSeq2SeqLM.from_pretrained(M).eval()
rd = lambda f: open(D + f, encoding="utf-8").read().rstrip("\n").split("\n")
SRC = dict(zip(rd("test.vref"), rd("test.src"))); SRC_TR = dict(zip(rd("train.vref"), rd("train.src"))); TRG_TR = dict(zip(rd("train.vref"), rd("train.trg")))
ENG = json.load(open(os.path.join(OUT, "engine_dev.json"), encoding="utf-8"))
plain = lambda s: " ".join(re.findall(r"[\w'’-]+", s))


@torch.no_grad()
def score(pairs, bs=8):
    """mean log-probability per target token of each (source, target)"""
    out = []
    for i in range(0, len(pairs), bs):
        s, t = zip(*pairs[i:i + bs])
        b = tok(list(s), text_target=list(t), return_tensors="pt", padding=True, truncation=True, max_length=256)
        lab = b["labels"]; lab[lab == tok.pad_token_id] = -100
        lg = model(**b).logits.log_softmax(-1)
        m = lab != -100
        lp = lg.gather(-1, lab.clamp(min=0).unsqueeze(-1)).squeeze(-1) * m
        out += (lp.sum(1) / m.sum(1)).tolist()
    return out


@torch.no_grad()
def translate(srcs, bs=4):
    out = []
    for i in range(0, len(srcs), bs):
        b = tok(srcs[i:i + bs], return_tensors="pt", padding=True, truncation=True, max_length=256)
        g = model.generate(**b, forced_bos_token_id=tok.convert_tokens_to_ids("eng_Latn"), num_beams=4, max_new_tokens=256)
        out += tok.batch_decode(g, skip_special_tokens=True)
    return out


def t1():
    refs = [r for r in ENG["ref"] if r in SRC]; st = ["ref", "e2", "e5", "e6", "e7"]
    sc = {s: score([(SRC[r], ENG[s][r]) for r in refs]) for s in st}
    ch = {s: [sacrebleu.sentence_chrf(ENG[s][r], [ENG["ref"][r]]).score for r in refs] for s in st if s != "ref"}
    first = sum(max(st, key=lambda s: sc[s][k]) == "ref" for k in range(len(refs)))
    pairs = agree = 0
    for a in ("e2", "e5", "e6", "e7"):
        for b in ("e2", "e5", "e6", "e7"):
            if a < b:
                for k in range(len(refs)):
                    if ENG[a][refs[k]] != ENG[b][refs[k]] and ch[a][k] != ch[b][k]:
                        pairs += 1; agree += (sc[a][k] > sc[b][k]) == (ch[a][k] > ch[b][k])
    return {"verses": len(refs), "mean logprob": {s: round(sum(v) / len(v), 3) for s, v in sc.items()},
            "mean chrF": {s: round(sum(v) / len(v), 2) for s, v in ch.items()},
            "reference ranked first": round(first / len(refs), 3),
            "engine pairs: NLLB order = chrF order": [agree, pairs, round(agree / max(pairs, 1), 3)]}


EDITS = {"tense": [("said", "says"), ("says", "said"), ("went", "goes"), ("came", "comes"), ("was", "is"), ("were", "are"), ("is", "was"),
                   ("answered", "answers"), ("asked", "asks"), ("saw", "sees"), ("will", "would")],
         "article": [("the", "")], "number": [("disciples", "disciple"), ("men", "man"), ("people", "person"), ("things", "thing"),
                   ("hands", "hand"), ("days", "day"), ("children", "child"), ("brothers", "brother"), ("sons", "son"), ("man", "men")]}


def t2():
    rng = random.Random(3); items = []
    for r, ref in ENG["ref"].items():
        if r not in SRC:
            continue
        w = ref.split()
        for kind, subs in EDITS.items():
            hits = [(k, b) for k, x in enumerate(w) for a, b in subs if x == a]
            if hits:
                k, b = rng.choice(hits); v = w[:k] + ([b] if b else []) + w[k + 1:]
                items.append((kind, r, ref, " ".join(v)))
    o = score([(SRC[r], a) for _, r, a, _ in items]); e = score([(SRC[r], b) for _, r, _, b in items])
    o0 = score([("", a) for _, r, a, _ in items]); e0 = score([("", b) for _, r, _, b in items])
    res = {}
    for kind in EDITS:
        ks = [k for k, it in enumerate(items) if it[0] == kind]
        if ks:
            res[kind] = {"pairs": len(ks), "prefers original (with Greek)": round(sum(o[k] > e[k] for k in ks) / len(ks), 3),
                         "prefers original (empty source)": round(sum(o0[k] > e0[k] for k in ks) / len(ks), 3),
                         "mean margin with Greek": round(sum(o[k] - e[k] for k in ks) / len(ks), 3),
                         "mean margin empty source": round(sum(o0[k] - e0[k] for k in ks) / len(ks), 3)}
    return res


def t3():
    tr = random.Random(5).sample(sorted(SRC_TR), 127)
    hyp_tr = translate([SRC_TR[r] for r in tr])
    pred = open(os.path.expanduser("~/bsb-nllb/rules-en/nogospels/run/test.pred"), encoding="utf-8").read().rstrip("\n").split("\n")
    trg = dict(zip(rd("test.vref"), rd("test.trg"))); dv = rd("test.vref")
    c = lambda h, r: round(sacrebleu.corpus_chrf(h, [r]).score, 2)
    exact = sum(plain(h).lower() == plain(TRG_TR[r]).lower() for h, r in zip(hyp_tr, tr))
    return {"train verses chrF": c(hyp_tr, [TRG_TR[r] for r in tr]), "dev verses chrF": c(pred, [trg[r] for r in dv]),
            "train verses reproduced word for word": [exact, len(tr)],
            "dev verses reproduced word for word": [sum(plain(p).lower() == plain(trg[r]).lower() for p, r in zip(pred, dv)), len(dv)]}


if __name__ == "__main__":
    want = sys.argv[1:] or ["t1", "t2", "t3"]; res = {}
    fp = os.path.join(OUT, "cpu_tests.json")
    if os.path.exists(fp):
        res = json.load(open(fp))
    for t in want:
        t0 = time.time(); res[t] = globals()[t](); res[t]["minutes"] = round((time.time() - t0) / 60, 1)
        json.dump(res, open(fp, "w"), indent=1, ensure_ascii=False); print(t, json.dumps(res[t], ensure_ascii=False), flush=True)
