import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from tenants.models import Tenant, Domain
from django.db.models import Sum


def is_superadmin(user):
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    from django_tenants.utils import schema_context
    from tenants.models import Tenant

    total_tenants   = Tenant.objects.exclude(schema_name='public').count()
    pending_count   = Tenant.objects.filter(status='awaiting_approval').count()
    active_count    = Tenant.objects.filter(status='active').count()
    trial_count     = Tenant.objects.filter(status='trial').count()
    suspended_count = Tenant.objects.filter(status='suspended').count()
    recent_tenants  = Tenant.objects.exclude(
                        schema_name='public'
                      ).order_by('-created_at')[:5]

    # ── Aggregate metrics across ALL tenant schemas ────
    total_revenue    = 0
    total_commission = 0
    total_sessions   = 0

    active_tenants = Tenant.objects.exclude(
        schema_name='public'
    ).filter(status__in=['active', 'trial'])

    for tenant in active_tenants:
        with schema_context(tenant.schema_name):
            from payments.models import Order
            from portal.models import WiFiSession
            from decimal import Decimal

            # Revenue — sum of all successful orders
            tenant_revenue = Order.objects.filter(
                status='success'
            ).aggregate(
                total=Sum('amount')
            )['total'] or 0

            # Commission — percentage of revenue
            commission_rate = tenant.commission_rate / Decimal('100')
            tenant_commission = Decimal(str(tenant_revenue)) * commission_rate

            # Active sessions
            tenant_sessions = WiFiSession.objects.filter(
                status='active'
            ).count()

            total_revenue    += float(tenant_revenue)
            total_commission += float(tenant_commission)
            total_sessions   += tenant_sessions

    return render(request, 'superadmin/dashboard.html', {
        'total_tenants'   : total_tenants,
        'pending_count'   : pending_count,
        'active_count'    : active_count,
        'trial_count'     : trial_count,
        'suspended_count' : suspended_count,
        'recent_tenants'  : recent_tenants,
        'total_revenue'   : total_revenue,
        'total_commission': total_commission,
        'total_sessions'  : total_sessions,
    })


@login_required
@user_passes_test(is_superadmin)
def applications(request):
    """
    Lists all tenant applications awaiting approval.
    """
    applications = Tenant.objects.filter(
        status='pending'
    ).order_by('-created_at')

    return render(request, 'superadmin/applications.html', {
        'applications': applications,
    })


@login_required
@user_passes_test(is_superadmin)
def approve_tenant(request, tenant_id):
    """
    Approves a tenant application.
    - Creates their PostgreSQL schema
    - Generates temporary password
    - Creates their subdomain
    - Emails credentials to tenant
    """
    tenant = get_object_or_404(Tenant, id=tenant_id, status='pending')

    if request.method == 'POST':
        trial_days       = int(request.POST.get('trial_days', 30))
        trial_commission = request.POST.get('trial_commission') == 'on'
        commission_rate  = float(request.POST.get('commission_rate', 10.0))

        # Create Django user for tenant owner — guard against duplicate email
        from django.contrib.auth.models import User

        if User.objects.filter(username=tenant.email).exists():
            messages.error(
                request,
                f'A user account with email {tenant.email} already exists. '
                'This application cannot be approved with a duplicate email.'
            )
            return redirect('superadmin:applications')

        # Generate temporary password
        temp_password = secrets.token_urlsafe(10)

        user = User.objects.create_user(
            username = tenant.email,
            email    = tenant.email,
            password = temp_password,
            is_staff = True,
        )
        # Force password change on first login
        from superadmin.models import UserProfile
        UserProfile.objects.create(user=user, must_change_password=True)

        # Update tenant record
        tenant.status          = 'trial'
        tenant.trial_start     = timezone.now()
        tenant.trial_end       = timezone.now() + timezone.timedelta(days=trial_days)
        tenant.trial_commission= trial_commission
        tenant.commission_rate = commission_rate
        tenant.approved_at     = timezone.now()
        tenant.approved_by     = request.user

        # Generate a unique token used to authenticate MikroTik router
        # registration requests for this tenant
        tenant.router_registration_token = secrets.token_urlsafe(32)

        tenant.auto_create_schema = True
        tenant.save()  # This creates the PostgreSQL schema

        # Create the subdomain domain record
        from tenants.utils import generate_subdomain
        subdomain = generate_subdomain(tenant.business_name)
        domain_str = f"{subdomain}.{settings.PLATFORM_DOMAIN}"

        Domain.objects.create(
            tenant     = tenant,
            domain     = domain_str,
            is_primary = True,
        )

        # Send credentials email to tenant
        login_url = f"http://{domain_str}:{settings.PLATFORM_PORT}/dashboard/login/"
        send_mail(
            subject  = 'Welcome to NETSPOT — Your account is ready!',
            message  = f"""
Hello {tenant.business_name},

Congratulations! Your NETSPOT account has been approved.

Your trial period: {trial_days} days
Your dashboard: {login_url}

Login credentials:
Email: {tenant.email}
Temporary Password: {temp_password}

Please change your password after first login.

— The NETSPOT Team
            """,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [tenant.email],
            fail_silently  = False,
        )

        messages.success(
            request,
            f'{tenant.business_name} approved successfully. Credentials emailed.'
        )
        return redirect('superadmin:applications')

    return render(request, 'superadmin/approve.html', {
        'tenant': tenant,
    })


@login_required
@user_passes_test(is_superadmin)
def reject_tenant(request, tenant_id):
    """
    Rejects a tenant application with a reason.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id, status='pending')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()

        tenant.status           = 'rejected'
        tenant.rejection_reason = reason
        tenant.save()

        send_mail(
            subject  = 'NETSPOT Application Update',
            message  = f"""
Hello {tenant.business_name},

Unfortunately we could not approve your application at this time.

Reason: {reason}

You are welcome to reapply after addressing the above.

— The NETSPOT Team
            """,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [tenant.email],
            fail_silently  = False,
        )

        messages.warning(
            request,
            f'{tenant.business_name} application rejected.'
        )
        return redirect('superadmin:applications')

    return render(request, 'superadmin/reject.html', {
        'tenant': tenant,
    })


@login_required
@user_passes_test(is_superadmin)
def tenant_list(request):
    """
    Lists all tenants on the platform.
    """
    tenants = Tenant.objects.exclude(
        schema_name='public'
    ).order_by('-created_at')

    return render(request, 'superadmin/tenant_list.html', {
        'tenants': tenants,
    })



from superadmin.models import WithdrawalRequest
from superadmin.utils import complete_withdrawal


@login_required
@user_passes_test(is_superadmin)
def withdrawal_queue(request):
    """
    Lists all withdrawal requests awaiting manual approval
    (amounts at or above the auto-approval threshold).
    """
    status_filter = request.GET.get('status', 'pending')

    withdrawals = WithdrawalRequest.objects.exclude(
        tenant__schema_name='public'
    ).order_by('-requested_at')

    if status_filter:
        withdrawals = withdrawals.filter(status=status_filter)

    pending_count = WithdrawalRequest.objects.filter(status='pending').count()

    return render(request, 'superadmin/withdrawal_queue.html', {
        'withdrawals'  : withdrawals,
        'status_filter': status_filter,
        'pending_count': pending_count,
    })


@login_required
@user_passes_test(is_superadmin)
def approve_withdrawal(request, withdrawal_id):
    """
    Approves a pending withdrawal request and immediately
    attempts disbursement via IOTEC.
    """
    withdrawal = get_object_or_404(
        WithdrawalRequest, id=withdrawal_id, status='pending'
    )

    if request.method == 'POST':
        withdrawal.status = WithdrawalRequest.APPROVED
        withdrawal.approved_at = timezone.now()
        withdrawal.save()

        result = complete_withdrawal(withdrawal)

        if result['success']:
            messages.success(
                request,
                f'Withdrawal of UGX {withdrawal.amount} for {withdrawal.tenant.business_name} approved and disbursed.'
            )
        else:
            messages.error(
                request,
                f'Withdrawal approved but disbursement failed: {result["message"]}'
            )

        return redirect('superadmin:withdrawal_queue')

    return render(request, 'superadmin/approve_withdrawal.html', {
        'withdrawal': withdrawal,
    })


@login_required
@user_passes_test(is_superadmin)
def reject_withdrawal(request, withdrawal_id):
    """
    Rejects a pending withdrawal request with a reason.
    Wallet is never touched since nothing was disbursed.
    """
    withdrawal = get_object_or_404(
        WithdrawalRequest, id=withdrawal_id, status='pending'
    )

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()

        withdrawal.status = WithdrawalRequest.FAILED
        withdrawal.failure_reason = reason or 'Rejected by admin'
        withdrawal.save()

        messages.warning(
            request,
            f'Withdrawal of UGX {withdrawal.amount} for {withdrawal.tenant.business_name} rejected.'
        )
        return redirect('superadmin:withdrawal_queue')

    return render(request, 'superadmin/reject_withdrawal.html', {
        'withdrawal': withdrawal,
    })




from superadmin.models import SMSBundle


@login_required
@user_passes_test(is_superadmin)
def sms_bundles(request):
    """
    Lists all SMS bundles for management.
    """
    bundles = SMSBundle.objects.all().order_by('display_order', 'sms_count')

    return render(request, 'superadmin/sms_bundles.html', {
        'bundles': bundles,
    })


@login_required
@user_passes_test(is_superadmin)
def create_sms_bundle(request):
    """
    Creates a new SMS bundle.
    """
    if request.method == 'POST':
        SMSBundle.objects.create(
            name          = request.POST.get('name'),
            sms_count     = request.POST.get('sms_count'),
            price         = request.POST.get('price'),
            display_order = request.POST.get('display_order', 0),
            is_active     = request.POST.get('is_active') == 'on',
        )
        messages.success(request, 'SMS bundle created successfully.')
        return redirect('superadmin:sms_bundles')

    return render(request, 'superadmin/create_sms_bundle.html')


@login_required
@user_passes_test(is_superadmin)
def edit_sms_bundle(request, bundle_id):
    """
    Edits an existing SMS bundle.
    """
    bundle = get_object_or_404(SMSBundle, id=bundle_id)

    if request.method == 'POST':
        bundle.name          = request.POST.get('name', bundle.name)
        bundle.sms_count     = request.POST.get('sms_count', bundle.sms_count)
        bundle.price         = request.POST.get('price', bundle.price)
        bundle.display_order = request.POST.get('display_order', bundle.display_order)
        bundle.is_active     = request.POST.get('is_active') == 'on'
        bundle.save()
        messages.success(request, 'SMS bundle updated successfully.')
        return redirect('superadmin:sms_bundles')

    return render(request, 'superadmin/edit_sms_bundle.html', {
        'bundle': bundle,
    })


@login_required
@user_passes_test(is_superadmin)
def toggle_sms_bundle(request, bundle_id):
    """
    Toggles a bundle's active status.
    """
    bundle = get_object_or_404(SMSBundle, id=bundle_id)

    if request.method == 'POST':
        bundle.is_active = not bundle.is_active
        bundle.save()

    return redirect('superadmin:sms_bundles')


@login_required
@user_passes_test(is_superadmin)
def tenant_detail(request, tenant_id):
    """
    Shows full details for a single tenant.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)

    return render(request, 'superadmin/tenant_detail.html', {
        'tenant': tenant,
    })

@login_required
@user_passes_test(is_superadmin)
def delete_tenant(request, tenant_id):
    """
    Permanently deletes a tenant, including their PostgreSQL schema
    and all business data within it. Requires explicit confirmation.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)

    if request.method == 'POST':
        business_name = tenant.business_name

        # Raw SQL delete avoids Django's cascade trying to touch
        # tenant-schema tables (like dashboard_lead) that don't exist
        # in the public schema context.
        # Raw SQL delete avoids Django's cascade trying to touch
        # tenant-schema tables (like dashboard_lead) that don't exist
        # in the public schema context.
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM superadmin_userprofile WHERE user_id IN "
                "(SELECT id FROM auth_user WHERE username = %s)",
                [tenant.email]
            )
            cursor.execute("DELETE FROM auth_user WHERE username = %s", [tenant.email])

        tenant.delete(force_drop=True)

        messages.warning(request, f'{business_name} and all associated data has been permanently deleted.')
        return redirect('superadmin:tenant_list')

    return render(request, 'superadmin/delete_tenant.html', {
        'tenant': tenant,
    })


@login_required
@user_passes_test(is_superadmin)
def revenue_report(request):
    """
    Shows daily/weekly/monthly revenue per tenant, plus platform-wide
    financial summary: real IOTEC balance, commission earned,
    tenant wallet liabilities, and pending withdrawals.
    """
    from django_tenants.utils import schema_context
    from datetime import timedelta
    from decimal import Decimal
    from payments import iotec
    from superadmin.models import WithdrawalRequest

    now       = timezone.now()
    today     = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    tenants = Tenant.objects.exclude(schema_name='public').filter(
        status__in=['active', 'trial']
    )

    report = []
    commission_today = Decimal('0')
    commission_week  = Decimal('0')
    commission_month = Decimal('0')

    for tenant in tenants:
        with schema_context(tenant.schema_name):
            from payments.models import Order

            today_revenue = Order.objects.filter(
                status='success', created_at__gte=today
            ).aggregate(total=Sum('amount'))['total'] or 0

            week_revenue = Order.objects.filter(
                status='success', created_at__gte=week_ago
            ).aggregate(total=Sum('amount'))['total'] or 0

            month_revenue = Order.objects.filter(
                status='success', created_at__gte=month_ago
            ).aggregate(total=Sum('amount'))['total'] or 0

        rate = tenant.commission_rate / Decimal('100')
        commission_today += Decimal(str(today_revenue)) * rate
        commission_week  += Decimal(str(week_revenue)) * rate
        commission_month += Decimal(str(month_revenue)) * rate

        report.append({
            'tenant': tenant,
            'today': today_revenue,
            'week': week_revenue,
            'month': month_revenue,
        })

    report.sort(key=lambda r: r['month'], reverse=True)

    # ── Real IOTEC wallet balance ──────────────────────
    iotec_balance = iotec.get_wallet_balance()

    # ── Total tenant wallet liabilities ────────────────
    total_tenant_wallets = Tenant.objects.exclude(
        schema_name='public'
    ).aggregate(total=Sum('wallet_balance'))['total'] or 0

    # ── Pending withdrawals ─────────────────────────────
    pending_withdrawals = WithdrawalRequest.objects.filter(
        status='pending'
    ).aggregate(total=Sum('amount'))['total'] or 0

    return render(request, 'superadmin/revenue_report.html', {
        'report': report,
        'commission_today': commission_today,
        'commission_week': commission_week,
        'commission_month': commission_month,
        'iotec_balance': iotec_balance,
        'total_tenant_wallets': total_tenant_wallets,
        'pending_withdrawals': pending_withdrawals,
    })


