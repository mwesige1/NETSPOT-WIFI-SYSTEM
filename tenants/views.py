import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import Tenant, Domain
from .utils import generate_schema_name




def build_verify_url(token):
    """
    Builds the email verification URL, correctly handling both
    local dev (http, explicit port) and production (https, no port).
    """
    domain = settings.PLATFORM_DOMAIN
    port = settings.PLATFORM_PORT

    if port:
        return f"http://{domain}:{port}/verify-email/{token}/"
    else:
        return f"https://{domain}/verify-email/{token}/"


def send_verification_email(business_name, email, verify_url, is_reapply=False):
    """
    Sends the verification email as both HTML (clickable link)
    and plain text (fallback for clients that don't render HTML).
    """
    from django.core.mail import EmailMultiAlternatives

    greeting = "Thank you for reapplying to join NETSPOT!" if is_reapply else "Thank you for applying to join NETSPOT!"

    text_content = f"""
Hello {business_name},

{greeting}

Please verify your email address by visiting the link below:

{verify_url}

This link expires in 24 hours.

If you did not apply for a NETSPOT account, please ignore this email.

— The NETSPOT Team
"""

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
        <h2 style="color: #1a1a2e;">Verify your NETSPOT account</h2>
        <p>Hello {business_name},</p>
        <p>{greeting}</p>
        <p style="margin: 24px 0;">
            <a href="{verify_url}" style="background: #0a0f2c; color: #ffffff; padding: 14px 28px; border-radius: 10px; text-decoration: none; font-weight: 700; display: inline-block;">
                Verify My Email
            </a>
        </p>
        <p style="color: #9ca3af; font-size: 13px;">This link expires in 24 hours. If you did not apply for a NETSPOT account, please ignore this email.</p>
        <p style="color: #9ca3af; font-size: 13px;">— The NETSPOT Team</p>
    </div>
    """

    msg = EmailMultiAlternatives(
        subject='Verify your NETSPOT account',
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)


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
    Allows a previously rejected business to reapply using the same email.
    """
    if request.method == 'POST':
        business_name = request.POST.get('business_name', '').strip()
        business_type = request.POST.get('business_type', '')
        email         = request.POST.get('email', '').strip()
        phone         = request.POST.get('phone', '').strip()
        location      = request.POST.get('location', '').strip()
        contact_person_name  = request.POST.get('contact_person_name', '').strip()
        contact_person_role  = request.POST.get('contact_person_role', '')

        if not all([business_name, business_type, email, phone, location, contact_person_name, contact_person_role]):
            messages.error(request, 'All fields are required.')
            return render(request, 'tenants/signup.html')

        existing_tenant = Tenant.objects.filter(email=email).first()

        if existing_tenant:
            if existing_tenant.status == 'rejected':
                # Allow reapplication — reset the same record instead of blocking
                existing_tenant.business_name      = business_name
                existing_tenant.business_type      = business_type
                existing_tenant.phone              = phone
                existing_tenant.location           = location
                existing_tenant.contact_person_name  = contact_person_name
                existing_tenant.contact_person_role  = contact_person_role
                existing_tenant.status             = 'pending'
                existing_tenant.rejection_reason   = ''
                existing_tenant.email_verified     = False
                existing_tenant.verification_token = uuid.uuid4().hex
                existing_tenant.save()

                verify_url = build_verify_url(existing_tenant.verification_token)
                send_verification_email(business_name, email, verify_url, is_reapply=True)

                messages.success(
                    request,
                    'Application resubmitted! Please check your email to verify your address.'
                )
                return redirect('tenants:landing')

            else:
                # Still pending, active, trial, suspended, etc — genuinely blocked
                messages.error(request, 'A business with this email already exists.')
                return render(request, 'tenants/signup.html')

        schema_name = generate_schema_name(business_name)

        if Tenant.objects.filter(schema_name=schema_name).exists():
            schema_name = f"{schema_name}_{Tenant.objects.count()}"

        # Generate a unique verification token
        verification_token = uuid.uuid4().hex

        tenant = Tenant(
            schema_name           = schema_name,
            business_name         = business_name,
            business_type         = business_type,
            email                 = email,
            phone                 = phone,
            location              = location,
            contact_person_name   = contact_person_name,
            contact_person_role   = contact_person_role,
            status                = 'pending',
            email_verified        = False,
            verification_token    = verification_token,
            )
        tenant.auto_create_schema = False
        tenant.save()

        verify_url = build_verify_url(verification_token)
        send_verification_email(business_name, email, verify_url, is_reapply=False)

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
    tenant.status         = 'pending'
    tenant.save()

    messages.success(
        request,
        'Email verified successfully! Your application is now under review. '
        'We will contact you within 24 hours.'
    )
    return redirect('tenants:landing')
    