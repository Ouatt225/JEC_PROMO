/* ════════════════════════════════════════════════════════════════
   SYGEPE — Notifications partagées (base.html + base_employe.html)
   L'URL de l'API est lue depuis data-api-url sur #sygepe-notif-container
   ════════════════════════════════════════════════════════════════ */
(function () {
  const container = document.getElementById('sygepe-notif-container');
  if (!container) return;

  const API_URL       = container.dataset.apiUrl;
  const STORE_KEY     = 'sygepe_notifs';
  const DISMISSED_KEY = 'sygepe_dismissed';
  const SHOWN_KEY     = 'sygepe_notif_shown_' + new Date().toDateString();

  function load()           { try { return JSON.parse(localStorage.getItem(STORE_KEY) || '[]'); } catch { return []; } }
  function save(list)       { localStorage.setItem(STORE_KEY, JSON.stringify(list)); }
  function loadDismissed()  { try { return new Set(JSON.parse(localStorage.getItem(DISMISSED_KEY) || '[]')); } catch { return new Set(); } }
  function saveDismissed(s) { localStorage.setItem(DISMISSED_KEY, JSON.stringify([...s])); }

  /* Échappe les caractères HTML spéciaux avant toute injection dans innerHTML.
     Empêche XSS si un nom d'employé ou un message contient du HTML/JS. */
  function esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;');
  }

  function updateBadge(n) {
    const b = document.getElementById('notifBadge');
    if (!b) return;
    if (n > 0) { b.textContent = n > 9 ? '9+' : n; b.style.display = 'flex'; }
    else        { b.style.display = 'none'; }
  }

  function renderList(list) {
    const el = document.getElementById('notifList');
    if (!el) return;
    if (!list.length) { el.innerHTML = '<div class="notif-empty">Aucune notification</div>'; return; }
    el.innerHTML = list.map((n, i) => `
      <div class="notif-item">
        <div class="notif-item-icon">${n.urgence === 'danger' ? '🔴' : '🟡'}</div>
        <div class="notif-item-titre">${esc(n.titre)}</div>
        <button class="notif-item-del" onclick="window._sygepeDelNotif(${i})">×</button>
        <div class="notif-item-body">${esc(n.message).replace(' \u2014 ', '<br>').replace(' du ', '<br>Du ').replace(' au ', ' \u2192 ')}</div>
      </div>`).join('');
  }

  window._sygepeDelNotif = function (i) {
    const list = load();
    const dismissed = loadDismissed();
    dismissed.add(list[i].message);
    saveDismissed(dismissed);
    list.splice(i, 1);
    save(list);
    updateBadge(list.length);
    renderList(list);
  };

  function showToast(n, delay) {
    setTimeout(() => {
      const t = document.createElement('div');
      t.className = `sygepe-toast ${n.urgence}`;
      t.innerHTML = `
        <div class="sygepe-toast-icon">${n.urgence === 'danger' ? '🔴' : '🟡'}</div>
        <div class="sygepe-toast-body">
          <div class="sygepe-toast-titre">${esc(n.titre)}</div>
          <div class="sygepe-toast-msg">${esc(n.message)}</div>
        </div>
        <button class="sygepe-toast-close" onclick="this.closest('.sygepe-toast').remove()">×</button>`;
      container.appendChild(t);
      setTimeout(() => t.remove(), 12000);
    }, delay);
  }

  function playSound(urgent) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      function beep(f, s, d) {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.connect(g); g.connect(ctx.destination);
        o.frequency.value = f; o.type = 'sine';
        g.gain.setValueAtTime(0, ctx.currentTime + s);
        g.gain.linearRampToValueAtTime(0.35, ctx.currentTime + s + 0.02);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + s + d);
        o.start(ctx.currentTime + s); o.stop(ctx.currentTime + s + d + 0.05);
      }
      urgent ? (beep(880, 0, .3), beep(880, .4, .3), beep(1100, .8, .5))
             : (beep(660, 0, .3), beep(880, .4, .3));
    } catch (e) {}
  }

  /* ── Initialisation depuis le stockage local ── */
  const stored = load();
  updateBadge(stored.length);
  renderList(stored);

  /* ── Fetch API ── */
  if (API_URL) {
    fetch(API_URL)
      .then(r => r.json())
      .then(data => {
        const dismissed  = loadDismissed();
        const incoming   = (data.notifications || []).filter(n => !dismissed.has(n.message));
        const storedMsgs = new Set(stored.map(n => n.message));
        const newOnes    = incoming.filter(n => !storedMsgs.has(n.message));

        save(incoming);
        updateBadge(incoming.length);
        renderList(incoming);

        if (newOnes.length && !sessionStorage.getItem(SHOWN_KEY)) {
          sessionStorage.setItem(SHOWN_KEY, '1');
          newOnes.forEach((n, i) => showToast(n, i * 600));
          playSound(newOnes.some(n => n.urgence === 'danger'));
        }
      })
      .catch(() => {}); /* Silencieux si hors ligne */
  }

  /* ── Événements ── */
  const bellBtn    = document.getElementById('notifBellBtn');
  const dropdown   = document.getElementById('notifDropdown');
  const clearBtn   = document.getElementById('notifClearAll');

  function positionDropdown() {
    const rect  = bellBtn.getBoundingClientRect();
    const right = Math.max(4, window.innerWidth - rect.right);
    dropdown.style.top   = (rect.bottom + 10) + 'px';
    dropdown.style.right = right + 'px';
    dropdown.style.left  = 'auto';
  }

  if (bellBtn && dropdown) {
    bellBtn.addEventListener('click', e => {
      e.stopPropagation();
      if (dropdown.classList.contains('open')) {
        dropdown.classList.remove('open');
      } else {
        positionDropdown();
        dropdown.classList.add('open');
      }
    });
    window.addEventListener('resize', () => {
      if (dropdown.classList.contains('open')) positionDropdown();
    });
    document.addEventListener('click', () => dropdown.classList.remove('open'));
    dropdown.addEventListener('click', e => e.stopPropagation());
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      const list = load();
      const dismissed = loadDismissed();
      list.forEach(n => dismissed.add(n.message));
      saveDismissed(dismissed);
      save([]); updateBadge(0); renderList([]);
    });
  }
})();
