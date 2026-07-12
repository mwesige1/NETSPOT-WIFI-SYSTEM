from decimal import Decimal
from superadmin.models import PlatformWallet, WalletTransaction,WithdrawalRequest

from django.utils import timezone
from datetime import timedelta
from django.conf import settings





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



MINIMUM_WALLET_BALANCE = Decimal('5000')


def request_withdrawal(tenant, amount, phone_number, provider):
    amount = Decimal(str(amount))

    # ── Check 1 — Sufficient balance, respecting the floor ──
    remaining_after = tenant.wallet_balance - amount
    if remaining_after < MINIMUM_WALLET_BALANCE:
        return {
            'success': False,
            'message': f'Insufficient balance. You must keep at least UGX {MINIMUM_WALLET_BALANCE} in your wallet.'
        }

    # ── Check 2 — 24-hour restriction ────────────────────────
    last_request = WithdrawalRequest.objects.filter(
        tenant=tenant
    ).exclude(status=WithdrawalRequest.CANCELLED).order_by('-requested_at').first()

    if last_request:
        time_since_last = timezone.now() - last_request.requested_at
        if time_since_last < timedelta(hours=24):
            hours_remaining = 24 - (time_since_last.total_seconds() / 3600)
            return {
                'success': False,
                'message': f'You can request another withdrawal in {hours_remaining:.1f} hours.'
            }

    # ── Create the withdrawal request ────────────────────────
    withdrawal = WithdrawalRequest.objects.create(
        tenant=tenant,
        amount=amount,
        phone_number=phone_number,
        provider=provider,
        status=WithdrawalRequest.PENDING,
    )

    # ── Auto-approval for amounts under the threshold ───────
    if amount < settings.AUTO_APPROVAL_WITHDRAWAL_THRESHOLD:
        withdrawal.status = WithdrawalRequest.APPROVED
        withdrawal.approved_at = timezone.now()
        withdrawal.save()
        print(f"✅ Auto-approved withdrawal of UGX {amount} for {tenant.business_name} (under threshold)")
        # Actual IOTEC disbursement call happens in the next step we build
    else:
        print(f"⏳ Withdrawal of UGX {amount} for {tenant.business_name} held for manual approval (threshold: UGX {settings.AUTO_APPROVAL_WITHDRAWAL_THRESHOLD})")

    return {'success': True, 'withdrawal': withdrawal}