/* PRESIDENT PRIVATE AGENCY — логика бегущей строки.
   Движение — CSS-анимация transform; JS только собирает трек,
   меряет ширину повтора и управляет скоростью через playbackRate. */
(function(){
  "use strict";

  var STAGE_W = 1920;
  var SHIELD = "../assets/president-favicon-512.png";

  var params = new URLSearchParams(location.search);
  var cycle = clamp(parseFloat(params.get("cycle")) || 10, 8, 12);

  var stage = document.querySelector(".stage");
  var track = stage.querySelector(".track");
  var unitW = 0;

  function clamp(v, a, b){ return Math.min(b, Math.max(a, v)); }

  function metal(text){
    return '<span class="metal" aria-hidden="true">' +
      '<span class="x">' + text + '</span>' +
      '<span class="f">' + text + '</span>' +
      '<span class="r">' + text + '</span>' +
    '</span>';
  }

  function unitHTML(){
    return '<div class="unit">' +
      '<span class="flare f1"></span><span class="flare f2"></span>' +
      '<img class="shield" src="' + SHIELD + '" alt="" draggable="false">' +
      '<div class="lockup">' +
        '<div class="word">' + metal("PRESIDENT") + '</div>' +
        '<div class="sub"><span class="dash"></span>' + metal("PRIVATE AGENCY") + '<span class="dash rev"></span></div>' +
        '<div class="chevron"></div>' +
      '</div>' +
    '</div>';
  }

  function build(){
    track.innerHTML = unitHTML();
    var first = track.firstElementChild;
    // целая ширина повтора — чтобы стык цикла совпадал до пикселя;
    // в предпросмотре сцена масштабирована, поэтому делим на масштаб
    var scale = stage.getBoundingClientRect().width / stage.offsetWidth;
    unitW = Math.ceil(first.getBoundingClientRect().width / scale);
    first.style.width = unitW + "px";

    var copies = Math.ceil(STAGE_W / unitW) + 1;
    var html = "";
    for (var i = 0; i < copies; i++) html += first.outerHTML;
    track.innerHTML = first.outerHTML + html;

    stage.style.setProperty("--unit-w", unitW + "px");
    setCycle(cycle);
  }

  function trackAnim(){
    return track.getAnimations()[0];
  }

  function setCycle(sec){
    cycle = clamp(sec, 8, 12);
    stage.style.setProperty("--cycle", cycle + "s");
  }

  // скорость в px/с относительно сцены 1920×400
  function baseSpeed(){ return unitW / cycle; }

  function setSpeed(pxPerSec){
    var a = trackAnim();
    if (a) a.playbackRate = pxPerSec / baseSpeed();
  }

  // щит должен быть загружен до замера, иначе у него нулевая ширина
  function preloadShield(){
    var img = new Image();
    img.src = SHIELD;
    return img.decode().catch(function(){});
  }

  // fonts.ready сам по себе не ждёт шрифты, которые ещё не начали грузиться
  function loadFonts(){
    return Promise.all([
      document.fonts.load('118px "Marcellus"', "PRESIDENT"),
      document.fonts.load('400 31px "Montserrat"', "PRIVATE AGENCY")
    ]).catch(function(){}).then(function(){ return document.fonts.ready; });
  }

  var ready = Promise.all([loadFonts(), preloadShield()]).then(function(){
    build();
    return Promise.all([].map.call(stage.querySelectorAll("img"), function(img){
      return img.decode().catch(function(){});
    }));
  }).then(function(){
    return { unitW: unitW, cycle: cycle };
  });

  // покадровая перемотка для экспорта: все анимации ставятся на паузу
  // и выставляются на одно и то же время — цикл получается точным
  function seek(ms){
    stage.getAnimations({ subtree: true }).forEach(function(a){
      a.pause();
      a.playbackRate = 1;
      a.currentTime = ms;
    });
  }

  window.Marquee = {
    ready: ready,
    seek: seek,
    setSpeed: setSpeed,
    setCycle: function(sec){ setCycle(sec); },
    baseSpeed: baseSpeed,
    get cycle(){ return cycle; },
    get unitW(){ return unitW; },
    pause: function(){ stage.getAnimations({ subtree: true }).forEach(function(a){ a.pause(); }); },
    play: function(){ stage.getAnimations({ subtree: true }).forEach(function(a){ a.play(); }); }
  };
})();
