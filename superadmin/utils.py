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

        # Immediately attempt disbursement for auto-approved withdrawals
        complete_withdrawal(withdrawal)

    else:
        print(f"⏳ Withdrawal of UGX {amount} for {tenant.business_name} held for manual approval (threshold: UGX {settings.AUTO_APPROVAL_WITHDRAWAL_THRESHOLD})")

    return {'success': True, 'withdrawal': withdrawal}



def complete_withdrawal(withdrawal):
    """
    Attempts to actually disburse a withdrawal via IOTEC.
    Only on confirmed success does it:
      - mark the withdrawal COMPLETED
      - debit the tenant's wallet_balance
      - write a WalletTransaction debit entry

    If disbursement fails, the withdrawal is marked FAILED
    and the wallet is never touched — no money was actually lost.
    """
    from payments import iotec

    tenant = withdrawal.tenant

    result = iotec.request_disbursement(
        phone_number=withdrawal.phone_number,
        amount=withdrawal.amount,
        withdrawal_id=withdrawal.id,
        provider=withdrawal.provider,
    )

    if result['status'] == 'pending':
        # IOTEC accepted the disbursement request
        tenant.wallet_balance -= withdrawal.amount
        tenant.save()

        WalletTransaction.objects.create(
            tenant=tenant,
            transaction_type=WalletTransaction.DEBIT,
            reason=WalletTransaction.REASON_WITHDRAWAL,
            amount=withdrawal.amount,
            balance_after=tenant.wallet_balance,
            order_id=None,
            note=f"Withdrawal to {withdrawal.phone_number} ({withdrawal.provider})"
        )

        withdrawal.status = WithdrawalRequest.COMPLETED
        withdrawal.completed_at = timezone.now()
        withdrawal.iotec_txn_id = result.get('reference_id', '')
        withdrawal.save()

        print(f"✅ Withdrawal completed for {tenant.business_name}: UGX {withdrawal.amount}")
        return {'success': True}

    else:
        withdrawal.status = WithdrawalRequest.FAILED
        withdrawal.failure_reason = result.get('message', 'Disbursement failed.')
        withdrawal.save()

        print(f"❌ Withdrawal failed for {tenant.business_name}: {result.get('message')}")
        return {'success': False, 'message': result.get('message', 'Disbursement failed.')}
    





from superadmin.models import SMSBundle


def purchase_sms_bundle(tenant, bundle_id):
    """
    Purchases an SMS bundle for a tenant, deducting from their
    wallet balance and crediting sms_credits.
    """
    try:
        bundle = SMSBundle.objects.get(id=bundle_id, is_active=True)
    except SMSBundle.DoesNotExist:
        return {'success': False, 'message': 'SMS bundle not found or no longer available.'}

    if tenant.wallet_balance < bundle.price:
        return {
            'success': False,
            'message': f'Insufficient wallet balance. This bundle costs UGX {bundle.price}, your balance is UGX {tenant.wallet_balance}.'
        }

    # Debit wallet
    tenant.wallet_balance -= bundle.price
    tenant.sms_credits += bundle.sms_count
    tenant.save()

    # Ledger entry
    WalletTransaction.objects.create(
        tenant=tenant,
        transaction_type=WalletTransaction.DEBIT,
        reason=WalletTransaction.REASON_SMS_PURCHASE,
        amount=bundle.price,
        balance_after=tenant.wallet_balance,
        order_id=None,
        note=f"Purchased {bundle.name} bundle — {bundle.sms_count} SMS credits"
    )

    return {
        'success': True,
        'sms_credits': tenant.sms_credits,
        'bundle': bundle,
    }



# ── Role-based permission definitions ───────────────────────

OWNER_ONLY = {'wallet', 'withdrawals', 'create_withdrawal', 'sms_bundles', 'settings', 'team'}

MANAGER_BLOCKED = OWNER_ONLY  # Managers can't touch anything Owner-only

STAFF_ALLOWED = {
    'overview', 'active_sessions', 'customers', 'customer_detail',
    'vouchers', 'payments', 'feedback', 'equipment',
}


def get_user_role(user):
    """
    Returns the role string for a user's team membership, or None
    if they have no TeamMember record (e.g. legacy accounts, superusers).
    """
    from superadmin.models import TeamMember
    membership = TeamMember.objects.filter(user=user).first()
    return membership.role if membership else None


def can_access(user, section):
    """
    Checks whether a user's role permits access to a given dashboard section.
    'section' should match the keys used in OWNER_ONLY / STAFF_ALLOWED.
    Superusers always have full access.
    """
    if user.is_superuser:
        return True

    role = get_user_role(user)

    if role == 'owner':
        return True
    elif role == 'manager':
        return section not in MANAGER_BLOCKED
    elif role == 'staff':
        return section in STAFF_ALLOWED
    else:
        # No TeamMember record — legacy/unmigrated account.
        # Treat as Owner to avoid locking out existing tenant users
        # who were created before this feature existed.
        return True