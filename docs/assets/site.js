/* Growth Engine — project website.
   Everything interactive here draws on window.ENGINE_DATA, which tools/build_site_data.py
   exports from the engine itself. This file decides nothing: it shows what was computed. */
(function () {
  'use strict';
  var D = window.ENGINE_DATA;
  if (!D) return;

  // ── helpers ────────────────────────────────────────────────────────────
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  var num = function (n) { return Math.round(n).toLocaleString('en-US'); };
  var pct = function (x) { return Math.round(x * 100); };
  var money = function (v) {
    if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e4) return '$' + Math.round(v / 1e3) + 'K';
    return '$' + num(v);
  };
  var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var unpack = function (o) {
    if (typeof o === 'string') return o.charAt(0) === '~' ? D.strings[+o.slice(1)] : o;
    if (Array.isArray(o)) return o.map(unpack);
    if (o && typeof o === 'object') { var r = {}; Object.keys(o).forEach(function (k) { r[k] = unpack(o[k]); }); return r; }
    return o;
  };
  var TONE = { blue: 'var(--blue)', amber: 'var(--amber)', green: 'var(--green)', purple: 'var(--violet)', violet: 'var(--violet)', red: 'var(--red)', neutral: 'var(--muted)', grey: 'var(--muted)' };
  var OK = '<svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><circle cx="10" cy="10" r="9" fill="rgba(47,214,163,.16)"/><path d="m6 10.3 2.7 2.7L14 7.6" fill="none" style="stroke:var(--green)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var NO = '<svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><circle cx="10" cy="10" r="9" fill="rgba(255,107,107,.18)"/><path d="m7 7 6 6m0-6-6 6" fill="none" style="stroke:var(--red)" stroke-width="2" stroke-linecap="round"/></svg>';

  function countTo(node, to, opt) {
    opt = opt || {};
    var dp = opt.dp || 0, pre = opt.prefix || '', suf = opt.suffix || '';
    var show = function (v) { node.textContent = pre + (dp ? v.toFixed(dp) : num(v)) + suf; };
    if (calm) { show(to); return; }
    var t0 = null, dur = opt.dur || 1400;
    requestAnimationFrame(function step(t) {
      if (t0 === null) t0 = t;
      var k = Math.min(1, (t - t0) / dur);
      show(to * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    });
  }

  function onSeen(node, fn, margin) {
    if (!node) return;
    if (!('IntersectionObserver' in window)) { fn(); return; }
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { io.disconnect(); fn(); } });
    }, { rootMargin: margin || '0px 0px -12% 0px' });
    io.observe(node);
  }

  // ── theme ──────────────────────────────────────────────────────────────
  (function () {
    var root = document.documentElement, btn = $('#themeBtn'), chosen = false;
    try { chosen = /^(light|dark)$/.test(localStorage.getItem('ge-theme') || ''); } catch (e) { /* private mode */ }
    function apply(t, remember) {
      root.setAttribute('data-theme', t);
      if (remember) { chosen = true; try { localStorage.setItem('ge-theme', t); } catch (e) { /* private mode */ } }
      var other = t === 'light' ? 'dark' : 'light';
      btn.setAttribute('aria-label', 'Switch to the ' + other + ' theme');
      btn.title = 'Switch to the ' + other + ' theme';
      $('#themeColor').setAttribute('content', t === 'light' ? '#f6f8fc' : '#070b16');
      document.dispatchEvent(new Event('themechange'));
    }
    btn.addEventListener('click', function () { apply(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light', true); });
    // Follow the system for as long as the visitor has not chosen for themselves.
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: light)');
      var follow = function (e) { if (!chosen) apply(e.matches ? 'light' : 'dark', false); };
      if (mq.addEventListener) mq.addEventListener('change', follow); else if (mq.addListener) mq.addListener(follow);
    }
    apply(root.getAttribute('data-theme') === 'light' ? 'light' : 'dark', false);
  })();

  // ── navigation ─────────────────────────────────────────────────────────
  (function () {
    var nav = $('#nav');
    var stick = function () { nav.classList.toggle('stuck', window.scrollY > 12); };
    stick();
    window.addEventListener('scroll', stick, { passive: true });
    if (!('IntersectionObserver' in window)) return;
    var links = $$('.links a');
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle('here', a.getAttribute('href') === '#' + e.target.id); });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    $$('main section[id]').forEach(function (s) { io.observe(s); });
  })();

  // ── hero: economics, stats ─────────────────────────────────────────────
  (function () {
    var E = D.economics;
    // The card shows a relation, not figures: a cost that stays level and a return that
    // climbs towards it. How far it climbs is the engine's own ratio of return to cost.
    (function () {
      var ratio = Math.max(0.1, Math.min(1, E.revenue_per_contact_target / E.cost_per_contact));
      var w = 360, h = 190, l = 8, r = 352, top = 34, base = 156;
      var y0 = base - 0.08 * (base - top), y1 = base - ratio * (base - top);
      var curve = 'M' + l + ' ' + y0 + ' C ' + (l + 130) + ' ' + (y0 - 2) + ', ' + (r - 120) + ' ' + (y1 + 46) + ', ' + r + ' ' + y1;
      $('#econChart').innerHTML =
        '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="The cost of handling a conversation stays level. What the conversation returns starts low and rises towards it.">' +
        '<defs><linearGradient id="gEcon" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--green)" stop-opacity=".42"/><stop offset="1" style="stop-color:var(--green)" stop-opacity="0"/></linearGradient>' +
        '<linearGradient id="gLine" gradientUnits="userSpaceOnUse" x1="' + l + '" y1="0" x2="' + r + '" y2="0"><stop offset="0" style="stop-color:var(--blue)"/><stop offset="1" style="stop-color:var(--green)"/></linearGradient></defs>' +
        '<line x1="' + l + '" x2="' + r + '" y1="' + base + '" y2="' + base + '" style="stroke:var(--line-2)"/>' +
        '<line x1="' + l + '" x2="' + r + '" y1="' + top + '" y2="' + top + '" style="stroke:var(--muted)" stroke-width="2" stroke-dasharray="5 6"/>' +
        '<text x="' + l + '" y="' + (top - 12) + '" style="fill:var(--soft)">Cost to handle</text>' +
        '<path class="area" d="' + curve + ' L' + r + ' ' + base + ' L' + l + ' ' + base + ' Z" fill="url(#gEcon)"/>' +
        '<path class="ret" pathLength="1" d="' + curve + '" fill="none" stroke="url(#gLine)" stroke-width="3.5" stroke-linecap="round"/>' +
        '<g class="gap"><line x1="' + r + '" x2="' + r + '" y1="' + (top + 5) + '" y2="' + (y1 - 11) + '" style="stroke:var(--muted)" stroke-dasharray="2 4"/></g>' +
        '<g class="tip"><circle class="halo" cx="' + r + '" cy="' + y1 + '" r="7" style="fill:var(--green)"/>' +
        '<circle cx="' + r + '" cy="' + y1 + '" r="6" style="fill:var(--green);stroke:var(--bg)" stroke-width="2.5"/>' +
        '<text x="' + (r - 16) + '" y="' + (y1 - 9) + '" text-anchor="end" style="fill:var(--green)">Return</text></g>' +
        '<text x="' + l + '" y="' + (base + 20) + '" style="fill:var(--muted)">Today</text>' +
        '<text x="' + r + '" y="' + (base + 20) + '" text-anchor="end" style="fill:var(--muted)">With the engine</text>' +
        '</svg>';
      var p = E.cost_offset_pct;
      $('#econWords').textContent = p >= 75 ? 'Most of it' : p >= 50 ? 'More than half' : p >= 25 ? 'A good part of it' : 'A first part of it';
    })();
    onSeen($('.econ'), function () {
      $('.econ').classList.add('go');
      setTimeout(function () { $('#econFill').style.width = E.cost_offset_pct + '%'; }, 900);
    }, '0px');

    var F = D.funnel;
    var stats = [
      { v: F[0].value, t: 'conversations every day. Today, none of them is measured for what it returns.', tag: 'Simulated', c: 'amber' },
      { v: F[3].value, t: 'are worth a sales conversation — about ' + pct(D.rates.triage) + ' in every 100. The rest are left alone.', tag: 'Simulated', c: 'amber' },
      { v: F[5].value, t: 'sales in a day, from conversations that began as a request for help.', tag: 'Simulated', c: 'amber' },
      { v: E.annual_arr, m: true, t: 'new recurring revenue a year. Pays for itself in ' + E.payback_months + ' months.', tag: 'Modelled', c: 'violet' }
    ];
    var box = $('#stats');
    box.innerHTML = stats.map(function (s, i) {
      return '<div class="stat reveal"><b data-i="' + i + '">' + (s.m ? money(s.v) : num(s.v)) + '</b><p>' + esc(s.t) +
        '</p><span class="tag tag-' + s.c + '">' + s.tag + '</span></div>';
    }).join('');
    onSeen(box, function () {
      $$('b[data-i]', box).forEach(function (b) {
        var s = stats[+b.dataset.i];
        if (s.m) { countTo(b, s.v / 1e6, { prefix: '$', suffix: 'M', dp: 1 }); } else { countTo(b, s.v); }
      });
    });
  })();

  // ── hero: the stream of contacts ───────────────────────────────────────
  (function () {
    var cv = $('#streamCanvas');
    if (!cv || !cv.getContext) return;
    var ctx = cv.getContext('2d');
    var W = 0, H = 0, P = [], last = 0, acc = 0, running = false, visible = true;
    var n = { all: 0, sell: 0, solve: 0, held: 0 };
    var pSell = D.rates.triage;
    var pHeld = D.guardrail_evidence.overrides / D.funnel[0].value;
    var DARK = { wait: [148, 163, 184], sell: [47, 214, 163], solve: [91, 157, 255], held: [255, 107, 107], gate: 'rgba(255,255,255,.2)' };
    var LIGHT = { wait: [100, 116, 139], sell: [11, 143, 104], solve: [37, 99, 235], held: [208, 58, 58], gate: 'rgba(15,23,42,.28)' };
    var COL = DARK;
    var paint = function () { COL = document.documentElement.getAttribute('data-theme') === 'light' ? LIGHT : DARK; };
    paint();
    document.addEventListener('themechange', function () { paint(); if (!running) { draw(); } });

    function size() {
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = cv.clientWidth; H = cv.clientHeight;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function spawn(x) {
      var r = Math.random();
      P.push({
        x: x == null ? -12 : x, y: H * (0.27 + 0.5 * Math.random()), v: 62 + Math.random() * 70,
        kind: r < pSell ? 'sell' : (r < pSell + pHeld ? 'held' : 'solve'),
        r: 1.8 + Math.random() * 1.7, done: false, ty: 0, flash: 0, px: 0, py: 0
      });
    }
    function step(dt) {
      var gx = W * 0.58;
      acc += dt * (W < 700 ? 9 : 17);
      while (acc > 1) { acc -= 1; spawn(); }
      for (var i = P.length - 1; i >= 0; i--) {
        var p = P[i];
        p.px = p.x; p.py = p.y;
        p.x += p.v * dt;
        if (!p.done && p.x >= gx) {
          p.done = true;
          n.all++; n[p.kind]++;
          if (p.kind === 'held') n.solve++;
          p.ty = p.kind === 'sell' ? H * (0.24 + 0.15 * Math.random()) : H * (0.58 + 0.21 * Math.random());
          if (p.kind === 'held') p.flash = 1;
        }
        if (p.done) p.y += (p.ty - p.y) * Math.min(1, dt * 2.4);
        if (p.flash > 0) p.flash -= dt * 1.1;
        if (p.x > W + 20) P.splice(i, 1);
      }
    }
    function draw() {
      var gx = W * 0.58;
      ctx.globalCompositeOperation = 'destination-out';
      ctx.fillStyle = 'rgba(0,0,0,.17)';
      ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = COL.gate;
      ctx.setLineDash([4, 7]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(gx, 52); ctx.lineTo(gx, H - 14); ctx.stroke();
      ctx.setLineDash([]);
      P.forEach(function (p) {
        var c = !p.done ? COL.wait : (p.kind === 'sell' ? COL.sell : COL.solve);
        var a = p.done ? 0.95 : 0.55;
        ctx.strokeStyle = 'rgba(' + c + ',' + a * 0.55 + ')';
        ctx.lineWidth = p.r * 1.5;
        ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(p.px, p.py); ctx.lineTo(p.x, p.y); ctx.stroke();
        ctx.fillStyle = 'rgba(' + c + ',' + a + ')';
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.2832); ctx.fill();
        if (p.flash > 0) {
          ctx.strokeStyle = 'rgba(' + COL.held + ',' + Math.max(0, p.flash) + ')';
          ctx.lineWidth = 1.6;
          ctx.beginPath(); ctx.arc(p.x, p.y, 5 + (1 - p.flash) * 16, 0, 6.2832); ctx.stroke();
        }
      });
    }
    var shown = {};
    function counts() {
      [['cAll', n.all], ['cSell', n.sell], ['cSolve', n.solve], ['cHeld', n.held]].forEach(function (c) {
        if (shown[c[0]] !== c[1]) { shown[c[0]] = c[1]; $('#' + c[0]).textContent = num(c[1]); }
      });
    }
    function frame(t) {
      if (!running) return;
      var dt = Math.min(0.05, (t - last) / 1000 || 0.016);
      last = t;
      step(dt); draw(); counts();
      requestAnimationFrame(frame);
    }
    function go() {
      var want = visible && !document.hidden && !calm;
      if (want && !running) { running = true; last = performance.now(); requestAnimationFrame(frame); }
      if (!want) running = false;
    }
    size();
    // Start mid-flow rather than with an empty picture.
    for (var i = 0; i < 260; i++) step(0.05);
    ctx.clearRect(0, 0, W, H);
    for (var k = 0; k < 14; k++) { step(0.016); draw(); }
    counts();
    window.addEventListener('resize', function () { size(); P.length = 0; });
    document.addEventListener('visibilitychange', go);
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) { visible = es[0].isIntersecting; go(); }).observe(cv);
    }
    go();
  })();

  // ── reveal on scroll ───────────────────────────────────────────────────
  function reveal() {
    var nodes = $$('.reveal:not(.in)');
    if (!('IntersectionObserver' in window) || calm) { nodes.forEach(function (x) { x.classList.add('in'); }); return; }
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px' });
    nodes.forEach(function (x, i) { x.style.transitionDelay = (i % 4) * 70 + 'ms'; io.observe(x); });
  }

  // ── decide: the engine, one customer at a time ─────────────────────────
  (function () {
    var C = D.customers, W = D.whatifs;
    var cur = Math.max(0, C.findIndex(function (c) { return c.base.held_by; }));
    var on = {};
    var lastVerdict = null;
    var people = $('#people');

    people.innerHTML = C.map(function (c, i) {
      var ini = c.name.split(' ').map(function (w) { return w.charAt(0); }).join('').slice(0, 2);
      return '<button class="person" type="button" role="tab" data-i="' + i + '"><span class="avatar">' + esc(ini) +
        '</span><span><b>' + esc(c.name) + '</b><small>' + esc(c.base.intent) + '</small></span>' +
        '<span class="pill pill-' + c.base.decision + '">' + c.base.decision.toUpperCase() + '</span></button>';
    }).join('');
    $('#dWhatif').innerHTML = W.map(function (w) {
      return '<button class="chip" type="button" aria-pressed="false" data-w="' + esc(w.id) + '">' + esc(w.label) + '</button>';
    }).join('');

    function outcome(c) {
      var key = W.map(function (w) { return w.id; }).filter(function (id) { return on[id]; }).join('+');
      if (!key) return c.base;
      var o = unpack(c.whatif[key]);
      o.guardrails = o.guardrails.map(function (g, i) {
        return { id: g.id, pass: g.pass, detail: g.detail, name: c.base.guardrails[i].name, block: c.base.guardrails[i].block };
      });
      o.threshold = c.base.threshold;
      return o;
    }

    function render() {
      var c = C[cur], o = outcome(c), changed = o !== c.base;
      $$('.person', people).forEach(function (b, i) {
        b.classList.toggle('on', i === cur);
        b.setAttribute('aria-selected', i === cur ? 'true' : 'false');
      });
      $$('#dWhatif .chip').forEach(function (b) {
        var a = !!on[b.dataset.w];
        b.classList.toggle('on', a); b.setAttribute('aria-pressed', a ? 'true' : 'false');
      });
      $('#dReset').hidden = !changed;
      $('#dName').textContent = c.name;
      $('#dStory').textContent = c.story;
      $('#dFacts').innerHTML = [c.plan, c.value, 'Customer for ' + c.tenure, 'Calling about: ' + o.intent, o.segment_name]
        .map(function (f, i) {
          return '<span class="chip chip-fact"' + (i === 4 ? ' style="color:' + (TONE[o.segment_tone] || TONE.blue) + ';border-color:currentColor"' : '') + '>' + esc(f) + '</span>';
        }).join('');

      var held = o.decision === 'solve' && (o.held_by || o.override);
      var kind = o.decision === 'sell' ? 'sell' : (held ? 'held' : 'solve');
      var v = $('#dVerdict');
      v.className = 'verdict ' + kind;
      v.innerHTML = '<b>' + (o.decision === 'sell' ? 'SELL' : 'SOLVE') + '</b><span>' +
        (kind === 'sell' ? 'Worth a sales conversation' : kind === 'held' ? 'Held back — no offer is made' : 'Solve the problem. Nothing to sell.') +
        (changed && o.decision !== c.base.decision ? '<br><em style="font-style:normal;opacity:.8">was ' + c.base.decision.toUpperCase() + ' before the change</em>' : '') + '</span>';
      var sig = cur + kind;
      if (lastVerdict !== null && lastVerdict !== sig && !calm) { void v.offsetWidth; v.classList.add('flash'); }
      lastVerdict = sig;

      var p = pct(o.propensity), line = pct(o.threshold);
      $('#dPct').textContent = p;
      $('#dLine').textContent = line;
      var fill = $('#dFill');
      fill.style.width = Math.max(2, p) + '%';
      fill.classList.toggle('low', p < line);
      $('#dMark').style.left = 'calc(' + line + '% - 1px)';
      var ov = $('#dOverride');
      ov.hidden = !o.override;
      ov.textContent = o.override || '';

      var max = Math.max.apply(null, o.features.map(function (f) { return Math.abs(f.contribution); })) || 1;
      $('#dEvidence').innerHTML = o.features.map(function (f) {
        var up = f.contribution >= 0, w = Math.max(1.5, Math.abs(f.contribution) / max * 50);
        return '<div class="ev"><div class="ev-head"><span>' + esc(f.name) + '</span><span class="' + (up ? 'up-t' : 'down-t') + '">' +
          (up ? '▲ +' : '▼ −') + Math.abs(f.contribution).toFixed(2) + '</span></div><div class="ev-bar"><i class="' + (up ? 'up' : 'down') +
          '" style="width:' + w + '%"></i></div><small>' + esc(f.value) + '</small></div>';
      }).join('');

      $('#dRails').innerHTML = o.guardrails.map(function (g) {
        return '<li class="' + (g.pass ? '' : 'block') + '">' + (g.pass ? OK : NO) + '<span>' + esc(g.pass ? g.name : g.block) +
          '<small>' + esc(g.detail) + '</small></span></li>';
      }).join('');

      var next = '';
      if (o.offer) {
        next += '<div class="offer"><b>' + esc(o.offer.value) + ' <span class="tag tag-green" style="vertical-align:middle">' + esc(o.offer.type) +
          (o.offer.crosses ? ' · across suites' : '') + '</span></b>' + esc(o.offer.action) + '</div>';
      }
      next += '<div class="route">Routed to <code>' + esc(o.routing.queue) + '</code><br><span class="muted">' + esc(o.routing.skill) + '</span></div>';
      if (!o.offer) next += '<p class="muted">No offer is prepared. The agent is told to solve the problem and nothing else.</p>';
      $('#dNext').innerHTML = next;
    }

    people.addEventListener('click', function (e) {
      var b = e.target.closest('.person'); if (!b) return;
      cur = +b.dataset.i; on = {}; render();
    });
    $('#dWhatif').addEventListener('click', function (e) {
      var b = e.target.closest('.chip'); if (!b) return;
      on[b.dataset.w] = !on[b.dataset.w]; render();
    });
    $('#dReset').addEventListener('click', function () { on = {}; render(); });
    render();
  })();

  // ── funnel and threshold ───────────────────────────────────────────────
  (function () {
    var F = D.funnel, S = D.sweep, top = F[0].value;
    var base = S.findIndex(function (s) { return Math.abs(s.threshold - D.threshold) < 1e-6; });
    if (base < 0) base = 5;
    var cols = ['#6b7a99', '#7a8fc0', '#5b9dff', '#7f8dff', '#9b7bff', '#2fd6a3'];
    var box = $('#funnelBars');
    box.innerHTML = '<p class="kicker">' + esc(D.source) + '</p>' + F.map(function (s, i) {
      return '<div class="fr' + (i >= 3 ? ' live' : '') + '" data-i="' + i + '"><div class="fr-head"><span>' + esc(s.stage) +
        '</span><b>0</b></div><div class="fr-bar"><i style="background:' + cols[i] + '"></i></div><small>' + esc(s.note) + '</small></div>';
    }).join('') + '<p class="fine" style="margin-top:14px">Bar lengths are on a square-root scale, so the small numbers stay visible.</p>';

    var seen = false;
    function bars(s, animate) {
      var v = [F[0].value, F[1].value, F[2].value, s.sell_treated, s.qualified, s.converted];
      $$('.fr', box).forEach(function (row, i) {
        $('i', row).style.width = Math.sqrt(v[i] / top) * 100 + '%';
        var b = $('b', row);
        if (animate) countTo(b, v[i], { dur: 1100 }); else b.textContent = num(v[i]);
      });
    }
    function delta(now, was, goodUp) {
      if (now === was) return '';
      var up = now > was;
      // Offering fewer conversations is neither good nor bad in itself, so it carries no colour.
      return '<em class="' + (goodUp === null ? 'muted' : (up === goodUp) ? 'up-t' : 'down-t') + '">' + (up ? '▲' : '▼') + ' ' +
        num(Math.abs(now - was)) + '</em>';
    }
    function chart(i) {
      var w = 520, h = 170, l = 12, r = 12, t = 14, b = 30;
      var x = function (k) { return l + k * (w - l - r) / (S.length - 1); };
      var rv = S.map(function (s) { return s.revenue_day; });
      var lo = Math.min.apply(null, rv), hi = Math.max.apply(null, rv);
      var yr = function (v) { return t + (1 - (v - lo) / (hi - lo)) * (h - t - b); };
      var yp = function (v) { return t + (1 - v) * (h - t - b); };
      var line = function (f) { return S.map(function (s, k) { return (k ? 'L' : 'M') + x(k).toFixed(1) + ' ' + f(s).toFixed(1); }).join(' '); };
      var rev = line(function (s) { return yr(s.revenue_day); });
      var pre = line(function (s) { return yp(s.precision); });
      var ticks = S.map(function (s, k) {
        return k % 2 ? '' : '<text x="' + x(k) + '" y="' + (h - 8) + '" text-anchor="middle" font-size="11" style="fill:var(--muted)" font-family="Inter,sans-serif">' + pct(s.threshold) + '%</text>';
      }).join('');
      $('#dialChart').innerHTML =
        '<defs><linearGradient id="gRev" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--green)" stop-opacity=".3"/><stop offset="1" style="stop-color:var(--green)" stop-opacity="0"/></linearGradient></defs>' +
        '<path d="' + rev + ' L' + x(S.length - 1) + ' ' + (h - b) + ' L' + x(0) + ' ' + (h - b) + ' Z" fill="url(#gRev)"/>' +
        '<path d="' + rev + '" fill="none" style="stroke:var(--green)" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<path d="' + pre + '" fill="none" style="stroke:var(--violet)" stroke-width="2.5" stroke-linejoin="round"/>' +
        '<line x1="' + x(i) + '" x2="' + x(i) + '" y1="' + t + '" y2="' + (h - b) + '" style="stroke:var(--mark)" stroke-opacity=".55" stroke-width="1.5"/>' +
        '<circle cx="' + x(i) + '" cy="' + yr(S[i].revenue_day) + '" r="5.5" style="fill:var(--green);stroke:var(--bg)" stroke-width="2"/>' +
        '<circle cx="' + x(i) + '" cy="' + yp(S[i].precision) + '" r="5.5" style="fill:var(--violet);stroke:var(--bg)" stroke-width="2"/>' + ticks;
    }
    function set(i) {
      var s = S[i], z = S[base];
      $('#thrOut').textContent = pct(s.threshold) + '%';
      $('#dialMetrics').innerHTML = [
        ['Customers offered a sales conversation', num(s.sell_treated), delta(s.sell_treated, z.sell_treated, null)],
        ['Offers that land on a real opportunity', pct(s.precision) + ' in 100', ''],
        ['Sales made', num(s.converted), delta(s.converted, z.converted, true)],
        ['Revenue a day', '$' + num(s.revenue_day), delta(s.revenue_day, z.revenue_day, true)]
      ].map(function (m) { return '<div class="dm"><b>' + m[1] + m[2] + '</b><span>' + m[0] + '</span></div>'; }).join('');
      $('#dialNote').textContent = 'At ' + pct(s.threshold) + '%, ' + num(s.no_opportunity) + ' of the ' + num(s.sell_treated) +
        ' sales conversations turn out to have nothing in them. ' +
        (i < base ? 'A lower line finds more sales, and interrupts more customers to find them.'
          : i > base ? 'A higher line interrupts fewer customers, and leaves sales unfound.'
            : 'This is where the demo draws the line.');
      chart(i);
      if (seen) bars(s, false);
    }
    var slider = $('#thr');
    slider.max = S.length - 1; slider.value = base;
    slider.addEventListener('input', function () { set(+slider.value); });
    set(base);
    onSeen(box, function () { seen = true; bars(S[+slider.value], true); });

    $('#segments').innerHTML = D.segments.map(function (g) {
      return '<div class="sg" style="--c:' + (TONE[g.tone] || TONE.blue) + '"><b>' + esc(g.name) + '</b><strong>' + (g.share * 100).toFixed(1) +
        '%</strong><p>' + esc(g.definition) + '</p><span class="pill pill-' + g['default'] + '">' + g['default'].toUpperCase() + ' by default</span></div>';
    }).join('');
  })();

  // ── the call player ────────────────────────────────────────────────────
  (function () {
    var K = D.calls, ci = 0, turn = -1, playing = false, speed = 1, timer = null, shownSignals = 0, lastTip = null;
    var RING = 207.3;
    var tabs = $('#callTabs'), bubbles = $('#callBubbles');
    tabs.innerHTML = K.map(function (c, i) {
      return '<button class="tab" type="button" role="tab" data-i="' + i + '"><b>' + esc(c.customer.split(' ')[0]) + '</b><small>' +
        (c.decision === 'sell' ? (c.result ? esc(c.result.estimated_value) + ' lead' : 'Sell') : 'Held back') + '</small></button>';
    }).join('');

    function ring(id, v, colour) {
      var r = $('#' + id);
      $('b', r).textContent = Math.round(v);
      var c = $('circle.v', r);
      c.style.strokeDashoffset = RING * (1 - Math.max(0, Math.min(100, v)) / 100);
      if (colour) c.style.stroke = colour;
    }
    function reset() {
      clearTimeout(timer); timer = null; playing = false; turn = -1; shownSignals = 0; lastTip = null;
      var c = K[ci];
      $$('.tab', tabs).forEach(function (b, i) { b.classList.toggle('on', i === ci); b.setAttribute('aria-selected', i === ci ? 'true' : 'false'); });
      $('#callWho').innerHTML = '<b>' + esc(c.customer) + '</b><span>' + esc(c.role) + '</span><span class="tag tag-blue">' + esc(c.segment) +
        '</span><span class="pill pill-' + c.decision + '">' + c.decision.toUpperCase() + '</span><span class="muted">' + pct(c.propensity) + '% likely to buy</span>';
      bubbles.innerHTML = '<p class="empty">' + esc(c.about) + '</p>';
      $('#callSignals').innerHTML = '<p class="empty">Nothing heard yet.</p>';
      $('#callAdvice').innerHTML = '<p class="empty">' + (c.override ? esc(c.override) : 'Advice appears as the conversation gives it something to go on.') + '</p>';
      $('#callResult').hidden = true;
      $('#callProgress').style.width = '0%';
      $('#callPlay').textContent = 'Play';
      ring('ringScore', 0); ring('ringMood', 50, TONE.amber);
    }
    function show(i) {
      var c = K[ci], t = c.turns[i];
      if (i === 0) bubbles.innerHTML = '';
      var old = $('.typing', bubbles); if (old) old.remove();
      var b = document.createElement('div');
      b.className = 'bubble ' + t.role;
      b.innerHTML = '<small>' + (t.role === 'agent' ? 'Agent' : 'Customer') + '</small>' + esc(t.text);
      bubbles.appendChild(b);
      ring('ringScore', t.score, t.score >= 70 ? TONE.green : t.score >= 40 ? TONE.amber : TONE.neutral);
      ring('ringMood', t.sentiment * 100, t.sentiment < 0.35 ? TONE.red : t.sentiment < 0.6 ? TONE.amber : TONE.green);
      if (t.signals.length !== shownSignals) {
        shownSignals = t.signals.length;
        $('#callSignals').innerHTML = t.signals.length ? t.signals.map(function (s) {
          return '<div class="signal"><div><b>' + esc(s.category) + '</b><span>' + pct(s.confidence) + '% confident</span></div>' + esc(s.signal) + '</div>';
        }).join('') : '<p class="empty">Nothing heard yet.</p>';
      }
      if (t.coaching && t.coaching.text !== lastTip) {
        lastTip = t.coaching.text;
        $('#callAdvice').innerHTML = '<div class="tip">' + esc(t.coaching.text) + (t.coaching.sources.length ? '<div class="src">' +
          t.coaching.sources.map(function (s) { return '<span>' + esc(s.id) + ' · ' + esc(s.title) + '</span>'; }).join('') + '</div>' : '') + '</div>';
      }
      $('#callProgress').style.width = ((i + 1) / c.turns.length * 100) + '%';
    }
    function finish() {
      var c = K[ci], r = $('#callResult');
      playing = false;
      $('#callPlay').textContent = 'Replay';
      if (c.result && c.decision === 'sell') {
        r.className = 'result lead';
        r.innerHTML = '<span class="tag tag-green">Lead captured</span><b>' + esc(c.result.estimated_value) + ' <small style="font-size:14px;font-weight:500;color:var(--soft)">more, every year</small></b><p>' +
          esc(c.result.recommended_action) + '</p>';
      } else if (c.resolution) {
        r.className = 'result nolead';
        r.innerHTML = '<span class="tag tag-blue">No offer made</span><b>' + esc(c.resolution.outcome) + '</b><p>' + esc(c.resolution.detail) + '</p>';
      } else { return; }
      r.hidden = false;
    }
    function next() {
      var c = K[ci];
      if (!playing) return;
      if (turn >= c.turns.length - 1) { finish(); return; }
      var t = c.turns[turn + 1];
      if (turn + 1 === 0) bubbles.innerHTML = '';
      var dots = document.createElement('div');
      dots.className = 'typing ' + t.role;
      dots.innerHTML = '<i></i><i></i><i></i>';
      bubbles.appendChild(dots);
      timer = setTimeout(function () {
        turn++; show(turn);
        timer = setTimeout(next, (1500 + t.text.length * 16) / speed);
      }, (calm ? 0 : 850) / speed);
    }
    function play() {
      if (playing) { playing = false; clearTimeout(timer); var d = $('.typing', bubbles); if (d) d.remove(); $('#callPlay').textContent = 'Play'; return; }
      if (turn >= K[ci].turns.length - 1) reset();
      playing = true; $('#callPlay').textContent = 'Pause'; next();
    }
    tabs.addEventListener('click', function (e) {
      var b = e.target.closest('.tab'); if (!b) return;
      ci = +b.dataset.i; reset(); play();
    });
    $('#callPlay').addEventListener('click', play);
    $('#callRestart').addEventListener('click', function () { reset(); play(); });
    $$('.controls .seg button').forEach(function (b) {
      b.addEventListener('click', function () {
        speed = +b.dataset.speed;
        $$('.controls .seg button').forEach(function (x) { x.classList.toggle('on', x === b); });
      });
    });
    reset();
    if (!calm) onSeen($('.player'), function () { if (!playing && turn < 0) play(); }, '0px 0px -30% 0px');
  })();


  // ── training mode ──────────────────────────────────────────────────────
  (function () {
    var T = D.training;
    if (!T) return;
    var MOVE = { greet: 'a greeting', empathy: 'empathy', verify: 'identity check', diagnose: 'a question, or a look at the account',
      explain: 'an explanation', fix: 'a fix', offer: 'an offer', price: 'a price', pressure: 'pressure', close: 'a close', reflect: 'playing it back', hold: 'a hold' };
    var WHY = {
      advanced: ['The call moves on', 'You did what the call needed. The customer tells you the next thing — and you learn more than you asked.', 'green'],
      answered: ['They answer, and wait', 'A straight answer to your question. Now do something with it.', 'blue'],
      holding: ['They wait', 'Asked to hold, a customer holds. Not for long.', 'blue'],
      stalled: ['Nothing happened', 'Words without an action. The customer repeats themselves, a little less patient than before.', 'amber'],
      pitched_early: ['Too soon', 'An offer before the problem is understood is a pitch. The customer pushes back, and the opening is harder to reach later.', 'amber'],
      pitched_when_not_selling: ['Compliance breach', 'An offer into a complaint. The engine had held this customer back; the debrief will cap the score at 49.', 'red'],
      pressure: ['Pressure', 'Manufactured urgency. The customer refuses to decide on the spot, and trusts you less.', 'red']
    };
    var cur = 0, tabs = $('#tryTabs');
    tabs.innerHTML = T.tryouts.map(function (t, i) {
      return '<button class="tab" type="button" role="tab" data-i="' + i + '"><b>' + esc(t.name.split(' ')[0]) + '</b><small>arrives ' + esc(t.mood_label) + '</small></button>';
    }).join('');
    function moodBar(a, b, label) {
      return '<div class="mood-move"><span>Mood</span><div class="track"><i style="width:' + Math.round(b * 100) + '%;background:' + TONE[b < 0.3 ? 'red' : b < 0.45 ? 'amber' : 'green'] + '"></i></div>' +
        '<b>' + esc(label) + '</b><span class="' + (b > a ? 'up-t' : b < a ? 'down-t' : 'muted') + '">' + (b > a ? '▲' : b < a ? '▼' : '—') + '</span></div>';
    }
    function show(sel) {
      var t = T.tryouts[cur];
      $$('.tab', tabs).forEach(function (b, i) { b.classList.toggle('on', i === cur); b.setAttribute('aria-selected', i === cur ? 'true' : 'false'); });
      $('#tryCust').innerHTML = '<div class="who"><b>' + esc(t.name) + '</b><span>' + esc(t.role) + '</span><span class="tag tag-' +
        (t.mood_label === 'upset' ? 'red' : t.mood_label === 'wary' ? 'amber' : 'blue') + '">' + esc(t.mood_label) + '</span></div><blockquote>' + esc(t.opening) +
        '</blockquote><p class="fine">In the application this is spoken aloud, in ' + esc(t.name.split(' ')[0]) + '\u2019s own voice. The lesson: ' + esc(t.focus.toLowerCase()) + '.</p>';
      $('#tryReplies').innerHTML = t.replies.map(function (r, i) {
        return '<button class="reply' + (sel === i ? ' on' : '') + '" type="button" data-i="' + i + '" aria-pressed="' + (sel === i ? 'true' : 'false') + '"><b>' + esc(r.label) + '</b><span>' + esc(r.text) + '</span></button>';
      }).join('');
      var box = $('#tryResult');
      if (sel == null) { box.hidden = true; return; }
      var r = t.replies[sel], w = WHY[r.why] || ['The customer reacts', '', 'blue'];
      box.hidden = false;
      box.innerHTML = '<div class="reaction"><div class="who"><b>' + esc(t.name.split(' ')[0]) + '</b><span class="muted">replies</span></div><p>' + esc(r.reaction) + '</p></div>' +
        '<div class="verdict-box"><h4><span class="tag tag-' + w[2] + '">' + esc(w[0]) + '</span></h4>' + moodBar(r.mood_before, r.mood_after, r.mood_label) +
        '<p>' + esc(w[1]) + '</p><p class="fine" style="margin-top:10px">What the engine heard in your words: ' +
        (r.moves.length ? esc(r.moves.map(function (m) { return MOVE[m] || m; }).join(', ')) : 'nothing it could act on') + '.</p></div>';
    }
    tabs.addEventListener('click', function (e) { var b = e.target.closest('.tab'); if (!b) return; cur = +b.dataset.i; show(null); });
    $('#tryReplies').addEventListener('click', function (e) { var b = e.target.closest('.reply'); if (!b) return; show(+b.dataset.i); });
    show(null);

    $('#skills').innerHTML = T.customers.map(function (c) {
      var tag = c.held ? '<span class="tag tag-red">Held back</span>' : c.decision === 'sell' ? '<span class="tag tag-green">Sell</span>' : '<span class="tag tag-grey">Solve</span>';
      return '<div class="skill"><header><b>' + esc(c.name.split(' ')[0]) + '</b>' + tag + '</header><p><strong>Practise:</strong> ' + esc(c.focus) + '</p><small>Arrives ' + esc(c.opening_mood) + '</small></div>';
    }).join('');

    function debrief(d, title) {
      var C = 2 * Math.PI * 31, tone = d.compliance === 'breach' ? 'red' : d.overall >= 90 ? 'green' : d.overall >= 75 ? 'blue' : 'amber';
      var w = 150, h = 34, pts = d.moods.map(function (m, i) { return ((i / Math.max(1, d.moods.length - 1)) * w).toFixed(1) + ',' + (h - m * h).toFixed(1); }).join(' ');
      return '<div class="dbf"><div class="dbf-top"><div class="dbf-ring"><svg viewBox="0 0 74 74"><circle cx="37" cy="37" r="31" style="stroke:var(--fill-3)"/>' +
        '<circle cx="37" cy="37" r="31" style="stroke:' + TONE[tone] + '" stroke-linecap="round" stroke-dasharray="' + (C * d.overall / 100).toFixed(1) + ' ' + C.toFixed(1) + '"/></svg><b>' + d.overall + '</b></div>' +
        '<div><h3>' + esc(title) + '</h3><p>' + esc(d.customer) + ' · ' + esc(d.difficulty) + ' · ' + d.turns + ' turns · ' + d.hints + ' hint' + (d.hints === 1 ? '' : 's') + '</p>' +
        '<span class="tag tag-' + tone + '">' + esc(d.band) + (d.compliance === 'breach' ? ' · compliance breach' : '') + '</span></div></div>' +
        '<ul>' + d.objectives.map(function (o) {
          var k = o.bad ? 'bad' : o.done ? 'ok' : 'miss';
          return '<li class="' + k + '"><i>' + (o.bad ? '✕' : o.done ? '✓' : '–') + '</i><span>' + esc(o.label) + '</span></li>';
        }).join('') + '</ul>' +
        '<div class="mood"><svg width="' + w + '" height="' + (h + 4) + '" viewBox="0 -2 ' + w + ' ' + (h + 4) + '"><line x1="0" x2="' + w + '" y1="' + h / 2 + '" y2="' + h / 2 + '" style="stroke:var(--line-2)" stroke-dasharray="3 4"/>' +
        '<polyline points="' + pts + '" fill="none" style="stroke:' + TONE[tone] + '" stroke-width="2.5" stroke-linejoin="round"/></svg><span>' + esc(d.verdict) + '</span></div>' +
        '<p class="note" style="background:' + (tone === 'red' ? 'rgba(255,107,107,.1)' : tone === 'amber' ? 'rgba(246,185,74,.1)' : 'rgba(47,214,163,.1)') + ';color:var(--' + tone + ')">' + esc(d.tips[0] || d.note) + '</p></div>';
    }
    $('#debriefs').innerHTML = debrief(T.debriefs.good, 'A good call') + debrief(T.debriefs.bad, 'The customer the engine held back, sold to');

    $('#trainShots').innerHTML = [['training-pick', 'Choosing a customer', 'Nine customers, three difficulties, and a sound check.'],
      ['training-call', 'On the call', 'Your words as you speak them; the customer\u2019s reply in their voice; the checklist filling in.'],
      ['training-debrief', 'The debrief', 'Score with evidence, how the customer felt, what to work on next.']].map(function (s) {
      return '<figure class="shot" style="margin:0"><img loading="lazy" decoding="async" width="1600" height="900" src="shots/' + s[0] + '.webp" alt="' + esc(s[1] + ': ' + s[2]) + '"><div><b>' + esc(s[1]) + '</b><span>' + esc(s[2]) + '</span></div></figure>';
    }).join('');
  })();

  // ── guardrails ─────────────────────────────────────────────────────────
  (function () {
    var ICON = {
      shield: '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 4.5 6v5.6c0 4.5 3 8.2 7.5 9.4 4.5-1.2 7.5-4.9 7.5-9.4V6z"/><path d="M12 8.5v4.2m0 3h.01"/></svg>',
      hand: '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m5.7 5.7 12.6 12.6"/></svg>',
      clock: '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/></svg>',
      pause: '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="3.5" width="17" height="17" rx="4"/><path d="M9.5 8.5v7m5-7v7"/></svg>'
    };
    var R = [
      ['shield', 'Checked first', 'Service recovery', 'There is an unresolved failure on the account. This one overrides the score entirely, however likely the sale looks.'],
      ['hand', 'Checked second', 'Marketing consent', 'The customer has opted out of offers. Their word is final, and the engine does not look for a way round it.'],
      ['clock', 'Checked third', 'Offer cooldown', 'An offer was made in the last 30 days. A customer who calls again tomorrow is helped, not pitched a second time.'],
      ['pause', 'Checked fourth', 'Commercial hold', 'A hold is set for 14 days after a service recovery, so that putting things right is never followed by a sales call.']
    ];
    $('#railCards').innerHTML = R.map(function (r) {
      return '<article class="card rail reveal">' + ICON[r[0]] + '<em>' + r[1] + '</em><h3>' + r[2] + '</h3><p>' + r[3] + '</p></article>';
    }).join('');
    var g = D.guardrail_evidence;
    $('#railProof').innerHTML =
      '<div><b data-v="' + g.recovery_contacts + '">0</b><p>customers called in one simulated day with a problem that had not been put right.</p></div>' +
      '<div><b data-v="' + g.recovery_offers_made + '">0</b><p>offers were made to any of them. A test fails the build if this number is ever anything else.</p></div>' +
      '<div><b data-v="' + g.overrides + '">0</b><p>customers were likely buyers and were held back anyway — ' + num(g.by_rule.consent || 0) +
      ' had opted out, ' + num(g.by_rule.recovery || 0) + ' had a problem outstanding.</p></div>';
    onSeen($('#railProof'), function () { $$('#railProof b').forEach(function (b) { countTo(b, +b.dataset.v); }); });
  })();

  // ── learning ───────────────────────────────────────────────────────────
  (function () {
    var T = D.model.challenger, a = T.evaluation.champion, b = T.evaluation.challenger;
    var row = function (cls, label, width, text) {
      return '<div class="duel-row ' + cls + '"><span>' + label + '</span><div class="duel-bar"><i data-w="' + width.toFixed(1) + '"></i></div><b>' + text + '</b></div>';
    };
    var auc = function (v) { return Math.max(0, (v - 0.5) / 0.5 * 100); };
    $('#duel').innerHTML =
      '<h4>How well it ranks customers · 0.50 is chance, 1.00 is perfect</h4>' +
      row('champ', 'In use today · ' + esc(D.model_version), auc(a.auc), a.auc.toFixed(2)) +
      row('chall', 'New version · ' + esc(T.version), auc(b.auc), b.auc.toFixed(2)) +
      '<h4>Offers that land on a real opportunity</h4>' +
      row('champ', 'In use today · ' + esc(D.model_version), a.precision * 100, pct(a.precision) + '%') +
      row('chall', 'New version · ' + esc(T.version), b.precision * 100, pct(b.precision) + '%') +
      '<p class="gain"><b>+' + num(T.verdict.extra_opportunities) + ' real opportunities a day</b> from the same ' + num(T.verdict.volume) +
      ' conversations. Trained on ' + num(T.trained_on.examples) + ' outcomes from three simulated days.</p>';
    $('#duelNote').textContent = 'The simulation’s hidden truth was written to differ from the first model on purpose. This shows that the loop works — not how much a real model would improve.';
    onSeen($('#duel'), function () { $$('#duel i').forEach(function (i) { i.style.width = i.dataset.w + '%'; }); });

    var M = T.moves.slice().sort(function (x, y) { return Math.abs(y.delta) - Math.abs(x.delta); }).slice(0, 6);
    var span = Math.max.apply(null, M.map(function (m) { return Math.max(Math.abs(m.from), Math.abs(m.to)); })) * 1.08;
    var pos = function (v) { return 50 + v / span * 50; };
    $('#moves').innerHTML = M.map(function (m) {
      var l = Math.min(pos(m.from), pos(m.to)), w = Math.abs(pos(m.to) - pos(m.from));
      return '<div class="mv"><div class="mv-head"><span>' + esc(m.name) + '</span><span>' + m.from.toFixed(2) + ' → ' + m.to.toFixed(2) + '</span></div>' +
        '<div class="mv-bar"><i style="left:' + l + '%;width:' + w + '%;background:' + (m.delta > 0 ? TONE.green : TONE.red) + '"></i><u style="left:calc(' + pos(m.to) + '% - 1px)"></u></div></div>';
    }).join('') + '<p class="fine">Each bar runs from the old weight to the new one. The white mark is where it landed; the middle of the track is zero.</p>';
  })();

  // ── platform ───────────────────────────────────────────────────────────
  (function () {
    var P = D.platform, op = 0, aud = 0, view = 'neutral';
    var chips = $('#opChips');
    chips.innerHTML = P.operations.map(function (o, i) {
      return '<button class="chip" type="button" role="tab" data-i="' + i + '" style="font-family:var(--mono);font-size:12.5px">' + esc(o.op) + '()</button>';
    }).join('');
    function ops() {
      var o = P.operations[op];
      $$('.chip', chips).forEach(function (b, i) { b.classList.toggle('on', i === op); b.setAttribute('aria-selected', i === op ? 'true' : 'false'); });
      $('#opDoes').textContent = o.does;
      $('#opCols').innerHTML = [
        ['Built-in store', o.local, 'SQLite, in-process', 'Tested', 'green'],
        ['Apache Unomi 3', o.unomi, 'Open source · Apache 2.0', 'Tested', 'green'],
        [P.vendor_label, o.vendor, o.vendor_api, 'Not exercised', 'amber']
      ].map(function (c) {
        return '<div class="pc"><header><b>' + esc(c[0]) + '</b><span class="tag tag-' + c[4] + '">' + c[3] + '</span></header><code>' + esc(c[1]) +
          '</code><small>' + esc(c[2]) + '</small></div>';
      }).join('');
    }
    chips.addEventListener('click', function (e) { var b = e.target.closest('.chip'); if (!b) return; op = +b.dataset.i; ops(); });
    ops();

    var pick = $('#audPick');
    pick.innerHTML = P.audiences.map(function (a, i) { return '<option value="' + i + '">' + esc(a.name) + '</option>'; }).join('');
    function audience() {
      var a = P.audiences[aud];
      $('#audDesc').textContent = a.description;
      $('#audCode').textContent = view === 'query' ? a.query : JSON.stringify(a[view], null, 2);
      $$('#audTabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.k === view); });
    }
    pick.addEventListener('change', function () { aud = +pick.value; audience(); });
    $('#audTabs').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; view = b.dataset.k; audience(); });
    aud = Math.max(0, P.audiences.findIndex(function (a) { return /licence/i.test(a.id); }));
    pick.value = aud;
    audience();

    var tag = { weaker: 'amber', different: 'blue', 'not covered': 'red', equivalent: 'green' };
    $('#gaps').innerHTML = '<div class="trow"><span>Capability</span><span>In this prototype</span><span>On a commercial platform</span><span></span></div>' +
      P.gaps.map(function (g) {
        return '<div class="trow"><span>' + esc(g.capability) + '</span><span>' + esc(g.here) + '</span><span>' + esc(g.vendor) +
          '</span><span class="tag tag-' + (tag[g.parity] || 'grey') + '" style="justify-self:start">' + esc(g.parity) + '</span></div>';
      }).join('');
  })();

  // ── architecture ───────────────────────────────────────────────────────
  (function () {
    var A = D.architecture, map = $('#archMap'), detail = $('#archDetail'), cap = $('#archCaption');
    var KIND = { existing: 'var(--blue)', vendor: 'var(--red)', ai: 'var(--amber)', connector: 'var(--green)', foundation: 'var(--violet)', aws: 'var(--blue)' };
    var STATUS = { built: ['Built', 'green'], partial: ['Partly built', 'amber'], planned: ['Planned', 'violet'], reference: ['Reference only', 'grey'] };
    var kindLabel = {}, comps = {}, filter = null, sel = null, step = -1, playing = false, timer = null;
    A.legend.forEach(function (l) { kindLabel[l.key] = l.label; });

    function card(c) {
      comps[c.id] = c;
      var s = STATUS[c.status];
      return '<button class="ac" type="button" data-id="' + esc(c.id) + '" data-status="' + c.status + '" style="--k:' + KIND[c.kind] + '"><b>' + esc(c.name) +
        (c.star ? '<i title="New or changed in the target state" aria-hidden="true">★</i>' : '') + '</b><span class="tag tag-' + s[1] + '">' + (c.status === 'reference' ? 'Reference' : s[0]) + '</span>' +
        ((c.agents || []).length ? '<span class="ac-agents">' + c.agents.map(function (a) {
          return '<span title="' + esc(a.name) + '">' + a.n + '</span>';
        }).join('') + '</span>' : '') + '</button>';
    }
    function band(l) {
      var n = l.components.length;
      return '<section class="aband' + (l.highlight ? ' hl' : '') + '" style="--k:' + (KIND[l.tone] || 'var(--muted)') + '"><header>' + esc(l.title) +
        (l.badge ? '<em>' + esc(l.badge) + '</em>' : '') + '</header><div class="acs' + (n < 4 ? ' cols-' + n : '') + '">' + l.components.map(card).join('') + '</div></section>';
    }
    var html = '', half = [];
    var flush = function () { if (half.length) { html += '<div class="arch-split">' + half.join('') + '</div>'; half = []; } };
    A.layers.forEach(function (l) {
      if (l.type === 'connector') { flush(); html += '<div class="aconn" data-id="' + esc(l.id) + '">' + esc(l.title) + '</div>'; return; }
      if (l.width && l.width < 1) { half.push(band(l)); return; }
      flush(); html += band(l);
    });
    flush();
    map.innerHTML = html;

    var counts = A.summary.by_status;
    $('#archFilter').innerHTML = Object.keys(STATUS).map(function (k) {
      return '<button class="chip" type="button" aria-pressed="false" data-k="' + k + '">' + STATUS[k][0] + ' · ' + (counts[k] || 0) + '</button>';
    }).join('');
    $('#archLegend').innerHTML = A.legend.filter(function (l) { return l.key !== 'connector'; }).map(function (l) {
      return '<span><i style="background:' + KIND[l.key] + '"></i>' + esc(l.label) + '</span>';
    }).join('') + '<span><i style="background:var(--fill-3);border-radius:50%"></i>Numbers are the agents that work there</span>';

    function overview() {
      detail.innerHTML = '<p class="kicker">How much of it runs</p><div class="arch-tally">' + Object.keys(STATUS).map(function (k) {
        return '<div><b>' + (counts[k] || 0) + '</b><span>' + STATUS[k][0] + '</span></div>';
      }).join('') + '</div><h4>How to read it</h4><p>Select a building block to see what it is in the target architecture, and exactly what stands behind it in the prototype.</p>' +
        '<h4>Or watch it work</h4><p>“Follow one contact through it” lights each block in the order a real contact would reach it — ' + A.trace.length + ' steps, from the phone menu to the follow-up journey.</p>';
    }
    function show(id) {
      var c = comps[id];
      sel = id;
      $$('.ac', map).forEach(function (b) { b.classList.toggle('sel', b.dataset.id === id); });
      if (!c) { overview(); return; }
      var s = STATUS[c.status];
      detail.innerHTML = '<span class="tag tag-' + s[1] + '">' + s[0] + '</span><h3>' + esc(c.name) + '</h3><p class="muted" style="font-size:13px">' + esc(kindLabel[c.kind] || '') + '</p>' +
        '<h4>In this prototype</h4><p>' + esc(c.poc) + '</p>' +
        '<h4>In the target architecture</h4><ul>' + c.items.map(function (i) { return '<li>' + esc(i) + '</li>'; }).join('') + '</ul>' +
        ((c.agents || []).length ? '<h4>Agents that work here</h4><div class="who">' + c.agents.map(function (a) {
          return '<span><b>' + a.n + '</b>' + esc(a.name) + '</span>';
        }).join('') + '</div>' : '') +
        '<p style="margin-top:20px"><button class="link" type="button" id="archBack">Back to the overview</button></p>';
    }
    function dim() {
      $$('.ac', map).forEach(function (b) { b.classList.toggle('dim', !!filter && b.dataset.status !== filter); });
      $$('.aconn', map).forEach(function (b) { b.classList.toggle('dim', !!filter); });
      $$('#archFilter .chip').forEach(function (b) {
        var on = b.dataset.k === filter;
        b.classList.toggle('on', on); b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }

    // Following a contact: one block lit at a time, in the order the contact reaches them.
    function light(i) {
      step = i;
      var t = A.trace[i];
      $$('.lit', map).forEach(function (n) { n.classList.remove('lit'); n.classList.add('seen'); });
      var node = $('[data-id="' + t.target + '"]', map);
      if (node) {
        node.classList.remove('seen'); node.classList.add('lit');
        var r = node.getBoundingClientRect();
        if (r.top < 150 || r.bottom > window.innerHeight - 20) {
          window.scrollTo({ top: window.scrollY + r.top - Math.max(170, (window.innerHeight - r.height) / 2), behavior: calm ? 'auto' : 'smooth' });
        }
      }
      cap.hidden = false;
      cap.innerHTML = '<b>' + (i + 1) + ' of ' + A.trace.length + '</b><div><strong>' + esc(comps[t.target] ? comps[t.target].name : 'Between the layers') +
        '</strong><span>' + esc(t.caption) + '</span></div>';
      if (comps[t.target]) show(t.target);
    }
    function stop(done) {
      playing = false; clearTimeout(timer);
      $('#archPlay').textContent = done ? 'Follow it again' : (step >= 0 ? 'Carry on' : 'Follow one contact through it');
    }
    function tick() {
      if (!playing) return;
      if (step >= A.trace.length - 1) { stop(true); return; }
      light(step + 1);
      timer = setTimeout(tick, calm ? 3200 : 2700);
    }
    function clear() {
      $$('.lit,.seen', map).forEach(function (n) { n.classList.remove('lit', 'seen'); });
      step = -1; cap.hidden = true;
    }
    $('#archPlay').addEventListener('click', function () {
      if (playing) { stop(false); return; }
      if (step >= A.trace.length - 1) clear();
      filter = null; dim();
      playing = true; this.textContent = 'Pause'; tick();
    });
    $('#archNext').addEventListener('click', function () { stop(false); filter = null; dim(); light(Math.min(A.trace.length - 1, step + 1)); if (step >= A.trace.length - 1) stop(true); });
    $('#archPrev').addEventListener('click', function () { stop(false); filter = null; dim(); light(Math.max(0, step - 1)); });
    map.addEventListener('click', function (e) {
      var b = e.target.closest('.ac'); if (!b) return;
      if (playing) stop(false);
      show(b.dataset.id);
      if (window.innerWidth <= 1080) { var r = detail.getBoundingClientRect(); if (r.top > window.innerHeight - 120) window.scrollTo({ top: window.scrollY + r.top - 150, behavior: calm ? 'auto' : 'smooth' }); }
    });
    detail.addEventListener('click', function (e) { if (e.target.id === 'archBack') { sel = null; show(null); } });
    $('#archFilter').addEventListener('click', function (e) {
      var b = e.target.closest('.chip'); if (!b) return;
      filter = filter === b.dataset.k ? null : b.dataset.k;
      if (filter) { stop(false); clear(); $('#archPlay').textContent = 'Follow one contact through it'; }
      dim();
    });
    overview();
  })();

  // ── agents and coverage ────────────────────────────────────────────────
  (function () {
    var A = D.architecture;
    $('#agentCards').innerHTML = A.m7.map(function (m) {
      var built = m.status === 'built';
      return '<article class="card agent reveal"><header><b>' + m.n + '</b><span class="tag tag-' + (built ? 'green' : 'amber') + '">' +
        (built ? 'Built' : 'Partly built') + '</span></header><h3>' + esc(m.name) + '</h3><p>' + esc(m.goal) + '</p></article>';
    }).join('');
    var s = A.summary.by_status, total = A.summary.total;
    var parts = [['built', 'Built', TONE.green], ['partial', 'Partly built', TONE.amber], ['planned', 'Planned', TONE.violet], ['reference', 'Reference only', '#64748b']];
    var C = 2 * Math.PI * 58, off = 0;
    var arcs = parts.map(function (p) {
      var len = (s[p[0]] || 0) / total * C;
      var a = '<circle cx="75" cy="75" r="58" style="stroke:' + p[2] + '" stroke-dasharray="' + Math.max(0, len - 3) + ' ' + (C - len + 3) + '" stroke-dashoffset="' + (-off) + '"/>';
      off += len;
      return a;
    }).join('');
    $('#coverage').innerHTML = '<svg class="donut" viewBox="0 0 150 150" role="img" aria-label="Architecture coverage">' + arcs + '</svg>' +
      '<div><p class="kicker">The target architecture has ' + total + ' components</p><div class="cov-list">' + parts.map(function (p) {
        return '<div><b>' + (s[p[0]] || 0) + '</b><span><i style="background:' + p[2] + '"></i>' + p[1] + '</span></div>';
      }).join('') + '</div><p class="fine" style="margin-top:16px">In the application, every component on the architecture screen says exactly what is real and what is a stand-in.</p></div>';
  })();

  // ── what is real, and what is not ──────────────────────────────────────
  (function () {
    var H = [
      ['Decision engine', 'Real', 'real', 'Likelihood to buy, segment, guardrails, routing and offer are computed from the customer’s profile. Change the profile and the decision changes.'],
      ['Guardrails', 'Real', 'real', 'Service recovery, consent, the 30-day cooldown and the commercial hold are code, covered by tests.'],
      ['Customer platform', 'Real', 'real', 'Profiles and events in one data model, on a built-in store or on Apache Unomi. Both pass the same conformance tests.'],
      ['Feedback loop', 'Real', 'real', 'A new version is trained on outcomes, judged on unseen traffic, and promoted by a person.'],
      ['Unscripted contact', 'Real', 'real', 'Type or speak as the customer. A rules engine detects signals, scores and recommends. No API key is needed.'],
      ['Quality scoring and knowledge search', 'Real', 'real', 'Each runs on whatever transcript or question it is given.'],
      ['Write-back', 'Real', 'real', 'Wrap-up writes events to the profile. The next decision for that customer reflects them.'],
      ['Training mode', 'Real', 'real', 'An agent takes a mock call in audio. The customer is a rules-based persona built from the demo contacts; the debrief is the quality agent’s score.'],
      ['Traffic', 'Synthetic', 'made', '9,200 contacts a day from a generated population of 6,000 customers. There is no real customer data anywhere.'],
      ['The nine guided contacts', 'Scripted', 'made', 'Conversation and analysis are written in advance, so the demo lands the same way every time.'],
      ['Knowledge articles and prices', 'Illustrative', 'made', 'Plausible, and invented.'],
      ['Translation', 'Prepared', 'made', 'The routing and the workspace are real. The Spanish and English text was written in advance.'],
      ['The business case', 'Modelled', 'made', 'The revenue and payback figures are assumptions, stated as assumptions.'],
      ['Journeys and cases', 'Stand-in', 'notyet', 'Composed and shown on screen, not sent anywhere.'],
      ['Amazon Connect', 'Emulated', 'notyet', 'The workspace looks and behaves like a Connect agent desktop. It is not connected to a Connect instance.'],
      ['The vendor’s own platform', 'Not exercised', 'notyet', 'An adapter is written and configurable, with placeholder endpoints. It has never made a request.']
    ];
    var tone = { real: 'green', made: 'amber', notyet: 'grey' };
    var F = [['all', 'Everything'], ['real', 'Real'], ['made', 'Synthetic, scripted or modelled'], ['notyet', 'Emulated or not yet exercised']];
    $('#honestFilter').innerHTML = F.map(function (f, i) {
      var n = f[0] === 'all' ? H.length : H.filter(function (h) { return h[2] === f[0]; }).length;
      return '<button class="chip' + (i ? '' : ' on') + '" type="button" aria-pressed="' + (i ? 'false' : 'true') + '" data-k="' + f[0] + '">' + f[1] + ' · ' + n + '</button>';
    }).join('');
    $('#honestList').innerHTML = H.map(function (h) {
      return '<article class="hn reveal" data-k="' + h[2] + '"><header><h3>' + esc(h[0]) + '</h3><span class="tag tag-' + tone[h[2]] + '">' + esc(h[1]) +
        '</span></header><p>' + esc(h[3]) + '</p></article>';
    }).join('');
    $('#honestFilter').addEventListener('click', function (e) {
      var b = e.target.closest('.chip'); if (!b) return;
      $$('#honestFilter .chip').forEach(function (x) { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      $$('#honestList .hn').forEach(function (x) { x.classList.toggle('off', b.dataset.k !== 'all' && x.dataset.k !== b.dataset.k); });
    });
  })();

  // ── gallery ────────────────────────────────────────────────────────────
  (function () {
    var G = [
      ['overview', 'Overview', 'The idea on one page: what a conversation costs, and what it could return.', true],
      ['frontier', 'Before the call', 'The day at a glance — contacts arriving, each already decided.'],
      ['held-back', 'One contact, step by step', 'Elena looks likely to buy. The engine holds back anyway.'],
      ['live-call', 'During the call', 'The agent’s desktop: transcript, signals heard, and what to say next.', true],
      ['workspace', 'The queue', 'Every waiting customer already carries a decision.'],
      ['wrap-up', 'After the call', 'What it was worth, how well it was handled, and what happens if she calls tomorrow.'],
      ['insights', 'Customer insights', 'Why customers are calling, and which reasons are moving.'],
      ['business-case', 'Business case', 'From cost centre to growth centre, with every assumption shown.'],
      ['architecture', 'Architecture', 'The target state, with what is built and what is not.'],
      ['technology', 'Technology', 'Where the customer data lives, and the same operation on each platform.']
    ];
    var box = $('#gallery'), lb = $('#lightbox'), at = 0, opener = null;
    box.innerHTML = G.map(function (g, i) {
      return '<button class="shot reveal' + (g[3] ? ' wide' : '') + '" type="button" data-i="' + i + '"><img loading="lazy" decoding="async" width="1600" height="900" src="shots/' +
        g[0] + '.webp" alt="' + esc(g[1] + ' screen: ' + g[2]) + '"><div><b>' + esc(g[1]) + '</b><span>' + esc(g[2]) + '</span></div></button>';
    }).join('');
    function show(i) {
      at = (i + G.length) % G.length;
      $('#lbImg').src = 'shots/' + G[at][0] + '.webp';
      $('#lbImg').alt = G[at][1];
      $('#lbCap').textContent = G[at][1] + ' — ' + G[at][2];
    }
    function open(i, from) { opener = from; show(i); lb.hidden = false; document.body.style.overflow = 'hidden'; $('.lb-x', lb).focus(); }
    function close() { lb.hidden = true; document.body.style.overflow = ''; if (opener) opener.focus(); }
    box.addEventListener('click', function (e) { var b = e.target.closest('.shot'); if (b) open(+b.dataset.i, b); });
    lb.addEventListener('click', function (e) {
      if (e.target.closest('.lb-prev')) show(at - 1);
      else if (e.target.closest('.lb-next')) show(at + 1);
      else if (e.target.closest('.lb-x') || e.target === lb || e.target.tagName === 'FIGURE') close();
    });
    document.addEventListener('keydown', function (e) {
      if (lb.hidden) return;
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowLeft') show(at - 1);
      if (e.key === 'ArrowRight') show(at + 1);
    });
  })();

  // ── run it ─────────────────────────────────────────────────────────────
  (function () {
    var REPO = 'https://github.com/saurabh-oss/cx-growth.git';
    var S = {
      win: ['git clone ' + REPO + '\ncd cx-growth\nrun.bat', 'Installs four Python packages, starts the server and opens http://localhost:8000.'],
      nix: ['git clone ' + REPO + '\ncd cx-growth\n./run.sh', 'Installs four Python packages, starts the server and opens http://localhost:8000.'],
      unomi: ['cd platform && docker compose up -d && cd ..\nexport CUSTOMER_PLATFORM=unomi     # Windows: set CUSTOMER_PLATFORM=unomi\npython backend/main.py',
        'Needs Docker. The first start pulls about 1.5 GB. If Unomi is not reachable the app says so and uses the built-in store.'],
      test: ['python -m unittest discover -s tests -v', '46 tests, about five seconds, no server and no network. With Unomi running, the platform tests run against it as well.']
    };
    var k = 'win';
    if (/Mac|Linux|X11/.test(navigator.platform || '') && !/Win/.test(navigator.platform || '')) k = 'nix';
    function set() {
      $('#startCode').textContent = S[k][0];
      $('#startNote').textContent = S[k][1];
      $$('#startTabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.k === k); });
    }
    $('#startTabs').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; k = b.dataset.k; set(); });
    $('#startCopy').addEventListener('click', function () {
      var text = S[k][0], btn = this;
      var done = function () { btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = 'Copy'; }, 1600); };
      if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(done, function () {}); return; }
      var ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); done(); } catch (err) { /* nothing to do */ }
      ta.remove();
    });
    set();

    // The same rule the application applies: a name must be inert in code and in a page.
    var clean = function (v, fallback) { return v.replace(/["'\\<>{}`$\n\r]/g, '').trim() || fallback; };
    function pack() {
      var co = clean($('#bpCo').value, 'Acme'), su = clean($('#bpSuite').value, 'Studio Cloud');
      $$('[data-bp="co"]').forEach(function (n) { n.textContent = co; });
      $$('[data-bp="suite"]').forEach(function (n) { n.textContent = su; });
      $('#bpCode').textContent = '// brand/local.json — ignored by git\n' + JSON.stringify({ names: { 'Acme': co, 'Studio Cloud': su } }, null, 2);
    }
    $('#bpCo').addEventListener('input', pack);
    $('#bpSuite').addEventListener('input', pack);
    pack();
  })();

  $('#footData').textContent = 'Every figure on this page was computed by the engine and exported — ' + D.source +
    ', line at ' + pct(D.threshold) + '%. To rebuild it: python tools/build_site_data.py';

  reveal();
})();
