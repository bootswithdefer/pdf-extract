# Fuzzing pdf-extract

`extract_text_from_mem` returns `Result`, but the parser underneath aborts on
input it doesn't expect, so a malformed document takes the process down rather
than returning `Err`. The target treats a panic as the bug and an `Err` as a
pass.

Requires a nightly toolchain (libFuzzer needs `-Z` sanitizer flags) and
`cargo-fuzz`:

    rustup toolchain install nightly --profile minimal
    cargo install cargo-fuzz

## Seeding

The corpus is not committed — the real-world seeds are the same files
`tests/` already downloads, and committing fuzzer-grown inputs bloats the
repo. Seed it from what's on disk:

    ./fuzz/seed-corpus.sh

That copies the synthetic fixtures from `tests/docs` and, if `cargo test` has
been run at least once, the downloaded documents from `tests/docs_cache`.

## Running

    cargo +nightly fuzz run extract_text -- -max_len=65536

The real-world seeds are a few hundred KB; `-max_len` keeps libFuzzer from
spending its time on inputs that size. A crash is written to
`fuzz/artifacts/extract_text/` and replays with:

    cargo +nightly fuzz run extract_text fuzz/artifacts/extract_text/crash-<hash>

## Triage

Not every crash is worth fixing. A panic reached only by bytes no producer
would ever emit is less interesting than one reached by a document that is
merely unusual. Before fixing, check whether the input is plausible output
from a real PDF producer, and prefer fixes that degrade (skip the entry, fall
back to a default) over fixes that reject the file.
