# pdf-extract: open findings

Notes for a future session. Everything here is **unfixed**; fixed work is in
the git log. Recorded 2026-10-13.

Fork master at time of writing: `8b0d710`. Three fixes landed this session
(`7eab691`, `b003161`) plus the fuzz target.

---

## 1. `Tj` panics on a non-string operand — CONFIRMED, reproducible

`src/lib.rs` (the `"Tj"` arm of `process_stream`):

```rust
_ => { panic!("unexpected Tj operand {:?}", operation) }
```

Found by the fuzzer **within ten executions**. Reproduce by taking any valid
one-page document and changing `Tf` to `Tj` in the content stream:

```
BT /F1 24 Tj 72 720 Td (AAA) Tj ET
```

That leaves a text-showing operator with a numeric operand and no font ever
set. Any truncated or lightly corrupted content stream can produce this.

**Why it wasn't fixed here:** this arm is the same territory as upstream PRs
#148, #154 and #158, which all propose competing "guard the operators"
rewrites and have been open for months. Picking a shape for it is a decision,
not a drive-by. The narrow fix is to skip the operator and log; the broad fix
is the `Result` threading in item 5.

Re-find it with `cargo +nightly fuzz run extract_text` (see `fuzz/README.md`).
The crash artifact itself is gitignored and will not have survived.

## 2. Colorspace array elements assumed to be direct objects — UNVERIFIED

In `make_colorspace`:

```rust
let cs_name = pdf_to_utf8(cs[0].as_name().expect("first arg must be a name"));
let name    = pdf_to_utf8(cs[1].as_name().expect("second arg must be a name"));
```

This is the *same bug class* as the indirect-CIE-dict panic fixed in
`477f87e`: `as_name()` does not resolve references, so an array element stored
as an indirect object aborts extraction. The fix there was
`maybe_deref(doc, &cs[1])`.

I found no real document that hits this, and a `/Separation` whose name is an
indirect object is unusual. Worth fixing on the same principle as `477f87e`
(the ICCBased arm in the same function already derefs), but it is speculative
until something reproduces it. Do not claim it is a real-world bug without a
sample.

## 3. Operand-count asserts in the path operators — KNOWN, contested

```rust
assert!(operation.operands.len() == 6);   // x2
assert!(operation.operands.len() == 2);   // x2
```

A content stream with a path operator missing operands aborts the document.
This is precisely what upstream #148/#154/#158 are about. Same decision
needed as item 1 — and note the maintainer has pushed back on all three.

## 4. Type3 never merges its ToUnicode map into `encoding_table`

`PdfType3Font::new` computes the ToUnicode map and then only passes it to
`dlog!` inside the `Differences` loop; `PdfSimpleFont` merges the two around
lines 493-531.

**This is a real asymmetry but it is NOT the cause of the mojibake bug** —
that was the font cache, fixed in `7eab691`. `decode_char` already prefers
`unicode_map` over the encoding table, so the merge is mostly redundant.
Recorded because two sessions independently flagged it as a suspect; if you
are chasing a Type3 decode problem, rule the cache out first, and do not
"fix" this expecting it to change behaviour.

## 5. 107 abort sites, and a `Result` API that nothing uses

`panic!` 30, `.unwrap()` 41, `.expect(` 28, `assert!`/`assert_eq!` 8,
`todo!` 1 — in 2461 lines, about one every 23 lines.

`extract_text` and friends already return `Result<String, OutputError>`, so
the error channel exists; the parser simply never uses it for malformed
input. Converting panics to errors therefore means threading `Result` through
the whole parser, which is why every upstream attempt (#97, #91, #48, #154,
#158, #148) has stalled at 1000+ line diffs.

If this gets taken on, do it leaf-first in reviewable slices, not as one
rewrite. An interim option with most of the benefit and none of the API
churn: `catch_unwind` per page, so one bad page degrades to a gap instead of
losing the document.

## 6. Test corpus is thin and partly network-dependent

`tests/docs` is 8 files. Four are `.link` files fetched at test time, and one
of those — `embeded-core-fonts.pdf.link` -> `dkp.de` — is a **live
third-party URL, not an archive snapshot**, so CI depends on a third party's
webserver. The other three point at web.archive.org.

Fuzzing (now set up) is a better bug-finder here than corpus growth; corpus
work is mainly about CI determinism.

## 7. Trap: `examples/extract` writes `<name>.txt` into the current directory

Not a library bug, but it bit me. Running the example from inside a checkout
drops the extracted text next to your source. When validating against a real
document — bank statements, anything private — that silently writes the
contents into the repo. Root `.gitignore` has `/*.txt`, so it will not be
committed, but it is still sitting on disk.

Run it from a scratch directory, or `cd` somewhere disposable first.

## 8. Run segmentation vs pdf.js — MISATTRIBUTED, mostly not this library

**Correction (2026-10-13).** Earlier revisions of this item recorded two
downstream symptoms — `M&TBank` for `M&T Bank`, and a detached minus sign
being absorbed so withdrawals import as deposits — as evidence that this
library fuses runs that pdf.js keeps separate. That attribution was wrong, and
it was wrong because it was taken from a consumer's report without checking
which code path the consumer uses.

What the code actually does:

- `OutputDev::output_character` is called **once per glyph**, with the text
  matrix, width, spacing and font size. This library performs no run merging
  on that path. Every glyph arrives individually, with its position.
- The consumer that reported both symptoms (slatesplit-cli) implements its own
  `OutputDev` and calls `output_doc`. It never uses `PlainTextOutput`.
- The merging is that consumer's own `merge_runs`
  (`slatesplit-cli/src/pdf/extract.rs:194`), which joins glyphs when
  `c.x - end <= c.size * WORD_GAP_FACTOR`, with `WORD_GAP_FACTOR = 0.5`.

So the detached minus **is** delivered to that consumer as its own positioned
glyph. Nothing here absorbs it; their gap threshold does. The same goes for
`M&T Bank`. Neither symptom is fixable in this repo, because the information
needed to avoid them is already being handed over.

Their own notes record that `WORD_GAP_FACTOR` values of 0.3, 0.4 and 0.5 all
give zero mismatched fields on their corpus, so there is likely room to tune
without regression — but that is their call and their corpus, not ours.

**What remains genuinely open here, and is UNVERIFIED:** `PlainTextOutput`
does join adjacent runs, so callers of `extract_text` and friends may still
see spacing that differs from `pdftotext` or pdf.js. No one has demonstrated
that. The two real-world cases that looked like proof of it turned out to come
from a caller that does not use `PlainTextOutput` at all. Before treating this
as a bug, reproduce it through `extract_text` itself and diff against
`pdftotext` on the same file; `tests/docs_cache` is enough to tell whether it
generalises.

**Process note, worth more than the finding.** This was recorded as a
confirmed library bug, with measurements, through two rounds of cross-session
review, and committed twice — because the measurements were real and precise,
and precision reads as correctness. Nobody, including me, checked which
function `merge_runs` belonged to. A consumer's measurement tells you a
symptom is real; it does not tell you whose code produced it.

---

## Upstream state

Upstream submission is **deprioritised by the operator** (2026-10-13): this
repo is a fork, fixes land on fork `master`, and PRs to `jrmuizel/pdf-extract`
are not to be opened without asking first.

- The colorspace fix is on `master` at `477f87e`. Branch
  `fix/colorspace-indirect-dict` was **deleted**, local and on origin — fully
  merged, and it existed only as a PR source. The six-line diff and its full
  rationale live in the `477f87e` commit message.
- `fix/type3-missing-width` still exists on origin at `824f91b` because it is
  the head ref of **PR #164, still open** upstream. Do not delete it and do not
  "catch it up" to master: deleting it closes the PR, advancing it would bundle
  unrelated fixes.

If upstream submission is revived, the agreed strategy for the colorspace fix
was: **src-only, six lines, rebased onto `upstream/master`**, fixture and test
wiring staying on the fork, PR body arguing from the adjacent ICCBased arm
which already derefs. The deleted branch could not have been used as-is — it
was based on `824f91b`, so a PR from it would have bundled the Type3 fix, which
the maintainer refused on #136. Rebuild from `upstream/master`; it is about ten
minutes.

Reason for withholding the fixture: the maintainer has refused synthetic
reproducers repeatedly (on #158, verbatim: *"I'm not interested in manually
generated PDF with the problem."*) and PR #164 is stalled on exactly that
request. Say in the PR body that a fixture exists and was withheld
deliberately, and offer it — declining to attach then reads as deference rather
than as an untested patch.

Do not bundle fixes into one PR; the maintainer asked for separate PRs on #136.
Tracked downstream as `slatesplit-cli-jqc` (open, unassigned, on hold by
operator decision rather than by its recorded blocker).
