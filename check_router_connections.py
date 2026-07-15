from django_tenants.utils import schema_context
from network.models import MikroTikRouter

with schema_context('kampala_schools'):
    for r in MikroTikRouter.objects.all():
        print(r.identity, '| connection_type:', r.connection_type, '| gateway_ip:', r.ip_address, '| wireguard_tunnel_ip:', r.wireguard_tunnel_ip)
