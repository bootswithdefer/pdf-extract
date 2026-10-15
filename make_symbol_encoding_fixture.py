#!/usr/bin/env python3
"""Build a minimal PDF that names base encodings `encoding_to_unicode_table`
did not handle.

That function matched exactly three names and aborted on everything else:

    _ => panic!("unexpected encoding {:?}", pdf_to_utf8(name))

SymbolEncoding is a legitimate standard base encoding, so a document using it
was refused outright rather than degraded on -- four of the operator's real
Chase statements crashed this way (slatesplit-cli-kxv). The tables for Symbol,
ZapfDingbats, Standard and Expert were already sitting in encodings.rs,
carrying `#[allow(dead_code)]`; they were simply never wired into the match.

Two fonts, because there are two distinct failures to pin down:

  /F1  /Encoding /SymbolEncoding   -> "abg" must extract as the Greek letters
       alpha/beta/gamma. This is the wired-up path, and it asserts the table
       actually resolves rather than just failing to panic. Note that Symbol's
       glyph names are Greek/math ("alpha", "universal"), so this also covers
       the second panic hiding one line below the first: the per-glyph lookup
       did name_to_unicode(x).unwrap(), which aborts on any name the glyph
       list lacks.

  /F2  /Encoding /NoSuchEncoding   -> "AAA" must still extract, via the
       StandardEncoding fallback. An encoding nobody has taught the library
       about is not a reason to abandon the document.

Entirely synthetic; contains no real-world document content.

Usage: make_symbol_encoding_fixture.py OUT.pdf
"""
import sys

CONTENT = b"""BT
/F1 18 Tf
72 700 Td
(abg) Tj
ET
BT
/F2 18 Tf
72 660 Td
(AAA) Tj
ET
"""


def build():
    objs = {}
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    objs[3] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
               b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>")
    objs[4] = (b"<< /Length " + str(len(CONTENT)).encode() + b" >>\nstream\n"
               + CONTENT + b"endstream")
    objs[5] = (b"<< /Type /Font /Subtype /Type1 /BaseFont /Symbol "
               b"/Encoding /SymbolEncoding >>")
    # An encoding name no version of this library has ever known.
    objs[6] = (b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
               b"/Encoding /NoSuchEncoding >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += str(num).encode() + b" 0 obj\n" + objs[num] + b"\nendobj\n"

    xref_at = len(out)
    n = max(objs) + 1
    out += b"xref\n0 " + str(n).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for num in sorted(objs):
        out += ("%010d 00000 n \n" % offsets[num]).encode()
    out += (b"trailer\n<< /Size " + str(n).encode() + b" /Root 1 0 R >>\n"
            b"startxref\n" + str(xref_at).encode() + b"\n%%EOF\n")
    return bytes(out)


if __name__ == "__main__":
    with open(sys.argv[1], "wb") as f:
        f.write(build())
