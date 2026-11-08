# Бегущая строка PRESIDENT PRIVATE AGENCY

Анимированная бесконечная строка для Telegram-канала, 1920×400.

- `index.html` — страница предпросмотра: скорость, длина цикла (8/10/12 с), пауза, ссылки на готовые файлы.
- `marquee.css` / `marquee.js` — сама строка. Движение — CSS-анимация `transform`, скорость меняется через `playbackRate` без рывков.
- `dist/` — готовые файлы: `president-marquee.mp4` (H.264, 60 fps, 10 с), `president-marquee.gif` (1920×400, 20 fps), `president-marquee-960.gif` (960×200).

За один цикл строка сдвигается ровно на один повтор «щит + надпись», а блики имеют тот же период — поэтому видео зацикливается без стыка.

## Пересобрать MP4 и GIF

Нужны Google Chrome и ffmpeg (или python-пакет `imageio-ffmpeg`, скрипт найдёт его сам).

```sh
cd marquee/export
npm install
npm run export                       # цикл 10 с
node render.mjs --cycle 12           # цикл 8–12 с
node render.mjs --only mp4 --fps 30  # только MP4
```

Для Telegram лучше загружать MP4 без звука: Telegram показывает его как зацикленную GIF-анимацию, а файл в ~15 раз легче GIF.
