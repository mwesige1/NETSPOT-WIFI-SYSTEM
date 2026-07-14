from django.db import models
from tenants.models import Tenant


class Commission(models.Model):
    """
    Records every commission deduction from a tenant payment.
    Lives in the PUBLIC schema — tracks platform earnings.
    """
    tenant          = models.ForeignKey(
                        Tenant,
                        on_delete=models.SET_NULL,
                        null=True,
                        related_name='commissions'
                      )
    tenant_name     = models.CharField(max_length=200)
    order_id        = models.IntegerField()
    gross_amount    = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tenant_amount   = models.DecimalField(max_digits=12, decimal_places=2)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tenant_name} — UGX {self.commission_amount}"


class PlatformWallet(models.Model):
    """
    Single record tracking total platform commission earnings.
    Always only one row — use get_or_create to access it.
    """
    total_commission = models.DecimalField(
                        max_digits=14, decimal_places=2, default=0
                      )
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Platform Wallet — UGX {self.total_commission}"




from django.db import models
from tenants.models import Tenant


class WalletTransaction(models.Model):
    CREDIT = 'credit'
    DEBIT = 'debit'
    TRANSACTION_TYPE_CHOICES = [
        (CREDIT, 'Credit'),
        (DEBIT, 'Debit'),
    ]

    REASON_COMMISSION = 'commission_payment'
    REASON_WITHDRAWAL = 'withdrawal'
    REASON_SMS_PURCHASE = 'sms_purchase'
    REASON_ADJUSTMENT = 'manual_adjustment'
    REASON_CHOICES = [
        (REASON_COMMISSION, 'Payment (after commission)'),
        (REASON_WITHDRAWAL, 'Withdrawal'),
        (REASON_SMS_PURCHASE, 'SMS Credit Purchase'),
        (REASON_ADJUSTMENT, 'Manual Adjustment'),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='wallet_transactions'
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    order_id = models.PositiveIntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tenant.schema_name} — {self.transaction_type} UGX {self.amount}"
    


class WithdrawalRequest(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
        (CANCELLED, 'Cancelled'),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='withdrawal_requests'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    provider = models.CharField(max_length=10, choices=[('mtn', 'MTN'), ('airtel', 'Airtel')])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)

    iotec_txn_id = models.CharField(max_length=100, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.tenant.schema_name} — UGX {self.amount} ({self.status})"
    


class SMSBundle(models.Model):
    name = models.CharField(max_length=100)
    sms_count = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'sms_count']

    def __str__(self):
        return f"{self.name} — {self.sms_count} SMS for UGX {self.price}"