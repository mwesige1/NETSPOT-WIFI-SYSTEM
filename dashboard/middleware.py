from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    Redirects any authenticated user with must_change_password=True
    to the force-password-change page, blocking access to the rest
    of the dashboard until they set a new password.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Avoid redirect loops on the change-password page and logout itself
            exempt_paths = [
                reverse('dashboard:force_password_change'),
                reverse('dashboard:logout'),
            ]

            if request.path not in exempt_paths:
                profile = getattr(request.user, 'profile', None)
                if profile and profile.must_change_password:
                    return redirect('dashboard:force_password_change')

        return self.get_response(request)