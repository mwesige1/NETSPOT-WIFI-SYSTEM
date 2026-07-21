from celery import shared_task
from django.utils import timezone
from django_tenants.utils import schema_context
from network.mikrotik import revoke_internet_access, grant_internet_access
import subprocess
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def for_each_active_tenant():
    """
    Yields the schema_name of every active/trial tenant.
    Used by every Celery task below to loop across tenants,
    since django-tenants models don't exist in the public schema.
    """
    from tenants.models import Tenant
    with schema_context('public'):
        schema_names = list(
            Tenant.objects.exclude(schema_name='public')
            .filter(status__in=['active', 'trial'])
            .values_list('schema_name', flat=True)
        )
    return schema_names


@shared_task
def check_expired_sessions():
    """
    Runs every 60 seconds via Celery Beat, across every tenant schema.
    Finds all sessions that have expired but are still marked active,
    revokes their router access, and marks them expired.
    """
    from portal.models import WiFiSession

    total_count = 0

    for schema_name in for_each_active_tenant():
        with schema_context(schema_name):
            expired_sessions = WiFiSession.objects.filter(
                status='active',
                expiry_time__lte=timezone.now()
            )

            count = expired_sessions.count()
            if count:
                logger.info(f"[{schema_name}] check_expired_sessions: found {count} expired sessions")

            for session in expired_sessions:
                try:
                    revoke_internet_access(
                        mac_address=session.device.mac_address,
                        ip_address=session.ip_address,
                        router=session.router
                    )
                    session.status = 'expired'
                    session.save()
                    logger.info(f"[{schema_name}] Expired session for MAC: {session.device.mac_address}")
                except Exception as e:
                    logger.error(f"[{schema_name}] Failed to expire session {session.id}: {str(e)}")

            total_count += count

    return f"Processed {total_count} expired sessions across all tenants"


@shared_task
def sync_active_sessions():
    """
    Runs every 60 seconds via Celery Beat, across every tenant schema.
    Handles devices that reconnected with a new DHCP-assigned IP.
    """
    from portal.models import WiFiSession

    total_synced = 0

    for schema_name in for_each_active_tenant():
        with schema_context(schema_name):
            active_sessions = WiFiSession.objects.filter(
                status='active',
                expiry_time__gt=timezone.now()
            )

            for session in active_sessions:
                try:
                    current_ip = get_current_ip(session.device.mac_address)

                    if current_ip is None:
                        continue

                    if current_ip != session.ip_address:
                        revoke_internet_access(
                            mac_address=session.device.mac_address,
                            ip_address=session.ip_address,
                            router=session.router
                        )

                        old_ip = session.ip_address
                        session.ip_address = current_ip
                        session.save()

                        grant_internet_access(
                            mac_address=session.device.mac_address,
                            ip_address=current_ip,
                            router=session.router
                        )

                        logger.info(f"[{schema_name}] Updated IP for {session.device.mac_address}: {old_ip} → {current_ip}")

                except Exception as e:
                    logger.error(f"[{schema_name}] Failed to sync session {session.id}: {str(e)}")

            total_synced += active_sessions.count()

    return f"Synced {total_synced} active sessions across all tenants"


@shared_task
def restore_router_rules():
    """
    Runs every 5 minutes via Celery Beat, across every tenant schema.
    Re-applies router rules for active sessions and removes stale bindings.
    """
    from portal.models import WiFiSession
    from network.models import MikroTikRouter
    from network.mikrotik import MikrotikAPI

    total_restored = 0

    for schema_name in for_each_active_tenant():
        with schema_context(schema_name):
            active_sessions = WiFiSession.objects.filter(
                status='active',
                expiry_time__gt=timezone.now()
            ).select_related('device', 'router')

            active_macs = set(s.device.mac_address for s in active_sessions)
            count = 0

            for session in active_sessions:
                try:
                    grant_internet_access(
                        mac_address=session.device.mac_address,
                        ip_address=session.ip_address,
                        router=session.router
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"[{schema_name}] Failed to restore rule for session {session.id}: {str(e)}")

            routers = MikroTikRouter.objects.filter(status='online')

            for router in routers:
                try:
                    api = MikrotikAPI(router=router)
                    if not api.connect():
                        continue
                    if not api.login():
                        api.disconnect()
                        continue

                    api.send_sentence(['/ip/hotspot/ip-binding/print', '?type=bypassed'])
                    response = api.read_sentence()
                    api.disconnect()

                    current_id = None
                    current_mac = None

                    for word in response:
                        if word.startswith('=.id='):
                            current_id = word[5:]
                            current_mac = None
                        elif word.startswith('=mac-address='):
                            current_mac = word[13:]
                        elif word == '!re' and current_id and current_mac:
                            if current_mac.upper() not in [m.upper() for m in active_macs]:
                                try:
                                    api2 = MikrotikAPI(router=router)
                                    api2.connect()
                                    api2.login()
                                    api2.send_sentence(['/ip/hotspot/ip-binding/remove', f'=.id={current_id}'])
                                    api2.read_sentence()
                                    api2.disconnect()
                                    logger.warning(f"[{schema_name}] 🧹 Removed stale binding for {current_mac} on {router.identity}")
                                except Exception as e:
                                    logger.error(f"[{schema_name}] Failed to remove stale binding: {e}")
                            current_id = None
                            current_mac = None

                except Exception as e:
                    logger.error(f"[{schema_name}] Stale binding cleanup error on {router.identity}: {e}")

            total_restored += count

    return f"Restored {total_restored} router rules across all tenants"


@shared_task
def check_router_health():
    """
    Runs every 60 seconds via Celery Beat, across every tenant schema.
    Direct routers — checks API reachability.
    WireGuard routers — checks if polled recently.
    Also creates a notification when a router transitions to offline.
    """
    from network.models import MikroTikRouter
    from network.mikrotik import is_router_reachable
    from dashboard.utils import create_notification

    cutoff = timezone.now() - timedelta(seconds=30)
    total_checked = 0

    for schema_name in for_each_active_tenant():
        with schema_context(schema_name):
            routers = MikroTikRouter.objects.all()

            for router in routers:
                try:
                    old_status = router.status

                    if router.connection_type == 'wireguard':
                        if router.last_seen and router.last_seen >= cutoff:
                            router.status = 'online'
                        else:
                            router.status = 'offline'
                        router.save()
                    else:
                        reachable = is_router_reachable(router.connection_address)
                        router.status = 'online' if reachable else 'offline'

                        if reachable:
                            router.last_seen = timezone.now()

                        router.save()

                    if old_status != router.status:
                        logger.warning(f"[{schema_name}] Router {router.identity} changed: {old_status} → {router.status}")

                        if router.status == 'offline':
                            create_notification(
                                notification_type='router_offline',
                                title='Router Offline',
                                message=f'{router.location or router.identity} has gone offline.',
                                link='/dashboard/routers/'
                            )

                except Exception as e:
                    logger.error(f"[{schema_name}] Health check failed for router {router.identity}: {str(e)}")

            total_checked += routers.count()

    return f"Health check completed for {total_checked} routers across all tenants"


def get_current_ip(mac_address):
    """
    Looks up the ARP table to find the current IP address
    for a given MAC address. Returns None if not found.
    """
    try:
        result = subprocess.run(['arp', '-n'], capture_output=True, text=True)

        for line in result.stdout.split('\n'):
            if mac_address.lower() in line.lower():
                parts = line.split()
                if len(parts) >= 1:
                    return parts[0]

    except Exception as e:
        logger.error(f"ARP lookup error for {mac_address}: {str(e)}")

    return None