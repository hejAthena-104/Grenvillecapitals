"""Seed a realistic, established customer so the UI can be reviewed with real depth.

Creates ~18 months of history: salary and client deposits, rent and card
withdrawals, outbound transfers to saved recipients, plus a completed KYC
profile and issued cards.

The balance is DERIVED from the ledger — income minus expenses — so the
dashboard's headline figure, the month KPIs and the transaction list all
reconcile. Nothing is invented independently of the rows.

This is demo data. It is namespaced to one username and `--reset` removes it.
"""
import calendar
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.models import User, KYCProfile
from services.models import Card
from transactions.models import (Transaction, Deposit, Withdrawal,
                                 Beneficiary, ExternalTransfer)

INCOME_TYPES = ('deposit', 'bonus', 'referral', 'loan', 'grant')

RECIPIENTS = [
    ('Marcus Kane',    'Marcus',    'Chase',            '3041', 'local_bank'),
    ('Jade Okoro',     'Jade',      'Wells Fargo',      '8827', 'local_bank'),
    ('Halden Estates', 'Landlord',  'Citibank',         '5510', 'local_bank'),
    ('Nkem Adeyemi',   'Nkem',      'Access Bank',      '9902', 'wire'),
    ('Sofia Ruiz',     'Sofia',     'Banco Santander',  '4416', 'wire'),
]

DEPOSIT_NOTES = [
    'Monthly retainer', 'Client settlement', 'Consulting invoice',
    'Quarterly distribution', 'Contract milestone', 'Advisory fee',
]
WITHDRAWAL_NOTES = [
    'Office rent', 'Payroll run', 'Equipment purchase',
    'Insurance premium', 'Contractor payment', 'Travel expenses',
]


class Command(BaseCommand):
    help = 'Seed a demo customer with a deep transaction history.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='willestes4')
        parser.add_argument('--password', default='willestes')
        parser.add_argument('--months', type=int, default=18)
        parser.add_argument('--reset', action='store_true',
                            help='Delete the user and all their data first.')

    @db_transaction.atomic
    def handle(self, *args, **o):
        rng = random.Random(4)               # deterministic: reruns give the same history
        now = timezone.now()
        username = o['username']

        if o['reset']:
            existing = User.objects.filter(username=username).first()
            if existing:
                existing.delete()
                self.stdout.write(f'  removed existing {username!r}')

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{username}@example.com',
                      'first_name': 'Will', 'last_name': 'Estes'},
        )
        user.set_password(o['password'])
        user.first_name, user.last_name = 'Will', 'Estes'
        user.email = f'{username}@example.com'
        user.phone = '+1 (312) 555-0148'
        user.country = 'United States'
        user.is_verified = True
        user.is_staff = user.is_superuser = False
        user.bank_name = 'Grenville Capitals'
        user.account_name = 'Will Estes'
        user.account_number = '4417820031'
        user.set_transaction_pin('1234')
        user.save()

        # --- KYC, so the profile screens render fully populated ---
        kyc, _ = KYCProfile.objects.get_or_create(user=user)
        kyc.middle_name = 'Andrew'
        kyc.date_of_birth = (now - timedelta(days=365 * 41)).date()
        kyc.gender = 'male'
        kyc.country_of_citizenship = 'United States'
        kyc.citizenship_status = 'Citizen'
        kyc.tax_id_type, kyc.tax_id = 'ssn', '***-**-4182'
        kyc.address, kyc.city = '1140 North Wells Street', 'Chicago'
        kyc.state, kyc.zipcode, kyc.country = 'Illinois', '60610', 'United States'
        kyc.employment_status = 'self_employed'
        kyc.employer, kyc.job_title = 'Estes Advisory Group', 'Managing Partner'
        kyc.years_employed, kyc.annual_income = '10+', '250000+'
        kyc.source_of_income = 'Business income'
        kyc.id_type, kyc.id_number, kyc.id_state = 'drivers_license', 'E512-4471-8820', 'Illinois'
        kyc.id_issue_date = (now - timedelta(days=900)).date()
        kyc.id_expiry_date = (now + timedelta(days=1200)).date()
        kyc.security_question = 'What was the name of your first school?'
        kyc.security_answer = 'Lakeview'
        kyc.status = 'approved'
        kyc.submitted_at = now - timedelta(days=o['months'] * 30 - 3)
        kyc.processed_at = kyc.submitted_at + timedelta(days=1)
        kyc.save()

        # --- saved recipients ---
        Beneficiary.objects.filter(user=user).delete()
        benes = [Beneficiary.objects.create(
            user=user, nickname=nick, account_holder_name=holder, bank_name=bank,
            account_number='00' + last4 * 2, type=kind, country='United States',
            routing_number='07100' + last4,   # ABA numbers are 9 digits swift_code='GRNVUS33' if kind == 'wire' else '',
        ) for holder, nick, bank, last4, kind in RECIPIENTS]

        # --- cards ---
        Card.objects.filter(user=user).delete()
        for brand, ctype, last4, bal in (('Visa', 'virtual_debit', '4471', '4200.00'),
                                         ('Mastercard', 'physical_debit', '8830', '1150.00')):
            Card.objects.create(
                user=user, card_brand=brand, card_type=ctype,
                card_holder='WILL ESTES', card_number='4' + last4 * 3 + last4,
                expiry='08/29', cvv='***', status='active', balance=Decimal(bal))

        # --- the ledger ---
        Transaction.objects.filter(user=user).delete()
        rows, income, expense = [], Decimal('0'), Decimal('0')

        def add(kind, amount, when, note, method=None, status='approved'):
            nonlocal income, expense
            # A ledger must never contain a future-dated row. The month walk
            # works in 30-day steps, so the newest month can overshoot today.
            if when > now:
                return None
            amount = Decimal(amount).quantize(Decimal('0.01'))
            t = Transaction.objects.create(
                user=user, type=kind, amount=amount, status=status,
                payment_method=method, description=note)
            Transaction.objects.filter(pk=t.pk).update(created_at=when, updated_at=when,
                                                       processed_at=when if status == 'approved' else None)
            t.refresh_from_db()
            if status == 'approved':
                if kind in INCOME_TYPES:
                    income += amount
                elif kind == 'withdrawal':
                    expense += amount
            rows.append(t)
            return t

        def month_start(offset):
            """First day of the month `offset` months before this one."""
            y, mo = now.year, now.month - offset
            while mo <= 0:
                mo += 12
                y -= 1
            return now.replace(year=y, month=mo, day=1, hour=0, minute=0,
                               second=0, microsecond=0)

        def day_in(ms, lo, hi, hour):
            """A datetime inside that calendar month, never past today."""
            last = calendar.monthrange(ms.year, ms.month)[1]
            if ms.year == now.year and ms.month == now.month:
                last = min(last, now.day)
            if lo > last:
                return None
            return ms.replace(day=rng.randint(lo, min(hi, last)),
                              hour=hour, minute=rng.randint(0, 59))

        for m in range(o['months'], -1, -1):
            ms = month_start(m)

            # income: a retainer plus one or two client payments
            when = day_in(ms, 1, 3, 9)
            if when:
                add('deposit', rng.uniform(48000, 72000), when,
                    'Monthly retainer', 'bank_transfer')
            for _ in range(rng.randint(1, 2)):
                when = day_in(ms, 4, 26, rng.randint(9, 17))
                if when:
                    add('deposit', rng.uniform(9000, 41000), when,
                        rng.choice(DEPOSIT_NOTES), 'bank_transfer')

            # outgoings: rent, plus a few operating costs
            for _ in range(rng.randint(2, 4)):
                when = day_in(ms, 2, 27, rng.randint(8, 19))
                if not when:
                    continue
                txn = add('withdrawal', rng.uniform(2400, 17000), when,
                          rng.choice(WITHDRAWAL_NOTES), 'bank_transfer')
                if txn is None:
                    continue
                b = rng.choice(benes)
                ExternalTransfer.objects.create(
                    transaction=txn, beneficiary=b,
                    transfer_type='local' if b.type == 'local_bank' else 'international',
                    method=b.type, fee=Decimal('0.00'),
                    account_holder_name=b.account_holder_name, account_number=b.account_number,
                    bank_name=b.bank_name, routing_number=b.routing_number,
                    swift_code=b.swift_code, country=b.country)

            # the occasional credit
            if rng.random() < 0.22:
                when = day_in(ms, 5, 20, 12)
                if when:
                    add('bonus', rng.uniform(400, 2200), when, 'Loyalty bonus')
            if rng.random() < 0.12:
                when = day_in(ms, 5, 20, 12)
                if when:
                    add('referral', rng.uniform(150, 600), when, 'Referral bonus')

        # a couple in flight, so the status styling is visible
        add('deposit', 26500, now - timedelta(hours=6), 'Client settlement', 'bank_transfer', status='pending')
        pend = add('withdrawal', 7400, now - timedelta(hours=2), 'Contractor payment',
                   'bank_transfer', status='pending')
        ExternalTransfer.objects.create(
            transaction=pend, beneficiary=benes[0], transfer_type='local', method='local_bank',
            fee=Decimal('0.00'), account_holder_name=benes[0].account_holder_name,
            account_number=benes[0].account_number, bank_name=benes[0].bank_name,
            routing_number=benes[0].routing_number, country='United States')

        # detail rows for the deposit/withdrawal screens
        for t in rows:
            if t.type == 'deposit':
                Deposit.objects.get_or_create(transaction=t)
            elif t.type == 'withdrawal' and not hasattr(t, 'external_transfer'):
                Withdrawal.objects.get_or_create(
                    transaction=t, defaults={'withdrawal_address': user.account_number,
                                             'withdrawal_method': 'Bank Transfer'})

        # The headline balance is the ledger, not a number typed in beside it.
        user.balance = (income - expense).quantize(Decimal('0.01'))
        user.save(update_fields=['balance'])

        self.stdout.write(self.style.SUCCESS(
            f'\n  {username}  ({"created" if created else "updated"})'))
        self.stdout.write(f'  password        {o["password"]}   PIN 1234')
        self.stdout.write(f'  transactions    {Transaction.objects.filter(user=user).count()}')
        self.stdout.write(f'  income (all)    ${income:,.2f}')
        self.stdout.write(f'  expense (all)   ${expense:,.2f}')
        self.stdout.write(f'  balance         ${user.balance:,.2f}')
        self.stdout.write(f'  this month  in  ${user.income_this_month:,.2f}')
        self.stdout.write(f'  this month  out ${user.expense_this_month:,.2f}')
        self.stdout.write(f'  recipients {len(benes)}  cards {user.cards.count()}  kyc {kyc.status}')
