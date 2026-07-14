from django.core.mail import send_mail
from django.conf import settings

send_mail(
    subject='NETSPOT Test Email',
    message='If you are reading this, real email sending is working.',
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=['mwesigedeveloper@gmail.com'],
    fail_silently=False,
)
print("Email sent successfully")
