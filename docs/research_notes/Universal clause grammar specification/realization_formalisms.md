# Realization formalisms: abstract clause representation to text in many languages

Research notes, 2026-10-22. Scope: GF, Apertium, LinGO Grammar Matrix + AGGREGATION, KPML/Nigel, LFG/XLE ParGram,
SIL FLEx (parsers, Grammar Sketch, FLExTrans), CARLA/AMPLE/STAMP, Adapt It, Linguist's Assistant (TBTA's sibling,
for comparison only), SimpleNLG and its ports, jsRealB/pyrealb, Ninai/Udiron (Abstract Wikipedia), and the Bantu
grammar engines of Keet, Khumalo and Byamugisha. Facts are as fetched on 2026-10-22 unless a date is given.
Three sub-researchers covered GF, the Grammar Matrix and Apertium in depth; their source files are in the session
scratchpad (`gf-dl/ResZul.gf`, `dl/zulu_choices.txt`, `pdftext/*.txt`), not in the repo.

Reading guide for the three planned layers: **(A)** universal per-clause spec from MACULA, **(B)** target-language
profile (verb template/slots, concords, order, locative strategy), **(C)** realization rules learned from
part-aligned corpora and agent decisions, with counts and provenance; the agent drafts, the rules only predict a
grammatical frame per clause.

## Grammatical Framework (GF) and the Resource Grammar Library

### Takeaway
GF separates a language-neutral *syntactic* abstract syntax from one hand-written, categorical concrete syntax per
language; its Bantu grammars (Zulu, Runyankore/Rukiga, the Bantu functor) already encode exactly the objects layer B
needs (agreement = person x noun class x number, concord tables keyed by phonological context, verb forms assembled
from morpheme slots with a glue token), but nothing in GF learns a concrete grammar from data or carries counts, and
the RGL's own authors put a new language at 2 to 6 person-months.

### Cited Findings
- Definition: "An abstract syntax defines a set of trees, and a concrete syntax specifies how they are linearized in different languages... In a multilingual grammar, translation is defined as parsing with one concrete syntax and linearization with another one." GF is statically typed, reversible, with "regular expression pattern matching used for morphology". — [Ranta, Multilingual Text Generation for Abstract Wikipedia in GF (preprint, c. 2023)](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- What the abstract layer abstracts is syntax, not semantics: "the abstract two-place verb have_V2 is in some languages implemented with non-verbal [constructions]"; "different languages can define Number, Case, and Gender in different ways" (parameter types belong to each concrete syntax). The API hides language-specific decisions: "mkCl selects the word order in German, Dutch, and Scandinavian; mkCl selects complement cases and prepositions of two-place verbs; mkCl implements the ergative agreement in Basque, Hindi, and Urdu; mkCl selects and orders clitic pronouns in Romance languages and Greek." — [Ranta preprint](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- RGL API: `Cl` "declarative clause, with all tenses"; `mkCl : NP -> V2 -> NP -> Cl` etc.; `mkS : (Tense) -> (Ant) -> (Pol) -> Cl -> S`; `mkTemp : Tense -> Ant -> Temp`; constants `presentTense, pastTense, conditionalTense, simultaneousAnt, anteriorAnt, positivePol, negativePol`; example `mkUtt (mkS conditionalTense anteriorAnt negativePol (mkCl she_NP sleep_V))` = "she wouldn't have slept". The synopsis header says the library covers "the morphology and basic syntax of currently 38 languages". — [RGL synopsis](https://www.grammaticalframework.org/lib/doc/synopsis/index.html)
- Parameter types and tables (tutorial): `param Number = Sg | Pl ;` `lincat Kind = {s : Number => Str} ;` (variable feature = table), `lincat Item = {s : Str ; n : Number} ;` (inherent feature = record field), `oper regNoun : Str -> {s : Number => Str} = \dog -> {s = table {Sg => dog ; Pl => dog + "s"}} ;`. — [GF tutorial](https://www.grammaticalframework.org/doc/tutorial/gf-tutorial.html)
- Smart paradigm by string patterns: `add_s w = case w of { _ + ("a"|"e"|"o"|"u") + "y" => w + "s" ; stem + "y" => stem + "ies" ; _ + ("ch"|"s"|"sh"|"x"|"z") => w + "es" ; _ => w + "s" }`. — [Ranta preprint](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- Coverage: the official status page (dated 2020-09-07) lists 48 languages; African entries Afrikaans, Amharic, Somali (paradigms only), Swahili (paradigms + lexicon, no syntax). — [RGL status](https://www.grammaticalframework.org/lib/doc/status.html). The `gf-rgl/src` tree today has 78 directories including afrikaans, amharic, egekusii, kikamba, rukiga, somali, swahili, zulu and a shared `bantu` functor; no Wolof, Hausa, Xhosa, Tswana, no Papuan language; Austronesian only malay. — [gf-rgl src](https://github.com/GrammaticalFramework/gf-rgl/tree/master/src). Ranta's 2022 table: RGL "defines syntactic structure, morphology, and basic lexicon for 55 languages, of which around 40 have complete implementations"; Zulu, Xhosa, Tswana, Chiga, Kikamba, Egekusii marked "+" (started). — [Ranta preprint](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- Zulu resource grammar (ZRG; Marais, Pretorius, Posthumus; SADiLaR): aims "to enable parsing, which is not possible for large, inefficient grammars". — [zulu/README](https://raw.githubusercontent.com/GrammaticalFramework/gf-rgl/master/src/zulu/README.md). "A key feature of the implementation of the ZRG is to model aspects of morphology as equivalent to syntax" and it is "the first openly available parser for isiZulu". — [SACAIR 2023 chapter](https://link.springer.com/chapter/10.1007/978-3-031-38318-2_17). 2025 paper: the ZRG "implicitly encodes rich morphosyntactic information about isiZulu... made explicit by adapting the way the grammar linearises GF abstract syntax trees". — [Marais & Pretorius, DHASA 6(2) 2025](https://upjournals.up.ac.za/index.php/dhasa/article/view/6741)
- Zulu parameter algebra (verbatim from `ResZul.gf`, 2,108 lines):
  ```gf
  param
    ClassGender = C1_2 | C1a_2a | C3_4 | C5_6 | C7_8 | C9_10 | C11_10 | C9_6 | C14 | C15 | C17 ;
    Agr = First Number | Second Number | Third ClassGender Number ;
    VForm = VFIndic CType Polarity BasicTense ;      -- CType = MainCl | RelCl
    BasicTense = PresTense | FutTense | PastTense | RemFutTense | RemPastTense ;
    SCForm = SC | SCVow | SCNeg | SCNegVow | SCPS | SCPart | SCVowP | SCBe | SCRP ; -- subject-concord allomorph by context
    OCForm = OC | OCAE | OCIOU | OCMono | OCThing ;
    RForm = R_a | R_ile | R_e | R_i | R_anga ;        -- final-vowel forms of the root
  oper
    subjConcLookup : Agr => SCForm => Str = table {
      First Sg      => table {SC => "ngi" ; SCVow => "ng"++BIND ; SCNeg => "ngi" ; ... ; SCBe => "bengi" ; SCRP => "ngangi"} ;
      Third C1_2 Sg => table {SC => "u" ; SCVow => "w"++BIND ; SCNeg => "ka" ; SCPart => "e" ; ... } ; ... } ;
    -- tense/polarity prefix chain glued with BIND:
    VFIndic MainCl Pos FutTense  => subjConcLookup!agr!SC ++BIND++ "zo" ++BIND ;
    VFIndic MainCl Neg PresTense => "a" ++BIND++ subjConcLookup!agr!SCVowP ++BIND ;
    prefix_nasal : Str -> Str = \r -> case r of { "ph"+x => "mp"+x ; "hl"+x => "nhl"+x ; "l"+x => "nd"+x ; ... ; _ => "n"+r } ;
  ```
  Possessive and demonstrative concords are tables `Agr => Str` and `Distance => Agr => Str`. — [ResZul.gf](https://raw.githubusercontent.com/GrammaticalFramework/gf-rgl/master/src/zulu/ResZul.gf)
- Runyankore and Rukiga (Bamutura, Ljunglöf, Nabende, LREC 2020): the Bantu verbal unit "results into 11 slots"; inflection "depends on tense, Anteriority (2), Polarity (2), Noun Class of Subject, Direct Object and Indirect Object markers (33 * 6 each) bringing the total possible number of combinations to 124,198,272 inflections which are impractical to enumerate and cannot be handled by the GF compiler"; subject-only 3,168 forms "was still prohibitive to successful compilation"; "it was impossible to design a smart-paradigm for verbs. Our solution... building the verb at sentence level by designing smaller tables and morpheme-generating operations... we dynamically built the verb from the radical up to its full form"; "thirty-eight rules for converting a verb in the imperative mood to the perfective mood"; `Agreement = AgP3 Number Gender | AgMUBAP1 Number | AgMUBAP2 Number | NONE`. No effort figures; evaluation left to future work. — [LREC 2020](https://aclanthology.org/2020.lrec-1.347.pdf)
- Bantu functor: `VerbForms : Type = Tense => Anteriority => Polarity => Agre => Str`; `Verb = {s, passive : Polarity => VForm => Str}`; a language instantiates `DiffBantu`. — [ResBantu.gf](https://raw.githubusercontent.com/GrammaticalFramework/gf-rgl/master/src/bantu/ResBantu.gf). Swahili bootstrapped on the functor (built from Kikamba and Ekegusii) shared 100% of linearization categories, 71.11% of paradigms (32/45), 68.75% of parameters (11/16), 91.41% of syntax rules (149/163; the 14 changed are 13 numeral rules + 1 idiom); "Monologue grammar development for under-resourced languages is very slow and laborious". — [Kituku & Muchemi, IJEECS 30(2), 2023](https://ijeecs.iaescore.com/index.php/IJEECS/article/download/26444/17265)
- Family functors: "only one language in the family needs a fully proficient RGL programmer, whereas the others can be added more easily by informants for those languages who provide values to functor parameters. This method has been extensively applied in Scandinavian, Romance, Indo-Iranian, and Bantu families." — [Ranta preprint](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- Effort and who writes: "RGL writers: linguistically proficient programmers implementing new languages"; "a two-week intensive training is enough for this task. Writing an RGL implementation for a new language itself typically takes two to six person months... the experimental implementation described here uses less than 20% of the common abstract syntax functions. Hence a basic rendering system for a new language can be released after a few weeks' work." — [Ranta preprint](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- Learning: smart paradigms "inspect the base form and tr[y] to infer which low-level paradigm applies"; predictability measured for English, French, Swedish, Finnish. — [Détrez & Ranta, EACL 2012](https://preview.aclanthology.org/moar-dois/E12-1066.pdf). Détrez's thesis: "automatically creating smart paradigms based on existing traditional paradigms using machine-learning techniques". — [GUPEA](https://gupea.ub.gu.se/handle/2077/43364?show=full). Ranta 2023: Wiktionary/Wikidata dictionaries "can often be converted to GF records and tables"; a 2022 student project aimed "to extract GF rendering functions from UD trees"; a Masters thesis built n-gram and neural LMs "for Wikipedia in 46 languages" so that "rule-based NLG generates several renderings of the same facts, all of them semantically correct, and the language model ranks them in terms of fluency". — [Ranta preprint](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- Probabilities attach to abstract trees only: the shell flag `-probs` "file with biased probabilities (format 'f 0.4' one by line)". — [GF shell reference](https://www.grammaticalframework.org/doc/gf-shell-reference.html); PGF API `rankTreesByProbs`, `setProbabilities`. — [Hackage gf-3.6 index](https://hackage.haskell.org/package/gf-3.6/docs/doc-index-P.html)
- Licences: compiler GPL, "the GF runtime in src/runtime is under dual GNU LESSER GENERAL PUBLIC LICENSE and BSD LICENSE". — [gf-core LICENSE](https://raw.githubusercontent.com/GrammaticalFramework/gf-core/master/LICENSE). RGL: "under GNU LESSER GENERAL PUBLIC LICENSE and BSD. However the user has the right to choose any license for any application grammar derived from the resource grammar by using the grammar API"; external lexicons "might be under different licenses". — [gf-rgl LICENSE](https://raw.githubusercontent.com/GrammaticalFramework/gf-rgl/master/LICENSE)
- Maintenance: GF `release-3.12` published 2025-08-03 (previous 3.11, 2021-07-25); gf-core pushed 2026-10-15; gf-rgl pushed 2026-10-21 (commits "extensions by Codex", "chenges in the verb morphology"). — [gf-core](https://github.com/GrammaticalFramework/gf-core); [gf-rgl](https://github.com/GrammaticalFramework/gf-rgl)
- Python: "Embedded GF grammars are available for C, C#, Haskell, Java, and Python". — [Ranta preprint](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- Abstract Wikipedia: GF offers "out-of-the-box baseline generation for currently 26 languages which can be quickly adjusted by hand"; Angelov argues GF's resources "built over about three decades" give it an advantage over Ninai/Udiron, which starts from scratch. — [Angelov, Wikidata paper](https://grammaticalframework.org/~krasimir/wikidata.pdf)

### Inferences
- GF's Zulu and Runyankore modules are the nearest existing formalisation of a Bantu "profile": agreement as a product type, concord allomorphs keyed by context, and per-clause assembly of the verb from slots. They are a direct template for Zinza and, by analogy (prefix/suffix chains), for Kuni.
- The Runyankore lesson ("never enumerate the slot product") is a design constraint for layer C: rules must be per slot and per clause, not full-form tables.
- GF gives no mechanism for counts or provenance; a count-bearing rule table can be exported into GF `table` syntax later if a GF backend is wanted, and the RGL licence lets such application grammars be CC0.

### Gaps
- No GF use for Bible, liturgy or Christian texts found (three searches, RGL publications page).
- No GF grammar for a Papuan language or any language with written tone; `ResZul.gf` has no tone handling.
- No person-month figure for a specific Bantu grammar; the Bantu papers give reuse percentages, not time.
- No published learning of concrete grammars from aligned corpora; Angelov's probabilistic parsing paper not fetched.

## Apertium

### Takeaway
Apertium's `^lemma<tags>$` stream is a frame-plus-stem split like ours; its transfer rules are categorical pattern/action
rules (the newer `.rtx` form has compact agreement and default-value syntax worth copying as a text format), its one
Bantu module is a skeleton, rule learning from small parallel corpora exists (ruLearn, GPL) but produces uncounted
categorical rules and does not scale past a few thousand sentences, and everything is GPL.

### Cited Findings
- Pipeline: morphological analysis (lttoolbox `.dix` or HFST lexc/twol), tagging (HMM, perceptron or CG-3), lexical selection, structural transfer (one-step, or chunker/interchunk/postchunk since Apertium 2.0), generation, post-generation; monolingual modules (`apertium-spa`) are shared across pairs. — [Khanna et al. 2021, Recent advances in Apertium](https://d-nb.info/1249211654/34)
- Statistical vs categorical: tagger statistical or constraint-based; lexical-selection rules weighted and learnable; transfer rules categorical by default, but "rules can now be weighted so as to apply different rules in different overlapping lexical contexts" (Bayatli et al. 2020, unsupervised weighting scored by a target LM). — [Khanna 2021](https://d-nb.info/1249211654/34)
- `.dix` paradigm and entry (Serbo-Croatian): `<pardef n="gramofon__n"><e><p><l/><r><s n="n"/><s n="sg"/></r></p></e><e><p><l>i</l><r><s n="n"/><s n="pl"/></r></p></e></pardef>` `<e lm="gramofon"><i>gramofon</i><par n="gramofon__n"/></e>`; stream `^gramofoni/gramofon<n><pl>$`. — [New Language Pair HOWTO](https://wiki.apertium.org/wiki/Apertium_New_Language_Pair_HOWTO)
- `.t1x` chunker rule (Esperanto to English determiner): pattern `<pattern-item n="c_det"/>`, action emitting `<chunk name="det"><tags><tag><lit-tag v="SN"/></tag><tag><clip pos="1" side="tl" part="a_nbr"/></tag></tags><lu><clip pos="1" side="tl" part="lem"/><clip pos="1" side="tl" part="a_det"/><clip pos="1" side="sl" part="a_nbr" link-to="2"/></lu></chunk>`; agreement is carried on the chunk's tags and resolved at postchunk via `link-to`. — [Chunking: A full example](https://wiki.apertium.org/wiki/Chunking:_A_full_example)
- Chunking limits: English–Spanish noun phrases needed "more than 30 rules"; apertium-recursive does it in "less than 10", most "by just 3 rules". — [Khanna 2021](https://d-nb.info/1249211654/34)
- `.rtx` recursive transfer (GSoC 2019): `gender = (GD m) m f GD;` (default for a missing value), `NP -> det n {2 _ 1};` (reorder), `DP -> det NP { 1[number=2.number] _ 2 } ;` (concord), `NP -> n.$number adj {1};` (chunk inherits the head's value), weighted alternatives `NP -> 1: n {1} | 2: n.*.def {the@det.def.sg _ 1};`, conditionals `(if (2.lem/sl = and) {...} else {...})`. — [Apertium-recursive](https://wiki.apertium.org/wiki/Apertium-recursive); [Formalism](https://wiki.apertium.org/wiki/Apertium-recursive/Formalism)
- Bantu module `apertium-swa` (GPL-3.0; HFST lexc/twol + CG; 17 commits, no releases): lexc continuation chain `Root -> VerbPersonNum-Prefix -> V-TAM-REL-OBJ-Stem -> V-TAM-Prefix -> V-Stems -> V-Suffix -> COMMON-Suffix`; implemented: subject prefix (`%<p1%>%<sg%>:ni%> V-TAM-REL-OBJ-Stem ;`), TAM (`%[%-past%]:li%> V-Stems ;`), root (`kusoma:som V-Suffix ;`), final vowel with flag diacritics (`%[%+pres%]%[%+p1%]%[%+sg%]...:a COMMON-Suffix ;`); negation, relative, object concord and the extensions have no entries ("!TODO"); noun classes as `%<cl1%>`, `%<cl3%>`...; no adjective concord. — [apertium-swa](https://github.com/apertium/apertium-swa); [swa.lexc](https://raw.githubusercontent.com/apertium/apertium-swa/master/apertium-swa.swa.lexc)
- Coverage: "As of December 2020, there are 51 translation pairs released, corresponding to 44 languages of 6 language families"; only three released pairs between unrelated languages (North Sámi–Bokmål, Basque–English, Basque–Spanish); Indonesian–Malay released; Lingala and Cuzco Quechua–Spanish "recent work... not systematically evaluated yet"; no Papuan language. — [Khanna 2021](https://d-nb.info/1249211654/34)
- Rule learning 1: alignment templates generalise GIZA++-aligned bilingual phrases by lexical category + inflection, restricted by the bilingual dictionary, written out as transfer rules; es–ca, es–gl, es–pt with 0.25 to 2.0 M words; better than word-for-word from 0.5 M words, "close to that obtained using hand-coded transfer rules"; SMT on the same corpus worse than word-for-word. — [Sánchez-Martínez & Forcada 2009 (JAIR), arXiv copy](https://arxiv.org/pdf/1401.5700)
- Rule learning 2 (GATs): wildcard and reference attributes; "the first approach that rewrites rule learning as a global minimisation problem"; better than 2009 with fewer rules, for some pairs better than hand-coded. — [Sánchez-Cartagena et al., CSL 32 (2015)](https://www.sciencedirect.com/science/article/abs/pii/S0885230814001028)
- ruLearn (GPL v3): 5 pairs, corpora 100 to 25,000 sentence pairs; "When the languages involved are closely-related, a few hundred parallel sentences proved to be sufficient"; minimisation with attribute generalisation impractical above 5,000 sentences; without it the learned rules "reach, and in some cases surpass" Apertium's hand-crafted ones (es–en); output = flat t1x rules, human-editable, "a hierarchy with a mix of general rules and more specific rules"; the 2009 formalism needed four rules to swap noun+adjective, one per gender/number combination. — [ruLearn, PBML 106 (2016)](https://ufal.mff.cuni.cz/pbml/106/art-sanchez-cartagena-perez-ortiz-sanchez-martinez.pdf)
- Lexical selection learning: unsupervised maximum-entropy models trained from SL text, the MT system and a TL LM; output weighted `.lrx` rules. — [Tyers, Sánchez-Martínez & Forcada, EAMT 2015](https://aclanthology.org/W15-4919.pdf)
- Who writes rules: "most modules in the pipeline work on rules written by language developers and linguists... speakers of a language with a limited understanding of programming and/or linguistics can create decent translation systems". — [Khanna 2021](https://d-nb.info/1249211654/34). Transfer rules are "the linguistic resource in Apertium that requires the deepest linguistic knowledge". — [ruLearn 2016](https://ufal.mff.cuni.cz/pbml/106/art-sanchez-cartagena-perez-ortiz-sanchez-martinez.pdf)
- Licence and status: `apertium/apertium` GPL-2.0, pushed 2026-10-13; `lttoolbox` GPL-2.0, pushed 2026-10-06 (GitHub API, 2026-10-22); `apertium-python` GPL-3.0 (`apertium.generate('en', '^cat<n><pl>$')` -> `cats`; subprocess and SWIG wrappers). — [apertium-python](https://github.com/apertium/apertium-python). GSoC participation listed for 2016–2021, 2023, 2024; none shown for 2025/2026. — [gsocorganizations.dev](https://www.gsocorganizations.dev/organization/apertium/)
- Positioning: "especially suitable for related language pairs"; RBMT "can still be successfully applied to the task of translation between closely related languages". — [Survey of low-resource MT, arXiv 2109.00486](https://arxiv.org/pdf/2109.00486)

### Inferences
- The `.rtx` one-liners (`number = (ND sg) sg pl sp ND;`, `1[number=2.number]`, `n.$number`) are a compact, readable text form for B and C; add per-rule count, provenance and confidence, which Apertium lacks.
- ruLearn's GATs are the closest precedent for learning categorical rules from a few hundred to a few thousand sentence pairs; its exact-cover minimisation is the part that does not scale; a counted table with thresholds avoids it and keeps provenance.
- GPL throughout: reuse by format and by subprocess only; no Apertium data can go into `export/` (CC0).

### Gaps
- `apertium-kin/zul/xho/nya` not verified; the List_of_language_pairs page not fetched; no Apertium use in Bible translation or by SIL found; no comparison with TBTA, GF or the Matrix in the literature.
- Forcada et al. 2011 (Machine Translation 25) not retrieved, so no person-month or dictionary-size figures per pair.

## LinGO Grammar Matrix and AGGREGATION

### Takeaway
The Matrix "choices" file is the closest existing analogue of layer B: a flat `key=value` text file with a section per
typological library whose morphology section is a stem-plus-position-class "parts" model with features and
requires/forbids constraints; the Zulu regression file encodes NC-, OC-, tense-, SC-, NEG- prefixes and the final vowel
in 55 lines. AGGREGATION infers such files from interlinear glossed text (word order 0.73 to 0.90 accuracy on small
sets, 99% on 97 languages with 40+ examples in the underlying method), but the output is one categorical file, the
grammars are categorical HPSG, and the project's last listed publication is 2022.

### Cited Findings
- Questionnaire sections (the choices-file sections): General Information, Word Order, Number, Person, Gender, Case, Adnominal Possession, Direct Inverse, Tense Aspect and Mood, Evidentials, Other Features, Sentential Negation, Coordination, Matrix Yes/No Questions, Constituent (wh-) Questions, Information Structure, Argument Optionality, Clausal Modifiers, Clausal Complements, Nominalized Clauses, Lexicon, Morphology, Import Toolbox Lexicon, Test Sentences, Test By Generation Options; users may "directly edit the choices file, rather than going through the customization web-interface". — [Matrix documentation index](https://delph-in.github.io/docs/matrix/MatrixDocTop/)
- Morphology model: "a stem defined on the Lexicon page, position classes which define a minimal set of affixes, a hierarchy of lexical rule types which define features, and a collection of affixes, known as lexical rule instances"; covers "morphotactics (position and grammatical properties of morphemes)", "does not cover morphophonological phenomena". — [MatrixDoc_Morphology](https://delph-in.github.io/docs/matrix/MatrixDoc_Morphology/)
- Position class definitions: "Position class: A supertype to lexical rules which fit in the same slot"; to define one: "Whether or not it is obligatory; Possible inputs and prefix/suffix = position in the string; Optional: Requires/forbids constraints"; a lexical rule type carries "Feature/value pairs (optional, but this is usually the point!)". — [Ling 567 slides 2022-01-18 (Goodman 2013)](https://courses.washington.edu/ling567/2022/0118.pdf)
- Verbatim Zulu regression choices file (`version=24`; `word-order=svo`, `has-dets=no`, `has-aux=no`, `person=none`, `case-marking=none`, `infl-neg=on`, `q-part-orth=na`; lexicon `verb2_stem1_orth=bon`, `verb2_stem1_pred=_see_v_rel`), morphology section:
  ```
  section=morphology
    noun-pc1_name=NC
    noun-pc1_obligatory=on
    noun-pc1_order=prefix
    noun-pc1_inputs=noun
      noun-pc1_lrt1_name=C1
        noun-pc1_lrt1_lri1_inflecting=yes
        noun-pc1_lrt1_lri1_orth=C1-
      noun-pc1_lrt2_name=C9 ...
    verb-pc1_name=OC
    verb-pc1_order=prefix
    verb-pc1_inputs=tverb
      verb-pc1_lrt1_name=OC1 ... verb-pc1_lrt1_lri1_orth=OC1-
    verb-pc2_name=tense
    verb-pc2_order=prefix
    verb-pc2_inputs=iverb, verb-pc1
      verb-pc2_lrt1_name=fut-tense ... lri1_orth=FUT-
      verb-pc2_lrt2_name=pres-tense ... lri1_orth=PRES-
    verb-pc3_name=SC
    verb-pc3_obligatory=on
    verb-pc3_order=prefix
    verb-pc3_inputs=verb-pc2
      verb-pc3_lrt1_name=SC1 ... verb-pc3_lrt2_name=SC9
    verb-pc4_name=FV
    verb-pc4_obligatory=on
    verb-pc4_order=suffix
    verb-pc4_inputs=verb-pc3, verb-pc5
      verb-pc4_lrt1_name=default-FV ... lri1_orth=-a
      verb-pc4_lrt2_name=neg-FV ... lri1_orth=-e
    verb-pc5_name=negation
    verb-pc5_order=prefix
    verb-pc5_inputs=verb-pc3
        verb-pc5_lrt1_lri1_orth=NEG-
  ```
  (the affixes are placeholders `SC1-`, `OC9-`; the test grammar checks the slot graph, not the spellings). — [matrix/tests/regression/choices/Zulu](https://raw.githubusercontent.com/delph-in/matrix/trunk/tests/regression/choices/Zulu)
- A Papuan test grammar exists: `Fore` (`version=17`, `word-order=v-final`, `case-marking=erg-abs`, `person=none`, sections number, gender, direct-inverse, tense-aspect, other-features, sentential-negation, coordination, matrix-yes-no, lexicon, test-sentences; no morphology section). — [matrix/tests/regression/choices/Fore](https://raw.githubusercontent.com/delph-in/matrix/trunk/tests/regression/choices/Fore). Language-named regression files: Cree, Dyirbal, Finnish, Fore, German, Hindi, Sahaptin, Slave, Tagalog, Zulu, plus 76 `adj-*` agreement tests. — [regression choices dir](https://github.com/delph-in/matrix/tree/trunk/tests/regression/choices)
- Libraries beyond the core: Clausal modifiers (Howell & Zamaraeva 2018): "88.4% coverage, 1.5% overgeneration" on five held-out languages. — [COLING 2018](https://aclanthology.org/C18-1249.pdf). Clausal complements (Zamaraeva, Howell & Bender 2019). — [SCiL 2019](https://aclanthology.org/W19-0105.pdf). Nominalized clauses (HPSG 2018). — [proceedings.hpsg.xyz](https://proceedings.hpsg.xyz/article/view/857). Valence-changing morphology: Curtis 2018 MS thesis listed among publications but not on the documentation index. — [matrix.ling.washington.edu](https://matrix.ling.washington.edu/). Action nominals thesis (Jan 2025) and light verb constructions thesis (Aug 2025). — [UW ResearchWorks](https://digital.lib.washington.edu/researchworks/items/18c7c71a-d2b4-4334-8672-a7d04509b63e/full)
- Generation: the questionnaire's "Test By Generation Options" page; grammars generate from MRS. — [Matrix docs](https://delph-in.github.io/docs/matrix/MatrixDocTop/). PyDelphin: "a suite of Python libraries for processing data and interacting with tools in the DELPH-IN ecosystem", MIT. — [PyDelphin](https://pydelphin.readthedocs.io/en/v0.9.2/index.html); GitHub pushed 2026-03-31 (API, 2026-10-22). — [delph-in/pydelphin](https://github.com/delph-in/pydelphin)
- Evaluation stance: "The matrix itself is not a grammar but a collection of generalizations across grammars. As such, it cannot be tested directly on corpora from particular languages". — [Bender & Flickinger 2005 / gee03](https://faculty.washington.edu/ebender/papers/gee03.pdf). Grammar Customization evaluated "using it to create grammars for seven languages from seven different language families". — [Bender et al. 2010, RoLC](https://link.springer.com/article/10.1007/s11168-010-9070-1)
- AGGREGATION: "Automatic Generation of Grammars for Endangered Languages from Glosses and Typological Information"; software: inference pipeline, MOM (morphotactic inference/visualisation), Xigt; publications listed up to Howell & Bender 2022 (NEJLT, "Building Analyses from Syntactic Inference in Local Languages"); no 2023–2025 entries. — [AGGREGATION project page](https://depts.washington.edu/uwcl/aggregation)
- Word-order and case inference (Bender, Goodman, Crowgey, Xia 2013): Lewis & Xia "tested their method in 97 languages and found that their system had 99% accuracy provided the IGT collections had at least 40 instances per language"; their own word-order inference: DEV1 0.900, DEV2 0.500, TEST 0.727 vs baselines 0.200/0.100/0.091; case-marking inference (GRAM method): DEV1 0.900, DEV2 0.900, TEST 0.545 vs baselines 0.400/0.500/0.455. — [W13-2710](https://aclanthology.org/W13-2710.pdf)
- Chintang end-to-end: the inferred grammar's results "are barely measurable in terms of coverage over running text, they nonetheless provide a proof of concept". — [Bender et al. 2014, W14-2206](https://aclanthology.org/W14-2206.pdf). Bender 2019 (ACL typology workshop): inference "Previously available: major constituent word order, case systems, case frames for verbs, case values for nouns"; Howell's extension "Testing on 15 languages: 5 dev, 5 initial held-out, 5 more held-out". — [Bender 2019 slides](https://faculty.washington.edu/ebender/papers/Typ-NLP-Bender.pdf)
- Licence and status: "The Grammar Matrix, including the core grammar and the customization system, is copyright (c) 2002- Emily M. Bender and licensed under the MIT license." — [matrix LICENSE](https://raw.githubusercontent.com/delph-in/matrix/trunk/LICENSE). Repo pushed 2026-08-04, no releases; README says it "is currently being ported from Subversion and converted from Python 2 to 3". — [delph-in/matrix](https://github.com/delph-in/matrix). The questionnaire host refused connections on 2026-10-22; docs now at delph-in.github.io.
- Toolbox: the questionnaire has an "Import Toolbox Lexicon" page (SIL Toolbox). — [Matrix docs](https://delph-in.github.io/docs/matrix/MatrixDocTop/)

### Inferences
- The choices-file section list is a ready checklist for what a profile (B) must state; its morphology section is a verb template as a directed graph of slots (order, inputs, obligatory, requires/forbids), already exercised on Zulu (prefix chain + final vowel) and Fore (v-final, erg-abs). It is trivial to read and write in Python (the Matrix's own `gmcs/choices.py`).
- MRS is the precedent for A: predicate-argument structure separate from variable properties (TENSE/ASPECT/MOOD on events; PERS/NUM/GEND on referents); predicate inventories are per grammar, so language neutrality is structural only.
- AGGREGATION is the precedent for inferring B from glossed, segmented data, but it stops at one categorical file, keeps no counts, and its running-text coverage was weak; our counted tables with provenance are a step beyond both.

### Gaps
- Exact figures for morphotactic inference (MOM) and word-class inference (Abui) not retrieved.
- Negation scope beyond sentential negation, and the `head=subj/obj` agreement mechanism on lexical rules, not verified from the Gender/Other Features pages.
- No hours-per-questionnaire figure; no claim that generated text is draft-quality; no comparison with TBTA, GF or Apertium in the Matrix literature.

## KPML / Nigel (systemic-functional generation)

### Takeaway
KPML realises a language-independent semantic input (SPL over an upper model) through system networks whose
choosers and realization statements are conditionalised per language (`:bu`, `:cz`), so shared and language-specific
grammar live in one network; it is Common Lisp, last documented in 2003 with no stated licence, and its authors'
effort figures are not in the sources fetched.

### Cited Findings
- KPML is "a graphically-based development environment for the construction, maintenance, and use of large-scale grammars written with the framework of Systemic-Functional Linguistics"; grammars for English, German, Dutch, Chinese, Spanish, Russian, Bulgarian, Czech; the English grammar is Nigel (Penman, USC/ISI, since the early 1980s); ANSI Common Lisp with CLIM; many grammars "freely available" for research; page dated January 2003; no licence named. — [What is KPML?](https://web.fb10.uni-bremen.de/kpml/kpml-description.htm)
- Use requirements: source code needs a commercial Common Lisp (Allegro, LispWorks; "the free trial or student versions" are insufficient) plus CLIM and a knowledge-representation language for the upper model; standalone Windows images need no Lisp licence. — [kpml-use-requirements](https://web.fb10.uni-bremen.de/kpml/kpml-use-requirements.htm). KPML 4 is "a beta release" compiling on ACL 5/6 and LispWorks 4.1+. — [kpml4 release notes](https://web.fb10.uni-bremen.de/kpml/kpml4-release-notes.htm)
- Bateman 1997, NLE 3(1):15–55: "the take-up of multilingual generation is being restricted by a critical lack both of large-scale linguistic resources suited to the generation task and of appropriate development environments"; KPML "is based on a new, generic approach to multilinguality in resource description". — [Cambridge Core listing](https://www.cambridge.org/core/product/0FBE61FE80BE05DFDAEEED6833D2873D)
- Agile (Bulgarian, Czech, Russian CAD/CAM manuals; Kruijff, Teich, Bateman et al., COLING 2000): "Starting from a language-independent semantic representation, the system drafts natural, continuous text"; design: "the input of the system should be specified irrespective of any particular output language"; "the text generation tasks which are common to the languages under consideration should be performed only once"; "More extensive differences between languages are handled by conditionalizing the text and sentence planner resources further according to language". Multilingual SPL: `(example :name D0-Text1 :logicalform (s / DM::draw :en :ru :PROPOSAL-Q & PROPOSAL :bu :cz :EXIST-SPEECHACT-Q & NOSPEECHACT :actee (d / DM::polyline)))`. Shared system for Bulgarian and Czech:
  ```lisp
  (gate :name MEDIUM-QUALIFIER :inputs processual-mediated
        :outputs ((1.0 medium-qualifier
                    (:bu :cz preselect Medium nominal-group)
                    (:cz preselect Medium noun-gen-case)
                    (:bu insert Mediumqualifiermarker)
                    (:bu lexify Mediumqualifiermarker na)))
        :region QUALIFICATION)
  ```
  "The difference in structure only shows in syntagmatic realization and is separate from the functional description: For Bulgarian, the postmodifier marker na ('of') is inserted, and for Czech, the nominal group realizing the Postmodifier is attributed genitive case." Lexical choice: a domain concept "is annotated with one or more lexical items from each language. If there is more than one item per language, the choice is constrained by features imposed by the grammar" (perfective/imperfective). — [C00-1069](https://aclanthology.org/C00-1069.pdf)

### Inferences
- KPML's conditionalised realization statements are a precedent for a single rule table keyed by language and feature (our rules per language with shared feature names); its "perform common tasks once" principle matches drafting from one universal clause spec.
- Nothing in KPML is learned from data or counted; its input requires an upper-model semantics richer than our MACULA-derived spec; the platform is effectively unmaintained (2003 page, beta KPML 4, commercial Lisp).

### Gaps
- No licence statement found; no Nigel size figures; no effort-per-language figures in the pages fetched (the 1997 NLE paper is paywalled).

## LFG / XLE and ParGram

### Takeaway
ParGram keeps parallelism at f-structure through a shared inventory of grammatical features (SUBJ/OBJ, tense, aspect,
number, gender) while c-structure varies; it is still active in 2026 (Cantonese, Irish; Wolof was added 2019–2020 with
noun classes, causatives and applicatives), but XLE is under a PARC non-commercial, confidential licence, so it is a
design reference only.

### Cited Findings
- "The Parallel Grammar (ParGram) Project is a large-scale, ongoing effort aimed at developing parallel LFG grammars for typologically diverse languages... implemented in the Xerox Linguistic Environment (XLE)"; f-structure "encodes grammatical functions (e.g., SUBJ, OBJ) and associated features such as tense, aspect, number, and gender"; ParGramBank treebanks "maintain a level of parallelism in the f-structure, achieved via a shared inventory of grammatical features (King, 2004)"; ParGramBank "originally comprised parallel treebanks for twelve languages from six families, based on a shared corpus of 101 sentences"; treebanks are "pure parsebanks"; "Regression testing using testsuite sentences is an intrinsic part of the XLE grammar development cycle". — [Lam & Uí Dhonnchadha, BriGap-3 2026](https://aclanthology.org/2026.brigap-1.11.pdf)
- Earlier: XLE has "an efficient parser and generator for LFG grammars"; the same grammars parse and generate, with Optimality Theory marks controlling generation; languages in 2007: English, Danish, French, German, Japanese, Malagasy, Norwegian, Turkish, Urdu, Welsh. — [ICON 2007 tutorial](https://ling.sprachwiss.uni-konstanz.de/pages/home/butt/main/material/icon-tutorial-2007.pdf); [Butt et al. 1999](https://aclweb.org/anthology/1999.mtsummit-1.20.pdf)
- Wolof (Dione): "the first parser reported for Wolof... part of ParGram"; coverage includes noun classes, clefts, copulas, causatives, applicatives; 72.72% full parses, 27.27% partial on the test sentences. — [LREC 2020](https://aclweb.org/anthology/2020.lrec-1.631.pdf); grammar "implemented in XLE with finite-state transducers for morphology". — [NJAS 28(3) 2019](https://njas.fi/njas/article/view/449)
- Licence: "NON-COMMERCIAL XLE SOFTWARE LICENSE Rev 2013/05/22" between PARC and the licensee; "Non-Commercial Purposes means use other than for commercial purposes or financial gain of any kind"; "Licensee agrees to maintain the confidentiality of the Licensed Software". — [XLE licence PDF](https://ling.sprachwiss.uni-konstanz.de/pages/xle/XLE-Non-Commercial-License.pdf). XLE releases in 2015 and 2017 required a licensee account. — [XLE list 2017](https://mailman-proxy-prod.kim.uni-konstanz.de/mailman3/hyperkitty/list/xle@mailman.uni-konstanz.de/thread/TNCG5LRKCMLLYS2DMVPMID35YX5NJI2S/)

### Inferences
- ParGram's "shared feature inventory at f-structure, free c-structure" is the same division as A (shared feature names) vs B/C (language-specific realization); King 2004's feature inventory is a candidate checklist for the universal spec's attribute names.
- XLE's licence rules it out as a component; LFG grammars are categorical (OT marks give preferences, not counts).

### Gaps
- King 2004's feature list not fetched; whether the Wolof grammar is public, and whether any XLE generation output has been evaluated as draft text, not found.

## SIL tools: FLEx parsers and Grammar Sketch, FLExTrans, CARLA (AMPLE/STAMP), Adapt It

### Takeaway
SIL's stack already contains a parts representation (FLEx affixes with morphosyntactic features, XAmple
item-and-arrangement and HermitCrab item-and-process parsers that also synthesise), a transfer layer written in
Apertium's rule format (FLExTrans, MIT, Python; a GUI Rule Assistant that generates agreement rules and, since
August 2026, an LLM "AI Rule Studio" that drafts rules), and a 1980s precedent for related-language adaptation
(CARLA) whose authors judged the output "only a rough draft for a native speaker to edit"; Adapt It is a translation
memory with no linguistic analysis.

### Cited Findings
- FLEx licence and version: "GNU Lesser General Public License" (link to LGPL 2.1); FieldWorks 9.3.12 dated 12 October 2026; the software handles "prefixes, suffixes, and infixes", parses words "manually or automatically", and can "generate a full grammar description from your input" (the Grammar Sketch). — [software.sil.org/fieldworks](https://software.sil.org/fieldworks/). GitHub pushed 2026-10-21 (API). — [sillsdev/FieldWorks](https://github.com/sillsdev/FieldWorks)
- Parsers: HermitCrab is "an item-and-process, rule-based, morphological/phonological parser" (NuGet, SIL.Machine.Morphology.HermitCrab). — [nuget.org](https://www.nuget.org/packages/SIL.Machine.Morphology.HermitCrab). In 2012 Andy Black noted "Required features is not implemented for Hermit Crab" while "The XAmple parser does correctly handle Required features". — [flex-list 2012](https://groups.google.com/g/flex-list/c/YDLEhT8Bn4A). SIL.Machine (MIT, C#) includes "a rule-based engine based on HermitCrab", Thot SMT, IBM 1-4/HMM/FastAlign; pushed 2026-10-22; machine.py MIT, pushed 2026-10-21. — [sillsdev/machine](https://github.com/sillsdev/machine)
- A 2025 critique: FLEx "makes many – more or less implicit – assumptions about the user and their computer; the language data; the (morphological) structure of the study language; and the types of output required after analysis". — [Language 101(3), 2025, DOI 10.1353/lan.2025.a969622](https://muse.jhu.edu/article/969622)
- Python access: "Python for FlexTools and FLEx 9.1" (LCM from Python). — [FlexTools technical documentation](https://github.com/cdfarrow/flextools/wiki/Technical-documentation)
- FLExTrans: "free, MIT-licensed machine translation software for low-resource languages" combining FLEx with Apertium; analysis = FLEx parsers with linguist-approved analyses; transfer = sense linking + transfer rules; synthesis = "target morphemes are assembled into coherent text that follows linguistic constraints"; "works best between related languages"; large differences mean "lots of work to get translation working"; testimonial pair Ayta Mag-Indi / Ayta Mag-Antsi, "60 chapters" adapted; version 3.16, 26 August 2026. — [software.sil.org/flextrans](https://software.sil.org/flextrans/). Repo MIT, 4,921 commits, pushed 2026-10-21. — [rmlockwood/FLExTrans](https://github.com/rmlockwood/FLExTrans)
- Origin: Lockwood, UW MS thesis 2015, "A Linguist-Friendly Machine Translation System for Low-Resource Languages": analysis-transfer-synthesis with FLEx, Apertium and STAMP, "a proof of concept" tested on Persian and Gilaki. — [UW ResearchWorks](https://digital.lib.washington.edu/researchworks/handle/1773/33999)
- Rule Assistant (3.11): "a graphical way to define things like agreement and then it generate[s] the needed Apertium rules automatically", which "might consist of dozens of sets of conditional logic blocks"; constituent reordering and affix changes supported. — [FLExTrans 3.11 news](https://lingtransoft.info/app/flextrans/news/flextrans-version-311-released). 3.8 added HermitCrab synthesis: "FLExTrans will correctly synthesize target morphemes to produce words using the HermitCrab grammar constraints defined in the project". — [FLExTrans 3.8 news](https://lingtransoft.info/app/flextrans/news/flextrans-version-38-released)
- 3.16 (2026-08-26): "AI Rule Studio": users "describe a transfer rule or macro in your own words" and an AI provider (Gemini, Anthropic, OpenAI) writes, modifies or explains it, grounded in "your FLEx project's categories, features, and affixes, plus sample rules"; each rule "validated and shown in a preview before it goes into the rules file"; One-project mode for "very closely related languages"; Rule Assistant rebuilt with "support for a 'many' noun class in Bantu noun class processing"; Paratext import/export handles `\id`. — [flex-list, Release of FLExTrans 3.16](https://groups.google.com/g/flex-list/c/fCi1g7Q7fDk)
- CARLA: STAMP "works with AMPLE to adapt text between closely related languages"; "its output is only a rough draft for a native speaker to edit"; AMPLE "is built on an item-and-arrangement approach and handles nonconcatenative morphology only indirectly"; all listed as discontinued. — [STAMP](https://lingtransoft.info/node/633); [AMPLE](https://lingtransoft.info/node/631); [CARLA Studio](https://lingtransoft.info/node/691). Weber & Mann 1981 set the same goal: output close enough for a native speaker to correct. — [Weber & Mann 1981](https://preview.aclanthology.org/setup/J81-3003)
- Adapt It: "a Machine Assisted Human Translation editor, and no linguistic analysis is performed"; a Knowledge Base translation memory of word/phrase adaptations inserted automatically; reads and writes USFM. — [adapt-it.org](https://adapt-it.org/oldindex.htm). Dual-licensed "Common Public License, version 0.5" or "GNU Lesser General Public License, version 2.1"; C++/wxWidgets; 5,254 commits, pushed 2026-09-26. — [LICENSING.txt](https://raw.githubusercontent.com/adapt-it/adaptit/master/license/LICENSING.txt); [adapt-it/adaptit](https://github.com/adapt-it/adaptit)
- TBTA and FLExTrans were "tested alongside" each other in 2024 with encouraging "synergy". — [Wycliffe Canada 2024 TBTA update](https://wycliffe.ca/wp-content/uploads/2024/05/2024-SUMMER-TBTA-Project-Update.pdf)

### Inferences
- FLExTrans is the one live, licence-clean (MIT), Python system in this survey that does what layer C does for related languages: a frame (FLEx features + affix glosses) is carried across and a synthesiser fills in the forms; its Rule Assistant is a GUI version of "concord rule -> generated rule set". Its August 2026 move to LLM-drafted rules with validation and preview is the same division of labour we plan (agent proposes, rule file holds it).
- A Bible team's FLEx project is a natural source for B: affix inventory, features, allomorph environments, and (via Grammar Sketch) a prose profile.

### Gaps
- FLExTrans user documentation (UserDoc.htm) and the Doc folder returned 404, so the exact target-word representation after transfer and the Rule Assistant's generated XML were not seen.
- No published FLExTrans quality or effort figures; no account of CARLA's rule formats beyond the catalogue pages (403 on fetch).

## Linguist's Assistant (the TBTA lineage, for comparison only)

### Takeaway
LA/TBTA is the only system here built for exactly our use case: a controlled, English-influenced semantic
representation with a rich feature system, a linguist-written transfer grammar and a synthesizing grammar "designed
to resemble... descriptive grammars", with feature-copying rules for agreement and table spellout rules for affix
sets; it reports 40–50 hours for a 500-sentence grammar introduction, rule counts per chapter that fall quickly, and
4–7x translator productivity on Jula, Kewa and Korean.

### Cited Findings
- Components: ontology, semantic representations (supplied), lexicon, transfer grammar, synthesizing grammar (user-supplied). Semantic representations are "a controlled, English influenced metalanguage augmented by a feature system"; features such as Object Number (Singular, Dual, Trial, Quadrial, Plural, Paucal), Participant Tracking (First Mention, Routine, ...), Proximity, Event Time (Discourse, Present, Immediate Past, Earlier Today, Yesterday, ...), Illocutionary Force, Salience Band (Longacre), Semantic Role (Agent, Patient, ..., Addressee). — [Allman, Beale & Denton, INLG 2012](https://aclanthology.org/W12-1510.pdf)
- Transfer grammar: nine rule types, including complex concept insertion, styles of direct speech (five features on every direct-speech proposition), relative clause strategies (Accessibility Hierarchy), collocation correction, theta grid adjustment, structural adjustment ("build clause chains from coranking propositions"). — [W12-1510](https://aclanthology.org/W12-1510.pdf)
- Synthesizing grammar: feature copying rules ("certain Jula nouns agree in person and number with their object nouns, so a feature copying rule copies the person and number of the object noun to the verb. Then a spellout rule adds the appropriate morphology"); spellout rules of four kinds: "(i) simple spellout rules which add a prefix, suffix, infix, circumfix, or a new word... (ii) form selection rules... (iii) morphophonemic rules... (iv) table spellout rules which group a common set of affixes together into a single rule" (example: Kewa tense suffixes); clitic rules (pre-, second-position, post-clitics; Kewa `-me`); pronoun rules; word morphophonemic rules. — [W12-1510](https://aclanthology.org/W12-1510.pdf)
- Effort and learning curve: "working through the Grammar Introduction took approximately 40 to 50 hours" (about 500 sentences); "the number of new grammatical rules required per chapter of text decreased very quickly". Productivity ratio of edited to manually translated words: Jula 4.3, Kewa 6.7, Korean 4.6; blind comparison of edited LA texts vs manual: Jula 12/11/17 (LA better/manual better/equal), Korean 88/71/33. Languages: English, Korean, Kewa (PNG), Jula, North Tanna (Vanuatu); proof-of-concept Spanish, Urdu, Tagalog, Chinantec, Angas. — [W12-1510](https://aclanthology.org/W12-1510.pdf)
- Tagalog: "when experienced mother-tongue translators use the drafts generated by LA, their productivity is more than tripled without any loss of quality". — [Allman & Sipacio, Tagalog paper](https://www.national-u.edu.ph/wp-content/uploads/2016/08/Linguist%E2%80%99s-Assistant-Gleaning-a-Tagalog-Lexicon-and-Grammar-from-a-Small-Lightly-Annotated-Corpus.pdf)
- TBTA in 2024: "combines a grammar analysis of a target language with book-by-book templates"; templates "created for each book of the Bible". — [Wycliffe Canada](https://wycliffe.ca/?p=16164)

### Inferences
- LA's synthesizing grammar is a rule inventory for layer C: feature copying (= concord), table spellout (= our affix cells), clitic placement, morphophonemics. Its rules are categorical and hand-written; our difference is counts, provenance and learning from part-aligned corpora.
- Kewa (a Papuan language) is the one documented case of this family of systems on a Papuan clause-chaining language.

### Gaps
- No source compares TBTA/LA with GF, the Grammar Matrix or Apertium; the LA paper cites none of them. TBTA details are left to the other researcher.

## SimpleNLG, its ports, jsRealB/pyrealb, Ninai/Udiron, and the Bantu grammar engines

### Takeaway
Surface realisers (SimpleNLG, jsRealB) take a syntactic phrase spec with features (TENSE, NEGATED, NUMBER...) and
apply hand-written per-language morphology and ordering; each port is a separate rewrite for one language, none
covers a Bantu or Papuan language, and the Bantu NLG work (Keet & Khumalo, Byamugisha) concludes that templates fail
and a slot grammar is required, with CFGs over the verb template and phonological conditioning as a last step.

### Cited Findings
- SimpleNLG: "licensed under the terms and conditions of the Mozilla Public Licence (MPL) version 2.0"; versions before 4.0 cannot be used commercially; V4.5.0; Java; English only officially, with ports to French, Italian, Spanish, Brazilian Portuguese, Dutch, German, Galician; grammatical coverage "limited compared with KPML and FUF/SURGE"; repo pushed 2024-12-06. — [simplenlg/simplenlg](https://github.com/simplenlg/simplenlg). SimpleNLG-EnFr is the one bilingual port; SimpleNLG-GL (English/Spanish/Galician) on 4.4.8; SimpleNLG-ZH for Mandarin; also Telugu. — [Data-to-text bilingual generation (arXiv 2311.14808)](https://arxiv.org/pdf/2311.14808); [SimpleNLG-GL](https://github.com/citiususc/SimpleNLG-GL)
- jsRealB: "A JavaScript bilingual text realizer" (English, French) with constituent and dependency notations, lexicons of 33,926 English and 52,512 French entries, "conjugation and declension tables" in `rule-en.js`/`rule-fr.js`; Apache-2.0; the lapalme repo (4.5, Sept 2022) is superseded by rali-udem/jsRealB (pushed 2026-09-12); pyrealb is the Python companion, GPL-3.0 (pushed 2026-09-13). — [lapalme/jsRealB](https://github.com/lapalme/jsRealB); GitHub API 2026-10-22.
- Surface Realisation shared tasks: UD trees to inflected, ordered sentences; 2018 shallow track ten languages, deep track three; 2020 entries used BART-style models. — [DCU, underspecified UD inputs](https://doras.dcu.ie/28623); [MSR 2020 proceedings](https://aclanthology.org/2020.msr-1)
- Ninai/Udiron: "Mahir Moshed has also created the Ninai and Udiron libraries in Python to prototype the realizer". — [Abstract Wikipedia update 2022-09-23](https://meta.wikimedia.org/wiki/Abstract_Wikipedia/Updates/2022-09-23). Udiron is "a natural language generation system that uses Wikidata lexemes as primitives", builds UD-like syntax trees, Apache 2.0, Python, requires the `tfsl` library. — [gitlab udiron README](https://gitlab.com/mahir256/udiron/-/raw/main/README.md). Ninai is "a statement construction system", Apache 2.0, Python 3.9+. — [gitlab ninai README](https://gitlab.com/mahir256/ninai/-/raw/main/README.md). Wikimedia judged Ninai/Udiron, GF and a template language "existence proofs that the goals are achievable, not... settled answers" (2022-11-04). — [Abstract Wikipedia update](https://meta.wikimedia.org/wiki/Abstract_Wikipedia/Updates/2022-11-04)
- isiZulu complex verb (Keet & Khumalo 2017): base template "[NEG] [SC] [T/A] [MOD] [OC] [VR] [C] [A] [R] [P] [FV]" (CARP extensions keep their order, any subset may appear; wh-modifiers -ni, -nini, -phi after FV); CFG rules "v -> pre vr post a wh | npre vr post i wh | ppre vr e | vr st a | excl s cont o vr post a", "pre -> s | s m | s t m | s asp m | s o | s m o | s t m o | s asp m o", "post -> c | c a | c a r | c a p | c r | ..."; the grammar is context-free, "beyond a regular grammar, hence, beyond a FSM"; tested in JFLAP (NLTK considered); all correct strings accepted, "*ngiveli" wrongly accepted for lack of phonological conditioning; brute-force parse of "niboniselana" needed 773,240 nodes; phonological conditioning (e.g. "if s==u then pl=aw, else pl=aw or mawu or ma") and tone left for future work. — [arXiv 1612.06581](https://ar5iv.labs.arxiv.org/html/1612.06581)
- Runyankore grammar engine (Byamugisha, Keet, DeRenzi, INLG 2017): templates "shown to be inapplicable to Bantu languages, due to their characteristic agglutinative structure"; Runyankore has "14 tenses", "20 noun classes"; example `ti-tu-ka-ki-mu-reet-er-a-ho-ga-nu` 'We have never ever brought it to him'; verb CFG with the passive in the extension slot: `S -> IG F M V S EX F V`, `IG -> P N IT`, `P N -> ti | ni`, `IT -> a | o | n | tu | mu | ba | gu | gi | ri | ga | ki | bi | e | zi | ru | tu | ka | bu | ku | gu | ga`, `EX -> w | er | erer | ir | zi | is | n | ur | uur | gur | ...`, `F V -> a | e | ire`; subject prefix looked up from the noun class (`getNC`, `getSubjectPrefix`); phonological conditioning "considered as a last step of text generation" with case-by-case rules (baona -> boona but baonka -> bonka); evaluated with 100 rural speakers and three linguists, most text judged grammatical and understandable, "over 60%... regarded all the text generated by our system to have been authored by a human being". — [W17-3514](https://aclanthology.org/W17-3514.pdf). Later: Meinhof's 1948 noun-class specification "inadequate for computational use", redefined into 53 classes from 29; generic pluraliser over 93% accuracy. — [Byamugisha, INLG 2020](https://aclweb.org/anthology/2020.inlg-1.34.pdf)

### Inferences
- The Bantu NLG literature converges on our design: a verb template of ordered slots, concord looked up from the noun class, extensions as an ordered sub-chain, and phonological/tonal adjustment as a separate final pass. Keet's parse-cost figures argue for deterministic slot filling (our frame) rather than parsing full forms.
- SimpleNLG-style realisers show the per-language cost of hand-written morphology (one port per language, ~2013–2018, none for Africa or Oceania); for an unknown language the realiser's tables must be learned, which these systems never do.

### Gaps
- The Ninai/Udiron Semantic Web Journal paper (SW-243564) was unreachable (503 three times), so its languages and per-language contributor work are unverified.
- No SimpleNLG port for any African or Papuan language found; jsRealB's agreement mechanism not described in the README.

## Key question: What does a GF Bantu concrete grammar look like, and how much is learnable tables?

### Takeaway
The Zulu grammar is mostly tables and string-pattern operations keyed by a small parameter algebra (class gender x
number x person, SC/OC allomorph contexts, root initial/syllable features); those tables are exactly what part-aligned
corpora can fill, while the control logic (which chain for which VForm) is a short hand-written list.

### Cited Findings
- `ResZul.gf` is 85 KB / 2,108 lines; its core objects are `ClassGender` (11 values), `Agr`, `SCForm` (9 allomorph contexts), `OCForm` (5), `RForm` (5), `subjConcLookup : Agr => SCForm => Str`, `regVerb` building `R_a`, `R_ile` etc. by string patterns, tense/polarity prefix chains per `VForm`, and sandhi functions (`prefix_nasal`). — [ResZul.gf](https://raw.githubusercontent.com/GrammaticalFramework/gf-rgl/master/src/zulu/ResZul.gf)
- Runyankore/Rukiga: 11 verb slots; verbs built "from the radical up to its full form" at sentence level; 38 imperative-to-perfective rules; `Noun = {s : Number => NounState => Str ; gender : Gender}`. — [LREC 2020](https://aclanthology.org/2020.lrec-1.347.pdf)
- Swahili on the Bantu functor reused 91.41% of syntax rules and 71.11% of paradigms from Kikamba/Ekegusii. — [IJEECS 2023](https://ijeecs.iaescore.com/index.php/IJEECS/article/download/26444/17265)

### Inferences
- For Zinza, a profile that declares the same objects (class set, concord tables by context, FV forms, extension order) and fills them from counts is a learned equivalent of `ResZul.gf`'s data; the Bantu functor's 69–91% reuse suggests a Bantu family profile can seed most of it before any Zinza data.
- Nothing in GF handles tone marks; Zinza's tone-distinguished prefixes need our own allomorph-by-tone cells.

### Gaps
- The share of `ResZul.gf` lines that are pure tables vs control code was not measured.

## Key question: What is in a Grammar Matrix choices file, and how well does AGGREGATION infer it?

### Takeaway
A choices file is ~20 sections of `key=value` lines (word order, number, person, gender, case, direct-inverse, TAM,
other features, negation, coordination, questions, information structure, argument optionality, clausal modifiers
and complements, nominalization, possession, evidentials, lexicon, morphology with position classes); AGGREGATION
infers word order and case from IGT at 0.5–0.9 accuracy on small held-out sets (99% on 97 languages for the
underlying word-order method with 40+ examples) and morphotactics via MOM, with weak running-text coverage.

### Cited Findings
- Sections and the morphology model as listed above. — [Matrix docs](https://delph-in.github.io/docs/matrix/MatrixDocTop/); [MatrixDoc_Morphology](https://delph-in.github.io/docs/matrix/MatrixDoc_Morphology/)
- Zulu and Fore regression files as quoted above. — [Zulu](https://raw.githubusercontent.com/delph-in/matrix/trunk/tests/regression/choices/Zulu); [Fore](https://raw.githubusercontent.com/delph-in/matrix/trunk/tests/regression/choices/Fore)
- Accuracies: word order DEV1 0.900 / DEV2 0.500 / TEST 0.727; case GRAM 0.900 / 0.900 / 0.545; Lewis & Xia 99% on 97 languages with at least 40 IGT instances. — [W13-2710](https://aclanthology.org/W13-2710.pdf). Chintang coverage "barely measurable". — [W14-2206](https://aclanthology.org/W14-2206.pdf)

### Inferences
- Our part-aligned corpora (whole Bible books) are far larger than the 40-instance IGT sets AGGREGATION works from, so the inference of order, case strategy and slot order should be more reliable than theirs; the choices-file schema is the right target to emit from the profile for interoperability (and for a Matrix/ACE generation experiment if ever wanted).

### Gaps
- MOM morphotactic-inference accuracy figures not retrieved.

## Key question: How do Apertium transfer rules and generators represent the same information, and what rule-learning results exist?

### Takeaway
Apertium puts the frame in a tag string and the form in a reversible transducer, with concord as attribute copying
in transfer; learned rules exist (alignment templates, GATs/ruLearn) with quality near hand-written rules for related
pairs from a few hundred to a few thousand sentence pairs, but they are categorical, uncounted and GPL.

### Cited Findings
- See the Apertium section: `.dix`, `.t1x`, `.rtx` snippets and the ruLearn/GAT results. — [HOWTO](https://wiki.apertium.org/wiki/Apertium_New_Language_Pair_HOWTO); [Apertium-recursive](https://wiki.apertium.org/wiki/Apertium-recursive); [ruLearn](https://ufal.mff.cuni.cz/pbml/106/art-sanchez-cartagena-perez-ortiz-sanchez-martinez.pdf); [JAIR 2009](https://arxiv.org/pdf/1401.5700)
- FLExTrans writes its transfer rules in Apertium's format and generates them from a GUI (Rule Assistant) and, since 2026-08, from an LLM with validation. — [FLExTrans 3.11](https://lingtransoft.info/app/flextrans/news/flextrans-version-311-released); [3.16](https://groups.google.com/g/flex-list/c/fCi1g7Q7fDk)

### Inferences
- The combination "Apertium rule format + FLEx affix features + HermitCrab/STAMP synthesis" is the SIL-world realisation of layer C for related languages; our learned tables could be exported to that format for teams who use FLExTrans.

### Gaps
- No published BLEU for the 2015 CSL paper; `apertium-streamparser` and lttoolbox Python bindings not verified.

## Key question: Which systems produce draft-quality text, and what did authors conclude about scaling?

### Takeaway
Only LA/TBTA (hand-written grammars, 40–50 h for the basics, 4–7x translator productivity) and the Runyankore engine
(human-rated grammatical in a narrow domain) report draft-quality output; GF's authors put a new language at 2–6
person-months by a trained linguist-programmer; Apertium's authors restrict strong results to related pairs; the
Matrix evaluates by test-suite coverage, not by text quality; CARLA's and FLExTrans's authors describe output as a
rough draft for native-speaker editing.

### Cited Findings
- LA: Grammar Introduction "approximately 40 to 50 hours"; productivity ratios 4.3 / 6.7 / 4.6; edited texts judged equal to manual. — [W12-1510](https://aclanthology.org/W12-1510.pdf)
- GF: "two to six person months"; "a basic rendering system for a new language can be released after a few weeks' work"; six bachelor students after "a 4-hour crash course" built a 1,235-locality system in 12 weeks. — [Ranta preprint](https://www.grammaticalframework.org/~aarne/preprint-AAM-textgen.pdf)
- Apertium: 51 pairs, 3 between unrelated languages; "especially suitable for related language pairs". — [Khanna 2021](https://d-nb.info/1249211654/34); [arXiv 2109.00486](https://arxiv.org/pdf/2109.00486)
- Matrix: "cannot be tested directly on corpora"; library coverage 88.4% / overgeneration 1.5% on test suites; Chintang running-text coverage "barely measurable". — [gee03](https://faculty.washington.edu/ebender/papers/gee03.pdf); [C18-1249](https://aclanthology.org/C18-1249.pdf); [W14-2206](https://aclanthology.org/W14-2206.pdf)
- CARLA/STAMP: "only a rough draft for a native speaker to edit". — [STAMP](https://lingtransoft.info/node/633). FLExTrans: large differences mean "lots of work to get translation working". — [software.sil.org/flextrans](https://software.sil.org/flextrans/)
- Runyankore: 100 speakers + 3 linguists, most sentences grammatical and understandable. — [W17-3514](https://aclanthology.org/W17-3514.pdf)
- Agile/KPML: output "intended to serve as drafts for final revision". — [C00-1069](https://aclanthology.org/C00-1069.pdf)

### Inferences
- Every full-generation system in this survey either needs months of expert grammar writing per language or restricts itself to related pairs or narrow domains; that supports our choice to generate only a grammatical frame per clause and let the agent choose stems and wording.
- The one quantified draft-quality result in a Bible-translation setting (LA/TBTA) came from hand-written feature-copying and table-spellout rules, which are the kind of rules our layer C would learn rather than write.

### Gaps
- No head-to-head evaluation of any two of these systems on the same language or text exists in the sources found.

## Key question: How does each treat word-internal structure (prefix chains, suffixes, tone)?

### Takeaway
Three traditions use a parts representation close to ours: the Grammar Matrix's position classes (slot graph with
features), FLEx/HermitCrab/AMPLE affixes with features and environments, and the Bantu NLG CFGs over the verb template;
GF and Apertium's lexc keep morphemes as strings concatenated by rules (GF's `BIND`, lexc continuation classes with flag
diacritics); none of them models written tone marks.

### Cited Findings
- Matrix: position classes with order prefix/suffix, inputs, obligatory, requires/forbids; "does not cover morphophonological phenomena". — [MatrixDoc_Morphology](https://delph-in.github.io/docs/matrix/MatrixDoc_Morphology/); [Zulu choices](https://raw.githubusercontent.com/delph-in/matrix/trunk/tests/regression/choices/Zulu)
- GF Zulu: morphemes glued with `BIND`, allomorphs by context tables, sandhi by string patterns; Runyankore: verb built "from the radical up". — [ResZul.gf](https://raw.githubusercontent.com/GrammaticalFramework/gf-rgl/master/src/zulu/ResZul.gf); [LREC 2020](https://aclanthology.org/2020.lrec-1.347.pdf)
- Apertium Swahili: lexc continuation chain with flag diacritics carrying person/tense from prefix to final vowel. — [swa.lexc](https://raw.githubusercontent.com/apertium/apertium-swa/master/apertium-swa.swa.lexc)
- FLEx: prefixes, suffixes, infixes; XAmple item-and-arrangement, HermitCrab item-and-process with phonological rules; AMPLE "handles nonconcatenative morphology only indirectly". — [software.sil.org/fieldworks](https://software.sil.org/fieldworks/); [nuget HermitCrab](https://www.nuget.org/packages/SIL.Machine.Morphology.HermitCrab); [AMPLE](https://lingtransoft.info/node/631)
- LA: simple spellout (prefix, suffix, infix, circumfix), form selection, morphophonemic and table spellout rules; clitic rules by position. — [W12-1510](https://aclanthology.org/W12-1510.pdf)
- Bantu CFGs: Keet & Khumalo's template and Byamugisha's `S -> IG F M V S EX F V` with phonological conditioning last. — [arXiv 1612.06581](https://ar5iv.labs.arxiv.org/html/1612.06581); [W17-3514](https://aclanthology.org/W17-3514.pdf)
- Tone: Keet & Khumalo do not model tone (only cite Ekegusii difficulties); GF Zulu has no tone handling; no system in this survey represents tone marks. — [arXiv 1612.06581](https://ar5iv.labs.arxiv.org/html/1612.06581); [ResZul.gf](https://raw.githubusercontent.com/GrammaticalFramework/gf-rgl/master/src/zulu/ResZul.gf)

### Inferences
- Our prefix+stem+suffix units align with the Matrix position-class graph and with FLEx's affix model, so a profile can be exported to a choices file or a FLEx-like affix list without loss; tone-conditioned allomorphs (Zinza) and tone marks on affixes (Kuni) are an addition no precedent supplies.

### Gaps
- HermitCrab's generation API (whether it synthesises directly from lemma + feature bundle) was not verified beyond FLExTrans's statement that it synthesises with HermitCrab constraints.

## Key question: What to borrow for layers B and C, and what not

### Takeaway
Borrow GF's parameter algebra and per-clause slot assembly, the Matrix's choices-file schema and position-class
graph, Apertium's `.rtx` attribute/agreement one-liners as a text form, LA's rule-type inventory (feature copying,
table spellout, clitic placement, morphophonemics), and FLExTrans's "proposed rule -> validation -> preview" loop;
do not borrow full generation, categorical-only rules, or any GPL/non-commercial component.

### Cited Findings
- Licence summary (as found): GF compiler GPL, runtime and RGL LGPL/BSD with free application-grammar licensing — [gf-core LICENSE](https://raw.githubusercontent.com/GrammaticalFramework/gf-core/master/LICENSE), [gf-rgl LICENSE](https://raw.githubusercontent.com/GrammaticalFramework/gf-rgl/master/LICENSE); Grammar Matrix MIT — [LICENSE](https://raw.githubusercontent.com/delph-in/matrix/trunk/LICENSE); PyDelphin MIT — [PyDelphin](https://pydelphin.readthedocs.io/en/v0.9.2/index.html); Apertium GPL-2.0/3.0 — [apertium](https://github.com/apertium/apertium), [apertium-python](https://github.com/apertium/apertium-python); ruLearn GPL v3 — [PBML 2016](https://ufal.mff.cuni.cz/pbml/106/art-sanchez-cartagena-perez-ortiz-sanchez-martinez.pdf); XLE PARC non-commercial, confidential — [XLE licence](https://ling.sprachwiss.uni-konstanz.de/pages/xle/XLE-Non-Commercial-License.pdf); KPML no stated licence, commercial Lisp for source — [kpml-use-requirements](https://web.fb10.uni-bremen.de/kpml/kpml-use-requirements.htm); FLEx LGPL 2.1 — [software.sil.org/fieldworks](https://software.sil.org/fieldworks/); SIL.Machine and machine.py MIT — [sillsdev/machine](https://github.com/sillsdev/machine); FLExTrans MIT — [software.sil.org/flextrans](https://software.sil.org/flextrans/); Adapt It CPL 0.5 / LGPL 2.1 — [LICENSING.txt](https://raw.githubusercontent.com/adapt-it/adaptit/master/license/LICENSING.txt); SimpleNLG MPL 2.0 — [simplenlg](https://github.com/simplenlg/simplenlg); jsRealB Apache-2.0, pyrealb GPL-3.0 (GitHub API 2026-10-22); Ninai/Udiron Apache 2.0 — [udiron README](https://gitlab.com/mahir256/udiron/-/raw/main/README.md)
- Categorical vs counted: GF probabilities on trees only — [GF shell](https://www.grammaticalframework.org/doc/gf-shell-reference.html); Apertium transfer categorical with optional lexicalised weights, lexical selection weighted — [Khanna 2021](https://d-nb.info/1249211654/34); Matrix categorical with counts only inside AGGREGATION's inference — [W13-2710](https://aclanthology.org/W13-2710.pdf); LA and KPML categorical — [W12-1510](https://aclanthology.org/W12-1510.pdf), [C00-1069](https://aclanthology.org/C00-1069.pdf)

### Inferences
- A rule table of the form `language, cell (feature bundle), slot, form, count, source` generalises every precedent above: it can be rendered as a GF `table`, a Matrix `verb-pcN_lrtM`, an `.rtx` attribute line, or an LA table spellout rule, which keeps the door open to any of them as a backend while our agents read only the compact table.
- Full generation is the wrong target: each full generator here needs either months of expert work per language or a related source language; the frame-only prediction keeps the LLM's lexical and stylistic choices and limits the rules to what counts can support.

### Gaps
- No precedent carries provenance per rule (corpus vs agent vs team decision); that design is ours alone, with FLExTrans's 2026 LLM-drafted-but-validated rules as the nearest workflow analogue.
