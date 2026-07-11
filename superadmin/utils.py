from decimal import Decimal
from superadmin.models import PlatformWallet, WalletTransaction


def deduct_commission(tenant, order_id, gross_amount):
    """
    Deducts platform commission from a successful payment.
    Called immediately after IOTEC confirms payment success.

    Args:
        tenant:       The Tenant object (from public schema)
        order_id:     The Order ID (from tenant schema)
        gross_amount: Total amount paid by customer (Decimal)

    Returns:
        dict with commission_amount and tenant_amount
    """
    from .models import Commission, PlatformWallet

    gross_amount    = Decimal(str(gross_amount))
    commission_rate = tenant.commission_rate  # e.g. Decimal('10.00')

    # Calculate split
    commission_amount = (gross_amount * commission_rate / Decimal('100')).quantize(Decimal('0.01'))
    tenant_amount     = gross_amount - commission_amount

    # Record commission transaction
    Commission.objects.create(
        tenant            = tenant,
        tenant_name       = tenant.business_name,
        order_id          = order_id,
        gross_amount      = gross_amount,
        commission_rate   = commission_rate,
        commission_amount = commission_amount,
        tenant_amount     = tenant_amount,
    )

    # Add to platform wallet
    wallet, _ = PlatformWallet.objects.get_or_create(id=1)
    wallet.total_commission += commission_amount
    wallet.save()

    # Add tenant's share to their wallet
    tenant.wallet_balance += tenant_amount
    tenant.save()

    return {
        'commission_amount': commission_amount,
        'tenant_amount'    : tenant_amount,
    }




def deduct_commission(tenant, order_id, gross_amount):
    gross_amount = Decimal(str(gross_amount))
    commission_rate = Decimal('0.10')

    commission_amount = gross_amount * commission_rate
    tenant_amount = gross_amount - commission_amount

    # Credit the tenant
    tenant.wallet_balance += tenant_amount
    tenant.save()

    # Credit the platform
    wallet = PlatformWallet.objects.get(id=1)
    wallet.total_commission += commission_amount
    wallet.save()

    # NEW — write the ledger entry for the tenant
    WalletTransaction.objects.create(
        tenant=tenant,
        transaction_type=WalletTransaction.CREDIT,
        reason=WalletTransaction.REASON_COMMISSION,
        amount=tenant_amount,
        balance_after=tenant.wallet_balance,
        order_id=order_id,
        note=f"Payment received — UGX {gross_amount} gross, UGX {commission_amount} commission deducted"
    )

    return {
        'commission_amount': commission_amount,
        'tenant_amount': tenant_amount,
    }