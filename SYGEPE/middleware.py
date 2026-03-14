"""Middleware de sécurité supplémentaires pour SYGEPE."""


class ContentSecurityPolicyMiddleware:
    """Ajoute l'en-tête Content-Security-Policy à chaque réponse HTTP.

    Politique :
    - Scripts autorisés : 'self' + cdn.jsdelivr.net (chart.js, fullcalendar).
      'unsafe-inline' conservé car les templates embarquent des <script> inline
      (calculs date, chart rendering). La whitelist de domaines bloque tout CDN non listé.
    - Styles autorisés : 'self' + fonts.googleapis.com + 'unsafe-inline' (nombreux style="").
    - Fonts : 'self' + fonts.gstatic.com.
    - Images : 'self' + data: (avatars base64) + blob:.
    - Formulaires : uniquement vers 'self' (bloque l'exfiltration vers un domaine externe).
    - Frames : 'none' (redondant avec X_FRAME_OPTIONS=DENY mais explicite dans le header).
    - Plugins/objets : 'none' (Flash, Java applets interdits).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._csp = (
            "default-src 'self'; "
            "script-src 'self' cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src 'self' fonts.googleapis.com 'unsafe-inline'; "
            "font-src 'self' fonts.gstatic.com data:; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self._csp)
        return response
