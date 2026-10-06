# wp.vladislove.online

Сайт с бесплатными паками обоев. Статический: `index.html` + `data/packs.json` + превью в `packs/`.
Полноразмерные обои лежат в `files/<pack>/`. Архивы не хранятся — сайт собирает их в браузере при нажатии «Скачать».
Лимит GitHub Pages — 1 ГБ, это примерно 4 пака по 200 МБ. Когда станет тесно, файлы можно вынести в Cloudflare R2 и прописать его адрес в `downloadBase`.

## Как добавить новый пак

1. Сгенерируй пак в папку вида `<Формат>/<Фон>/<PREFIX>_<Motif>_<Palette>_<Фон>.jpg`
   (пример генератора: `tools/gen_strata.py`).
2. Создай `meta/<pack>.json` по образцу `meta/strata.json`.
3. `python3 tools/add_pack.py meta/<pack>.json <папка_пака>` — сделает превью, скопирует файлы и обновит `data/packs.json`.
4. `git add . && git commit -m "Новый пак" && git push` — сайт обновится сам через минуту.

## Локальный просмотр

    python3 -m http.server 8000
