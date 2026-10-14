#![no_main]

use libfuzzer_sys::fuzz_target;

// pdf-extract's public entry points return Result, but the parser underneath
// aborts on input it doesn't expect, so a malformed file takes the process
// down instead of returning Err. Every panic found here is a document that
// cannot be extracted at all, however little else is wrong with it.
//
// An Err return is a pass: that is the library correctly rejecting input.
fuzz_target!(|data: &[u8]| {
    let _ = pdf_extract::extract_text_from_mem(data);
});
