from decimal import Decimal
from django_tenants.utils import schema_context
from tenants.models import Tenant

with schema_context('public'):
    tenant = Tenant.objects.get(schema_name='kampala_schools')
    tenant.wallet_balance = Decimal('20000')
    tenant.save()
    print('Balance topped up to:', tenant.wallet_balance)
