#!/usr/bin/env python3
"""Build a minimal PDF whose content stream contains malformed POSITIONING
operators, followed by valid text.

pdf-extract asserted an exact operand count on four of them:

    "cm" => assert!(operation.operands.len() == 6)
    "Tm" => assert!(operation.operands.len() == 6)
    "Td" => assert!(operation.operands.len() == 2)
    "TD" => assert!(operation.operands.len() == 2)

So one truncated or lightly corrupted operation aborted the ENTIRE document.
On a real bank statement that is the difference between one misplaced glyph
and no text at all: five of the operator's PDFs were unreadable for this
reason alone (slatesplit-cli-62l).

This is the same defect shape as the text-showing operators next door, in the
positioning arms instead, and the fix is the same: skip the operation and keep
parsing.

The valid `(AAA) Tj` comes last on purpose: the test asserts "AAA" is still
extracted, so this proves the bad operators are SKIPPED and parsing continues,
not merely that nothing crashed.

Entirely synthetic; contains no real-world document content.

Usage: make_position_operator_fixture.py OUT.pdf
"""
import sys


CONTENT = b"""BT
/F1 18 Tf
1 0 0 1 cm
1 0 0 1 0 Tm
72 Td
72 700 0 TD
72 700 Td
(AAA) Tj
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
    objs[5] = (b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
               b"/Encoding /WinAnsiEncoding >>")

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
