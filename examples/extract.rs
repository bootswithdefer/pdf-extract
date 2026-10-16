//! Extract a PDF's text to a file.
//!
//! THE OUTPUT PATH IS REQUIRED, AND THAT IS DELIBERATE. This example used to
//! derive it from the input filename and write into the CURRENT DIRECTORY, so
//! running it against a private document — a bank statement, anything
//! sensitive — silently deposited that document's text wherever you happened
//! to be standing. One such run left a real mortgage statement in /tmp for
//! about forty minutes, and the behaviour has misled more than one session
//! (FINDINGS.md item 7).
//!
//! There is no safe default to choose instead. Writing beside the INPUT is
//! worse — that puts extracted text into the directory the private documents
//! live in. Writing to STDOUT is worse still for the common case here, which
//! is an automated agent whose stdout is a transcript it cannot purge. So the
//! destination is named explicitly or the program refuses to run.
//!
//!     cargo run --example extract -- input.pdf /path/to/out.txt [txt|html|svg]
//!
//! AND THE RESULT IS NO LONGER DISCARDED. `output_doc`'s error was dropped
//! outright, so a mid-document failure produced a short output file, a clean
//! exit, and nothing on stderr — the example could only tell you that nothing
//! panicked. It now reports and exits non-zero.

extern crate lopdf;
extern crate pdf_extract;

use lopdf::*;
use pdf_extract::*;
use simple_logger::SimpleLogger;
use std::env;
use std::fs::File;
use std::io::BufWriter;
use std::path;
use std::process::ExitCode;

fn main() -> ExitCode {
    SimpleLogger::new().init().unwrap();

    let mut args = env::args().skip(1);
    let (Some(input), Some(output)) = (args.next(), args.next()) else {
        eprintln!(
            "usage: extract <input.pdf> <output-file> [txt|html|svg]\n\
             \n\
             The output path is REQUIRED. This program writes the document's\n\
             extracted TEXT there; point it somewhere you are willing for a\n\
             private document's contents to land."
        );
        return ExitCode::FAILURE;
    };
    let output_kind = args.next().unwrap_or_else(|| "txt".to_owned());

    let path = path::Path::new(&input);
    let output_file = match File::create(&output) {
        Ok(f) => BufWriter::new(f),
        Err(e) => {
            eprintln!("could not create {output}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let mut output_file = output_file;

    // Reported rather than unwrapped: a damaged file is the ordinary case this
    // crate exists to survive, and a panic here says nothing useful.
    let mut doc = match Document::load(path) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("could not load {input}: {e}");
            return ExitCode::FAILURE;
        }
    };

    print_metadata(&doc);

    let mut out: Box<dyn OutputDev> = match output_kind.as_ref() {
        "txt" => Box::new(PlainTextOutput::new(
            &mut output_file as &mut dyn std::io::Write,
        )),
        "html" => Box::new(HTMLOutput::new(&mut output_file)),
        "svg" => Box::new(SVGOutput::new(&mut output_file)),
        other => {
            eprintln!("unknown output kind {other:?}; expected txt, html or svg");
            return ExitCode::FAILURE;
        }
    };

    if doc.is_encrypted() {
        // Its Result was dropped too, so a failed decrypt looked like a
        // successful one and the extraction then produced nothing useful.
        if let Err(e) = doc.decrypt("") {
            eprintln!("{input} is encrypted and the empty password failed: {e:?}");
            return ExitCode::FAILURE;
        }
    }

    match output_doc(&doc, out.as_mut()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            // The whole point: a mid-document error used to be swallowed, and
            // the short output file that resulted was indistinguishable from a
            // short document.
            eprintln!("extraction of {input} failed: {e}");
            eprintln!("NOTE: {output} may hold a PARTIAL extraction.");
            ExitCode::FAILURE
        }
    }
}
