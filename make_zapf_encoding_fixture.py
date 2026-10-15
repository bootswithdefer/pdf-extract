#!/usr/bin/env python3
"""Build a minimal PDF with a ZapfDingbats font that carries an /Encoding.

PdfSimpleFont::new walks the core-font metrics in two branches. The branch for
a font with no encoding routes ZapfDingbats through zapfglyphnames; the branch
for a font that has one called glyphnames::name_to_unicode(..).unwrap() on the
same metric names ("a1".."a191"), which glyphnames does not contain, and
aborted the document (slatesplit-cli-esq).

Entirely synthetic; contains no real-world document content.

Usage: make_zapf_encoding_fixture.py OUT.pdf
"""
import sys

CONTENT = b"""BT
/F1 18 Tf
72 700 Td
(abc) Tj
ET
"""


def build():
    objs = {}
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    objs[3] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
               b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>")
    objs[4] = (b"<< /Length " + str(len(CONTENT)).encode() + b" >>\nstream\n"
               + CONTENT + b"endstream")
    objs[5] = (b"<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats "
               b"/Encoding /ZapfDingbatsEncoding >>")

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
