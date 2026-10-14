#!/bin/sh
# Seed the fuzz corpus from the test documents already on disk.
set -eu
cd "$(dirname "$0")/.."
mkdir -p fuzz/corpus/extract_text
n=0
for f in tests/docs/*.pdf; do
    [ -e "$f" ] || continue
    cp "$f" fuzz/corpus/extract_text/
    n=$((n + 1))
done
if [ -d tests/docs_cache ]; then
    for f in tests/docs_cache/*.pdf; do
        [ -e "$f" ] || continue
        cp "$f" fuzz/corpus/extract_text/
        n=$((n + 1))
    done
else
    echo "tests/docs_cache is absent; run 'cargo test' once to download the real-world seeds." >&2
fi
echo "seeded $n files into fuzz/corpus/extract_text"
