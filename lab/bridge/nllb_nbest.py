#!/usr/bin/env python3
"""N-best lists from a fine-tuned NLLB model (run_nllb.sh) for the verses of <data>/test.src, as {BSB ref: [candidates...]} for
the reranking arm (checker.py rerank). Beam search, one list per verse, the best-first order kept.

    . ./env.sh; HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ~/sil-study/.venv/bin/python lab/bridge/nllb_nbest.py --data nllb/dfb_cons
        --model ~/models/nllb-finetuned/heb-dan-dfb+300/model --out bridge/nbest_dfb+300.json [--beams 8] [--batch 8]"""
import argparse, json, os, sys, torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as S  # noqa: E402
sys.path.insert(0, os.path.join(S.E.R, "scripts"))
import vrs  # noqa: E402


def main(a):
    d = os.path.join(S.E.PRIV, a.data)
    src = open(os.path.join(d, "test.src"), encoding="utf-8").read().rstrip("\n").split("\n")
    vref = open(os.path.join(d, "test.vref"), encoding="utf-8").read().rstrip("\n").split("\n")
    assert len(src) == len(vref)
    tok = AutoTokenizer.from_pretrained(os.path.expanduser(a.model), src_lang="heb_Hebr")
    model = AutoModelForSeq2SeqLM.from_pretrained(os.path.expanduser(a.model), torch_dtype=torch.float16).cuda().eval()
    bos = tok.convert_tokens_to_ids("dan_Latn")
    out = {}
    for i in range(0, len(src), a.batch):
        batch = src[i:i + a.batch]
        enc = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=256).to("cuda")
        with torch.no_grad():
            gen = model.generate(**enc, forced_bos_token_id=bos, num_return_sequences=a.beams, max_new_tokens=256,
                                 **({} if a.sample else {"num_beams": a.beams, "early_stopping": True}), **({"do_sample": True, "top_p": 0.9, "temperature": 0.9, "num_beams": 1} if a.sample else {}))
        texts = tok.batch_decode(gen, skip_special_tokens=True)
        for j, r in enumerate(vref[i:i + a.batch]):
            book, cv = r.split(); ch, v = (int(x) for x in cv.split(":"))
            e = vrs.to_bsb(book.lower(), ch, v)
            if e and e[1] != "title":
                cands = texts[j * a.beams:(j + 1) * a.beams]
                seen, uniq = set(), []
                for c in cands:
                    if c not in seen:
                        seen.add(c); uniq.append(c)
                out[f"{book} {int(e[0])}:{int(e[1])}"] = uniq
        if i % (a.batch * 10) == 0:
            print(i, len(src), file=sys.stderr)
    p = os.path.join(S.E.PRIV, a.out); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("written", p, len(out), "verses; mean distinct candidates", round(sum(len(v) for v in out.values()) / len(out), 2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--model", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--beams", type=int, default=8); ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--sample", action="store_true", help="nucleus sampling (top-p 0.9, T 0.9) instead of beam search, for diversity")
    main(ap.parse_args())
