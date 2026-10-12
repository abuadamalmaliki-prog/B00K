"""Download hadith books (with isnads) from the AuthenticIlm/Shamela4_Full_DB
dataset on Hugging Face and convert them to OpenITI mARkdown, the same format
as the other books in this repo.

Usage:
    pip install huggingface_hub pandas pyarrow
    python tools/download_shamela.py --out books          # everything selected
    python tools/download_shamela.py --list               # just print the list
    python tools/download_shamela.py --max-death 300      # only early authors
    python tools/download_shamela.py --ids 172 4593       # specific book ids

By default it selects every book in these Shamela categories whose author died
in or before 600 AH (the era of works transmitted with full chains):
    06 كتب السنة   (sihah, sunan, masanid, musannafat, ma'ajim, ajza')
    09 العلل والسؤالات الحديثية
    24 السيرة النبوية (sirah and maghazi)
    25 التاريخ
"""
import argparse, html, json, os, re, sys

from huggingface_hub import HfApi, hf_hub_download
import pandas as pd

REPO = "AuthenticIlm/Shamela4_Full_DB"
CATEGORIES = ["06__كتب-السنة", "09__العلل-والسؤلات-الحديثية",
              "24__السيرة-النبوية", "25__التاريخ"]


def dl(path, cache):
    return hf_hub_download(REPO, path, repo_type="dataset", local_dir=cache)


def clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = html.unescape(s).replace("\r", " ").replace("\n", " ")
    return re.sub(r"[ \t]+", " ", s).strip()


def to_markdown(folder, uri, shamela_id, footnotes=True):
    pages = [json.loads(l) for l in open(f"{folder}/pages.jsonl", encoding="utf-8")]
    toc = [json.loads(l) for l in open(f"{folder}/toc.jsonl", encoding="utf-8")]
    pages.sort(key=lambda p: p["page_id"])
    toc.sort(key=lambda t: (t["page_id"], t["title_id"]))
    lines = ["######OpenITI#", "", "#META# Header#Begin#",
             f"#META# 000.BookURI# {uri}",
             f"#META# 000.Source# https://shamela.ws/book/{shamela_id}",
             "#META# Header#End#", "", ""]
    ti, title, part = 0, "مقدمة", None
    for p in pages:
        while ti < len(toc) and toc[ti]["page_id"] <= p["page_id"]:
            title = clean(toc[ti]["title_text"]).rstrip(" -") or title
            ti += 1
        vol = int(p["part"]) if str(p["part"]).isdigit() else 1
        if vol != part:
            part = vol
            lines += [f"### | الجزء {vol:02d}", ""]
        else:
            lines += [f"### || {title}", ""]
        lines += [f"PageV{vol:02d}P{int(p['page_num'] or 0):03d}", f"# {clean(p['body'])}", ""]
        if footnotes and p.get("footnotes"):
            lines += ["---", f"% {clean(p['footnotes'])}", ""]
        lines += ["____________________", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="books", help="output folder (default: books)")
    ap.add_argument("--cache", default=".shamela_cache", help="download cache folder")
    ap.add_argument("--max-death", type=int, default=600, help="latest author death year AH (default 600)")
    ap.add_argument("--categories", nargs="*", default=CATEGORIES)
    ap.add_argument("--ids", nargs="*", type=int, help="download only these dataset book ids")
    ap.add_argument("--no-footnotes", action="store_true", help="drop the editors' footnotes")
    ap.add_argument("--list", action="store_true", help="only list the selected books")
    a = ap.parse_args()

    meta = pd.read_parquet(dl("_meta/book_metadata.parquet", a.cache)).set_index("book_id")
    api = HfApi()
    books = []
    for cat in a.categories:
        for f in api.list_repo_tree(REPO, path_in_repo=cat, repo_type="dataset"):
            bid = int(f.path.split("/")[1].split("__")[0])
            row = meta.loc[bid]
            death = row["main_author_death_hijri"]
            if a.ids:
                if bid not in a.ids:
                    continue
            elif pd.isna(death) or death > a.max_death:
                continue
            books.append((cat, f.path, bid, row))
    print(f"{len(books)} books selected", file=sys.stderr)

    for i, (cat, path, bid, row) in enumerate(books, 1):
        name = path.split("/")[1]
        line = f"{bid}\t{int(row['main_author_death_hijri'] or 0)}\t{row['main_author_name_ar']}\t{row['title_ar']}"
        if a.list:
            print(line)
            continue
        dest = os.path.join(a.out, cat, name.split("__", 1)[1].replace("-", "_") + ".mARkdown")
        if os.path.exists(dest):
            continue
        print(f"[{i}/{len(books)}] {line}", file=sys.stderr)
        for fn in ("pages.jsonl", "toc.jsonl"):
            dl(f"{path}/{fn}", a.cache)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        text = to_markdown(os.path.join(a.cache, path), os.path.basename(dest)[:-10],
                           row["shamela_id"], footnotes=not a.no_footnotes)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)


if __name__ == "__main__":
    main()
