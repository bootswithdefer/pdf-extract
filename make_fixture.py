#!/usr/bin/env python3
"""Build a minimal PDF whose CIE-based colorspaces all store their parameter
dictionary as an INDIRECT reference.

pdf-extract's make_colorspace had six arms - CalGray/CalRGB/Lab, each both
nested under a /Separation alternate space and at the top level - that called
cs[1].as_dict() directly. as_dict() does not resolve references, so any of
these shapes panicked with:

    ObjectType { expected: "Dictionary", found: "Reference" }

This fixture exercises all six in a single document. Entirely synthetic; it
contains no real-world document content.

Usage: make_fixture.py OUT.pdf
"""
import sys

# Each `cs` invocation drives one arm of make_colorspace. Text is drawn after
# them so a successful run still produces extractable output.
CONTENT = b"""/CS0 cs 1 scn
/CS1 cs 1 scn
/CS2 cs 1 scn
/CS3 cs 1 1 1 scn
/CS4 cs 1 1 1 scn
/CS5 cs 1 scn
BT
/F1 18 Tf
72 700 Td
(Indirect colorspace dicts) Tj
ET
"""

# Objects 6/8/9 are the CIE parameter dictionaries. Every colorspace below
# reaches them by REFERENCE rather than inline - that indirection is the whole
# point of the fixture.
COLORSPACES = (
    b"<< "
    # nested under /Separation -> the three alternate-space arms
    b"/CS0 [/Separation /Spot [/Lab 6 0 R] 7 0 R] "
    b"/CS1 [/Separation /Spot [/CalRGB 8 0 R] 7 0 R] "
    b"/CS2 [/Separation /Spot [/CalGray 9 0 R] 7 0 R] "
    # top level -> the three outer arms
    b"/CS3 [/Lab 6 0 R] "
    b"/CS4 [/CalRGB 8 0 R] "
    b"/CS5 [/CalGray 9 0 R] "
    b">>"
)

objects = {
    1: b"<< /Type /Catalog /Pages 2 0 R >>",
    2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    3: (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> /ColorSpace " + COLORSPACES + b" >> "
        b"/Contents 4 0 R >>"
    ),
    4: b"<< /Length " + str(len(CONTENT)).encode() + b" >>\nstream\n" + CONTENT + b"endstream",
    5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    6: b"<< /WhitePoint [0.9505 1.0 1.089] /Range [-100 100 -100 100] >>",
    7: b"<< /FunctionType 2 /Domain [0 1] /C0 [0 0 0] /C1 [1 1 1] /N 1 >>",
    8: b"<< /WhitePoint [0.9505 1.0 1.089] /Gamma [2.2 2.2 2.2] >>",
    9: b"<< /WhitePoint [0.9505 1.0 1.089] /Gamma 2.2 >>",
}


def build() -> bytes:
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += str(num).encode() + b" 0 obj\n" + objects[num] + b"\nendobj\n"

    xref_at = len(out)
    count = len(objects) + 1
    out += b"xref\n0 " + str(count).encode() + b"\n0000000000 65535 f \n"
    for num in sorted(objects):
        out += ("%010d 00000 n \n" % offsets[num]).encode()
    out += (
        b"trailer\n<< /Size " + str(count).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_at).encode() + b"\n%%EOF\n"
    )
    return bytes(out)


if __name__ == "__main__":
    data = build()
    with open(sys.argv[1], "wb") as fh:
        fh.write(data)
    print("wrote %s (%d bytes)" % (sys.argv[1], len(data)))
