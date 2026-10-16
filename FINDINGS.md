# pdf-extract: open findings

Notes for a future session. Everything here is **unfixed**; fixed work is in
the git log. Recorded 2026-10-13, last revised the same day.

Fork master at time of writing: `3724aae`. Fixes landed so far: `7eab691`
(font cache keyed by object id), `b003161` (two malformed-font cases),
`477f87e` (indirect CIE colorspace dicts), `3724aae` (malformed text-showing
operators), plus the fuzz target in `8b0d710`.

---

## 1. Dangling object references abort the document — CONFIRMED by fuzzer

`maybe_deref`, `src/lib.rs:177`:

```rust
&Object::Reference(r) => doc.get_object(r).expect("missing object reference"),
```

A reference to an object that is missing or unparseable aborts extraction.
Found by the fuzzer in a five-minute run immediately after the `Tj` arm was
fixed, by corrupting one byte inside the function dictionary that
`indirect-colorspace-dicts.pdf` reaches by reference.

This matters more than it looks, because `477f87e` added six new `maybe_deref`
call sites to `make_colorspace`. That fix was right -- it replaced a panic on
a valid construct with correct handling -- but it does mean malformed files
now reach this `expect` through more paths than before. It is the same bug
class as item 2: the arms around it already tolerate what they cannot use.

The narrow fix is for `maybe_deref` to return the original object, or an
`Object::Null`, when the reference does not resolve, so the caller's existing
"unexpected operand" handling takes over. Note that callers currently assume
the deref succeeded, so check each of the six colorspace sites before
changing the signature.

Reproduce: `cargo +nightly fuzz run extract_text` with the existing seed
corpus finds it quickly. The crash artifact is gitignored and will not have
survived; the mutation replaces the `/` of `/C0` inside object 7 with a `0x01`
byte.
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

## 3. Operand-count asserts in the positioning operators — FIXED in `5401b23`

```rust
assert!(operation.operands.len() == 6);   // "cm", "Tm"
assert!(operation.operands.len() == 2);   // "Td", "TD"
```

Taken the narrow way, same as the `Tj` arm in `3724aae`: skip the operation,
warn, keep parsing. A fixture and generator went in with it
(`make_position_operator_fixture.py`), asserting the text after the bad
operators is still EXTRACTED rather than merely that nothing panicked.

**This entry sat here as "KNOWN, contested" while it was the single largest
cause of unreadable documents in a real corpus.** Classifying every failure
across 182 PDFs found five of the seven unreadable ones aborting here — and
found them by measurement, not by reading this file. Nobody had connected the
documented defect to the documents it was breaking.

The lesson is about this file rather than that bug: a finding recorded as
"known" is not thereby costed. Before leaving one contested, point the thing
at real input and count what it refuses. After the fix: unreadable 7 → 2, and
all 177 other documents byte-for-byte identical.

They were never "path" operators — `cm` is graphics state and the other three
are text positioning. The title was wrong from the start, which is its own
small argument for re-deriving a claim rather than inheriting it.

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

## 5. 108 abort sites, and a `Result` API that nothing uses

`panic!` 28, `.unwrap()` 46, `.expect(` 29, `assert!`/`assert_eq!` 4,
`todo!` 1 — 108 in 2718 lines, about one every 25 lines. Recounted
2026-10-15 after `kxv`, `esq` and `5401b23`; the previous figure was 115 in
2461 lines on 2026-10-13. Counted by occurrence, not by matching line:

```sh
for pat in 'panic!' '.unwrap()' '.expect('; do
    grep -oF "$pat" src/lib.rs | wc -l      # -F: these are not regexes
done
grep -oE 'assert!|assert_eq!' src/lib.rs | wc -l
grep -oF 'todo!' src/lib.rs | wc -l
```

The original snippet used `grep -oE` for all five patterns, which fails on
`.unwrap()` and `.expect(` — `()` is an empty group and `(` is unbalanced.
Depending on the grep it errors or silently reports 0, so re-run it with `-F`
for the literal patterns rather than trusting a number it produced.

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

## 7. Trap: `examples/extract` is not a safe oracle

Not a library bug, but it has now misled two sessions in different ways. If
you are reaching for this example as a quick check, read all three.

**It writes `<name>.<kind>` into the current directory.** Running it from
inside a checkout drops the extracted text next to your source. When
validating against a real document — bank statements, anything private — that
silently writes the contents into the repo. Root `.gitignore` has `/*.txt`, so
it will not be committed, but it is still sitting on disk. Run it from a
scratch directory and clear it afterwards. One such run left a real mortgage
statement in `/tmp` for roughly forty minutes.

**Stdout is not the extraction.** Stdout carries only the filename and
`print_metadata(&doc)`. The text goes to the output file. Measuring stdout and
believing it to be the extraction produced a figure 3x too small and a
confident "confirmed clean" that happened to be right for the wrong reason.
Measure the output file.

**Exit 0 does not mean the extraction completed.** The last line is:

```rust
output_doc(&doc, output.as_mut());
```

The `Result` is discarded outright — not even `let _ =`. A mid-document error
is swallowed, and you get a short output file and a clean exit with nothing on
stderr. `doc.decrypt("")` above it drops its result the same way, and
`Document::load(path).unwrap()` panics rather than reporting.

So the example can only tell you that nothing *panicked*. To establish that a
document extracted fully, compare the output length against an independent
path — `extract_text_from_mem` is the obvious one — rather than trusting the
exit status.

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
