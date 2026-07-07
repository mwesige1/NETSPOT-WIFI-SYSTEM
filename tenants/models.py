from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Tenant(TenantMixin):
    """
    Represents a business on the NETSPOT platform.
    Each tenant gets their own PostgreSQL schema.
    TenantMixin provides: schema_name, created_on
    """
    # ── Business Identity ──────────────────────────
    business_name  = models.CharField(max_length=200)
    business_type  = models.CharField(max_length=50, choices=[
        ('hotel',      'Hotel'),
        ('school',     'School'),
        ('individual', 'Individual'),
        ('isp',        'ISP'),
        ('other',      'Other'),
    ])
    logo           = models.ImageField(upload_to='tenant_logos/', null=True, blank=True)
    primary_color  = models.CharField(max_length=7, default='#F5A623')

    # ── Contact Details ────────────────────────────
    email          = models.EmailField(unique=True)
    phone          = models.CharField(max_length=20)
    location       = models.CharField(max_length=200)
    country        = models.CharField(max_length=100, default='Uganda')

    # ── Status & Lifecycle ─────────────────────────
    status         = models.CharField(max_length=20, choices=[
        ('pending',    'Pending Approval'),
        ('trial',      'Trial'),
        ('active',     'Active'),
        ('suspended',  'Suspended'),
        ('terminated', 'Terminated'),
    ], default='pending')

    # ── Trial Configuration ────────────────────────
    trial_start       = models.DateTimeField(null=True, blank=True)
    trial_end         = models.DateTimeField(null=True, blank=True)
    trial_commission  = models.BooleanField(default=False)

    # ── Financial ──────────────────────────────────
    wallet_balance    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    minimum_balance   = models.DecimalField(max_digits=12, decimal_places=2, default=5000)
    commission_rate   = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)

    # ── SMS Credits ────────────────────────────────
    sms_credits       = models.PositiveIntegerField(default=0)

    # ── Approval ───────────────────────────────────
    approved_at       = models.DateTimeField(null=True, blank=True)
    approved_by       = models.ForeignKey(
        'auth.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_tenants'
    )
    rejection_reason  = models.TextField(blank=True)

    # ── Timestamps ─────────────────────────────────
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    # django-tenants requires this — auto creates schema on save
    auto_create_schema = True

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.business_name


class Domain(DomainMixin):
    """
    Maps a subdomain to a tenant.
    DomainMixin provides: tenant (FK), domain, is_primary
    e.g. serena-hotel.kevidtechhotspot.com → Serena Hotel tenant
    """
    pass