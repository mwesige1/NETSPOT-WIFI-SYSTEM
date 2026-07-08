import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from tenants.models import Tenant, Domain


def is_superadmin(user):
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    """
    Super admin platform overview.
    Shows key metrics across all tenants.
    """
    total_tenants     = Tenant.objects.exclude(schema_name='public').count()
    pending_count     = Tenant.objects.filter(status='awaiting_approval').count()
    active_count      = Tenant.objects.filter(status='active').count()
    trial_count       = Tenant.objects.filter(status='trial').count()
    suspended_count   = Tenant.objects.filter(status='suspended').count()
    recent_tenants    = Tenant.objects.exclude(
                            schema_name='public'
                        ).order_by('-created_at')[:5]

    return render(request, 'superadmin/dashboard.html', {
        'total_tenants'  : total_tenants,
        'pending_count'  : pending_count,
        'active_count'   : active_count,
        'trial_count'    : trial_count,
        'suspended_count': suspended_count,
        'recent_tenants' : recent_tenants,
    })


@login_required
@user_passes_test(is_superadmin)
def applications(request):
    """
    Lists all tenant applications awaiting approval.
    """
    applications = Tenant.objects.filter(
        status='awaiting_approval'
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
    tenant = get_object_or_404(Tenant, id=tenant_id, status='awaiting_approval')

    if request.method == 'POST':
        trial_days       = int(request.POST.get('trial_days', 30))
        trial_commission = request.POST.get('trial_commission') == 'on'
        commission_rate  = float(request.POST.get('commission_rate', 10.0))

        # Generate temporary password
        temp_password = secrets.token_urlsafe(10)

        # Create Django user for tenant owner
        from django.contrib.auth.models import User
        user = User.objects.create_user(
            username = tenant.email,
            email    = tenant.email,
            password = temp_password,
            is_staff = True,
        )

        # Update tenant record
        tenant.status          = 'trial'
        tenant.trial_start     = timezone.now()
        tenant.trial_end       = timezone.now() + timezone.timedelta(days=trial_days)
        tenant.trial_commission= trial_commission
        tenant.commission_rate = commission_rate
        tenant.approved_at     = timezone.now()
        tenant.approved_by     = request.user
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
        login_url = f"http://{domain_str}:{settings.PLATFORM_PORT}/login/"
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
    tenant = get_object_or_404(Tenant, id=tenant_id, status='awaiting_approval')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()

        tenant.status           = 'pending'
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