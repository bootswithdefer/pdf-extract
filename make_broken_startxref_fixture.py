#!/usr/bin/env python3
"""Build a minimal PDF whose xref table is complete and valid but whose
`startxref` offset does not address it.

This is the shape of two real documents in the wild (iText 5.5.13.3 output):
the cross-reference table is intact, the objects are intact, and only the
pointer is wrong -- in those files by exactly 570 bytes. qpdf, poppler and
pdf.js all recover by going to look for the table; lopdf hands the offset
straight to its parser, which fails with:

    PDF error: couldn't parse input: invalid file trailer

so Document::load fails outright and the whole document is lost.

The offset here points into the middle of an object, exactly as it does in the
real files, rather than past EOF -- lopdf already guards the past-EOF case, so
a fixture using that shape would not exercise the gap.

Entirely synthetic; contains no real-world document content.

Usage: make_broken_startxref_fixture.py OUT.pdf
"""
import sys

CONTENT = b"""BT
/F1 18 Tf
72 700 Td
(AAA) Tj
ET
"""

def build():
    objs = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"),
        4: (b"<< /Length " + str(len(CONTENT)).encode() + b" >>\nstream\n"
            + CONTENT + b"endstream"),
        5: (b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"),
    }

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

    # The table above is correct. The pointer below is not: it addresses the
    # middle of object 3 instead. Everything needed to read the file is
    # present; only this number is wrong.
    wrong = offsets[3] + 20
    assert wrong != xref_at
    out += (b"trailer\n<< /Size " + str(n).encode() + b" /Root 1 0 R >>\n"
            b"startxref\n" + str(wrong).encode() + b"\n%%EOF\n")
    return bytes(out)

if __name__ == "__main__":
    data = build()
    with open(sys.argv[1], "wb") as fh:
        fh.write(data)
    print("wrote %s (%d bytes)" % (sys.argv[1], len(data)))
