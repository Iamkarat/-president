// Одностраничный форум: приветствие, «Задать вопрос», лента «Вопрос — ответ», темы.
// Вопросы и ответы хранит server.py (data.json); темы пока заданы здесь.

const NAV = [
  { href: "#top", label: "Главная" },
  { href: "#ai", label: "AI-поиск" },
  { href: "#qa", label: "Вопрос — ответ" },
];

// Темы: заголовок + краткий ответ; мнения участников хранятся на сервере.
const TOPICS = [
  { id: "greece", icon: "globe", title: "Как зарабатывать в Греции", answer: "Проверьте, разрешена ли работа в Греции для вашего гражданства и статуса. До переезда письменно уточните зарплату, условия жилья, страховку и договор. Не передавайте деньги и документы непроверенным посредникам." },
  { id: "tickets", icon: "plane", title: "Как найти недорогие билеты", answer: "Ищите билеты за 1–2 месяца до поездки и сравнивайте цены в нескольких агрегаторах. Гибкие даты почти всегда дешевле: смотрите календарь цен на неделю вперёд и назад.\n\nЛоукостеры выгодны, только если вы летите с рюкзаком. Багаж и выбор места часто стоят как сам билет, поэтому считайте итоговую сумму." },
  { id: "packing", icon: "doc", title: "Что взять с собой: документы и мелочи", answer: "Загранпаспорт со сроком действия минимум 6 месяцев после поездки, страховка, бронь жилья и обратный билет — их могут спросить на границе.\n\nСохраните фото паспорта и страховки в облаке и отправьте близкому человеку. Возьмите две карты разных банков и немного наличных в местной валюте." },
  { id: "budget", icon: "wallet", title: "Как спланировать бюджет поездки", answer: "Разделите бюджет на четыре части: дорога, жильё, еда и развлечения. К итоговой сумме прибавьте 15–20% на непредвиденное.\n\nЗаписывайте траты в заметках или приложении — так сразу видно, где можно сэкономить. Обедать выгоднее там, где едят местные, а не у главных достопримечательностей." },
  { id: "stay", icon: "home", title: "Где жить: отель, апартаменты или хостел", answer: "Хостел подходит, если вы едете за знакомствами и хотите сэкономить. Апартаменты удобны компанией или надолго: есть кухня и больше места. Отель — когда важен сервис и не хочется думать о быте.\n\nПеред бронированием читайте свежие отзывы и смотрите, сколько идти до центра и транспорта." },
  { id: "party", icon: "party", title: "Как найти хорошую тусовку в новом городе", answer: "Спросите у местных и у персонала хостела или бара — они знают, куда ходят сами, а не туристы. Загляните в афиши клубов и площадок в соцсетях, а также в чаты путешественников по городу.\n\nУточните заранее дресс-код, время, когда начинается движ, и как вход — по билетам, спискам или бесплатно." },
  { id: "safety", icon: "shield", title: "Безопасность на вечеринках", answer: "Не оставляйте напиток без присмотра и не берите открытые напитки у незнакомцев. Договоритесь с друзьями, как вы вернётесь, и включите им геолокацию.\n\nЗапишите адрес жилья и номер местной экстренной службы (в Европе — 112). Держите при себе только нужную сумму и одну карту, документы оставьте в сейфе." },
  { id: "meet", icon: "chat", title: "Как знакомиться в поездке", answer: "Самый простой способ — групповые активности: пешие экскурсии, мастер-классы, спортивные и языковые встречи. В хостелах часто бывают совместные ужины и вечеринки.\n\nПервые встречи назначайте в людных местах и рассказывайте друзьям, где вы. Никому не отдавайте свой паспорт и не соглашайтесь на «работу мечты» от новых знакомых без проверки." },
  { id: "season", icon: "sun", title: "Когда ехать: сезоны и праздники", answer: "Высокий сезон — это толпы и высокие цены, зато работает всё. В межсезонье (весна и ранняя осень) дешевле и спокойнее, а погода часто ещё хорошая.\n\nПосмотрите календарь местных праздников и фестивалей: ради них стоит подстроить даты, но жильё на такие дни бронируйте заранее." },
];

const TOPIC_ICONS = {
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.8 5.5 3.8 9s-1.3 6.5-3.8 9c-2.5-2.5-3.8-5.5-3.8-9S9.5 5.5 12 3z"/>',
  doc: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>',
  home: '<path d="M4 11l8-7 8 7v9H4z"/><path d="M10 20v-5h4v5"/>',
  wallet: '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 10h18M16 14.5h2"/>',
  chat: '<path d="M4 5h16v11H8l-4 4z"/><path d="M8 9h8M8 12h5"/>',
  shield: '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  plane: '<path d="M10.5 13.5L3 11l1.5-1.5 8 .5 4-4.5c1-1 2.5-1.2 3-.7s.3 2-.7 3l-4.5 4 .5 8L13.3 21l-2.5-7.5z"/>',
  party: '<path d="M5 4h14l-7 8z"/><path d="M12 12v8M8 20h8"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
};
const topicIcon = (k) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${TOPIC_ICONS[k] || TOPIC_ICONS.chat}</svg>`;

const ICON = {
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  chat: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 5h16v11H8l-4 4z"/></svg>',
};

const $ = (s, el = document) => el.querySelector(s);
const AVATARS = [
  { src: "assets/avatars/avatar-1.webp", label: "Фиолетовый в очках и с часами" },
  { src: "assets/avatars/avatar-2.webp", label: "Фиолетовый в золотых очках" },
  { src: "assets/avatars/avatar-3.webp", label: "Брюнетка в фиолетовой шапке" },
  { src: "assets/avatars/avatar-4.webp", label: "Блондинка в наушниках" },
  { src: "assets/avatars/avatar-5.webp", label: "Чёрный с телефоном" },
  { src: "assets/avatars/avatar-6.webp", label: "Блондинка с чокером" },
];
const DEFAULT_AVATAR = AVATARS[0].src;

// Safari и WebView на iOS (в т.ч. браузер Telegram) не показывают прозрачность webm —
// там и на мобильных логотип — прозрачная PNG, как на основном сайте.
const STATIC_LOGO = matchMedia("(max-width: 860px)").matches
  || (/AppleWebKit/.test(navigator.userAgent) && !/Chrome|Chromium|Android/.test(navigator.userAgent));
const LOGO_MARK = `<span class="logo-mark" aria-hidden="true">${STATIC_LOGO
  ? '<img class="logo-video" src="assets/president-logo.png" alt="">'
  : '<video class="logo-video" autoplay loop muted playsinline><source src="assets/president-logo.webm" type="video/webm"></video>'}</span>`;

function shell() {
  document.body.insertAdjacentHTML("afterbegin", `
    <div class="backdrop"><span></span><span></span><span></span></div>
    <div class="nav-wrap">
      <nav class="nav" aria-label="Основная навигация">
        <a class="logo" href="#top">${LOGO_MARK}<span>PRESIDENT PRIVATE AGENCY FORUM</span></a>
        <ul class="nav-links">
          ${NAV.map((n) => `<li><a href="${n.href}">${n.label}</a></li>`).join("")}
        </ul>
        <div class="nav-actions">
          <a class="btn btn-light btn-sm" href="#ask">Задать вопрос</a>
          <button class="icon-btn burger" aria-label="Меню" aria-expanded="false">${ICON.menu}</button>
        </div>
      </nav>
      <div class="mobile-menu glass">
        ${NAV.map((n) => `<a href="${n.href}">${n.label}</a>`).join("")}
        <a href="#ask">Задать вопрос</a>
      </div>
    </div>`);

  document.body.insertAdjacentHTML("beforeend", `
    <footer><div class="container"><div class="footer glass">
      <div><a class="logo">${LOGO_MARK}<span>PRESIDENT PRIVATE AGENCY FORUM</span></a>
      <p>Официальный форум агентства.</p></div>
      <div><h5>Разделы</h5>${NAV.map((n) => `<a href="${n.href}">${n.label}</a>`).join("")}</div>
      <div><h5>Правила публикации</h5><p>Не публикуйте ссылки, рекламу и личные данные. Будьте уважительны к участникам.</p><a href="#ask">Как задать вопрос</a></div>
    </div></div></footer>`);

  const burger = $(".burger");
  const menu = $(".mobile-menu");
  burger.addEventListener("click", () => burger.setAttribute("aria-expanded", menu.classList.toggle("open")));
  menu.addEventListener("click", (e) => {
    if (!e.target.closest("a")) return;
    menu.classList.remove("open");
    burger.setAttribute("aria-expanded", "false");
  });

  // Подсветка активного пункта по прокрутке
  const links = document.querySelectorAll(".nav-links a, .mobile-menu a[href^='#']");
  const spy = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return;
      links.forEach((a) => a.toggleAttribute("aria-current", a.getAttribute("href") === `#${en.target.id}`));
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  ["top", "ai", "qa"].forEach((id) => spy.observe(document.getElementById(id)));
}

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (ts) => new Date(ts).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
const initials = (name) => esc(name.trim().slice(0, 2).toUpperCase());
const avatarMarkup = (name, src, className = "") => {
  const avatarSrc = src || DEFAULT_AVATAR;
  const safeSrc = AVATARS.some((avatar) => avatar.src === avatarSrc) || /^data:image\/(?:webp|png|jpeg);base64,[A-Za-z0-9+/]+=*$/.test(avatarSrc)
    ? avatarSrc
    : DEFAULT_AVATAR;
  return safeSrc
    ? `<img class="avatar ${className}" src="${esc(safeSrc)}" alt="" loading="lazy">`
    : `<span class="avatar ${className}" aria-hidden="true">${initials(name)}</span>`;
};
const avatarPicker = () => `
  <fieldset class="avatar-picker">
    <legend>Аватар</legend>
    <input type="hidden" name="avatar" value="${DEFAULT_AVATAR}">
    <div class="avatar-options">
      ${AVATARS.map((avatar) => `<button class="avatar-option${avatar.src === DEFAULT_AVATAR ? " selected" : ""}" type="button" data-avatar-choice="${avatar.src}" aria-label="${avatar.label}" aria-pressed="${avatar.src === DEFAULT_AVATAR}"><img src="${avatar.src}" alt=""></button>`).join("")}
      <label class="avatar-upload">Загрузить свой аватар<input type="file" accept="image/png,image/jpeg,image/webp" aria-label="Загрузить свой аватар"></label>
    </div>
    <div class="avatar-preview" aria-live="polite"><img src="${DEFAULT_AVATAR}" alt=""><span>Стандартный аватар</span></div>
    <div class="note" data-avatar-status role="status"></div>
  </fieldset>`;

const emptyState = (title, text) => `
  <div class="glass empty">
    <div class="empty-icon">${ICON.chat}</div>
    <h3>${title}</h3><p>${text}</p>
  </div>`;

const qaItem = (q) => `
  <article class="post glass" id="q-${q.id}">
    ${avatarMarkup(q.name, q.avatar)}
    <div>
      <div class="post-head"><b>${esc(q.name)}</b><span class="meta">${fmt(q.created)}</span></div>
      <p class="q-text">${esc(q.text)}</p>
      ${q.answers.map((a) => `
        <div class="answer">
          <div class="post-head">${avatarMarkup(a.name, a.avatar, "avatar-small")}<b>${esc(a.name)}</b><span class="meta">${fmt(a.created)}</span></div>
          <p>${esc(a.text)}</p>
        </div>`).join("")}
      <div class="post-actions">
        <button class="link-btn" data-reply="${q.id}">Ответить${q.answers.length ? ` · ${q.answers.length}` : ""}</button>
      </div>
      <form class="reply-form" data-qid="${q.id}" hidden novalidate>
        <input class="input" name="name" maxlength="40" placeholder="Имя (необязательно)">
        <textarea class="textarea" name="text" required minlength="2" maxlength="1000" placeholder="Ваш ответ"></textarea>
        ${avatarPicker()}
        <div class="hp" aria-hidden="true"><input tabindex="-1" autocomplete="off" name="website"></div>
        <button class="btn btn-light btn-sm" style="justify-self:start">Отправить ответ</button>
        <div data-status role="status"></div>
      </form>
    </div>
  </article>`;

let questions = [];

const CONFIG = { access: "link", passwordSha256: "", apiBase: "", ...window.FORUM_CONFIG };

const apiUrl = (path) => CONFIG.apiBase.replace(/\/$/, "") + path;

async function api(path, body) {
  const res = await fetch(apiUrl(path), body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Не удалось связаться с сервером");
  return data;
}

function drawQA() {
  const list = $("#qa-list");
  list.innerHTML = questions.length
    ? questions.map(qaItem).join("")
    : emptyState("Вопросов пока нет", "Задайте первый вопрос — он появится здесь сразу после отправки.");
}

async function loadQA() {
  const list = $("#qa-list");
  list.innerHTML = `<div class="glass post" aria-hidden="true"><div class="skeleton avatar"></div><div style="display:grid;gap:10px"><div class="skeleton" style="height:14px;width:30%"></div><div class="skeleton" style="height:16px;width:90%"></div></div></div>`;
  try {
    questions = await api("/api/questions");
    drawQA();
  } catch (e) {
    console.error("loadQA:", e);
    list.innerHTML = emptyState("Вопросы временно недоступны", `Попробуйте обновить чуть позже. <button class="link-btn" data-retry>Повторить</button>`);
  }
}

function setStatus(form, cls, text) {
  const s = $("[data-status]", form);
  s.className = cls ? `alert ${cls}` : "";
  s.textContent = text;
}

async function submit(form, path, onDone, textPrefix = "") {
  if ($(".hp input", form).value) return;
  const text = form.elements.text;
  if (text.value.trim().length < Number(text.minLength || 1)) {
    setStatus(form, "error", `Напишите хотя бы ${text.minLength} символов.`);
    text.focus();
    return;
  }
  const btn = $("button:not([type=button])", form);
  btn.disabled = true;
  try {
    const avatar = await avatarPayload(form.elements.avatar?.value || "");
    const item = await api(path, { name: form.elements.name.value, text: textPrefix ? `${textPrefix}: ${text.value.trim()}` : text.value, avatar, website: $(".hp input", form).value });
    form.reset();
    setAvatarChoice(form, DEFAULT_AVATAR);
    onDone(item);
  } catch (e) {
    setStatus(form, "error", e.message);
  } finally {
    btn.disabled = false;
  }
}

// Готовые аватарки отправляются на сервер как data:image — сервер принимает их без списка путей.
async function avatarPayload(value) {
  if (!AVATARS.some((avatar) => avatar.src === value)) return value;
  const blob = await (await fetch(value)).blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Не удалось загрузить аватар."));
    reader.readAsDataURL(blob);
  });
}

function setAvatarChoice(form, value) {
  const input = form.elements.avatar;
  const preview = $(".avatar-preview", form);
  if (!input || !preview) return;
  input.value = value;
  form.querySelectorAll("[data-avatar-choice]").forEach((button) => {
    const selected = button.dataset.avatarChoice === value;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  preview.innerHTML = value
    ? `<img src="${esc(value)}" alt=""><span>${value === DEFAULT_AVATAR ? "Стандартный аватар" : "Предпросмотр аватара"}</span>`
    : `<img src="${DEFAULT_AVATAR}" alt=""><span>Стандартный аватар</span>`;
}

function bindAvatarPickers() {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-avatar-choice]");
    if (!button) return;
    setAvatarChoice(button.closest("form"), button.dataset.avatarChoice);
  });
  document.addEventListener("change", async (event) => {
    const fileInput = event.target.closest(".avatar-upload input[type=file]");
    if (!fileInput || !fileInput.files?.[0]) return;
    const form = fileInput.closest("form");
    const status = $("[data-avatar-status]", form);
    const file = fileInput.files[0];
    try {
      if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024) {
        throw new Error("Выберите PNG, JPEG или WebP размером до 5 МБ.");
      }
      const bitmap = await createImageBitmap(file);
      if (bitmap.width > 8000 || bitmap.height > 8000 || bitmap.width * bitmap.height > 16_000_000) {
        bitmap.close();
        throw new Error("Размеры изображения слишком велики.");
      }
      const scale = Math.min(1, 192 / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();
      const blob = await new Promise((resolve, reject) => canvas.toBlob(
        (result) => result ? resolve(result) : reject(new Error("Не удалось обработать изображение.")),
        "image/webp",
        0.78,
      ));
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error("Не удалось прочитать изображение."));
        reader.readAsDataURL(blob);
      });
      if (dataUrl.length > 90_000) throw new Error("Изображение слишком большое после обработки.");
      setAvatarChoice(form, dataUrl);
      status.textContent = "";
    } catch (error) {
      status.textContent = error.message;
      fileInput.value = "";
    }
  });
}

function bindQA() {
  const toggle = $("#ask-toggle");
  const askForm = $("#ask-form");
  const textLabel = $('label[for="q-text"]', askForm);
  const textInput = $("#q-text", askForm);
  const postTypes = {
    question: { label: "Ваш вопрос", placeholder: "Например: какие документы нужны для работы за границей?", prefix: "" },
    "agency-review": { label: "Ваш отзыв об агентстве", placeholder: "Поделитесь опытом взаимодействия с агентством", prefix: "Отзыв об агентстве" },
    "model-review": { label: "Ваш отзыв о модели", placeholder: "Поделитесь мнением о модели", prefix: "Отзыв о модели" },
  };
  const updatePostType = () => {
    const type = postTypes[askForm.elements.postType.value];
    textLabel.textContent = type.label;
    textInput.placeholder = type.placeholder;
    textInput.maxLength = type.prefix ? 1000 - type.prefix.length - 2 : 1000;
  };
  const openAsk = () => { askForm.hidden = false; toggle.setAttribute("aria-expanded", "true"); askForm.elements.text.focus(); };
  toggle.addEventListener("click", () => (askForm.hidden ? openAsk() : (askForm.hidden = true, toggle.setAttribute("aria-expanded", "false"))));
  document.querySelectorAll('a[href="#ask"]').forEach((a) => a.addEventListener("click", () => setTimeout(openAsk, 300)));
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal" id="rules-modal" role="alertdialog" aria-modal="true" aria-labelledby="rules-title" aria-describedby="rules-text">
      <div class="rules-dialog">
        <h3 id="rules-title">Пишите уважительно</h3>
        <p class="muted" id="rules-text">Высказывайте мнение корректно и по делу. Спам, оскорбления и мат запрещены — за нарушение аккаунт блокируется навсегда.</p>
        <button type="button" class="btn btn-light" data-rules-ok>Ок</button>
      </div>
    </div>`);
  const rulesModal = $("#rules-modal");
  const closeRules = () => { rulesModal.classList.remove("open"); textInput.focus(); };
  $("[data-rules-ok]", rulesModal).addEventListener("click", closeRules);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && rulesModal.classList.contains("open")) closeRules(); });

  askForm.addEventListener("change", (e) => {
    if (e.target.name !== "postType") return;
    updatePostType();
    if (postTypes[e.target.value].prefix) {
      rulesModal.classList.add("open");
      $("[data-rules-ok]", rulesModal).focus();
    }
  });

  askForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const type = postTypes[askForm.elements.postType.value];
    submit(askForm, "/api/questions", (q) => {
      questions.unshift(q);
      drawQA();
      setStatus(askForm, "ok", type.prefix ? "Отзыв опубликован." : "Вопрос опубликован.");
      document.getElementById(`q-${q.id}`).scrollIntoView({ behavior: "smooth", block: "center" });
      updatePostType();
    }, type.prefix);
  });

  $("#qa-list").addEventListener("click", (e) => {
    if (e.target.closest("[data-retry]")) {
      loadQA();
      return;
    }
    const b = e.target.closest("[data-reply]");
    if (!b) return;
    const f = $(`.reply-form[data-qid="${b.dataset.reply}"]`);
    f.hidden = !f.hidden;
    if (!f.hidden) f.elements.text.focus();
  });
  $("#qa-list").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const id = Number(f.dataset.qid);
    submit(f, `/api/questions/${id}/answers`, (a) => {
      questions.find((q) => q.id === id).answers.push(a);
      drawQA();
    });
  });
}

// Темы — плитки с иконками; по клику открывается окно: ответ + мнения участников
let topicComments = {};
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? few : many;
};
const opinions = (n) => `${n} ${plural(n, "мнение", "мнения", "мнений")}`;

function drawTiles() {
  $("#topic-list").innerHTML = TOPICS.map((t, i) => {
    const n = (topicComments[t.id] || []).length;
    return `
    <button class="topic-tile glass ${i % 2 ? "light" : ""}" data-topic="${i}">
      <span class="topic-icon">${topicIcon(t.icon)}</span>
      <h3>${esc(t.title)}</h3>
      <span class="topic-more">Читать ответ →${n ? ` <span class="topic-count">${opinions(n)}</span>` : ""}</span>
    </button>`;
  }).join("");
}

function drawComments(t) {
  const list = topicComments[t.id] || [];
  $("#tm-count").textContent = list.length ? opinions(list.length) : "Пока нет мнений";
  $("#tm-comments").innerHTML = list.length
    ? list.map((c) => `
      <div class="answer">
        <div class="post-head">${avatarMarkup(c.name, c.avatar, "avatar-small")}<b>${esc(c.name)}</b><span class="meta">${fmt(c.created)}</span></div>
        <p>${esc(c.text)}</p>
      </div>`).join("")
    : '<p class="note" style="margin:0">Будьте первым — поделитесь опытом или дополните ответ.</p>';
}

function drawTopics() {
  const list = $("#topic-list");
  list.className = "topic-grid";
  drawTiles();

  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal" id="topic-modal" role="dialog" aria-modal="true" aria-labelledby="tm-title">
      <div class="form glass topic-dialog">
        <div class="topic-dialog-head">
          <span class="topic-icon" id="tm-icon"></span>
          <button type="button" class="icon-btn" data-close aria-label="Закрыть">✕</button>
        </div>
        <h3 id="tm-title"></h3>
        <span class="eyebrow">Ответ</span>
        <p class="muted" id="tm-answer" style="margin:0"></p>
        <div class="topic-opinions">
          <div class="section-head" style="margin:0"><h3 style="font-size:16px">Мнения участников</h3><span class="note" id="tm-count"></span></div>
          <div id="tm-comments" aria-live="polite"></div>
          <form class="reply-form" id="tm-form" novalidate>
            <input class="input" name="name" maxlength="40" placeholder="Имя (необязательно)">
            <textarea class="textarea" name="text" required minlength="2" maxlength="1000" placeholder="Ваше мнение или опыт по теме"></textarea>
            ${avatarPicker()}
            <div class="hp" aria-hidden="true"><input tabindex="-1" autocomplete="off" name="website"></div>
            <button class="btn btn-light btn-sm" style="justify-self:start">Добавить мнение</button>
            <div data-status role="status"></div>
          </form>
        </div>
      </div>
    </div>`);

  const modal = $("#topic-modal");
  const form = $("#tm-form");
  let current = null;

  list.addEventListener("click", (e) => {
    const tile = e.target.closest("[data-topic]");
    if (!tile) return;
    current = TOPICS[tile.dataset.topic];
    $("#tm-icon").innerHTML = topicIcon(current.icon);
    $("#tm-title").textContent = current.title;
    $("#tm-answer").textContent = current.answer;
    setStatus(form, "", "");
    drawComments(current);
    modal.classList.add("open");
    $(".topic-dialog", modal).scrollTop = 0;
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const t = current;
    submit(form, `/api/topics/${t.id}/comments`, (c) => {
      (topicComments[t.id] ||= []).push(c);
      drawComments(t);
      drawTiles();
      setStatus(form, "ok", "Мнение опубликовано.");
    });
  });

  modal.addEventListener("click", (e) => { if (e.target === modal || e.target.closest("[data-close]")) modal.classList.remove("open"); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") modal.classList.remove("open"); });

  loadTopics();
}

async function loadTopics() {
  const status = $("#topic-status");
  status.replaceChildren();
  try {
    topicComments = await api("/api/topics");
    if (!topicComments || typeof topicComments !== "object" || Array.isArray(topicComments)) {
      throw new Error("Сервер вернул некорректный список мнений.");
    }
    drawTiles();
  } catch (e) {
    console.error("loadTopics:", e);
    status.className = "alert";
    status.textContent = "Мнения временно недоступны. Попробуйте обновить чуть позже. ";
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "link-btn";
    retry.textContent = "Повторить";
    retry.addEventListener("click", loadTopics, { once: true });
    status.append(retry);
  }
}

const TG_TAGS = new Set(["p", "h3", "h4", "ul", "ol", "li", "a", "hr", "br", "b", "strong", "i", "em", "u", "s", "blockquote", "aside", "figure", "figcaption", "img", "code", "pre"]);

function tgNode(n) {
  if (typeof n === "string") return document.createTextNode(n);
  const children = (n && n.children) || [];
  if (!n || !TG_TAGS.has(n.tag)) {
    const frag = document.createDocumentFragment();
    children.forEach((c) => frag.append(tgNode(c)));
    return frag;
  }
  const el = document.createElement(n.tag);
  const attrs = n.attrs || {};
  if (n.tag === "a" && attrs.href) {
    const url = new URL(attrs.href, "https://telegra.ph");
    if (/^https?:$/.test(url.protocol)) {
      el.href = url.href;
      el.target = "_blank";
      el.rel = "noopener noreferrer";
    }
  }
  if (n.tag === "img" && attrs.src) {
    el.src = new URL(attrs.src, "https://telegra.ph").href;
    el.alt = "";
    el.loading = "lazy";
  }
  children.forEach((c) => el.append(tgNode(c)));
  return el;
}

function bindReader() {
  const section = $("#welcome");
  if (!section) return;

  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal reader-modal" id="reader-modal" role="dialog" aria-modal="true" aria-labelledby="rd-title">
      <article class="glass reader">
        <button type="button" class="btn btn-ghost reader-back" data-reader-close>← Назад к материалам</button>
        <h2 class="reader-title" id="rd-title"></h2>
        <div class="reader-body" id="rd-body" aria-live="polite"></div>
      </article>
    </div>`);

  const modal = $("#reader-modal");
  const body = $("#rd-body");
  const cache = new Map();
  let opener = null;
  let token = 0;

  const close = () => {
    if (!modal.classList.contains("open")) return;
    modal.classList.remove("open");
    document.body.style.overflow = "";
    if (opener) opener.focus();
  };

  async function open(link) {
    const req = ++token;
    opener = link;
    const card = link.closest(".edu-card");
    $("#rd-title").textContent = card ? $("h3", card).textContent : "";
    body.replaceChildren(Object.assign(document.createElement("p"), { className: "reader-note", textContent: "Загрузка статьи…" }));
    modal.classList.add("open");
    document.body.style.overflow = "hidden";
    $(".reader", modal).scrollTop = 0;
    $("[data-reader-close]", modal).focus();

    const path = new URL(link.href).pathname.replace(/^\/+/, "");
    try {
      let page = cache.get(path);
      if (!page) {
        const res = await fetch(`https://api.telegra.ph/getPage/${encodeURIComponent(path)}?return_content=true`);
        const data = await res.json();
        if (!res.ok || !data.ok || !data.result || !Array.isArray(data.result.content)) throw new Error(data.error || `HTTP ${res.status}`);
        page = data.result;
        cache.set(path, page);
      }
      if (req !== token) return;
      $("#rd-title").textContent = page.title;
      body.replaceChildren(...page.content.map(tgNode));
    } catch (e) {
      if (req !== token) return;
      console.error("reader:", e);
      body.replaceChildren(Object.assign(document.createElement("p"), {
        className: "reader-note",
        textContent: "Не удалось загрузить текст статьи: техническая ошибка соединения с источником. Попробуйте позже.",
      }));
    }
  }

  section.addEventListener("click", (e) => {
    const link = e.target.closest(".edu-link");
    if (!link || e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    open(link);
  });
  modal.addEventListener("click", (e) => { if (e.target === modal || e.target.closest("[data-reader-close]")) close(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
}

// ---------- PRESIDENT AI SEARCH: поиск с ответом по источникам (бэкенд — ai_search.py) ----------
const AI_MODES = {
  quick: { label: "Quick Search", note: "Быстрый поиск и краткий ответ" },
  deep: { label: "Deep Research", note: "Углублённое исследование: больше источников, 1–3 минуты" },
};
const AI_HISTORY_KEY = "ai-history";
let aiMode = "quick";
let aiTurns = [];
let aiBusy = false;

function aiHistory() {
  try { return JSON.parse(localStorage.getItem(AI_HISTORY_KEY)) || []; } catch { return []; }
}
function saveAiHistory(list) {
  try { localStorage.setItem(AI_HISTORY_KEY, JSON.stringify(list.slice(0, 20))); } catch {}
}

// Ссылки в ответе кликабельны, только если этот URL действительно нашёл поиск
const normUrl = (u) => u.replace(/([?&])utm_source=openai(&|$)/, (m, a, b) => (b ? a : "")).replace(/[?#/]+$/, "");
const hostOf = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };

function mdInline(text, allowed) {
  return esc(text)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (m, label, url) =>
      allowed.has(normUrl(url.replace(/&amp;/g, "&"))) ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>` : label)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:)!?]|$)/g, "$1<em>$2</em>");
}

function md(src, allowed) {
  const out = [];
  let list = null;
  let rows = [];
  const cells = (t) => t.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  const flush = () => {
    if (!rows.length) return;
    const body = rows.filter((r) => !/^\|?[\s:|-]+\|?$/.test(r)).map(cells);
    const [head, ...rest] = body;
    out.push(`<div class="ai-table"><table><thead><tr>${head.map((c) => `<th>${mdInline(c, allowed)}</th>`).join("")}</tr></thead><tbody>${
      rest.map((r) => `<tr>${r.map((c) => `<td>${mdInline(c, allowed)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
    rows = [];
  };
  const close = () => { flush(); if (list) out.push(`</${list}>`); list = null; };
  for (const line of src.split("\n")) {
    const t = line.trim();
    let m;
    if (t.startsWith("|")) { if (list) { out.push(`</${list}>`); list = null; } rows.push(t); continue; }
    flush();
    if (!t) { close(); continue; }
    if ((m = t.match(/^(#{1,4})\s+(.*)$/))) {
      close();
      const h = m[1].length <= 2 ? "h3" : "h4";
      out.push(`<${h}>${mdInline(m[2], allowed)}</${h}>`);
    } else if ((m = t.match(/^(?:[-*•]|(\d+)[.)])\s+(.*)$/))) {
      const tag = m[1] ? "ol" : "ul";
      if (list !== tag) { close(); out.push(`<${tag}>`); list = tag; }
      out.push(`<li>${mdInline(m[2], allowed)}</li>`);
    } else {
      close();
      out.push(`<p>${mdInline(t, allowed)}</p>`);
    }
  }
  close();
  return out.join("");
}

const aiAllowed = (turn) => new Set([...turn.citations, ...turn.sources].map((s) => normUrl(s.url)));

const aiSteps = (turn) => `
  <ol class="ai-steps">
    ${turn.steps.map((st, i) => `<li class="${i === turn.steps.length - 1 && turn.pending ? "active" : "done"}">${esc(st)}</li>`).join("")}
  </ol>`;

function aiSources(turn) {
  const cited = new Set(turn.citations.map((c) => normUrl(c.url)));
  const rest = turn.sources.filter((s) => !cited.has(normUrl(s.url)));
  const item = (s) => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title || hostOf(s.url))}</a><span>${esc(hostOf(s.url))}</span></li>`;
  if (!turn.citations.length && !rest.length) return "";
  return `
    <div class="ai-sources">
      ${turn.citations.length ? `<h4>Использованные источники · ${turn.citations.length}</h4><ol>${turn.citations.map(item).join("")}</ol>` : ""}
      ${rest.length ? `<details><summary>Также просмотрено · ${rest.length}</summary><ol>${rest.map(item).join("")}</ol></details>` : ""}
    </div>`;
}

function aiTurnHtml(turn, i) {
  const last = i === aiTurns.length - 1;
  return `
  <article class="ai-turn glass" data-turn="${i}">
    <div class="ai-q"><span class="tag">${AI_MODES[turn.mode].label}</span><h3>${esc(turn.query)}</h3></div>
    ${turn.pending && !turn.answer ? aiSteps(turn) : ""}
    <div class="prose ai-answer">${md(turn.answer, aiAllowed(turn))}${turn.pending && turn.answer ? '<span class="ai-caret" aria-hidden="true"></span>' : ""}</div>
    ${turn.error ? `<div class="alert error">${esc(turn.error)}</div>` : ""}
    ${turn.incomplete && !turn.pending ? '<p class="note">Ответ мог оборваться из-за ограничений сервиса. Попробуйте «Повторить» или режим Quick Search.</p>' : ""}
    ${turn.pending ? "" : aiSources(turn)}
    ${turn.pending ? "" : `
    <div class="ai-actions">
      ${turn.id ? `<button class="btn btn-ghost btn-sm" type="button" data-ai-copy="${i}">Копировать</button>
      <button class="btn btn-ghost btn-sm" type="button" data-ai-share="${i}">Поделиться</button>` : ""}
      ${last ? `<button class="btn btn-ghost btn-sm" type="button" data-ai-repeat>Повторить</button>` : ""}
    </div>`}
  </article>`;
}

function drawAi() {
  const last = aiTurns[aiTurns.length - 1];
  $("#ai-thread").innerHTML = aiTurns.map(aiTurnHtml).join("") + (last && !aiBusy && last.id ? `
    <form class="ai-follow glass" id="ai-follow" novalidate>
      <div class="search">
        <input name="query" maxlength="600" autocomplete="off" enterkeyhint="send" placeholder="Уточните или задайте следующий вопрос" aria-label="Уточняющий вопрос">
        <button class="btn btn-light">Спросить</button>
      </div>
      <div data-status role="status"></div>
    </form>
    <button class="link-btn" type="button" data-ai-new>Новый поиск</button>` : "");
}

function drawAiHistory() {
  const list = aiHistory();
  const box = $("#ai-history");
  box.hidden = !list.length;
  box.innerHTML = list.length ? `
    <span class="note">Недавние:</span>
    <div class="chips">${list.map((h) => `<button class="chip" type="button" data-ai-open="${esc(h.id)}" title="${esc(h.query)}">${esc(h.query.length > 48 ? h.query.slice(0, 47) + "…" : h.query)}</button>`).join("")}</div>
    <button class="link-btn" type="button" data-ai-clear>Очистить</button>` : "";
}

// Читает поток событий SSE из POST-ответа
async function aiStream(body, on) {
  const res = await fetch(apiUrl("/api/ai/search"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "AI-поиск временно недоступен");
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let cut;
    while ((cut = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, cut);
      buf = buf.slice(cut + 2);
      const event = /^event: (.*)$/m.exec(chunk)?.[1];
      const data = /^data: (.*)$/m.exec(chunk)?.[1];
      if (event && data) on[event]?.(JSON.parse(data));
    }
  }
}

async function aiRun(query, mode, parent) {
  if (aiBusy) return;
  aiBusy = true;
  $("#ai-submit").disabled = true;
  const turn = { query, mode, parent, answer: "", citations: [], sources: [], steps: ["Анализирую вопрос"], pending: true };
  aiTurns.push(turn);
  drawAi();
  $(`[data-turn="${aiTurns.length - 1}"]`).scrollIntoView({ behavior: "smooth", block: "start" });

  // Перерисовка карточки текущего ответа не чаще раза за кадр
  let frame = 0;
  const redraw = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const i = aiTurns.indexOf(turn);
      $(`[data-turn="${i}"]`).outerHTML = aiTurnHtml(turn, i);
    });
  };

  let finished = false;
  try {
    await aiStream({ query, mode, parent }, {
      status(s) {
        if (s.stage === "searched") {
          turn.steps.push(s.action === "search" && s.query ? `Ищу: «${s.query}»` : s.action === "open_page" ? `Читаю ${hostOf(s.query)}` : "Проверяю найденное");
          if (s.sources) turn.steps.push(`Изучено источников: ${s.sources}`);
          turn.steps = turn.steps.filter((st, i, a) => !st.startsWith("Изучено") || a.findLastIndex((x) => x.startsWith("Изучено")) === i);
          redraw();
        } else if (s.stage === "searching" && !turn.steps.some((st) => st.startsWith("Ищу") || st === "Поиск в интернете")) {
          turn.steps.push("Поиск в интернете");
          redraw();
        }
      },
      delta(d) {
        if (!turn.answer) { turn.steps.push("Формирую ответ"); }
        turn.answer += d.text;
        redraw();
      },
      done(result) {
        finished = true;
        Object.assign(turn, result, { pending: false });
        saveAiHistory([{ id: result.id, query, mode, created: result.created }, ...aiHistory().filter((h) => h.id !== result.id)]);
      },
      error(e) {
        finished = true;
        turn.error = e.error;
      },
    });
    if (!finished) turn.error = "Соединение прервалось. Попробуйте ещё раз.";
  } catch (e) {
    turn.error = e.message === "Failed to fetch" ? "Нет связи с сервером AI-поиска." : e.message;
  } finally {
    cancelAnimationFrame(frame);
    turn.pending = false;
    aiBusy = false;
    $("#ai-submit").disabled = false;
    drawAi();
    drawAiHistory();
  }
}

async function aiOpen(id) {
  try {
    const data = await api(`/api/ai/results/${encodeURIComponent(id)}`);
    aiTurns = data.turns.map((t) => ({ ...t, steps: [], pending: false }));
    drawAi();
    $("#ai").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    setStatus($("#ai-form"), "error", e.message === "Failed to fetch" ? "Нет связи с сервером AI-поиска." : e.message);
  }
}

const aiShareUrl = (id) => `${location.origin}${location.pathname}?ai=${encodeURIComponent(id)}#ai`;

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = Object.assign(document.createElement("textarea"), { value: text });
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  const label = button.textContent;
  button.textContent = "Скопировано";
  setTimeout(() => { button.textContent = label; }, 1800);
}

function bindAi() {
  const form = $("#ai-form");
  const setMode = (mode) => {
    aiMode = mode;
    form.querySelectorAll("[data-ai-mode]").forEach((b) => {
      b.classList.toggle("active", b.dataset.aiMode === mode);
      b.setAttribute("aria-checked", String(b.dataset.aiMode === mode));
    });
    $("#ai-mode-note").textContent = AI_MODES[mode].note;
  };
  form.addEventListener("click", (e) => {
    const b = e.target.closest("[data-ai-mode]");
    if (b) setMode(b.dataset.aiMode);
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = form.elements.query.value.trim();
    if (query.length < 3) {
      setStatus(form, "error", "Напишите вопрос хотя бы из 3 символов.");
      return;
    }
    setStatus(form, "", "");
    aiTurns = [];
    aiRun(query, aiMode);
  });

  const thread = $("#ai-thread");
  thread.addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const query = f.elements.query.value.trim();
    if (query.length < 3) {
      setStatus(f, "error", "Напишите вопрос хотя бы из 3 символов.");
      return;
    }
    aiRun(query, aiMode, aiTurns[aiTurns.length - 1].id);
  });
  thread.addEventListener("click", (e) => {
    const copy = e.target.closest("[data-ai-copy]");
    const share = e.target.closest("[data-ai-share]");
    if (copy) {
      const t = aiTurns[Number(copy.dataset.aiCopy)];
      const sources = t.citations.map((c, i) => `${i + 1}. ${c.title || hostOf(c.url)} — ${c.url}`).join("\n");
      copyText(`${t.query}\n\n${t.answer}${sources ? `\n\nИсточники:\n${sources}` : ""}`, copy);
    } else if (share) {
      const t = aiTurns[Number(share.dataset.aiShare)];
      const url = aiShareUrl(t.id);
      if (navigator.share) navigator.share({ title: t.query, url }).catch(() => {});
      else copyText(url, share);
    } else if (e.target.closest("[data-ai-repeat]") && !aiBusy) {
      const t = aiTurns.pop();
      aiRun(t.query, t.mode, t.parent || undefined);
    } else if (e.target.closest("[data-ai-new]")) {
      aiTurns = [];
      drawAi();
      form.elements.query.value = "";
      form.elements.query.focus();
    }
  });

  $("#ai-history").addEventListener("click", (e) => {
    const open = e.target.closest("[data-ai-open]");
    if (open && !aiBusy) aiOpen(open.dataset.aiOpen);
    if (e.target.closest("[data-ai-clear]")) {
      saveAiHistory([]);
      drawAiHistory();
    }
  });

  drawAiHistory();
  const shared = new URLSearchParams(location.search).get("ai");
  if (shared) aiOpen(shared);

  api("/api/ai/status").then((s) => {
    if (s.enabled) return;
    $("#ai-submit").disabled = true;
    setStatus(form, "", "AI-поиск временно недоступен.");
  }).catch(() => {
    $("#ai-submit").disabled = true;
    setStatus(form, "", "AI-поиск временно недоступен.");
  });
}

function start() {
  shell();
  bindAvatarPickers();
  bindReader();
  bindAi();
  bindQA();
  loadQA();
}

// Режим «password» из config.js: форум показывается после ввода пароля.
const UNLOCK_KEY = "forum-unlocked";

async function sha256(text) {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function gate() {
  const expected = CONFIG.passwordSha256.toLowerCase();
  let unlocked = false;
  try { unlocked = sessionStorage.getItem(UNLOCK_KEY) === expected; } catch {}
  if (CONFIG.access !== "password" || unlocked) return start();

  const main = $("main");
  main.hidden = true;
  document.body.insertAdjacentHTML("afterbegin", `
    <section class="container section" id="gate">
      <form class="form glass light" novalidate>
        <h2>Вход на форум</h2>
        <div class="field">
          <label for="gate-password">Пароль</label>
          <input class="input" id="gate-password" type="password" autocomplete="current-password" required>
        </div>
        <button class="btn btn-light" style="justify-self:start">Войти</button>
        <div data-status role="status"></div>
      </form>
    </section>`);
  const form = $("#gate form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!expected || (await sha256(form.elements[0].value)) !== expected) {
      setStatus(form, "error", "Неверный пароль.");
      return;
    }
    try { sessionStorage.setItem(UNLOCK_KEY, expected); } catch {}
    $("#gate").remove();
    main.hidden = false;
    start();
  });
}

gate();
