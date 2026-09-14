"""End-to-end checks for the crypto removal + deposit-request + bank-search work.

Runs on SQLite with `python manage.py test dashboard`.
"""
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import EmailOTP, User
from transactions import models as tmodels
from transactions.models import PaymentMethod, Transaction, Withdrawal

# The production static storage hashes filenames from a manifest that only
# exists after collectstatic. Tests render templates without that step, so use
# the plain storage here.
_PLAIN_STATIC = override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')


class CryptoRemovalTests(TestCase):
    def test_crypto_models_are_gone(self):
        self.assertFalse(hasattr(tmodels, 'Swap'))
        self.assertFalse(hasattr(tmodels, 'SwapRate'))

    def test_user_has_no_crypto_fields(self):
        field_names = {f.name for f in User._meta.get_fields()}
        for gone in ('btc_balance', 'btc_address', 'eth_address',
                     'ltc_address', 'usdt_address', 'total_profit',
                     'email_on_roi', 'email_on_expiration'):
            self.assertNotIn(gone, field_names)

    def test_transaction_choices_have_no_crypto(self):
        type_keys = dict(Transaction.TYPE_CHOICES)
        self.assertNotIn('swap', type_keys)
        self.assertNotIn('profit', type_keys)
        method_keys = dict(Transaction.PAYMENT_METHOD_CHOICES)
        for crypto in ('bitcoin', 'ethereum', 'usdt'):
            self.assertNotIn(crypto, method_keys)

    def test_feature_flags_has_no_swap(self):
        field_names = {f.name for f in tmodels.FeatureFlags._meta.get_fields()}
        self.assertNotIn('swap_enabled', field_names)

    def test_seed_basics_leaves_only_bank_transfer(self):
        # Pretend a legacy crypto method still exists, as production might.
        PaymentMethod.objects.create(name='Bitcoin', type='both')
        call_command('seed_basics')
        names = set(PaymentMethod.objects.values_list('name', flat=True))
        self.assertEqual(names, {'Bank Transfer'})


@_PLAIN_STATIC
class DepositRequestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='depositor', password='pw12345678', email='d@example.com')
        self.client.force_login(self.user)

    def test_deposit_creates_pending_request_without_crediting_balance(self):
        resp = self.client.post(reverse('dashboard:new_deposit'),
                                {'amount': '500'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('0.00'))
        txn = Transaction.objects.get(user=self.user, type='deposit')
        self.assertEqual(txn.status, 'pending')
        self.assertEqual(txn.payment_method, 'bank_transfer')
        self.assertTrue(txn.payment_reference.startswith('GC-'))
        self.assertIsNone(txn.processed_at)
        self.assertTrue(tmodels.Deposit.objects.filter(transaction=txn).exists())
        self.assertContains(resp, 'Deposit request submitted')
        self.assertContains(resp, txn.payment_reference)
        self.assertNotContains(resp, 'Grenville Crest Bank')
        self.assertNotContains(resp, 'gc-blurred-detail')

    def test_deposit_rejects_bad_amount(self):
        self.client.post(reverse('dashboard:new_deposit'), {'amount': 'abc'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('0.00'))

    def test_no_payment_route(self):
        from django.urls import NoReverseMatch
        with self.assertRaises(NoReverseMatch):
            reverse('dashboard:payment', args=[1])
        with self.assertRaises(NoReverseMatch):
            reverse('dashboard:swap')


class BankSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='searcher', password='pw12345678', email='s@example.com')
        self.client.force_login(self.user)

    def test_search_by_routing_prefix(self):
        resp = self.client.get(reverse('dashboard:bank_search'), {'q': '021000021'})
        data = resp.json()
        self.assertTrue(any(b['routing'] == '021000021' for b in data['results']))

    def test_search_by_name(self):
        resp = self.client.get(reverse('dashboard:bank_search'), {'q': 'Wells Fargo'})
        data = resp.json()
        self.assertTrue(data['results'])
        self.assertTrue(all('wells fargo' in b['name'].lower() for b in data['results']))

    def test_short_query_returns_nothing(self):
        resp = self.client.get(reverse('dashboard:bank_search'), {'q': 'a'})
        self.assertEqual(resp.json()['results'], [])

    def test_login_required(self):
        self.client.logout()
        resp = self.client.get(reverse('dashboard:bank_search'), {'q': 'chase'})
        self.assertEqual(resp.status_code, 302)


@_PLAIN_STATIC
class BankWithdrawalTests(TestCase):
    def setUp(self):
        call_command('seed_basics')          # creates the Bank Transfer method
        self.user = User.objects.create_user(
            username='withdrawer', password='pw12345678', email='w@example.com')
        self.user.balance = Decimal('1000.00')
        self.user.save(update_fields=['balance'])
        self.client.force_login(self.user)

    def test_bank_withdrawal_holds_funds_and_snapshots_bank(self):
        session = self.client.session
        session['withdrawal_method'] = 'Bank Transfer'
        session.save()
        otp = EmailOTP.issue(self.user, purpose='withdrawal')

        resp = self.client.post(reverse('dashboard:withdraw_funds'), {
            'otp': otp.code,
            'amount': '250',
            'account_holder_name': 'Ada Lovelace',
            'account_number': '1234567890',
            'bank_name': 'JPMorgan Chase Bank',
            'routing_number': '021000021',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('750.00'))     # held
        txn = Transaction.objects.get(user=self.user, type='withdrawal')
        self.assertEqual(txn.status, 'pending')
        self.assertTrue(txn.funds_held)
        self.assertEqual(txn.payment_method, 'bank_transfer')
        wd = Withdrawal.objects.get(transaction=txn)
        self.assertIn('JPMorgan Chase Bank', wd.withdrawal_address)
        self.assertIn('7890', wd.withdrawal_address)               # masked last 4
        self.assertIn('021000021', wd.withdrawal_address)

    def test_withdrawal_requires_bank_details(self):
        session = self.client.session
        session['withdrawal_method'] = 'Bank Transfer'
        session.save()
        otp = EmailOTP.issue(self.user, purpose='withdrawal')
        self.client.post(reverse('dashboard:withdraw_funds'), {
            'otp': otp.code, 'amount': '250',
            # no bank fields
        }, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('1000.00'))     # nothing held
        self.assertFalse(Transaction.objects.filter(user=self.user, type='withdrawal').exists())
