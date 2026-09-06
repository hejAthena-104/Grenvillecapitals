from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Sum, Q, Count
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import random
import string

from accounts.models import User, Notification, EmailOTP
from transactions.models import (
    Transaction, Deposit, Withdrawal, Transfer, PaymentMethod,
    SwapRate, Swap, Beneficiary, ExternalTransfer,
)
from services.models import LoanApplication, GrantApplication, CardApplication, Card
from support.models import SupportTicket, EmailLog
from accounts.email_utils import EmailService


@login_required
def dashboard_index(request):
    """Main dashboard view with comprehensive statistics"""
    user = request.user

    # Get recent transactions
    recent_transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:5]

    # Get pending transactions count
    pending_deposits = Transaction.objects.filter(user=user, type='deposit', status='pending').count()
    pending_withdrawals = Transaction.objects.filter(user=user, type='withdrawal', status='pending').count()

    # Total earnings (bonuses + referrals)
    total_earnings = user.total_bonus + user.referral_bonus

    context = {
        'user': user,
        'total_earnings': total_earnings,
        'current_balance': user.balance,
        'btc_balance': user.btc_balance,
        'recent_transactions': recent_transactions,
        'pending_deposits': pending_deposits,
        'pending_withdrawals': pending_withdrawals,
        'referral_count': user.referrals.count(),
        'referral_code': user.referral_code,
        'cards': Card.objects.filter(user=user)[:3],
    }

    return render(request, 'dashboard/index.html', context)

@login_required
def deposits(request):
    """View deposit page with payment methods"""
    # Get active deposit payment methods
    payment_methods = PaymentMethod.objects.filter(
        is_active=True,
        type__in=['deposit', 'both']
    ).order_by('order')

    # Get user's deposit history
    user_deposits = Transaction.objects.filter(
        user=request.user,
        type='deposit'
    ).order_by('-created_at')

    context = {
        'user': request.user,
        'payment_methods': payment_methods,
        'deposits': user_deposits,
    }

    return render(request, 'dashboard/deposits.html', context)


@login_required
def new_deposit(request):
    """Process new deposit request"""
    if request.method == 'POST':
        amount = request.POST.get('amount', '0')
        payment_method_name = request.POST.get('payment_method')

        try:
            amount = Decimal(amount)
        except:
            messages.error(request, 'Invalid amount entered')
            return redirect('dashboard:deposits')

        try:
            # Get payment method
            payment_method = PaymentMethod.objects.get(
                name=payment_method_name,
                is_active=True,
                type__in=['deposit', 'both']
            )

            # Validate amount
            if amount < payment_method.min_amount:
                messages.error(request, f'Minimum deposit amount for {payment_method.name} is ${payment_method.min_amount}')
                return redirect('dashboard:deposits')

            if payment_method.max_amount and amount > payment_method.max_amount:
                messages.error(request, f'Maximum deposit amount for {payment_method.name} is ${payment_method.max_amount}')
                return redirect('dashboard:deposits')

            # Create deposit transaction
            transaction = Transaction.objects.create(
                user=request.user,
                type='deposit',
                amount=amount,
                payment_method=payment_method.name,
                status='pending',
                description=f'Deposit via {payment_method.name}'
            )

            # Create deposit details
            Deposit.objects.create(
                transaction=transaction
            )

            # Create notification
            Notification.objects.create(
                user=request.user,
                title='Deposit Request Created',
                message=f'Your deposit request of ${amount} via {payment_method.name} is pending',
                type='deposit'
            )

            messages.success(request, 'Deposit request created! Please proceed to payment.')
            return redirect('dashboard:payment', transaction_id=transaction.id)

        except PaymentMethod.DoesNotExist:
            messages.error(request, 'Invalid payment method')
            return redirect('dashboard:deposits')
        except Exception as e:
            messages.error(request, f'Error creating deposit: {str(e)}')
            return redirect('dashboard:deposits')

    return redirect('dashboard:deposits')


@login_required
def payment(request, transaction_id):
    """Show payment instructions and upload proof"""
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user, type='deposit')

    # Get payment method details
    try:
        payment_method = PaymentMethod.objects.get(name=transaction.payment_method, is_active=True)
    except PaymentMethod.DoesNotExist:
        messages.error(request, 'Payment method not found')
        return redirect('dashboard:deposits')

    if request.method == 'POST':
        # Handle proof upload
        if 'proof_image' in request.FILES:
            proof_image = request.FILES['proof_image']
            deposit = transaction.deposit_details
            deposit.proof_image = proof_image
            deposit.save()

            messages.success(request, 'Payment proof uploaded successfully! Your deposit will be reviewed.')
            return redirect('dashboard:deposits')

    context = {
        'user': request.user,
        'transaction': transaction,
        'payment_method': payment_method,
    }

    return render(request, 'dashboard/payment.html', context)


@login_required
def withdrawals(request):
    """View withdrawal methods selection page"""
    # Get active withdrawal payment methods
    payment_methods = PaymentMethod.objects.filter(
        is_active=True,
        type__in=['withdrawal', 'both']
    ).order_by('order')

    # Get user's withdrawal history
    user_withdrawals = Transaction.objects.filter(
        user=request.user,
        type='withdrawal'
    ).order_by('-created_at')

    context = {
        'user': request.user,
        'payment_methods': payment_methods,
        'withdrawals': user_withdrawals,
    }

    return render(request, 'dashboard/withdrawals.html', context)


@login_required
def select_withdrawal_method(request):
    """Select withdrawal method and proceed to withdrawal form"""
    if request.method == 'POST':
        method = request.POST.get('method')

        try:
            # Verify payment method exists
            payment_method = PaymentMethod.objects.get(
                name=method,
                is_active=True,
                type__in=['withdrawal', 'both']
            )

            # Store in session
            request.session['withdrawal_method'] = method
            return redirect('dashboard:withdraw_funds')

        except PaymentMethod.DoesNotExist:
            messages.error(request, 'Invalid withdrawal method')
            return redirect('dashboard:withdrawals')

    return redirect('dashboard:withdrawals')


@login_required
def withdraw_funds(request):
    """Withdraw funds form"""
    # Get selected withdrawal method from session
    withdrawal_method_name = request.session.get('withdrawal_method')

    if not withdrawal_method_name:
        messages.error(request, 'Please select a withdrawal method first')
        return redirect('dashboard:withdrawals')

    try:
        withdrawal_method = PaymentMethod.objects.get(
            name=withdrawal_method_name,
            is_active=True,
            type__in=['withdrawal', 'both']
        )
    except PaymentMethod.DoesNotExist:
        messages.error(request, 'Invalid withdrawal method')
        return redirect('dashboard:withdrawals')

    if request.method == 'POST':
        # The emailed code is the second factor: verify it before anything else.
        submitted = ''.join(request.POST.get('otp', '').split())
        if not submitted:
            messages.error(request, 'Enter the 6-digit code we emailed you.')
            return redirect('dashboard:withdraw_funds')

        otp = (EmailOTP.objects
               .filter(user=request.user, purpose='withdrawal', is_used=False)
               .order_by('-created_at').first())
        if otp is None:
            messages.error(request, 'Request a withdrawal code first.')
            return redirect('dashboard:withdraw_funds')

        ok, reason = otp.verify(submitted)
        if not ok:
            messages.error(request, reason)
            return redirect('dashboard:withdraw_funds')

        amount = request.POST.get('amount', '0')

        try:
            amount = Decimal(amount)
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, 'Invalid amount entered')
            return redirect('dashboard:withdraw_funds')

        # Validate amount
        if amount < withdrawal_method.min_amount:
            messages.error(request, f'Minimum withdrawal amount is ${withdrawal_method.min_amount}')
            return redirect('dashboard:withdraw_funds')

        if withdrawal_method.max_amount and amount > withdrawal_method.max_amount:
            messages.error(request, f'Maximum withdrawal amount is ${withdrawal_method.max_amount}')
            return redirect('dashboard:withdraw_funds')

        if amount > request.user.balance:
            messages.error(request, 'Insufficient balance')
            return redirect('dashboard:withdraw_funds')

        # Get withdrawal address based on method
        withdrawal_address = ''
        if withdrawal_method.name.upper() == 'USDT':
            withdrawal_address = request.user.usdt_address
        elif withdrawal_method.name.upper() == 'BITCOIN':
            withdrawal_address = request.user.btc_address
        elif withdrawal_method.name.upper() == 'ETHEREUM':
            withdrawal_address = request.user.eth_address
        elif withdrawal_method.name.upper() == 'LITECOIN':
            withdrawal_address = request.user.ltc_address

        if not withdrawal_address:
            messages.error(request, f'Please add your {withdrawal_method.name} address in account settings first')
            return redirect('dashboard:account_settings')

        # Create withdrawal transaction
        transaction = Transaction.objects.create(
            user=request.user,
            type='withdrawal',
            amount=amount,
            payment_method=withdrawal_method.name,
            status='pending',
            description=f'Withdrawal request via {withdrawal_method.name}'
        )

        # Create withdrawal details
        Withdrawal.objects.create(
            transaction=transaction,
            withdrawal_address=withdrawal_address,
            withdrawal_method=withdrawal_method.name
        )

        # The OTP was consumed by verify(); clear the legacy field too.
        if request.user.withdrawal_otp:
            request.user.withdrawal_otp = None
            request.user.save(update_fields=['withdrawal_otp'])

        # Clear session
        del request.session['withdrawal_method']

        # Create notification
        Notification.objects.create(
            user=request.user,
            title='Withdrawal Request Submitted',
            message=f'Your withdrawal request of ${amount} via {withdrawal_method.name} is being processed',
            type='withdrawal'
        )

        messages.success(request, 'Withdrawal request submitted successfully! It will be processed within 24-48 hours.')
        return redirect('dashboard:withdrawals')

    context = {
        'user': request.user,
        'withdrawal_method': withdrawal_method,
    }

    return render(request, 'dashboard/withdraw-funds.html', context)


@login_required
def request_otp(request):
    """Email a withdrawal authorisation code.

    The code is never rendered back to the browser: possession of the mailbox is
    the whole point of the second factor.
    """
    last = (EmailOTP.objects.filter(user=request.user, purpose='withdrawal')
            .order_by('-created_at').first())
    if last and (timezone.now() - last.created_at).total_seconds() < 60:
        wait = 60 - int((timezone.now() - last.created_at).total_seconds())
        messages.info(request, f'Please wait {wait}s before requesting another code.')
        return redirect('dashboard:withdraw_funds')

    otp = EmailOTP.issue(request.user, purpose='withdrawal')
    if EmailService.send_otp_email(request.user, otp.code, 'withdrawal'):
        messages.success(request, f'We sent a 6-digit code to {request.user.email}.')
    else:
        messages.error(request, 'We could not send your code. Please try again shortly.')

    return redirect('dashboard:withdraw_funds')


@login_required
def account_history(request):
    """View all account transactions"""
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')

    context = {
        'user': request.user,
        'transactions': transactions,
    }

    return render(request, 'dashboard/accounthistory.html', context)


@login_required
def withdrawal_history(request):
    """View withdrawal history"""
    withdrawals = Transaction.objects.filter(
        user=request.user,
        type='withdrawal'
    ).order_by('-created_at')

    context = {
        'user': request.user,
        'withdrawals': withdrawals,
    }

    return render(request, 'dashboard/withdrawal-history.html', context)


@login_required
def other_history(request):
    """View other transactions (bonuses, referrals, transfers)"""
    others = Transaction.objects.filter(
        user=request.user,
        type__in=['bonus', 'referral', 'transfer']
    ).order_by('-created_at')

    context = {
        'user': request.user,
        'transactions': others,
    }

    return render(request, 'dashboard/other-history.html', context)


@login_required
def refer_user(request):
    """Referral page"""
    referrals = User.objects.filter(referred_by=request.user).order_by('-created_at')

    context = {
        'user': request.user,
        'referrals': referrals,
        'referral_link': f"{request.scheme}://{request.get_host()}/auth/register/?ref={request.user.referral_code}",
    }

    return render(request, 'dashboard/referuser.html', context)


@login_required
def account_settings(request):
    """Account settings page with multiple update sections"""

    # Handle different form submissions
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            # Update basic profile info
            name = request.POST.get('name', '')
            name_parts = name.split(' ', 1)
            request.user.first_name = name_parts[0] if name_parts else ''
            request.user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            request.user.phone = request.POST.get('phone', '')
            request.user.country = request.POST.get('country', '')
            request.user.save()
            messages.success(request, 'Profile updated successfully!')

        elif action == 'update_avatar':
            # Update profile picture
            if 'photo' in request.FILES:
                request.user.avatar = request.FILES['photo']
                request.user.save()
                messages.success(request, 'Profile picture updated!')

        elif action == 'update_password':
            # Update password
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('password')
            confirm_password = request.POST.get('password_confirmation')

            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect!')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match!')
            elif len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters!')
            else:
                request.user.set_password(new_password)
                request.user.save()
                # Re-authenticate user
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password updated successfully!')

        elif action == 'update_payment_methods':
            # Update payment method addresses
            request.user.bank_name = request.POST.get('bankName', '')
            request.user.account_name = request.POST.get('accountName', '')
            request.user.account_number = request.POST.get('accountNumber', '')
            request.user.swift_code = request.POST.get('swiftCode', '')
            request.user.btc_address = request.POST.get('btcAddress', '')
            request.user.eth_address = request.POST.get('ethAddress', '')
            request.user.ltc_address = request.POST.get('ltcAddress', '')
            request.user.usdt_address = request.POST.get('usdtAddress', '')
            request.user.save()
            messages.success(request, 'Payment methods updated successfully!')

        elif action == 'update_email_preferences':
            # Update email notification preferences
            request.user.email_on_withdrawal = request.POST.get('emailOnWithdrawal') == 'Yes'
            request.user.email_on_roi = request.POST.get('emailOnRoi') == 'Yes'
            request.user.email_on_expiration = request.POST.get('emailOnExpiration') == 'Yes'
            request.user.save()
            messages.success(request, 'Email preferences updated successfully!')

        return redirect('dashboard:account_settings')

    context = {
        'user': request.user,
    }

    return render(request, 'dashboard/account-settings.html', context)


@login_required
def manage_account_security(request):
    """Account security settings page"""
    login_history = request.user.login_history.all().order_by('-login_time')[:10]

    context = {
        'user': request.user,
        'login_history': login_history,
    }

    return render(request, 'dashboard/manage-account-security.html', context)


@login_required
def support(request):
    """Support/Help page"""
    if request.method == 'POST':
        subject = request.POST.get('subject', '')
        category = request.POST.get('category', 'general')
        message = request.POST.get('message', '')

        if subject and message:
            ticket = SupportTicket.objects.create(
                user=request.user,
                subject=subject,
                category=category,
                message=message
            )

            # Create notification
            Notification.objects.create(
                user=request.user,
                title='Support Ticket Created',
                message=f'Your support ticket #{ticket.ticket_number} has been created',
                type='system'
            )

            messages.success(request, f'Support ticket #{ticket.ticket_number} created successfully!')
        else:
            messages.error(request, 'Please fill in all required fields')

        return redirect('dashboard:support')

    # Get user's tickets
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')

    context = {
        'user': request.user,
        'tickets': tickets,
    }
    return render(request, 'dashboard/support.html', context)


@login_required
def transfer_funds(request):
    """Transfer funds to another user"""
    if request.method == 'POST':
        try:
            recipient_username = request.POST.get('recipient_username', '').strip()
            amount = request.POST.get('amount', '0')
            description = request.POST.get('description', '')

            # Validate recipient username
            if not recipient_username:
                messages.error(request, 'Please enter a recipient username')
                return redirect('dashboard:transfer_funds')

            # Validate and parse amount
            try:
                amount = Decimal(amount)
            except (ValueError, TypeError, Decimal.InvalidOperation):
                messages.error(request, 'Invalid amount entered')
                return redirect('dashboard:transfer_funds')

            # Validate amount
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount')
                return redirect('dashboard:transfer_funds')

            if amount > request.user.balance:
                messages.error(request, f'Insufficient balance. Your balance is ${request.user.balance}')
                return redirect('dashboard:transfer_funds')

            # Find recipient
            try:
                recipient = User.objects.get(username=recipient_username)
            except User.DoesNotExist:
                messages.error(request, f'Recipient user "{recipient_username}" not found')
                return redirect('dashboard:transfer_funds')

            # Can't transfer to self
            if recipient.id == request.user.id:
                messages.error(request, 'Cannot transfer to yourself')
                return redirect('dashboard:transfer_funds')

            # Create transfer
            transfer = Transfer.objects.create(
                sender=request.user,
                recipient=recipient,
                amount=amount,
                description=description,
                fee_amount=Decimal('0.00'),  # No fee for now
                status='pending'
            )

            # Complete transfer immediately
            if transfer.complete():
                # Create notifications
                try:
                    Notification.objects.create(
                        user=request.user,
                        title='Transfer Sent',
                        message=f'You transferred ${amount} to {recipient.username}',
                        type='system'
                    )

                    Notification.objects.create(
                        user=recipient,
                        title='Transfer Received',
                        message=f'You received ${amount} from {request.user.username}',
                        type='system'
                    )
                except Exception as notification_error:
                    # Don't fail the transfer if notification creation fails
                    print(f"Warning: Failed to create notifications: {notification_error}")

                messages.success(request, f'Successfully transferred ${amount} to {recipient.username}')
            else:
                messages.error(request, f'Transfer failed. Status: {transfer.status}. Please try again.')

        except Exception as e:
            # Catch any unexpected errors
            messages.error(request, f'An error occurred during the transfer: {str(e)}')
            print(f"Transfer error: {e}")
            import traceback
            traceback.print_exc()

        return redirect('dashboard:transfer_funds')

    # Get user's transfer history
    sent_transfers = Transfer.objects.filter(sender=request.user).order_by('-created_at')[:10]
    received_transfers = Transfer.objects.filter(recipient=request.user).order_by('-created_at')[:10]

    context = {
        'user': request.user,
        'sent_transfers': sent_transfers,
        'received_transfers': received_transfers,
    }
    return render(request, 'dashboard/transfer-funds.html', context)


@login_required
def send_email(request):
    """Admin page to send emails to customers"""
    # Check if user is staff/admin
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page')
        return redirect('dashboard:index')

    if request.method == 'POST':
        recipient_email = request.POST.get('recipient')
        template = request.POST.get('template')
        subject = request.POST.get('subject')
        content = request.POST.get('content')

        # Get recipient user
        try:
            recipient_user = User.objects.get(email=recipient_email)
        except User.DoesNotExist:
            messages.error(request, 'Recipient not found')
            return redirect('dashboard:send_email')

        # Prepare context for email
        context = {
            'first_name': recipient_user.first_name or recipient_user.username,
            'email_subject': subject,
            'email_content': content,
            'dashboard_url': f"{request.scheme}://{request.get_host()}/dashboard/",
        }

        # Send email
        try:
            success = EmailService.send_email(
                to_email=recipient_email,
                subject=subject,
                template_name=template,
                context=context
            )

            # Log the email
            email_log = EmailLog.objects.create(
                recipient=recipient_email,
                recipient_name=recipient_user.get_full_name(),
                subject=subject,
                template=template,
                content=content,
                sent=success,
                sent_by=request.user
            )

            if success:
                messages.success(request, f'Email sent successfully to {recipient_email}!')
            else:
                messages.error(request, f'Failed to send email to {recipient_email}')
                email_log.error_message = 'Email sending failed'
                email_log.save()

        except Exception as e:
            messages.error(request, f'Error sending email: {str(e)}')
            EmailLog.objects.create(
                recipient=recipient_email,
                recipient_name=recipient_user.get_full_name(),
                subject=subject,
                template=template,
                content=content,
                sent=False,
                error_message=str(e),
                sent_by=request.user
            )

        return redirect('dashboard:send_email')

    # Get all users for dropdown
    users = User.objects.filter(is_active=True).order_by('email')

    # Get recent emails sent
    recent_emails = EmailLog.objects.all()[:10]

    context = {
        'user': request.user,
        'users': users,
        'recent_emails': recent_emails,
    }

    return render(request, 'dashboard/send-email.html', context)


# ============================================================
#  NEW FEATURES: Swap · Transfers · Beneficiaries · Loans · Grants · Cards · PIN
# ============================================================

def _to_decimal(value):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


@login_required
def swap(request):
    """Instant USD <-> BTC swap at the admin-set rate."""
    user = request.user
    rate = SwapRate.current()
    price = rate.btc_usd_price

    if request.method == 'POST':
        direction = request.POST.get('direction', 'usd_to_btc')
        amount = _to_decimal(request.POST.get('amount'))
        if amount is None or amount <= 0:
            messages.error(request, 'Enter a valid amount.')
            return redirect('dashboard:swap')

        # Atomic read-check-mutate-save with a row lock to prevent TOCTOU double-spend.
        with transaction.atomic():
            locked = User.objects.select_for_update().get(pk=user.pk)
            if direction == 'usd_to_btc':
                if locked.balance < amount:
                    messages.error(request, 'Insufficient USD balance.')
                    return redirect('dashboard:swap')
                btc = (amount / price).quantize(Decimal('0.00000001'))
                locked.balance -= amount
                locked.btc_balance += btc
                locked.save()
                Swap.objects.create(user=locked, direction='usd_to_btc', from_amount=amount,
                                    to_amount=btc, rate_used=price)
                Transaction.objects.create(user=locked, type='swap', amount=amount, status='approved',
                                           description=f'Swapped ${amount} USD to {btc} BTC')
                messages.success(request, f'Swapped ${amount} to {btc} BTC.')
            else:  # btc_to_usd
                if locked.btc_balance < amount:
                    messages.error(request, 'Insufficient BTC balance.')
                    return redirect('dashboard:swap')
                usd = (amount * price).quantize(Decimal('0.01'))
                locked.btc_balance -= amount
                locked.balance += usd
                locked.save()
                Swap.objects.create(user=locked, direction='btc_to_usd', from_amount=amount,
                                    to_amount=usd, rate_used=price)
                Transaction.objects.create(user=locked, type='swap', amount=usd, status='approved',
                                           description=f'Swapped {amount} BTC to ${usd} USD')
                messages.success(request, f'Swapped {amount} BTC to ${usd}.')
        return redirect('dashboard:swap')

    context = {
        'user': user,
        'btc_usd_price': price,
        'usd_balance': user.balance,
        'btc_balance': user.btc_balance,
        'swaps': Swap.objects.filter(user=user)[:10],
    }
    return render(request, 'dashboard/swap.html', context)


@login_required
def transfers(request):
    """Transfers hub: tabbed Local / International + saved beneficiaries."""
    user = request.user
    context = {
        'user': user,
        'usd_balance': user.balance,
        'beneficiaries': Beneficiary.objects.filter(user=user),
        'has_pin': user.has_transaction_pin,
        'recent_transfers': Transaction.objects.filter(user=user, type='withdrawal').order_by('-created_at')[:10],
    }
    return render(request, 'dashboard/transfer.html', context)


def _create_external_transfer(request, transfer_type, method, data):
    """Shared: validate PIN + balance, create pending Transaction + ExternalTransfer."""
    user = request.user
    amount = _to_decimal(data.get('amount'))
    if amount is None or amount <= 0:
        messages.error(request, 'Enter a valid amount.')
        return False
    if not user.has_transaction_pin:
        messages.error(request, 'Please set a Transaction PIN in Account Settings first.')
        return False
    if not user.check_transaction_pin(data.get('transaction_pin', '')):
        messages.error(request, 'Invalid Transaction PIN.')
        return False
    if user.balance < amount:
        messages.error(request, 'Insufficient balance for this transfer.')
        return False

    txn = Transaction.objects.create(
        user=user, type='withdrawal', amount=amount, status='pending',
        payment_method='bank_transfer' if method in ('local_bank', 'wire') else method,
        description=data.get('description', '') or f'{transfer_type.title()} transfer',
    )
    bene = None
    bid = data.get('beneficiary_id')
    if bid:
        bene = Beneficiary.objects.filter(user=user, pk=bid).first()
    ExternalTransfer.objects.create(
        transaction=txn, beneficiary=bene, transfer_type=transfer_type, method=method,
        account_holder_name=data.get('account_holder_name', ''),
        account_number=data.get('account_number', ''),
        bank_name=data.get('bank_name', ''),
        account_type=data.get('account_type', ''),
        routing_number=data.get('routing_number', ''),
        swift_code=data.get('swift_code', ''),
        country=data.get('country', ''),
        extra={k: v for k, v in data.items() if k in ('email', 'tag', 'wallet_address', 'phone')},
    )
    Notification.objects.create(user=user, type='withdrawal', title='Transfer Submitted',
                                message=f'Your {transfer_type} transfer of ${amount} is pending review.')
    # Optionally save as beneficiary
    if data.get('save_beneficiary') and not bene:
        Beneficiary.objects.create(
            user=user, nickname=data.get('account_holder_name') or 'Beneficiary',
            type='local_bank' if transfer_type == 'local' else method,
            account_holder_name=data.get('account_holder_name', ''),
            account_number=data.get('account_number', ''), bank_name=data.get('bank_name', ''),
            account_type=data.get('account_type', ''), routing_number=data.get('routing_number', ''),
            swift_code=data.get('swift_code', ''), country=data.get('country', ''),
        )
    messages.success(request, f'{transfer_type.title()} transfer of ${amount} submitted for review.')
    return True


@login_required
def local_transfer(request):
    if request.method == 'POST':
        _create_external_transfer(request, 'local', 'local_bank', request.POST)
    return redirect('dashboard:transfers')


@login_required
def international_transfer(request):
    if request.method == 'POST':
        method = request.POST.get('method', 'wire')
        _create_external_transfer(request, 'international', method, request.POST)
    return redirect('dashboard:transfers')


@login_required
def save_beneficiary(request):
    if request.method == 'POST':
        Beneficiary.objects.create(
            user=request.user,
            nickname=request.POST.get('nickname') or request.POST.get('account_holder_name') or 'Beneficiary',
            type=request.POST.get('type', 'local_bank'),
            account_holder_name=request.POST.get('account_holder_name', ''),
            account_number=request.POST.get('account_number', ''),
            bank_name=request.POST.get('bank_name', ''),
            account_type=request.POST.get('account_type', ''),
            routing_number=request.POST.get('routing_number', ''),
            swift_code=request.POST.get('swift_code', ''),
            country=request.POST.get('country', ''),
        )
        messages.success(request, 'Beneficiary saved.')
    return redirect('dashboard:transfers')


@login_required
@require_POST
def delete_beneficiary(request, pk):
    Beneficiary.objects.filter(user=request.user, pk=pk).delete()
    messages.success(request, 'Beneficiary removed.')
    return redirect('dashboard:transfers')


@login_required
def loans(request):
    user = request.user
    if request.method == 'POST':
        amount = _to_decimal(request.POST.get('amount'))
        if amount is None or amount <= 0:
            messages.error(request, 'Enter a valid loan amount.')
            return redirect('dashboard:loans')
        LoanApplication.objects.create(
            user=user, amount=amount,
            purpose=request.POST.get('purpose', 'personal'),
            term_months=int(request.POST.get('term_months') or 12),
            monthly_income=_to_decimal(request.POST.get('monthly_income')) or 0,
            employment_status=request.POST.get('employment_status', ''),
            details=request.POST.get('details', ''),
        )
        messages.success(request, 'Loan application submitted for review.')
        return redirect('dashboard:loans')
    context = {'user': user, 'applications': LoanApplication.objects.filter(user=user)}
    return render(request, 'dashboard/loans.html', context)


@login_required
def grants(request):
    user = request.user
    if request.method == 'POST':
        amount = _to_decimal(request.POST.get('amount'))
        if amount is None or amount <= 0:
            messages.error(request, 'Enter a valid grant amount.')
            return redirect('dashboard:grants')
        GrantApplication.objects.create(
            user=user, amount=amount,
            applicant_type=request.POST.get('applicant_type', 'individual'),
            purpose=request.POST.get('purpose', ''),
            details=request.POST.get('details', ''),
            full_name=request.POST.get('full_name', ''),
            business_name=request.POST.get('business_name', ''),
            registration_number=request.POST.get('registration_number', ''),
            business_type=request.POST.get('business_type', ''),
        )
        messages.success(request, 'Grant application submitted for review.')
        return redirect('dashboard:grants')
    context = {'user': user, 'applications': GrantApplication.objects.filter(user=user)}
    return render(request, 'dashboard/grants.html', context)


@login_required
def cards(request):
    user = request.user
    if request.method == 'POST':
        CardApplication.objects.create(
            user=user,
            card_type=request.POST.get('card_type', 'virtual_debit'),
            card_brand=request.POST.get('card_brand', 'Visa'),
            full_name=request.POST.get('full_name', '') or user.get_full_name(),
            delivery_address=request.POST.get('delivery_address', ''),
        )
        messages.success(request, 'Card application submitted for review.')
        return redirect('dashboard:cards')
    context = {
        'user': user,
        'applications': CardApplication.objects.filter(user=user),
        'cards': Card.objects.filter(user=user),
    }
    return render(request, 'dashboard/cards.html', context)


@login_required
def set_transaction_pin(request):
    if request.method == 'POST':
        pin = (request.POST.get('pin') or '').strip()
        confirm = (request.POST.get('confirm_pin') or '').strip()
        if not pin.isdigit() or not (4 <= len(pin) <= 6):
            messages.error(request, 'PIN must be 4-6 digits.')
        elif pin != confirm:
            messages.error(request, 'PINs do not match.')
        else:
            request.user.set_transaction_pin(pin)
            request.user.save()
            messages.success(request, 'Transaction PIN saved.')
    return redirect('dashboard:account_settings')
