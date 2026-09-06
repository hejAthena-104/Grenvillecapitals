from django.core.management.base import BaseCommand
from transactions.models import PaymentMethod, SwapRate


class Command(BaseCommand):
    help = 'Seed baseline data: crypto payment methods + the USD/BTC swap rate (idempotent).'

    def handle(self, *args, **options):
        methods = [
            ('USDT', 'TXYZa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5', 'TRC20 Network'),
            ('Bitcoin', 'bc1qexampleexampleexampleexampleexamp', 'BTC Network'),
            ('Ethereum', '0xExampleExampleExampleExampleExample0000', 'ERC20 Network'),
            ('Litecoin', 'ltc1qexampleexampleexampleexampleexample', 'LTC Network'),
        ]
        created = 0
        for i, (name, addr, duration) in enumerate(methods):
            obj, was_created = PaymentMethod.objects.get_or_create(
                name=name,
                defaults={
                    'type': 'both', 'min_amount': 10.00, 'max_amount': 1000000.00,
                    'charge_type': 'percentage', 'charge_amount': 0.00,
                    'wallet_address': addr, 'duration': duration, 'is_active': True, 'order': i,
                },
            )
            created += 1 if was_created else 0
        self.stdout.write(self.style.SUCCESS(f'Payment methods: {created} created, {len(methods) - created} existed'))

        if not SwapRate.objects.exists():
            SwapRate.objects.create(btc_usd_price=65000.00)
            self.stdout.write(self.style.SUCCESS('Swap rate created: 1 BTC = $65,000.00'))
        else:
            self.stdout.write('Swap rate already set.')
