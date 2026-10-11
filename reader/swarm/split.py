# Splits the book into 50 page-aligned parts for the reader swarm.
# Needs shamela_reader.py (for assemble()) next to it; usage: python split.py PAGES.jsonl WORKDIR
import sys, re, importlib.util
from pathlib import Path
W = Path(sys.argv[2]); pages = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("sr", W / "shamela_reader.py"); sr = importlib.util.module_from_spec(spec); spec.loader.exec_module(sr)
sr.assemble(pages, W / "book.txt")                       # the user's own assembler
text = re.sub(r"[ً-ْٰ]", "", (W / "book.txt").read_text(encoding="utf-8"))
pg = re.split(r"(?=\n\[ج[^/\]]*/ص[^\]]*\]\n)", text)
pg = [p for p in pg if p.strip()]
N = 50; target = len(text) / N
parts = [[] for _ in range(N)]
pos = 0
for i, p in enumerate(pg):                       # part = where the page starts
    parts[min(N - 1, int(pos / len(text) * N))].append(i); pos += len(p)
parts = [x for x in parts if x]
for k, idx in enumerate(parts, 1):
    lo, hi = idx[0], idx[-1]
    body = []
    if lo > 0: body.append("<<< تداخل: الصفحة السابقة للسياق فقط >>>" + pg[lo-1])
    body += [pg[i] for i in idx]
    if hi + 1 < len(pg): body.append("\n<<< تداخل: الصفحة التالية للسياق فقط >>>" + pg[hi+1])
    first = re.search(r"\[(ج[^\]]*)\]", pg[lo]).group(1); last = re.search(r"\[(ج[^\]]*)\]", pg[hi]).group(1)
    (W / "parts" / f"part{k:02d}.txt").write_text("".join(body), encoding="utf-8")
    print(f"{k:02d}\t{first}\t{last}\t{len(idx)}p\t{sum(len(pg[i]) for i in idx)}ch")
print("pages", len(pg), "chars", len(text))
