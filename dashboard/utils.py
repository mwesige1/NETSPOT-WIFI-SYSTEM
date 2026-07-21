"""
SMS sending logic — wraps Africa's Talking API and handles
credit deduction from the tenant's sms_credits balance.
"""
from django.conf import settings


def send_sms(tenant, phone_number, message_text):
    """
    Sends an SMS via Africa's Talking and deducts one credit
    from the tenant's balance. Returns a dict with 'success' and
    'message' keys.

    NOTE: Real Africa's Talking API call is not wired in yet —
    this currently simulates success once credentials are added
    to settings (AT_USERNAME, AT_API_KEY), replace the marked
    section below with the real API call.
    """
    if tenant.sms_credits <= 0:
        return {
            'success': False,
            'message': 'Insufficient SMS credits. Please purchase more credits.'
        }

    # ── TODO: Replace this block with real Africa's Talking call ──
    # import africastalking
    # africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
    # sms = africastalking.SMS
    # response = sms.send(message_text, [phone_number])
    # api_success = response['SMSMessageData']['Recipients'][0]['status'] == 'Success'
    api_success = True  # placeholder until real API is wired in
    # ── End placeholder ─────────────────────────────────────────

    if api_success:
        tenant.sms_credits -= 1
        tenant.save()
        return {'success': True, 'message': 'SMS sent successfully.'}
    else:
        return {'success': False, 'message': 'SMS delivery failed. Please try again.'}
    





def create_notification(notification_type, title, message, link=''):
    """
    Creates a notification for the current tenant.
    Must be called from within the correct tenant schema context.
    """
    from dashboard.models import Notification

    Notification.objects.create(
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
    )