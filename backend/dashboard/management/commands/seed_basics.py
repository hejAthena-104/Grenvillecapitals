from django.core.management.base import BaseCommand
from transactions.models import PaymentMethod

# Crypto payment methods that earlier deploys seeded. seed_basics runs on every
# container start, so these must be actively removed here or they reappear.
LEGACY_CRYPTO_METHODS = ['USDT', 'Bitcoin', 'Ethereum', 'Litecoin']


class Command(BaseCommand):
    help = 'Seed baseline data: a single Bank Transfer method; purge legacy crypto methods (idempotent).'

    def handle(self, *args, **options):
        removed, _ = PaymentMethod.objects.filter(name__in=LEGACY_CRYPTO_METHODS).delete()
        if removed:
            self.stdout.write(self.style.WARNING(f'Removed {removed} legacy crypto payment method row(s).'))

        _, was_created = PaymentMethod.objects.get_or_create(
            name='Bank Transfer',
            defaults={
                'type': 'both', 'min_amount': 10.00, 'max_amount': 1000000.00,
                'charge_type': 'percentage', 'charge_amount': 0.00,
                'duration': 'Instant', 'is_active': True, 'order': 0,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            'Bank Transfer method ' + ('created.' if was_created else 'already present.')
        ))
