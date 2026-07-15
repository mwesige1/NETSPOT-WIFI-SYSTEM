from django.core.mail import send_mail
from django.conf import settings

print("EMAIL_HOST_USER:", repr(settings.EMAIL_HOST_USER))
print("EMAIL_HOST_PASSWORD length:", len(settings.EMAIL_HOST_PASSWORD))
print("EMAIL_BACKEND:", settings.EMAIL_BACKEND)

send_mail(
    subject='NETSPOT Test Email 2',
    message='Testing again.',
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=['messiahpatrick6@gmail.com'],
    fail_silently=False,
)
print("Email sent successfully")
