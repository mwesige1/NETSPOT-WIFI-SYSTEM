import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import Tenant, Domain
from .utils import generate_schema_name


def landing(request):
    """
    Main platform landing page.
    Shown at kevidtechhotspot.com
    """
    return render(request, 'tenants/landing.html')


def signup(request):
    """
    Tenant signup form.
    Creates a pending tenant application and sends verification email.
    """
    if request.method == 'POST':
        business_name = request.POST.get('business_name', '').strip()
        business_type = request.POST.get('business_type', '')
        email         = request.POST.get('email', '').strip()
        phone         = request.POST.get('phone', '').strip()
        location      = request.POST.get('location', '').strip()

        if not all([business_name, business_type, email, phone, location]):
            messages.error(request, 'All fields are required.')
            return render(request, 'tenants/signup.html')

        if Tenant.objects.filter(email=email).exists():
            messages.error(request, 'A business with this email already exists.')
            return render(request, 'tenants/signup.html')

        schema_name = generate_schema_name(business_name)

        if Tenant.objects.filter(schema_name=schema_name).exists():
            schema_name = f"{schema_name}_{Tenant.objects.count()}"

        # Generate a unique verification token
        verification_token = uuid.uuid4().hex

        tenant = Tenant(
            schema_name        = schema_name,
            business_name      = business_name,
            business_type      = business_type,
            email              = email,
            phone              = phone,
            location           = location,
            status             = 'pending',
            email_verified     = False,
            verification_token = verification_token,
        )
        tenant.auto_create_schema = False
        tenant.save()

        # Build verification URL
        domain = settings.PLATFORM_DOMAIN
        port   = settings.PLATFORM_PORT
        verify_url = f"http://{domain}:{port}/verify-email/{verification_token}/"

        # Send verification email
        send_mail(
            subject    = 'Verify your NETSPOT account',
            message    = f"""
Hello {business_name},

Thank you for applying to join NETSPOT!

Please verify your email address by clicking the link below:

{verify_url}

This link expires in 24 hours.

If you did not apply for a NETSPOT account, please ignore this email.

— The NETSPOT Team
            """,
            from_email = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [email],
            fail_silently  = False,
        )

        messages.success(
            request,
            'Application submitted! Please check your email to verify your address.'
        )
        return redirect('tenants:landing')

    return render(request, 'tenants/signup.html')


def verify_email(request, token):
    """
    Handles email verification link clicks.
    Moves tenant from pending to awaiting_approval.
    """
    tenant = get_object_or_404(Tenant, verification_token=token)

    if tenant.email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('tenants:landing')

    # Mark email as verified and move to awaiting approval
    tenant.email_verified = True
    tenant.status         = 'awaiting_approval'
    tenant.save()

    messages.success(
        request,
        'Email verified successfully! Your application is now under review. '
        'We will contact you within 24 hours.'
    )
    return redirect('tenants:landing')
    