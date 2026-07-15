from django_tenants.utils import schema_context
from tenants.models import Tenant

with schema_context('public'):
    for t in Tenant.objects.exclude(schema_name='public'):
        print(t.business_name, '| status:', t.status, '| rejection_reason:', repr(t.rejection_reason))
