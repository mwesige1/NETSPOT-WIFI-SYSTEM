"""
Access-control decorators for the tenant dashboard.
Enforces role-based permissions (Owner / Manager / Staff) on views.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from superadmin.utils import can_access


def require_access(section):
    """
    Blocks access to a view unless the logged-in user's role
    permits access to the given section. Must be used together
    with @login_required (place @require_access above it).

    Usage:
        @login_required
        @require_access('wallet')
        def wallet_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not can_access(request.user, section):
                messages.error(
                    request,
                    "You don't have permission to access that page."
                )
                return redirect('dashboard:overview')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator