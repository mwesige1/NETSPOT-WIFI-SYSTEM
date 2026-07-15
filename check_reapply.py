from django_tenants.utils import schema_context
from tenants.models import Tenant

with schema_context('public'):
    t = Tenant.objects.get(email='messiahpatrick6@gmail.com')
    print('Business:', t.business_name)
    print('Status:', t.status)
    print('Rejection reason:', repr(t.rejection_reason))
    print('Email verified:', t.email_verified)
