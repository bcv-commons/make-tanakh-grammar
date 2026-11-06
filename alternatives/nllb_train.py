#!/usr/bin/env python3
"""Train a language's NLLB model for the NLLB alternative (alternatives/nllb.py): the pairs, then the fine-tuning.

    . ./env.sh
    python3 alternatives/nllb_train.py data  --lang xxx --source hbo [--leave-out JHN]
    python3 alternatives/nllb_train.py train --lang xxx --source hbo --trg-code xxx_Latn --init-lang lug_Latn [--steps 5000]

data writes $MAKE_TANAKH_PRIVATE/lang/<iso>/nllb/<source>/{train,val}.{src,trg,vref} and SPLIT.json:
  target   the team's verse as parts, a divided word's parts joined by "@@ " (ni@@ ba@@ ku@@ ...), from the language's corpora
  source   grc: the Greek NT verse as written.
           hbo: Hebrew in consonants only (maqaf as a space, no punctuation): for the team's NT verses the Salkinson-Ginsburg
           Hebrew New Testament (hebrew-nt-analysis, CC BY 4.0), for its Tanakh verses the WLC. So a language with an NT
           only still gets a model that reads Hebrew, which is what drafting the Tanakh needs.
  Only what a pool may hold is written: no closed or held-out chapter, no excluded book, none of the books left out (leave
  the dev book out, so that the dev check is fair). val = 250 verses drawn with a fixed seed; the rest is train.

train fine-tunes facebook/nllb-200-distilled-600M (Scripture Forge's settings scaled to an 8 GB GPU: lr 2e-4 cosine, warmup
1000, effective batch 64, label smoothing 0.2, max length 200, Adafactor, bf16, early stopping on the validation loss). The
target's characters missing from NLLB's vocabulary are added as tokens; the target gets its own language code, initialised
from --init-lang (a related language NLLB knows; several codes, comma-separated, are averaged). Writes
$MAKE_TANAKH_PRIVATE/models/nllb/<iso>-<source>/model/ and MODEL.json, and prints the lines for the language's configuration.

Licence: NLLB-200 is CC BY-NC 4.0, and so is a model fine-tuned from it. A model trained on a team's text stays private."""
import argparse, collections, json, os, random, sqlite3, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import holdout, paths  # noqa: E402
from source import tokens  # noqa: E402
from alternatives import nllb  # noqa: E402

SEED, NVAL = 20261104, 250
SRC_CODE = {"grc": "ell_Grek", "hbo": "heb_Hebr"}
BASE = "facebook/nllb-200-distilled-600M"


def hebrew_nt():
    """ref -> a verse of the Salkinson-Ginsburg Hebrew NT, consonants only"""
    import pyarrow.parquet as pq
    p = paths.work("download", "hebrew-nt-analysis", "heb_scg", "words.parquet")
    if not os.path.exists(p):
        sys.exit(f"the Hebrew New Testament is missing: {p}")
    rows = pq.read_table(p, columns=["book", "chapter", "verse", "i", "part", "token", "class"]).to_pylist(); out = collections.defaultdict(list)
    for r in sorted((r for r in rows if r["part"] == 0 and r["class"] != "verse-number"), key=lambda r: (r["book"], r["chapter"], r["verse"], r["i"])):
        out[f"{r['book']} {r['chapter']}:{r['verse']}"].append(r["token"])
    return {r: " ".join(t) for r, t in out.items()}


def targets(cfg, corpus, leave):
    """[(ref as the source numbers it, the verse as parts)] of one corpus, outside everything a pool may not hold"""
    shut = holdout.shut(cfg); out = []; skip = set(corpus.get("exclude_books", ())) | set(leave)
    z = sqlite3.connect(corpus["_db"]); heb = "heb" if "heb" in [r[1] for r in z.execute("pragma table_info(verse)")] else "ref"
    for ref, book, ch, words, wi in z.execute(f"select coalesce({heb}, ref), book, ch, words, wordidx from verse order by rowid"):
        if not wi or book in skip or shut(book, ch):
            continue
        ws = collections.defaultdict(list)
        for p, i in zip(json.loads(words), json.loads(wi)):
            ws[i].append(p)
        out.append((ref, " ".join(nllb.JOIN.join(ws[i]) for i in sorted(ws))))
    return out


def data_dir(lang, source):
    d = paths.lang_dir(lang, "nllb", source); os.makedirs(d, exist_ok=True); return d


def cmd_data(a):
    cfg = paths.config(a.lang); leave = tuple(x for x in (a.leave_out or "").split(",") if x); pairs = []; missing = collections.Counter()
    nt, tk = paths.corpus(cfg, "grc"), paths.corpus(cfg, "hbo")
    if a.source == "grc":
        tg = targets(cfg, nt, leave) if nt else []; src = tokens.verse_texts("grc", {r for r, _ in tg})
    else:
        tg = (targets(cfg, nt, leave) if nt else []) + (targets(cfg, tk, leave) if tk else [])
        hb = set(tokens.books("hbo")); src = hebrew_nt(); src.update(nllb.source_lines("hbo", [r for r, _ in tg if r.split()[0] in hb]))
    for r, t in tg:
        if src.get(r) and t:
            pairs.append((src[r], t, r))
        else:
            missing[r.split()[0]] += 1
    if len(pairs) < NVAL * 4:
        sys.exit(f"only {len(pairs)} verse pairs: too few to train on")
    order = {p[2]: i for i, p in enumerate(pairs)}; rng = random.Random(SEED); sh = pairs[:]; rng.shuffle(sh)
    split = {"val": sh[:NVAL], "train": sorted(sh[NVAL:], key=lambda p: order[p[2]])}; d = data_dir(a.lang, a.source)
    for s, ps in split.items():
        for k, x in enumerate(("src", "trg", "vref")):
            open(os.path.join(d, f"{s}.{x}"), "w", encoding="utf-8").write("\n".join(p[k] for p in ps) + "\n")
    rep = {"language": a.lang, "source": a.source, "when": time.strftime("%Y-%m-%d %H:%M"), "left out": list(leave),
           "counts": {s: len(ps) for s, ps in split.items()}, "verses without a source verse": dict(missing),
           "books": dict(sorted(collections.Counter(p[2].split()[0] for p in pairs).items()))}
    json.dump(rep, open(os.path.join(d, "SPLIT.json"), "w"), indent=1); print(json.dumps({k: rep[k] for k in ("counts", "left out", "verses without a source verse")}), "->", d)


def cmd_train(a):
    import torch
    from datasets import Dataset
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, DataCollatorForSeq2Seq, EarlyStoppingCallback, Seq2SeqTrainer, Seq2SeqTrainingArguments
    d = data_dir(a.lang, a.source); out = paths.private("models", "nllb", a.name or f"{a.lang}-{a.source}"); os.makedirs(out, exist_ok=True)
    if os.path.exists(os.path.join(out, "model", "model.safetensors")) and not a.smoke:
        sys.exit(f"a model is already there: {out}/model (give another --name; models are never overwritten)")
    read = lambda n: open(os.path.join(d, n), encoding="utf-8").read().splitlines()
    tr = (read("train.src"), read("train.trg")); va = (read("val.src"), read("val.trg")); t0 = time.time(); src_code = SRC_CODE[a.source]
    if a.smoke:
        tr = (tr[0][:64], tr[1][:64]); va = (va[0][:8], va[1][:8])
    tok = AutoTokenizer.from_pretrained(a.base, src_lang=src_code); model = AutoModelForSeq2SeqLM.from_pretrained(a.base)
    unk = tok.unk_token_id; chars = sorted({c for s in tr[1] + va[1] for c in s if not c.isspace()})
    missing = [c for c in chars if unk in tok(c, add_special_tokens=False).input_ids]; fresh = a.trg_code not in tok.get_vocab()
    if missing:
        tok.add_tokens(missing)
    if fresh:
        tok.add_tokens([a.trg_code], special_tokens=True)
    model.resize_token_embeddings(len(tok)); init = a.init_lang.split(",")
    if fresh:
        if not all(c in tok.get_vocab() for c in init):
            sys.exit(f"--init-lang: NLLB does not know {[c for c in init if c not in tok.get_vocab()]}")
        with torch.no_grad():
            emb = model.get_input_embeddings().weight
            emb[tok.convert_tokens_to_ids(a.trg_code)] = torch.stack([emb[tok.convert_tokens_to_ids(c)] for c in init]).mean(0)
    tok.tgt_lang = a.trg_code
    print(f"{len(tr[0])} train pairs, {len(va[0])} val; added {len(missing)} characters; target code {a.trg_code}", flush=True)

    def enc(src, trg):
        ds = Dataset.from_dict({"src": src, "trg": trg})
        return ds.map(lambda b: tok(b["src"], text_target=b["trg"], max_length=a.max_len, truncation=True), batched=True, remove_columns=["src", "trg"])
    dtr, dva = enc(*tr), enc(*va); base_collate = DataCollatorForSeq2Seq(tok); start_id = model.config.decoder_start_token_id

    def collate(feats):
        """padded batch plus decoder_input_ids (labels shifted right): with label smoothing the trainer takes the labels out
        before the forward call, and newer transformers no longer build the decoder inputs in the collator"""
        b = base_collate(feats); lab = b["labels"].clone(); lab[lab == -100] = tok.pad_token_id
        dec = lab.new_full(lab.shape, tok.pad_token_id); dec[:, 1:] = lab[:, :-1]; dec[:, 0] = start_id; b["decoder_input_ids"] = dec
        return b
    cuda = torch.cuda.is_available(); steps = 20 if a.smoke else a.steps
    targs = Seq2SeqTrainingArguments(
        output_dir=os.path.join(out, "ckpt"), max_steps=steps, per_device_train_batch_size=2 if a.smoke else a.batch,
        per_device_eval_batch_size=a.eval_batch, gradient_accumulation_steps=1 if a.smoke else a.accum, learning_rate=a.lr,
        lr_scheduler_type="cosine", warmup_steps=2 if a.smoke else min(1000, a.steps // 5), label_smoothing_factor=0.2, optim="adafactor",
        bf16=cuda, gradient_checkpointing=True, eval_strategy="steps", eval_steps=10 if a.smoke else 500, save_strategy="steps",
        save_steps=10 if a.smoke else 500, save_total_limit=1, load_best_model_at_end=True, metric_for_best_model="eval_loss",
        greater_is_better=False, logging_steps=5 if a.smoke else 50, report_to=[], predict_with_generate=False, dataloader_num_workers=2, seed=111)
    trainer = Seq2SeqTrainer(model=model, args=targs, train_dataset=dtr, eval_dataset=dva, data_collator=collate,
                             callbacks=[EarlyStoppingCallback(early_stopping_patience=4)])
    trainer.train()
    rec = {"language": a.lang, "source": a.source, "base": a.base, "codes": [src_code, a.trg_code], "init": init, "steps": trainer.state.global_step,
           "best": trainer.state.best_model_checkpoint and os.path.basename(trainer.state.best_model_checkpoint), "best eval loss": trainer.state.best_metric,
           "train minutes": round((time.time() - t0) / 60, 1), "gpu": torch.cuda.get_device_name(0) if cuda else "cpu", "smoke": a.smoke,
           "data": json.load(open(os.path.join(d, "SPLIT.json"))), "licence": "CC BY-NC 4.0 (NLLB-200); trained on a team's text: private"}
    if a.smoke:
        print(json.dumps({k: rec[k] for k in ("steps", "best eval loss", "train minutes", "gpu")}), "(smoke run: no model kept)")
    else:
        trainer.save_model(os.path.join(out, "model")); tok.save_pretrained(os.path.join(out, "model"))
        json.dump(rec, open(os.path.join(out, "MODEL.json"), "w"), indent=1)
        print(json.dumps({k: rec[k] for k in ("steps", "best eval loss", "train minutes", "gpu")}))
        print(f'in {paths.lang_dir(a.lang, "config.json")}:  "nllb": {{"{a.source}": {{"model": "$PRIVATE/models/nllb/{os.path.basename(out)}", '
              f'"src_code": "{src_code}", "trg_code": "{a.trg_code}"}}}}')
    import shutil
    shutil.rmtree(os.path.join(out, "ckpt"), ignore_errors=True)            # the checkpoints only; the model stays


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("data", "train")); ap.add_argument("--lang", required=True); ap.add_argument("--source", required=True, choices=paths.SOURCES)
    ap.add_argument("--leave-out"); ap.add_argument("--trg-code"); ap.add_argument("--init-lang"); ap.add_argument("--name")
    ap.add_argument("--base", default=BASE); ap.add_argument("--steps", type=int, default=5000); ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--accum", type=int, default=32); ap.add_argument("--eval-batch", type=int, default=2); ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-len", type=int, default=200); ap.add_argument("--smoke", action="store_true", help="20 steps on 64 pairs: does it run? nothing kept")
    a = ap.parse_args()
    if a.cmd == "train" and not (a.trg_code and a.init_lang):
        ap.error("train needs --trg-code (e.g. xxx_Latn) and --init-lang (a related language's NLLB code, e.g. lug_Latn)")
    {"data": cmd_data, "train": cmd_train}[a.cmd](a)


if __name__ == "__main__":
    main()
