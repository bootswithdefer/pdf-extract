use log::info;
use pdf_extract::extract_text;
use test_log::test;
// Shorthand for creating ExpectedText
// example: expected!("atomic.pdf", "Atomic Data");
macro_rules! expected {
    ($filename:expr, $text:expr) => {
        ExpectedText {
            filename: $filename,
            text: $text,
        }
    };
}

// Use the macro to create a list of ExpectedText
// and then check if the text is correctly extracted
#[test]
fn extract_expected_text() {
    let docs = vec![
        expected!("documents_stack.pdf.link", "mouse button until"),
        // CalGray/CalRGB/Lab parameter dictionaries reached by indirect
        // reference, both nested under /Separation and at the top level.
        // Each of those six arms used to panic in make_colorspace.
        expected!("indirect-colorspace-dicts.pdf", "Indirect colorspace dicts"),
        // The page and a form XObject it draws both define /F1, pointing at
        // different fonts. "YYY" only appears if the form's own /F1 is used
        // rather than the page's; a name-keyed font cache yields "XXX" twice.
        expected!("nested-resource-font-names.pdf", "YYY"),
        // A ToUnicode value that is an unpaired surrogate followed by another
        // code unit. The entry is unrepresentable and gets skipped, so the text
        // comes back through the font's encoding instead of aborting the file.
        expected!("tounicode-lone-surrogate.pdf", "AAA"),
        // Widths stops short of LastChar. Uncovered codes take MissingWidth
        // rather than tripping an assert.
        expected!("widths-shorter-than-lastchar.pdf", "AAA"),
        // Malformed text-showing operators: a Tj whose operand is not a
        // string, a Tj with no operand at all, and a TJ with no operand. Each
        // aborted the document before. "AAA" comes from a valid Tj placed
        // after all three, so this asserts that the bad operators are skipped
        // and parsing continues, not merely that nothing panicked.
        expected!("malformed-text-operators.pdf", "AAA"),
        // A complete, valid xref table that startxref does not address -- the
        // offset points into the middle of an object. The whole document used
        // to be lost with "invalid file trailer"; it is now recovered by
        // correcting the pointer.
        expected!("broken-startxref.pdf", "AAA"),
        // /Encoding /SymbolEncoding. Only three base encodings were matched
        // and every other name hit a panic!, so a legitimate encoding aborted
        // the document. Asserting the Greek letters rather than mere survival
        // also covers the second panic one line below the first: the per-glyph
        // name_to_unicode(x).unwrap(), which Symbol's "alpha"/"beta" names
        // reach and ZapfDingbats' "a1".."a191" names would abort on.
        expected!("symbol-encoding.pdf", "\u{3b1}\u{3b2}\u{3b3}"),
        // Same file, second font: /Encoding /NoSuchEncoding. An unknown
        // encoding now warns and falls back to StandardEncoding, so "AAA"
        // still extracts instead of the document being abandoned.
        expected!("symbol-encoding.pdf", "AAA"),
    ];
    for doc in docs {
        doc.test();
    }
}

#[test]
// iterate over all docs in the `tests/docs` directory, don't crash
fn extract_all_docs() {
    let docs = std::fs::read_dir("tests/docs").unwrap();
    for doc in docs {
        let doc = doc.unwrap();
        let path = doc.path();
        let filename = path.file_name().unwrap().to_string_lossy();
        expected!(&filename, "").test();
    }
}

// data structure to make it easy to check if certain files are correctly parsed
// e.g. ExpectedText { filename: "atomic.pdf", text: "Atomic Data" }
#[derive(Debug, PartialEq)]
struct ExpectedText<'a> {
    filename: &'a str,
    text: &'a str,
}

impl ExpectedText<'_> {
    /// Opens the `filename` from `tests/docs`, extracts the text and checks if it contains `text`
    /// If the file ends with `_link`, it will download the file from the url in the file to the `tests/docs_cache` directory
    fn test(self) {
        let ExpectedText { filename, text } = self;
        let file_path = if filename.ends_with(".pdf.link") {
            let docs_cache = "tests/docs_cache";
            if !std::path::Path::new(docs_cache).exists() {
                // This might race with exists test above, but that's fine
                if let Err(e) = std::fs::create_dir(docs_cache) {
                    if e.kind() != std::io::ErrorKind::AlreadyExists {
                        panic!("Failed to create directory {}, {}", docs_cache, e);
                    }
                } 
            }
            let file_path = format!("{}/{}", docs_cache, filename.replace(".link", ""));
            if std::path::Path::new(&file_path).exists() {
                file_path
            } else {
                let url = std::fs::read_to_string(format!("tests/docs/{}", filename)).unwrap();
                let resp = ureq::get(&url).call().unwrap();
                let mut file = std::fs::File::create(&file_path).unwrap();
                std::io::copy(&mut resp.into_reader(), &mut file).unwrap();
                file_path
            }
        } else {
            format!("tests/docs/{}", filename)
        };
        let out = extract_text(file_path)
            .unwrap_or_else(|e| panic!("Failed to extract text from {}, {}", filename, e));
        info!("{}", out);
        assert!(
            out.contains(text),
            "Text {} does not contain '{}'",
            filename,
            text
        );
    }
}

#[test]
// ZapfDingbats carrying an /Encoding. The core-font width loop looked names up
// in glyphnames only, which lacks "a1".."a191", and aborted the document.
// Synthetic fixture (make_zapf_encoding_fixture.py): three glyphs, none blank.
fn zapf_dingbats_with_encoding() {
    let out = extract_text("tests/docs/zapf-encoding.pdf").unwrap();
    assert!(out.contains("\u{2741}\u{2742}\u{2743}"), "got {:?}", out);
}
