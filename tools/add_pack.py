#!/usr/bin/env python3
"""Добавляет пак обоев на сайт.

Использование:
    python3 tools/add_pack.py meta/<pack>.json <папка_с_паком>

Папка пака: <format.dir>/<background>/<PREFIX>_<Motif>_<Palette>_<Background>.jpg
Что делает:
  * превью webp -> packs/<id>/  (лежат в репозитории сайта)
  * файлы для скачивания -> ../release/<id>/  (заливаются в GitHub Release)
  * архивы по форматам + общий архив -> ../release/<id>/
  * добавляет/обновляет запись в data/packs.json
"""
import json, os, sys, zipfile, shutil
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main(meta_path, src):
    meta = json.load(open(meta_path, encoding="utf-8"))
    pid, pre = meta["id"], meta["prefix"]
    thumbs = os.path.join(ROOT, "packs", pid)
    rel = os.path.join(ROOT, "..", "release", pid)
    shutil.rmtree(thumbs, ignore_errors=True); shutil.rmtree(rel, ignore_errors=True)
    os.makedirs(thumbs); os.makedirs(rel)
    readme = os.path.join(src, f"{pre}_README.txt")
    zips = {f["id"]: zipfile.ZipFile(os.path.join(rel, f"{pre}_{f['id']}.zip"), "w", zipfile.ZIP_STORED) for f in meta["formats"]}
    allz = zipfile.ZipFile(os.path.join(rel, f"{pre}_all.zip"), "w", zipfile.ZIP_STORED)
    n = 0
    for f in meta["formats"]:
        for bg in meta["backgrounds"]:
            for m in meta["motifs"]:
                for p in meta["palettes"]:
                    name = f"{pre}_{m['id']}_{p['id']}_{bg['id']}"
                    path = os.path.join(src, f["dir"], bg["id"], name + ".jpg")
                    if not os.path.exists(path):
                        print("нет файла:", path); continue
                    out = f"{name}_{f['id']}.jpg"
                    shutil.copy(path, os.path.join(rel, out))
                    arc = f"{f['name']}/{bg['name']}/{out}"
                    zips[f["id"]].write(path, arc); allz.write(path, arc); n += 1
                    im = Image.open(path).convert("RGB")
                    key = f"{m['id']}_{p['id']}_{bg['id']}"
                    if f["id"] == "desktop":
                        im.resize((640, 360), Image.LANCZOS).save(os.path.join(thumbs, f"{key}_s.webp"), quality=82)
                        im.resize((1600, 900), Image.LANCZOS).save(os.path.join(thumbs, f"{key}_l.webp"), quality=84)
                    elif f["id"] == "mobile":
                        im.resize((430, 932), Image.LANCZOS).save(os.path.join(thumbs, f"{key}_m.webp"), quality=84)
    for z in list(zips.values()) + [allz]:
        if os.path.exists(readme): z.write(readme, "README.txt")
        z.close()
    sizes = {k: os.path.getsize(os.path.join(rel, f"{pre}_{k}.zip")) for k in list(zips) + ["all"]}
    entry = dict(meta, count=n, designs=len(meta["motifs"]) * len(meta["palettes"]) * len(meta["backgrounds"]),
                 bundles={k: {"file": f"{pre}_{k}.zip", "size": s} for k, s in sizes.items()},
                 release=f"{pid}-{meta['version']}")
    db_path = os.path.join(ROOT, "data", "packs.json")
    db = json.load(open(db_path, encoding="utf-8")) if os.path.exists(db_path) else {"downloadBase": "", "packs": []}
    db["packs"] = [x for x in db["packs"] if x["id"] != pid]
    db["packs"].insert(0, entry)
    db["packs"].sort(key=lambda x: x.get("date", ""), reverse=True)
    json.dump(db, open(db_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"готово: {n} файлов, превью в packs/{pid}, раздача в release/{pid}")

if __name__ == "__main__":
    main(*sys.argv[1:3])
