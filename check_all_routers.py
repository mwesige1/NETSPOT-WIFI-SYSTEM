from django_tenants.utils import schema_context
from tenants.models import Tenant
from network.models import MikroTikRouter

for tenant in Tenant.objects.exclude(schema_name='public'):
    with schema_context(tenant.schema_name):
        routers = MikroTikRouter.objects.all()
        if routers.exists():
            print(f"--- {tenant.business_name} ({tenant.schema_name}) ---")
            for r in routers:
                print(' ', r.identity, '| connection_type:', r.connection_type, '| gateway_ip:', r.ip_address, '| wireguard_tunnel_ip:', r.wireguard_tunnel_ip)
