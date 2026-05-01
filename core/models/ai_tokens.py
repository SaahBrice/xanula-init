from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AITokenSettings(models.Model):
    free_initial_tokens = models.PositiveIntegerField(default=10000)
    usage_multiplier = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("1.000"))
    minimum_request_tokens = models.PositiveIntegerField(default=5)
    low_balance_threshold = models.PositiveIntegerField(default=1000)
    input_context_weight = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("0.005"))
    output_chars_per_token = models.PositiveIntegerField(default=4)
    analyze_flat_tokens = models.PositiveIntegerField(default=150)
    base_bundle_tokens = models.PositiveIntegerField(default=5000)
    base_price_xaf = models.PositiveIntegerField(default=1000)
    custom_min_tokens = models.PositiveIntegerField(default=5000)
    custom_step_tokens = models.PositiveIntegerField(default=1000)
    analyze_multiplier = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("1.000"))
    generate_multiplier = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("1.000"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("AI token settings")
        verbose_name_plural = _("AI token settings")

    def __str__(self):
        return "AI token settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AITokenWallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_token_wallet",
    )
    balance = models.PositiveIntegerField(default=0)
    total_granted = models.PositiveIntegerField(default=0)
    total_purchased = models.PositiveIntegerField(default=0)
    total_used = models.PositiveIntegerField(default=0)
    free_grant_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("AI token wallet")
        verbose_name_plural = _("AI token wallets")

    def __str__(self):
        return f"{self.user} - {self.balance} tokens"


class AITokenLedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        FREE_GRANT = "free_grant", _("Free grant")
        USAGE = "usage", _("AI usage")
        PURCHASE = "purchase", _("Purchase")
        REFUND = "refund", _("Refund")
        ADMIN_ADJUSTMENT = "admin_adjustment", _("Admin adjustment")

    wallet = models.ForeignKey(AITokenWallet, on_delete=models.CASCADE, related_name="ledger_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_token_ledger_entries")
    entry_type = models.CharField(max_length=30, choices=EntryType.choices)
    delta = models.IntegerField()
    balance_after = models.PositiveIntegerField()
    action = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("AI token ledger entry")
        verbose_name_plural = _("AI token ledger entries")
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["entry_type"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"{self.user} {self.delta:+d} ({self.entry_type})"


class AITokenPurchase(models.Model):
    class PaymentMethod(models.TextChoices):
        STRIPE = "stripe", _("Stripe")
        FAPSHI = "fapshi", _("Fapshi")

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_token_purchases")
    token_amount = models.PositiveIntegerField()
    amount_xaf = models.PositiveIntegerField()
    amount_eur = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_transaction_id = models.CharField(max_length=255, blank=True)
    credited_at = models.DateTimeField(null=True, blank=True)
    return_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("AI token purchase")
        verbose_name_plural = _("AI token purchases")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "payment_status"]),
            models.Index(fields=["payment_transaction_id"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.token_amount} AI tokens"

    @property
    def is_credited(self):
        return self.credited_at is not None

    def mark_credited(self):
        self.payment_status = self.PaymentStatus.COMPLETED
        self.credited_at = self.credited_at or timezone.now()
        self.save(update_fields=["payment_status", "credited_at", "updated_at"])
