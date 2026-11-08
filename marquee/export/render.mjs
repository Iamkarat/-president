// Экспорт бегущей строки PRESIDENT в MP4 и GIF.
//
//   cd marquee/export && npm install && npm run export
//   node render.mjs --cycle 12 --fps 60 --gif-fps 20 --only gif
//
// Страница открывается в headless Chrome в режиме ?render, все анимации
// ставятся на паузу и перематываются покадрово на t = i / fps внутри [0, cycle).
// Последний кадр не равен первому, поэтому видео зацикливается без стыка.

import { chromium } from "playwright-core";
import { createServer } from "node:http";
import { readFile, mkdir, rm, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { spawnSync, execFileSync } from "node:child_process";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(here, "../..");

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => {
    if (a.startsWith("--")) acc.push([a.slice(2), all[i + 1]]);
    return acc;
  }, [])
);

const cycle = Math.min(12, Math.max(8, Number(args.cycle) || 10));
const fps = Number(args.fps) || 60;
const gifFps = Number(args["gif-fps"]) || 20;   // 20 fps = ровно 5 сотых на кадр GIF
const only = args.only;                          // "mp4" | "gif" — собрать только один формат
const outDir = path.resolve(here, args.out || "../dist");
const W = 1920;
const H = 400;

// ---------- ffmpeg ----------

function findFfmpeg() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const which = spawnSync("which", ["ffmpeg"], { encoding: "utf8" });
  if (which.status === 0) return which.stdout.trim();
  try {
    // запасной вариант: бинарник из python-пакета imageio-ffmpeg
    return execFileSync("python3", ["-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"], { encoding: "utf8" }).trim();
  } catch {
    throw new Error("ffmpeg не найден: установите ffmpeg или задайте FFMPEG=/путь/к/ffmpeg");
  }
}

function ffmpeg(bin, argv) {
  const r = spawnSync(bin, ["-hide_banner", "-loglevel", "error", "-y", ...argv], { stdio: "inherit" });
  if (r.status !== 0) throw new Error("ffmpeg завершился с ошибкой");
}

// ---------- статический сервер (шрифты и картинки по http, а не file://) ----------

const types = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".woff2": "font/woff2" };

function serve() {
  const server = createServer(async (req, res) => {
    const p = path.join(siteRoot, decodeURIComponent(new URL(req.url, "http://x").pathname));
    if (!p.startsWith(siteRoot)) return res.writeHead(403).end();
    try {
      const body = await readFile(p);
      res.writeHead(200, { "content-type": types[path.extname(p)] || "application/octet-stream" }).end(body);
    } catch {
      res.writeHead(404).end();
    }
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

// ---------- рендер кадров ----------

async function renderFrames(page, rate, dir) {
  await mkdir(dir, { recursive: true });
  const total = Math.round(cycle * rate);
  for (let i = 0; i < total; i++) {
    await page.evaluate((ms) => window.Marquee.seek(ms), (i * 1000) / rate);
    await page.screenshot({ path: path.join(dir, String(i).padStart(5, "0") + ".png"), clip: { x: 0, y: 0, width: W, height: H } });
    if (i % 50 === 0) process.stdout.write(`\r  кадр ${i + 1}/${total}`);
  }
  process.stdout.write(`\r  кадров: ${total}            \n`);
}

async function launch() {
  const opts = { headless: true, args: ["--force-color-profile=srgb", "--hide-scrollbars"] };
  if (process.env.CHROME_PATH) return chromium.launch({ ...opts, executablePath: process.env.CHROME_PATH });
  return chromium.launch({ ...opts, channel: "chrome" });
}

async function main() {
  const bin = findFfmpeg();
  const tmp = path.join(os.tmpdir(), "president-marquee-" + process.pid);
  const server = await serve();
  const url = `http://127.0.0.1:${server.address().port}/marquee/index.html?render&cycle=${cycle}`;

  const browser = await launch();
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await page.goto(url);
  const info = await page.evaluate(() => window.Marquee.ready);
  // первый скриншот после загрузки Chrome иногда отдаёт недорисованным — прогреваем
  await page.evaluate(() => window.Marquee.seek(0));
  await page.screenshot();

  console.log(`Цикл ${cycle} с, повтор ${info.unitW}px, скорость ${(info.unitW / cycle).toFixed(1)} px/с`);

  try {
    await mkdir(outDir, { recursive: true });

    const made = [];

    if (only !== "gif") {
      console.log(`MP4 ${fps} fps`);
      await renderFrames(page, fps, path.join(tmp, "mp4"));
      const mp4 = path.join(outDir, "president-marquee.mp4");
      ffmpeg(bin, [
        "-framerate", String(fps), "-i", path.join(tmp, "mp4", "%05d.png"),
        "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-tune", "animation",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", "-an",
        mp4,
      ]);
      made.push(mp4);
    }

    if (only !== "mp4") {
      console.log(`GIF ${gifFps} fps`);
      await renderFrames(page, gifFps, path.join(tmp, "gif"));
      const gifIn = ["-framerate", String(gifFps), "-i", path.join(tmp, "gif", "%05d.png")];
      const pal = "split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=5";
      const gif = path.join(outDir, "president-marquee.gif");
      const gifSmall = path.join(outDir, "president-marquee-960.gif");
      ffmpeg(bin, [...gifIn, "-vf", pal, "-loop", "0", gif]);
      ffmpeg(bin, [...gifIn, "-vf", "scale=960:-1:flags=lanczos," + pal, "-loop", "0", gifSmall]);
      made.push(gif, gifSmall);
    }

    for (const f of made) {
      console.log(`  ${path.relative(siteRoot, f)}  ${((await stat(f)).size / 1048576).toFixed(1)} МБ`);
    }
  } finally {
    await browser.close();
    server.close();
    if (existsSync(tmp)) await rm(tmp, { recursive: true, force: true });
  }
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
