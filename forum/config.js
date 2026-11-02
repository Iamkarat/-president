// Настройки доступа к форуму.
//
// access:
//   "link"     — форум открыт всем, у кого есть прямая ссылка (текущий режим).
//   "password" — перед форумом спрашивается пароль. На статическом хостинге
//                (GitHub Pages) это только «занавеска»: файлы форума всё равно
//                доступны по прямым адресам. Настоящая защита — FORUM_PASSWORD
//                в server.py (HTTP Basic Auth) или авторизация на уровне CDN.
// passwordSha256: SHA-256 пароля в hex, например:
//   printf '%s' 'пароль' | shasum -a 256
// apiBase: адрес сервера server.py, например "https://api.example.com".
//   Пустая строка — API на том же домене, что и страница.
window.FORUM_CONFIG = {
  access: "link",
  passwordSha256: "",
  apiBase: "https://presidentmodel-forum-api.onrender.com",
};
