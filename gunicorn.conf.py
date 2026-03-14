"""Configuration Gunicorn pour SYGEPE.

Règles de dimensionnement (instance unique) :
    workers = 2 × vCPU + 1
    → 2 vCPU : 5 workers  → ~50 users simultanés
    → 4 vCPU : 9 workers  → ~100 users simultanés

Pour dépasser 100 users simultanés : ajouter Nginx en reverse-proxy pour les statics,
Celery pour les exports lourds, et un read-replica PostgreSQL.
"""

import multiprocessing
import os

# ── Liaison ───────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# ── Workers ───────────────────────────────────────────────────────────────────
# worker_class sync : approprié pour les vues CPU-bound (PDF, Excel).
# Si les vues deviennent IO-bound (WebSockets, long-polling), basculer sur 'gevent'.
workers     = int(os.environ.get('GUNICORN_WORKERS', 2 * multiprocessing.cpu_count() + 1))
worker_class = 'sync'
threads     = 1  # sync worker → 1 thread, pas de partage d'état entre threads

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout      = int(os.environ.get('GUNICORN_TIMEOUT', '120'))   # worker tué après N s
graceful_timeout = 30   # délai supplémentaire pour finir les requêtes en cours
keepalive    = 5        # connexions keep-alive HTTP/1.1 (secondes)

# ── Recycling mémoire ─────────────────────────────────────────────────────────
# Redémarre chaque worker après N requêtes pour libérer les fuites mémoire progressives
# (Pillow, ReportLab, openpyxl peuvent fragmenter le heap sur de longues sessions).
max_requests        = 1_000
max_requests_jitter = 100   # étale les redémarrages pour éviter un spike simultané

# ── Preload ───────────────────────────────────────────────────────────────────
# Charge l'application Django avant le fork() des workers.
# Avantage : économise ~30-50 Mo RAM via Copy-on-Write (CoW).
# Prérequis : migrations déjà appliquées avant le démarrage (voir Dockerfile CMD).
preload_app = True

# ── Logs ──────────────────────────────────────────────────────────────────────
accesslog   = '-'      # stdout → collecté par Docker / systemd
errorlog    = '-'      # stderr
loglevel    = os.environ.get('GUNICORN_LOGLEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'
