"""
Makes role-based navigation visibility available in every template
without needing to pass it manually from each view.
"""

def role_permissions(request):
    if not request.user.is_authenticated:
        return {}

    from superadmin.utils import can_access

    sections = [
        'wallet', 'withdrawals', 'sms_bundles', 'settings', 'team',
        'packages', 'vouchers', 'payments', 'expenses', 'analytics',
        'voucher_agents', 'routers', 'equipment', 'advertisements',
        'messages', 'leads', 'customers',
    ]

    nav_access = {section: can_access(request.user, section) for section in sections}

    return {'nav_access': nav_access}