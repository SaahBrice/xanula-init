from django.utils import translation


class UserLanguageMiddleware:
    """
    Apply user's preferred language from DB after LocaleMiddleware.
    If the user is authenticated and has a preferred_language set,
    activate that language and persist it in the session.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            preferred = getattr(request.user, 'preferred_language', '')
            if preferred and preferred != request.LANGUAGE_CODE:
                translation.activate(preferred)
                request.LANGUAGE_CODE = preferred
                # Persist in session so LocaleMiddleware picks it up next time
                if hasattr(request, 'session'):
                    request.session[translation.LANGUAGE_SESSION_KEY] = preferred

        response = self.get_response(request)
        return response
