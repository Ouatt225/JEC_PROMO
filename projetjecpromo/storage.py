"""Storage Django personnalisé pour SYGEPE.

MinifiedManifestStaticFilesStorage :
    Étend ManifestStaticFilesStorage pour minifier CSS et JS avec rcssmin/rjsmin
    lors du `collectstatic`. Zéro changement de templates requis.

    Fonctionnement :
    1. `collectstatic` copie les fichiers de STATICFILES_DIRS vers STATIC_ROOT.
    2. `post_process` est appelé — notre override minifie les fichiers en place
       dans STATIC_ROOT avant que le parent génère les hashes de contenu.
    3. Le parent produit ensuite les URL versionées (cache-busting) sur les fichiers
       déjà minifiés.

    Résultat attendu : style.css 43 Ko → ~22 Ko | main.js 32 Ko → ~18 Ko.
    Avec gzip Nginx/gunicorn : ~8 Ko + ~7 Ko en transfert.
"""

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class MinifiedManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """ManifestStaticFilesStorage + minification CSS/JS via rcssmin et rjsmin."""

    def post_process(self, paths, dry_run=False, **options):
        if not dry_run:
            for path in paths:
                if path.endswith('.css') and not path.endswith('.min.css'):
                    self._minify_in_place(path, 'css')
                elif path.endswith('.js') and not path.endswith('.min.js'):
                    self._minify_in_place(path, 'js')
        yield from super().post_process(paths, dry_run, **options)

    def _minify_in_place(self, path, kind):
        """Minifie le fichier `path` dans STATIC_ROOT et l'écrase."""
        try:
            with self.open(path) as f:
                content = f.read().decode('utf-8')

            if kind == 'css':
                import rcssmin
                minified = rcssmin.cssmin(content)
            else:
                import rjsmin
                minified = rjsmin.jsmin(content)

            if len(minified) < len(content):
                abs_path = self.path(path)
                with open(abs_path, 'w', encoding='utf-8') as f:
                    f.write(minified)
        except Exception:
            pass  # Ne jamais bloquer collectstatic — on garde le fichier original
