import subprocess
from django.shortcuts import render, redirect
from django.utils import timezone
from portal.models import Package, Device, WiFiSession, Customer
import json
from django.http import JsonResponse
from dashboard.models import Feedback



def get_client_ip(request):
    """
    Gets the real client IP address behind Nginx/Docker proxy.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_mac_from_ip(ip_address):
    """
    Looks up the system ARP table to find the MAC
    address associated with a given IP address.
    Returns None if device is not found in ARP table.
    """
    try:
        result = subprocess.run(
            ['arp', '-n', ip_address],
            capture_output=True,
            text=True
        )
        lines = result.stdout.split('\n')
        for line in lines:
            if ip_address in line:
                parts = line.split()
                if len(parts) >= 3:
                    mac = parts[2]
                    if mac and mac != '--' and ':' in mac:
                        return mac
    except Exception:
        pass
    return None


def portal_landing(request):
    """
    The main captive portal page that every customer
    sees when they connect to the WiFi network.
    """
    from network.models import MikroTikRouter

    ip_address  = request.GET.get('ip') or get_client_ip(request)
    mac_address = request.GET.get('mac', None)

    # ── Detect which router this customer is on ────────
    router_identity = request.GET.get('router', None)
    router          = None

    if router_identity:
        try:
            router = MikroTikRouter.objects.get(identity=router_identity)
        except MikroTikRouter.DoesNotExist:
            pass

    # ── If no router in URL try to detect from gateway IP
    if not router:
        try:
            router = MikroTikRouter.objects.get(
                gateway_ip=request.META.get('REMOTE_ADDR')
            )
        except MikroTikRouter.DoesNotExist:
            pass

    # ── If still no router fall back to first online router
    if not router:
        router = MikroTikRouter.objects.filter(
            status='online'
        ).first()

    # ── MAC detection ──────────────────────────────────
    if not mac_address:
        mac_address = get_mac_from_ip(ip_address)

    if mac_address:
        device, created = Device.objects.get_or_create(
            mac_address=mac_address
        )
        device.last_seen = timezone.now()

        # Link device to its router
        if router:
            device.last_router = router

        device.save()

        if device.is_blocked:
            return render(request, 'portal/blocked.html', {
                'mac_address': mac_address,
                'ip_address' : ip_address,
            })

        active_session = WiFiSession.objects.filter(
            device=device,
            status='active',
            expiry_time__gt=timezone.now()
        ).first()

        if active_session:
            return redirect(f'/connected/?mac={mac_address}')

    # ── Fetch active packages ──────────────────────────
    packages = Package.objects.filter(
        status='active'
    ).order_by('display_order', 'price')

    # ── Fetch active advertisement (for the scrolling ticker) ──
    from dashboard.models import Advertisement
    active_ad = Advertisement.objects.filter(
        is_active=True
    ).order_by('-priority').first()

    # ── Fetch active image ad specifically (for the popup) ─────
    popup_ad = Advertisement.objects.filter(
        is_active=True
    ).exclude(media_file='').order_by('-priority').first()

    from dashboard.models import SystemSettings

    tenant_settings = SystemSettings.get_settings()

    settings = {
        'business_name': tenant_settings.business_name,
        'logo': tenant_settings.logo.url if tenant_settings.logo else None,
        'primary_color': tenant_settings.brand_color,
        'welcome_message': tenant_settings.welcome_message,
        'footer_text': tenant_settings.footer_text,
    }

    return render(request, 'portal/landing.html', {
        'packages'   : packages,
        'mac_address': mac_address if mac_address and mac_address not in ['--', 'None', ''] else 'AA:BB:CC:DD:EE:FF',
        'ip_address' : ip_address,
        'active_ad'  : active_ad,
        'settings'   : settings,
        'popup_ad'   : popup_ad,
        'router_id'  : router.id if router else '',
    })


def connected(request):
    mac_address = request.GET.get('mac', '')
    session     = None

    if mac_address:
        try:
            device = Device.objects.get(mac_address=mac_address)

            if device.is_blocked:
                return render(request, 'portal/blocked.html', {
                    'mac_address': mac_address,
                })

            session = WiFiSession.objects.filter(
                device=device,
                status='active',
                expiry_time__gt=timezone.now()
            ).select_related('package').first()

            if not session:
                return redirect(f'/?mac={mac_address}')

        except Device.DoesNotExist:
            pass

    settings = {}

    return render(request, 'portal/connected.html', {
        'session'    : session,
        'mac_address': mac_address,
        'settings'   : settings,
    })


def blocked(request):
    """
    Page shown when a device has been blocked by admin.
    """
    return render(request, 'portal/blocked.html')


def submit_feedback(request):
    """
    Handles star rating and comment submission
    from the connected page via AJAX POST.
    """
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        rating     = request.POST.get('rating', 0)
        comment    = request.POST.get('comment', '')

        try:
            session = WiFiSession.objects.get(id=session_id)
            Feedback.objects.create(
                session = session,
                device  = session.device,
                rating  = int(rating),
                comment = comment.strip(),
            )
            return JsonResponse({'success': True})
        except WiFiSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


def session_status(request):
    """
    Called every 3 seconds by JavaScript on the
    connected and blocked pages to check if the
    device status has changed.
    """
    mac_address = request.GET.get('mac', '')

    if not mac_address:
        return JsonResponse({'status': 'unknown'})

    try:
        device = Device.objects.get(mac_address=mac_address)

        if device.is_blocked:
            return JsonResponse({'status': 'blocked'})

        active_session = WiFiSession.objects.filter(
            device=device,
            status='active',
            expiry_time__gt=timezone.now()
        ).first()

        if active_session:
            return JsonResponse({
                'status'     : 'active',
                'expiry_time': active_session.expiry_time.isoformat(),
            })

        return JsonResponse({'status': 'expired'})

    except Device.DoesNotExist:
        return JsonResponse({'status': 'unknown'})


