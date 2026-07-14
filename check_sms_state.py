from django_tenants.utils import schema_context
from tenants.models import Tenant

with schema_context('public'):
    tenant = Tenant.objects.get(schema_name='kampala_schools')
    print('Wallet balance:', tenant.wallet_balance)
    print('SMS credits:', tenant.sms_credits)
