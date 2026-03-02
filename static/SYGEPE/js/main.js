/* ================================================================
   SYGEPE — main.js  |  Thème Soleil d'Harmattan
   ================================================================
   Modules :
   01. Sidebar (toggle, persistence, tooltips collapsed)
   02. Topbar (ombre au scroll)
   03. KPI Counter (IntersectionObserver + easing)
   04. Chart.js (palette Harmattan — bar + donut)
   05. Modal de confirmation (remplace window.confirm)
   06. Système de toasts
   07. Alertes Django (auto-dismiss animé)
   08. Lignes de tableau cliquables
   09. Recherche live côté client
   10. Toggle afficher/masquer mot de passe
   11. Effet ripple sur les boutons
   12. Bouton scroll-to-top
   13. Soumission avec état de chargement
   14. Raccourcis clavier
   15. Auto-submit filtres select
   ================================================================ */

(function () {
  'use strict';

  /* ── Palette Harmattan (miroir des variables CSS) ── */
  const PALETTE = {
    espresso:   '#1A0E06',
    amber:      '#C8750A',
    amberLt:    '#F2A820',
    terra:      '#B54B1F',
    success:    '#1E7C4D',
    danger:     '#C0291F',
    textMuted:  '#7A6045',
    border:     '#E4D7C5',
    bg:         '#F5EFE6',
  };

  /* ────────────────────────────────────────────────
     01. SIDEBAR
  ──────────────────────────────────────────────── */
  const sidebar      = document.getElementById('sidebar');
  const mainWrapper  = document.getElementById('mainWrapper');
  const sidebarToggle = document.getElementById('sidebarToggle');

  function setSidebar(collapsed) {
    sidebar.classList.toggle('collapsed', collapsed);
    mainWrapper && mainWrapper.classList.toggle('expanded', collapsed);
    localStorage.setItem('sidebarCollapsed', collapsed);
    updateCollapsedTooltips();
  }

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      setSidebar(!sidebar.classList.contains('collapsed'));
    });
    /* Restaurer l'état persisté */
    const savedState = localStorage.getItem('sidebarCollapsed') === 'true';
    if (savedState) setSidebar(true);
  }

  /* Tooltips sur les items quand la sidebar est réduite */
  function updateCollapsedTooltips() {
    if (!sidebar) return;
    const collapsed = sidebar.classList.contains('collapsed');
    document.querySelectorAll('.nav-item').forEach(item => {
      const label = item.querySelector('span:not(.nav-icon):not(.nav-badge)');
      if (label) {
        if (collapsed) {
          item.setAttribute('data-tip', label.textContent.trim());
        } else {
          item.removeAttribute('data-tip');
        }
      }
    });
  }

  /* Fermer la sidebar sur mobile en cliquant en dehors */
  document.addEventListener('click', e => {
    if (!sidebar) return;
    if (window.innerWidth <= 768) return; // géré par CSS
    if (!sidebar.contains(e.target) && !sidebarToggle?.contains(e.target)) {
      // pas de fermeture auto sur desktop
    }
  });

  /* ────────────────────────────────────────────────
     02. TOPBAR — ombre dynamique au scroll
  ──────────────────────────────────────────────── */
  const topbar = document.querySelector('.topbar');
  if (topbar) {
    const scrollHandler = () => {
      topbar.style.boxShadow = window.scrollY > 10
        ? '0 4px 20px rgba(26,14,6,0.10)'
        : 'none';
      topbar.style.borderBottomColor = window.scrollY > 10
        ? PALETTE.border
        : 'transparent';
    };
    window.addEventListener('scroll', scrollHandler, { passive: true });
    scrollHandler();
  }

  /* ────────────────────────────────────────────────
     03. KPI COUNTER — IntersectionObserver + easing
  ──────────────────────────────────────────────── */
  function easeOutQuart(t) { return 1 - Math.pow(1 - t, 4); }

  function animateCounter(el) {
    const target = parseInt(el.getAttribute('data-target') || el.textContent, 10);
    if (isNaN(target) || target === 0) return;
    const duration = 900;
    const start    = performance.now();

    function step(now) {
      const elapsed  = now - start;
      const progress = Math.min(elapsed / duration, 1);
      el.textContent = Math.round(easeOutQuart(progress) * target);
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = target;
    }
    requestAnimationFrame(step);
  }

  const kpiObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const val = entry.target.querySelector('.kpi-value[data-target]');
        if (val && !val.dataset.animated) {
          val.dataset.animated = 'true';
          animateCounter(val);
        }
        kpiObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });

  document.querySelectorAll('.kpi-card').forEach(card => kpiObserver.observe(card));

  /* ────────────────────────────────────────────────
     04. CHART.JS — palette Harmattan
  ──────────────────────────────────────────────── */
  /* Couleurs Harmattan pour les graphiques */
  const CHART_COLORS = [
    '#C8750A', '#B54B1F', '#1E7C4D', '#185EA6',
    '#9B6100', '#6D3E91', '#0E7490', '#7F1D1D',
  ];

  const CHART_DEFAULTS = {
    tooltip: {
      backgroundColor: PALETTE.espresso,
      titleColor: '#fff',
      bodyColor: 'rgba(255,255,255,0.8)',
      padding: 12,
      cornerRadius: 10,
      displayColors: true,
      boxRadius: 4,
    },
    font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
  };

  /* Graphique barres — Présences par mois */
  const presencesCtx = document.getElementById('chartPresences');
  if (presencesCtx && typeof Chart !== 'undefined') {
    const labels = JSON.parse(presencesCtx.dataset.labels || '[]');
    const data   = JSON.parse(presencesCtx.dataset.values || '[]');

    new Chart(presencesCtx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Présences',
          data,
          backgroundColor: data.map((_, i) =>
            i === data.length - 1 ? PALETTE.amber : PALETTE.amberLt + 'AA'
          ),
          borderRadius: 10,
          borderSkipped: false,
          hoverBackgroundColor: PALETTE.amber,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 900, easing: 'easeOutQuart' },
        plugins: {
          legend: { display: false },
          tooltip: CHART_DEFAULTS.tooltip,
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { font: CHART_DEFAULTS.font, color: PALETTE.textMuted }
          },
          y: {
            grid: { color: PALETTE.border, lineWidth: 1 },
            ticks: { font: CHART_DEFAULTS.font, color: PALETTE.textMuted },
            beginAtZero: true,
          }
        }
      }
    });
  }

  /* Graphique donut — Employés par département */
  const deptCtx = document.getElementById('chartDepartements');
  if (deptCtx && typeof Chart !== 'undefined') {
    const labels = JSON.parse(deptCtx.dataset.labels || '[]');
    const data   = JSON.parse(deptCtx.dataset.values || '[]');

    new Chart(deptCtx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: CHART_COLORS.slice(0, data.length),
          borderWidth: 3,
          borderColor: '#FFFDF9',
          hoverOffset: 10,
          hoverBorderWidth: 0,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        animation: { animateRotate: true, duration: 900, easing: 'easeOutQuart' },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              padding: 14,
              font: CHART_DEFAULTS.font,
              color: PALETTE.textMuted,
              usePointStyle: true,
              pointStyleWidth: 10,
            }
          },
          tooltip: CHART_DEFAULTS.tooltip,
        }
      }
    });
  }

  /* ────────────────────────────────────────────────
     05. MODAL DE CONFIRMATION personnalisée
  ──────────────────────────────────────────────── */
  function createModal() {
    if (document.getElementById('sygepe-modal')) return;
    const el = document.createElement('div');
    el.id = 'sygepe-modal';
    el.innerHTML = `
      <div class="syg-modal-overlay" id="sygModalOverlay">
        <div class="syg-modal-box" role="dialog" aria-modal="true">
          <div class="syg-modal-icon" id="sygModalIcon">⚠️</div>
          <h3 class="syg-modal-title" id="sygModalTitle">Confirmation</h3>
          <p class="syg-modal-body" id="sygModalBody"></p>
          <div class="syg-modal-actions">
            <button class="btn btn-outline" id="sygModalCancel">Annuler</button>
            <button class="btn btn-danger" id="sygModalConfirm">Confirmer</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(el);
  }

  function showModal({ title = 'Confirmer', body = '', icon = '⚠️', confirmLabel = 'Confirmer', confirmClass = 'btn-danger' } = {}) {
    createModal();
    document.getElementById('sygModalTitle').textContent   = title;
    document.getElementById('sygModalBody').textContent    = body;
    document.getElementById('sygModalIcon').textContent    = icon;

    const confirmBtn = document.getElementById('sygModalConfirm');
    confirmBtn.textContent = confirmLabel;
    confirmBtn.className   = `btn ${confirmClass}`;

    const overlay = document.getElementById('sygModalOverlay');
    overlay.classList.add('active');

    return new Promise(resolve => {
      function cleanup() {
        overlay.classList.remove('active');
        confirmBtn.replaceWith(confirmBtn.cloneNode(true));
        document.getElementById('sygModalCancel').replaceWith(
          document.getElementById('sygModalCancel').cloneNode(true)
        );
      }
      document.getElementById('sygModalConfirm').onclick = () => { cleanup(); resolve(true); };
      document.getElementById('sygModalCancel').onclick  = () => { cleanup(); resolve(false); };
      overlay.addEventListener('click', e => {
        if (e.target === overlay) { cleanup(); resolve(false); }
      }, { once: true });
    });
  }

  /* Remplacer les liens/boutons avec data-confirm */
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', async function (e) {
      e.preventDefault();
      const msg  = this.getAttribute('data-confirm') || 'Voulez-vous vraiment effectuer cette action ?';
      const href = this.getAttribute('href');

      const ok = await showModal({
        title: 'Confirmer la suppression',
        body: msg,
        icon: '🗑️',
        confirmLabel: 'Supprimer',
        confirmClass: 'btn-danger',
      });

      if (ok) {
        if (href) window.location.href = href;
        else if (this.form) this.form.submit();
      }
    });
  });

  /* ────────────────────────────────────────────────
     06. SYSTÈME DE TOASTS
  ──────────────────────────────────────────────── */
  function getToastContainer() {
    let c = document.getElementById('syg-toasts');
    if (!c) {
      c = document.createElement('div');
      c.id = 'syg-toasts';
      document.body.appendChild(c);
    }
    return c;
  }

  function showToast(message, type = 'info', duration = 4000) {
    const container = getToastContainer();
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };

    const toast = document.createElement('div');
    toast.className = `syg-toast syg-toast-${type}`;
    toast.innerHTML = `
      <span class="syg-toast-icon">${icons[type] || icons.info}</span>
      <span class="syg-toast-msg">${message}</span>
      <button class="syg-toast-close" aria-label="Fermer">&times;</button>`;

    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));

    const dismiss = () => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 350);
    };

    toast.querySelector('.syg-toast-close').addEventListener('click', dismiss);
    if (duration > 0) setTimeout(dismiss, duration);
  }

  /* Exposer globalement */
  window.sygToast = showToast;

  /* ────────────────────────────────────────────────
     07. ALERTES DJANGO — auto-dismiss avec slide
  ──────────────────────────────────────────────── */
  document.querySelectorAll('.alert').forEach((alert, i) => {
    /* Conversion des alertes en toasts si le système est disponible */
    const type = alert.classList.contains('alert-success') ? 'success'
               : alert.classList.contains('alert-error')   ? 'error'
               : alert.classList.contains('alert-warning')  ? 'warning'
               : 'info';

    const text = alert.textContent.trim().replace(/^[✅❌⚠️ℹ️]\s*/, '');
    setTimeout(() => showToast(text, type), i * 200);
    alert.style.display = 'none'; /* Masquer les alertes originales */
  });

  /* ────────────────────────────────────────────────
     08. LIGNES DE TABLEAU cliquables
  ──────────────────────────────────────────────── */
  document.querySelectorAll('tr[data-href]').forEach(row => {
    row.style.cursor = 'pointer';
    row.addEventListener('click', () => window.location.href = row.dataset.href);
    row.setAttribute('tabindex', '0');
    row.addEventListener('keydown', e => {
      if (e.key === 'Enter') window.location.href = row.dataset.href;
    });
  });

  /* ────────────────────────────────────────────────
     09. RECHERCHE LIVE côté client
  ──────────────────────────────────────────────── */
  const liveSearch = document.getElementById('liveSearch');
  if (liveSearch) {
    const target = document.getElementById(liveSearch.dataset.target || 'searchTable');
    if (target) {
      liveSearch.addEventListener('input', function () {
        const q = this.value.toLowerCase().trim();
        target.querySelectorAll('tbody tr').forEach(row => {
          row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
        });
      });
    }
  }

  /* ────────────────────────────────────────────────
     10. TOGGLE MOT DE PASSE
  ──────────────────────────────────────────────── */
  document.querySelectorAll('.login-input-wrapper').forEach(wrapper => {
    const input = wrapper.querySelector('input[type="password"]');
    if (!input) return;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pwd-toggle';
    btn.setAttribute('aria-label', 'Afficher/masquer le mot de passe');
    btn.innerHTML = '👁️';
    btn.style.cssText = `
      position:absolute; right:12px; top:50%; transform:translateY(-50%);
      background:none; border:none; cursor:pointer; font-size:1rem;
      color:var(--text-light); padding:0; line-height:1;`;
    wrapper.style.position = 'relative';
    wrapper.appendChild(btn);

    btn.addEventListener('click', () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = show ? '🙈' : '👁️';
      btn.setAttribute('aria-label', show ? 'Masquer' : 'Afficher');
    });
  });

  /* ────────────────────────────────────────────────
     11. EFFET RIPPLE sur les boutons
  ──────────────────────────────────────────────── */
  function createRipple(e) {
    const btn    = e.currentTarget;
    const circle = document.createElement('span');
    const rect   = btn.getBoundingClientRect();
    const size   = Math.max(rect.width, rect.height);
    const x      = e.clientX - rect.left - size / 2;
    const y      = e.clientY - rect.top  - size / 2;

    circle.style.cssText = `
      position:absolute; width:${size}px; height:${size}px;
      left:${x}px; top:${y}px; border-radius:50%;
      background:rgba(255,255,255,0.28); pointer-events:none;
      animation:rippleAnim 0.55s ease-out forwards;`;

    btn.style.position   = 'relative';
    btn.style.overflow   = 'hidden';
    btn.appendChild(circle);
    setTimeout(() => circle.remove(), 600);
  }

  document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', createRipple);
  });

  /* ────────────────────────────────────────────────
     12. BOUTON SCROLL-TO-TOP
  ──────────────────────────────────────────────── */
  const scrollBtn = document.createElement('button');
  scrollBtn.id = 'scrollTopBtn';
  scrollBtn.innerHTML = '↑';
  scrollBtn.setAttribute('aria-label', 'Remonter en haut');
  document.body.appendChild(scrollBtn);

  window.addEventListener('scroll', () => {
    scrollBtn.classList.toggle('visible', window.scrollY > 300);
  }, { passive: true });

  scrollBtn.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  /* ────────────────────────────────────────────────
     13. SOUMISSION — état de chargement
  ──────────────────────────────────────────────── */
  document.querySelectorAll('form').forEach(form => {
    /* Exclure les formulaires de filtre (GET) */
    if (form.method.toLowerCase() === 'get') return;
    form.addEventListener('submit', function () {
      const btn = form.querySelector('[type="submit"]');
      if (btn && !btn.disabled) {
        btn.disabled = true;
        const original = btn.innerHTML;
        btn.innerHTML = '<span class="syg-spinner"></span> Traitement…';
        /* Restaurer si erreur (ex. navigation arrière) */
        setTimeout(() => {
          btn.disabled = false;
          btn.innerHTML = original;
        }, 8000);
      }
    });
  });

  /* ────────────────────────────────────────────────
     14. RACCOURCIS CLAVIER
  ──────────────────────────────────────────────── */
  const SHORTCUTS = {
    'd': '/dashboard/',
    'e': '/employes/',
    'p': '/presences/',
    'c': '/conges/',
    'm': '/permissions/',
    'b': '/boutiques/',
  };

  document.addEventListener('keydown', e => {
    /* Ignorer si focus sur un champ de saisie */
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;
    /* Ignorer si modal ouverte */
    if (document.getElementById('sygModalOverlay')?.classList.contains('active')) return;

    const key = e.key.toLowerCase();

    /* Alt + lettre → navigation */
    if (e.altKey && SHORTCUTS[key]) {
      e.preventDefault();
      window.location.href = SHORTCUTS[key];
      return;
    }

    /* '?' → afficher les raccourcis */
    if (key === '?') {
      const lines = Object.entries(SHORTCUTS)
        .map(([k, v]) => `Alt+${k.toUpperCase()} → ${v}`)
        .join('\n');
      showModal({
        title: 'Raccourcis clavier',
        body: lines,
        icon: '⌨️',
        confirmLabel: 'Fermer',
        confirmClass: 'btn-primary',
      });
    }
  });

  /* Afficher les raccourcis dans la console pour les devs */
  console.info(
    '%c SYGEPE — Raccourcis clavier\n%c Alt+D: Tableau de bord | Alt+E: Employés | Alt+P: Présences\nAlt+C: Congés | Alt+M: Permissions | Alt+B: Boutiques | ?: aide',
    'color:#C8750A; font-weight:bold; font-size:13px;',
    'color:#7A6045; font-size:11px;'
  );

  /* ────────────────────────────────────────────────
     15. AUTO-SUBMIT des selects dans les filtres
  ──────────────────────────────────────────────── */
  document.querySelectorAll('.filter-bar select').forEach(sel => {
    sel.addEventListener('change', () => {
      sel.closest('form')?.submit();
    });
  });

  /* ────────────────────────────────────────────────
     16. TILT 3D sur les cartes KPI
         – perspective rotateX/Y selon position souris
         – reflet lumineux qui suit le curseur
         – icône qui flotte à l'opposé du tilt
         – spring-back fluide au mouseleave
  ──────────────────────────────────────────────── */
  const MAX_TILT   = 14;   // degrés max
  const MAX_LIFT   = 10;   // px de translateZ
  const MAX_SHINE  = 0.18; // opacité max du reflet

  document.querySelectorAll('.kpi-card').forEach(card => {
    /* Créer l'élément de reflet lumineux */
    const shine = document.createElement('div');
    shine.className = 'kpi-shine';
    card.appendChild(shine);

    /* Récupérer le wrapper icône à animer (contient bg-shadow + icône) */
    const icon = card.querySelector('.kpi-icon-wrap');

    let rafId = null;
    let targetRX = 0, targetRY = 0, currentRX = 0, currentRY = 0;
    let isHovered = false;

    /* Lerp pour le spring-back */
    function lerp(a, b, t) { return a + (b - a) * t; }

    function animateFrame() {
      const ease = isHovered ? 0.16 : 0.09; // plus lent au retour
      currentRX = lerp(currentRX, targetRX, ease);
      currentRY = lerp(currentRY, targetRY, ease);

      const dist = Math.abs(currentRX - targetRX) + Math.abs(currentRY - targetRY);

      card.style.transform = `
        perspective(900px)
        rotateX(${currentRX}deg)
        rotateY(${currentRY}deg)
        translateZ(${isHovered ? MAX_LIFT : lerp(MAX_LIFT, 0, 1 - dist / (MAX_TILT * 2))}px)
        scale(${isHovered ? 1.03 : lerp(1.03, 1, 1 - dist / (MAX_TILT * 2))})
      `;

      /* Ombre dynamique selon inclinaison */
      const sx = currentRY * -0.6;
      const sy = currentRX *  0.6;
      card.style.boxShadow = isHovered || dist > 0.05
        ? `${sx}px ${sy + 12}px 32px rgba(26,14,6,0.16), 0 4px 12px rgba(26,14,6,0.08)`
        : '';

      /* Icône : léger mouvement inverse du tilt (parallaxe) */
      if (icon) {
        icon.style.transform = `
          translateX(${-currentRY * 0.5}px)
          translateY(${currentRX * 0.5}px)
          scale(${isHovered ? 1.08 : 1})
        `;
      }

      if (dist > 0.02 || isHovered) rafId = requestAnimationFrame(animateFrame);
      else {
        card.style.transform  = '';
        card.style.boxShadow  = '';
        if (icon) icon.style.transform = '';
        rafId = null;
      }
    }

    card.addEventListener('mousemove', e => {
      const rect    = card.getBoundingClientRect();
      const x       = e.clientX - rect.left;
      const y       = e.clientY - rect.top;
      const cx      = rect.width  / 2;
      const cy      = rect.height / 2;
      const dx      = (x - cx) / cx;   // –1 … +1
      const dy      = (y - cy) / cy;

      targetRY =  dx * MAX_TILT;
      targetRX = -dy * MAX_TILT;

      /* Reflet lumineux */
      const shineX = (x / rect.width)  * 100;
      const shineY = (y / rect.height) * 100;
      shine.style.background = `radial-gradient(circle at ${shineX}% ${shineY}%, rgba(255,255,255,${MAX_SHINE}), transparent 60%)`;
      shine.style.opacity = '1';

      if (!rafId) rafId = requestAnimationFrame(animateFrame);
    });

    card.addEventListener('mouseenter', () => {
      isHovered = true;
      card.style.transition  = 'none'; /* désactiver le CSS transition pendant le JS */
      shine.style.transition = 'opacity 0.2s';
    });

    card.addEventListener('mouseleave', () => {
      isHovered  = false;
      targetRX   = 0;
      targetRY   = 0;
      shine.style.opacity = '0';
      if (!rafId) rafId = requestAnimationFrame(animateFrame);
    });
  });

  /* ────────────────────────────────────────────────
     16b. TILT 3D — Boutique cards (.btq-card)
  ──────────────────────────────────────────────── */
  const BTQ_MAX_TILT  = 12;
  const BTQ_MAX_LIFT  = 8;
  const BTQ_MAX_SHINE = 0.15;

  document.querySelectorAll('.btq-card').forEach(card => {
    /* Injecter l'élément de reflet */
    const shine = document.createElement('div');
    shine.className = 'btq-shine';
    card.appendChild(shine);

    const icon = card.querySelector('.btq-icon-wrap');

    let targetRX = 0, targetRY = 0;
    let currentRX = 0, currentRY = 0;
    let isHovered = false;
    let rafId = null;

    function lerp(a, b, t) { return a + (b - a) * t; }

    function animateFrame() {
      rafId = null;
      const SPEED = isHovered ? 0.12 : 0.08;

      currentRX = lerp(currentRX, targetRX, SPEED);
      currentRY = lerp(currentRY, targetRY, SPEED);

      const liftZ = isHovered ? BTQ_MAX_LIFT : 0;
      const currentLift = lerp(parseFloat(card.dataset.liftZ || 0), liftZ, SPEED);
      card.dataset.liftZ = currentLift;

      card.style.transform = `perspective(900px) rotateX(${currentRX}deg) rotateY(${currentRY}deg) translateZ(${currentLift}px)`;

      if (icon) {
        icon.style.transform = `translateX(${currentRY * 0.6}px) translateY(${-currentRX * 0.6}px) translateZ(8px)`;
      }

      const dist = Math.abs(currentRX - targetRX) + Math.abs(currentRY - targetRY) + Math.abs(currentLift - liftZ);
      if (dist > 0.05) {
        rafId = requestAnimationFrame(animateFrame);
      } else {
        if (!isHovered) {
          card.style.transform = '';
          if (icon) icon.style.transform = '';
        }
      }
    }

    card.addEventListener('mousemove', e => {
      const rect = card.getBoundingClientRect();
      const x    = e.clientX - rect.left;
      const y    = e.clientY - rect.top;
      const cx   = rect.width  / 2;
      const cy   = rect.height / 2;
      const dx   = (x - cx) / cx;
      const dy   = (y - cy) / cy;

      targetRY =  dx * BTQ_MAX_TILT;
      targetRX = -dy * BTQ_MAX_TILT;

      const shineX = (x / rect.width)  * 100;
      const shineY = (y / rect.height) * 100;
      shine.style.background = `radial-gradient(circle at ${shineX}% ${shineY}%, rgba(255,255,255,${BTQ_MAX_SHINE}), transparent 60%)`;
      shine.style.opacity = '1';

      if (!rafId) rafId = requestAnimationFrame(animateFrame);
    });

    card.addEventListener('mouseenter', () => {
      isHovered = true;
      card.style.transition  = 'none';
      card.style.boxShadow   = '0 20px 50px rgba(26,14,6,0.18)';
      shine.style.transition = 'opacity 0.2s';
    });

    card.addEventListener('mouseleave', () => {
      isHovered  = false;
      targetRX   = 0;
      targetRY   = 0;
      shine.style.opacity = '0';
      card.style.transition  = 'transform 0.55s cubic-bezier(0.23, 1, 0.32, 1), box-shadow 0.55s ease';
      card.style.boxShadow   = '';
      if (!rafId) rafId = requestAnimationFrame(animateFrame);
    });
  });

  /* ────────────────────────────────────────────────
     16. TOOLTIPS (data-tooltip)
  ──────────────────────────────────────────────── */
  let activeTooltip = null;

  document.querySelectorAll('[data-tooltip]').forEach(el => {
    el.addEventListener('mouseenter', function () {
      if (activeTooltip) activeTooltip.remove();

      const tip = document.createElement('div');
      tip.className = 'syg-tooltip';
      tip.textContent = this.getAttribute('data-tooltip');
      document.body.appendChild(tip);

      const rect  = el.getBoundingClientRect();
      const tipW  = tip.offsetWidth;
      tip.style.top  = (rect.top + window.scrollY - tip.offsetHeight - 8) + 'px';
      tip.style.left = (rect.left + rect.width / 2 - tipW / 2 + window.scrollX) + 'px';
      requestAnimationFrame(() => tip.classList.add('show'));
      activeTooltip = tip;
    });

    el.addEventListener('mouseleave', () => {
      if (activeTooltip) {
        activeTooltip.classList.remove('show');
        setTimeout(() => { activeTooltip?.remove(); activeTooltip = null; }, 200);
      }
    });
  });

})();
