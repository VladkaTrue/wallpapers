# wp.vladislove.online

Сайт с бесплатными паками обоев. Статический: `index.html` + `data/packs.json` + превью в `packs/`.
Полноразмерные файлы и архивы лежат в GitHub Releases (тег `<pack>-<version>`), сайт ссылается на них через `downloadBase` в `data/packs.json`.

## Как добавить новый пак

1. Сгенерируй пак в папку вида `<Формат>/<Фон>/<PREFIX>_<Motif>_<Palette>_<Фон>.jpg`
   (пример генератора: `tools/gen_strata.py`).
2. Создай `meta/<pack>.json` по образцу `meta/strata.json`.
3. `python3 tools/add_pack.py meta/<pack>.json <папка_пака>` — сделает превью, архивы и обновит `data/packs.json`.
4. `tools/publish_release.sh <pack>` — зальёт файлы в GitHub Release.
5. `git add . && git commit -m "Новый пак" && git push` — сайт обновится сам через минуту.

## Локальный просмотр

    python3 -m http.server 8000
