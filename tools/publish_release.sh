#!/usr/bin/env bash
# Заливает файлы пака в GitHub Release.
# Использование: tools/publish_release.sh <pack_id>   (нужен gh, авторизованный в GitHub)
set -e
ID="$1"; cd "$(dirname "$0")/.."
TAG=$(python3 -c "import json;print(next(p['release'] for p in json.load(open('data/packs.json'))['packs'] if p['id']=='$ID'))")
NAME=$(python3 -c "import json;print(next(p['name'] for p in json.load(open('data/packs.json'))['packs'] if p['id']=='$ID'))")
gh release view "$TAG" >/dev/null 2>&1 || gh release create "$TAG" --title "$NAME" --notes "Пак обоев $NAME"
gh release upload "$TAG" ../release/"$ID"/* --clobber
