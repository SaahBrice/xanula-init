from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import AITokenLedgerEntry, AITokenPurchase, AITokenSettings, AITokenWallet

XAF_TO_EUR_RATE = Decimal("655")


class InsufficientAITokens(Exception):
    def __init__(self, wallet, settings):
        self.wallet = wallet
        self.settings = settings
        super().__init__("You need more Reepls AI tokens to continue.")


def _safe_int(value, default=0):
    try:
        return max(0, int(value or default))
    except (TypeError, ValueError):
        return default


def get_token_settings():
    return AITokenSettings.get_solo()


def get_purchase_options(settings_obj=None):
    settings_obj = settings_obj or get_token_settings()
    base_tokens = max(1, settings_obj.base_bundle_tokens)

    def option(tokens):
        tokens, amount_xaf, amount_eur = price_for_tokens(tokens, settings_obj)
        return {
            "tokens": int(tokens),
            "price_xaf": amount_xaf,
            "price_eur": str(amount_eur),
        }

    return {
        "bundles": [option(5000), option(15000), option(30000)],
        "custom": {
            "min_tokens": settings_obj.custom_min_tokens,
            "step_tokens": settings_obj.custom_step_tokens,
            "base_tokens": base_tokens,
            "base_price_xaf": settings_obj.base_price_xaf,
            "stripe_xaf_to_eur_rate": int(XAF_TO_EUR_RATE),
        },
    }


def price_for_tokens(token_amount, settings_obj=None):
    settings_obj = settings_obj or get_token_settings()
    tokens = normalize_token_amount(token_amount, settings_obj)
    multiplier = Decimal(tokens) / Decimal(max(1, settings_obj.base_bundle_tokens))
    amount_xaf = int((Decimal(settings_obj.base_price_xaf) * multiplier).to_integral_value(rounding=ROUND_CEILING))
    amount_eur = (Decimal(amount_xaf) / XAF_TO_EUR_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return tokens, amount_xaf, amount_eur


def normalize_token_amount(token_amount, settings_obj=None):
    settings_obj = settings_obj or get_token_settings()
    amount = _safe_int(token_amount, settings_obj.custom_min_tokens)
    amount = max(settings_obj.custom_min_tokens, amount)
    step = max(1, settings_obj.custom_step_tokens)
    remainder = amount % step
    if remainder:
        amount += step - remainder
    return amount


def _ledger(wallet, entry_type, delta, balance_after, action="", reference="", metadata=None):
    return AITokenLedgerEntry.objects.create(
        wallet=wallet,
        user=wallet.user,
        entry_type=entry_type,
        delta=delta,
        balance_after=balance_after,
        action=action,
        reference=reference,
        metadata=metadata or {},
    )


@transaction.atomic
def ensure_wallet(user, grant_if_needed=True):
    settings_obj = get_token_settings()
    wallet, _ = AITokenWallet.objects.select_for_update().get_or_create(user=user)
    if grant_if_needed and not wallet.free_grant_at and settings_obj.free_initial_tokens:
        grant = settings_obj.free_initial_tokens
        wallet.balance += grant
        wallet.total_granted += grant
        wallet.free_grant_at = timezone.now()
        wallet.save(update_fields=["balance", "total_granted", "free_grant_at", "updated_at"])
        _ledger(
            wallet,
            AITokenLedgerEntry.EntryType.FREE_GRANT,
            grant,
            wallet.balance,
            reference="initial-free-grant",
            metadata={"source": "first_ai_use"},
        )
    return wallet


def token_status_for_user(user, grant_if_needed=False):
    wallet = ensure_wallet(user, grant_if_needed=grant_if_needed)
    settings_obj = get_token_settings()
    return token_status(wallet, settings_obj)


def token_status(wallet, settings_obj=None, delta=0):
    settings_obj = settings_obj or get_token_settings()
    wallet_balance = _safe_int(wallet.balance)
    starter_tokens = settings_obj.free_initial_tokens if not wallet.free_grant_at else 0
    balance = wallet_balance + starter_tokens
    return {
        "balance": balance,
        "wallet_balance": wallet_balance,
        "balance_display": f"{balance:,}",
        "delta": int(delta or 0),
        "low_balance": balance <= settings_obj.low_balance_threshold,
        "empty": balance < settings_obj.minimum_request_tokens,
        "low_balance_threshold": settings_obj.low_balance_threshold,
        "minimum_request_tokens": settings_obj.minimum_request_tokens,
        "free_grant_applied": bool(wallet.free_grant_at),
        "starter_tokens_available": starter_tokens,
    }


def assert_can_start_ai_request(user):
    wallet = ensure_wallet(user, grant_if_needed=True)
    settings_obj = get_token_settings()
    if wallet.balance < settings_obj.minimum_request_tokens:
        raise InsufficientAITokens(wallet, settings_obj)
    return wallet, settings_obj


def raw_ai_tokens(input_chars=0, output_chars=0, provider_usage=None):
    provider_usage = provider_usage if isinstance(provider_usage, dict) else {}
    total = provider_usage.get("total_tokens")
    if total is not None:
        return _safe_int(total)
    return max(1, int((_safe_int(input_chars) + _safe_int(output_chars) + 3) / 4))


def action_multiplier(settings_obj, action):
    if action == "analyze":
        return settings_obj.analyze_multiplier
    return settings_obj.generate_multiplier


def calculate_charge(action, input_chars=0, output_chars=0, provider_usage=None, settings_obj=None):
    settings_obj = settings_obj or get_token_settings()
    provider_tokens = raw_ai_tokens(input_chars, output_chars, provider_usage)
    if action == "analyze":
        raw_tokens = max(1, _safe_int(settings_obj.analyze_flat_tokens, 150))
    else:
        input_units = (
            Decimal(_safe_int(input_chars))
            / Decimal(4)
            * Decimal(settings_obj.input_context_weight)
        ).to_integral_value(rounding=ROUND_CEILING)
        output_units = (
            Decimal(_safe_int(output_chars))
            / Decimal(max(1, settings_obj.output_chars_per_token))
        ).to_integral_value(rounding=ROUND_CEILING)
        raw_tokens = max(1, int(input_units) + int(output_units))
    multiplier = Decimal(settings_obj.usage_multiplier) * Decimal(action_multiplier(settings_obj, action))
    charged = int((Decimal(raw_tokens) * multiplier).to_integral_value(rounding=ROUND_CEILING))
    return max(settings_obj.minimum_request_tokens, charged), raw_tokens, provider_tokens


@transaction.atomic
def deduct_ai_tokens(user, action, input_chars=0, output_chars=0, provider_usage=None, metadata=None):
    settings_obj = get_token_settings()
    wallet = AITokenWallet.objects.select_for_update().get(user=user)
    charge, raw_tokens, provider_tokens = calculate_charge(action, input_chars, output_chars, provider_usage, settings_obj)
    charge = min(wallet.balance, charge)
    wallet.balance -= charge
    wallet.total_used += charge
    wallet.save(update_fields=["balance", "total_used", "updated_at"])
    entry = _ledger(
        wallet,
        AITokenLedgerEntry.EntryType.USAGE,
        -charge,
        wallet.balance,
        action=action,
        metadata={
            "raw_ai_tokens": raw_tokens,
            "estimated_provider_tokens": provider_tokens,
            "input_chars": _safe_int(input_chars),
            "output_chars": _safe_int(output_chars),
            "provider_usage": provider_usage if isinstance(provider_usage, dict) else {},
            "billing_model": "writing_credit_v2",
            "input_context_weight": str(settings_obj.input_context_weight),
            "output_chars_per_token": settings_obj.output_chars_per_token,
            **(metadata or {}),
        },
    )
    return wallet, entry, token_status(wallet, settings_obj, delta=-charge)


@transaction.atomic
def credit_token_purchase(purchase):
    purchase = AITokenPurchase.objects.select_for_update().get(pk=purchase.pk)
    wallet = ensure_wallet(purchase.user, grant_if_needed=False)
    if purchase.credited_at:
        return wallet, None, token_status(wallet, delta=0)

    wallet.balance += purchase.token_amount
    wallet.total_purchased += purchase.token_amount
    wallet.save(update_fields=["balance", "total_purchased", "updated_at"])
    purchase.mark_credited()
    entry = _ledger(
        wallet,
        AITokenLedgerEntry.EntryType.PURCHASE,
        purchase.token_amount,
        wallet.balance,
        reference=f"ai-token-purchase:{purchase.pk}",
        metadata={
            "payment_method": purchase.payment_method,
            "transaction_id": purchase.payment_transaction_id,
            "amount_xaf": purchase.amount_xaf,
            "amount_eur": str(purchase.amount_eur),
        },
    )
    return wallet, entry, token_status(wallet, delta=purchase.token_amount)
