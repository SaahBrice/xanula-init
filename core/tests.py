from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .ai_tokens import (
    assert_can_start_ai_request,
    calculate_charge,
    credit_token_purchase,
    deduct_ai_tokens,
    ensure_wallet,
    get_purchase_options,
    price_for_tokens,
)
from .models import AITokenLedgerEntry, AITokenPurchase, AITokenSettings


class AITokenWalletTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="tokens@example.com", password="pass12345")

    def test_free_grant_is_applied_once_per_user(self):
        first_wallet = ensure_wallet(self.user, grant_if_needed=True)
        second_wallet = ensure_wallet(self.user, grant_if_needed=True)

        self.assertEqual(first_wallet.balance, 10000)
        self.assertEqual(second_wallet.balance, 10000)
        self.assertEqual(
            AITokenLedgerEntry.objects.filter(user=self.user, entry_type=AITokenLedgerEntry.EntryType.FREE_GRANT).count(),
            1,
        )

    def test_usage_charge_uses_provider_tokens_and_admin_multiplier(self):
        settings = AITokenSettings.get_solo()
        settings.usage_multiplier = Decimal("2.000")
        settings.minimum_request_tokens = 10
        settings.input_context_weight = Decimal("0.005")
        settings.output_chars_per_token = 4
        settings.save()
        ensure_wallet(self.user, grant_if_needed=True)

        wallet, entry, status = deduct_ai_tokens(
            self.user,
            "continue",
            input_chars=1000,
            output_chars=400,
            provider_usage={"total_tokens": 123},
            metadata={"manuscript_id": 1},
        )

        self.assertEqual(entry.delta, -204)
        self.assertEqual(wallet.balance, 9796)
        self.assertEqual(status["delta"], -204)
        self.assertEqual(entry.metadata["raw_ai_tokens"], 102)
        self.assertEqual(entry.metadata["estimated_provider_tokens"], 123)

    def test_charge_falls_back_to_character_estimate_and_minimum(self):
        settings = AITokenSettings.get_solo()
        settings.minimum_request_tokens = 100
        settings.save()

        charge, raw_tokens, provider_tokens = calculate_charge("summarize", input_chars=20, output_chars=10)

        self.assertEqual(provider_tokens, 8)
        self.assertEqual(raw_tokens, 4)
        self.assertEqual(charge, 100)

    def test_memory_refresh_has_flat_bounded_charge(self):
        settings = AITokenSettings.get_solo()
        settings.analyze_flat_tokens = 150
        settings.minimum_request_tokens = 5
        settings.save()

        charge, raw_tokens, provider_tokens = calculate_charge("analyze", input_chars=45000, output_chars=3000)

        self.assertEqual(charge, 150)
        self.assertEqual(raw_tokens, 150)
        self.assertGreater(provider_tokens, 10000)

    def test_insufficient_balance_blocks_start(self):
        settings = AITokenSettings.get_solo()
        settings.free_initial_tokens = 0
        settings.minimum_request_tokens = 50
        settings.save()

        with self.assertRaisesMessage(Exception, "more Reepls AI tokens"):
            assert_can_start_ai_request(self.user)

    def test_purchase_options_and_custom_price_are_linear(self):
        settings = AITokenSettings.get_solo()
        settings.base_price_xaf = 1200
        settings.save()

        options = get_purchase_options()
        tokens, amount_xaf, amount_eur = price_for_tokens(15300)

        self.assertEqual(options["bundles"][0]["price_xaf"], 1200)
        self.assertEqual(options["bundles"][0]["price_eur"], "1.83")
        self.assertEqual(options["bundles"][1]["price_eur"], "5.50")
        self.assertEqual(options["custom"]["stripe_xaf_to_eur_rate"], 655)
        self.assertEqual(tokens, 16000)
        self.assertEqual(amount_xaf, 3840)
        self.assertEqual(amount_eur, Decimal("5.86"))

    def test_credit_purchase_is_idempotent(self):
        purchase = AITokenPurchase.objects.create(
            user=self.user,
            token_amount=5000,
            amount_xaf=1000,
            amount_eur=Decimal("2.00"),
            payment_method=AITokenPurchase.PaymentMethod.FAPSHI,
            payment_status=AITokenPurchase.PaymentStatus.PENDING,
        )

        wallet, entry, first_status = credit_token_purchase(purchase)
        wallet, second_entry, second_status = credit_token_purchase(purchase)

        self.assertEqual(wallet.balance, 5000)
        self.assertIsNotNone(entry)
        self.assertIsNone(second_entry)
        self.assertEqual(first_status["delta"], 5000)
        self.assertEqual(second_status["delta"], 0)
        self.assertEqual(
            AITokenLedgerEntry.objects.filter(user=self.user, entry_type=AITokenLedgerEntry.EntryType.PURCHASE).count(),
            1,
        )


class AITokenPaymentViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="paytokens@example.com", password="pass12345")
        self.client.force_login(self.user)

    @patch("core.fapshi_utils.is_payment_successful", return_value=True)
    @patch("core.fapshi_utils.check_payment_status", return_value={"success": True, "status": "SUCCESSFUL"})
    def test_fapshi_status_poll_credits_tokens_once(self, status_mock, success_mock):
        purchase = AITokenPurchase.objects.create(
            user=self.user,
            token_amount=5000,
            amount_xaf=1000,
            amount_eur=Decimal("2.00"),
            payment_method=AITokenPurchase.PaymentMethod.FAPSHI,
            payment_status=AITokenPurchase.PaymentStatus.PENDING,
            payment_transaction_id="fapshi-123",
        )

        first = self.client.get(reverse("core:ai_token_purchase_status", args=[purchase.pk]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        second = self.client.get(reverse("core:ai_token_purchase_status", args=[purchase.pk]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["status"], "completed")
        self.assertEqual(second.json()["status"], "completed")
        self.user.refresh_from_db()
        self.assertEqual(self.user.ai_token_wallet.balance, 5000)

    @override_settings(STRIPE_SECRET_KEY="sk_test")
    @patch("stripe.checkout.Session.create")
    def test_stripe_checkout_uses_admin_token_rate_in_eur_cents(self, create_mock):
        settings = AITokenSettings.get_solo()
        settings.base_price_xaf = 1000
        settings.save()
        session = Mock()
        session.id = "cs_tokens"
        session.url = "https://stripe.example/checkout"
        create_mock.return_value = session

        response = self.client.post(reverse("core:ai_token_stripe_checkout"), {"token_amount": 15000, "next": "/write/1/"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, session.url)
        kwargs = create_mock.call_args.kwargs
        self.assertEqual(kwargs["line_items"][0]["price_data"]["currency"], "eur")
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 458)

    @override_settings(STRIPE_SECRET_KEY="")
    @patch("stripe.checkout.Session.create")
    def test_stripe_checkout_requires_gateway_credentials(self, create_mock):
        response = self.client.post(reverse("core:ai_token_stripe_checkout"), {"token_amount": 5000, "next": "/write/1/"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/write/1/")
        create_mock.assert_not_called()
        purchase = AITokenPurchase.objects.latest("pk")
        self.assertEqual(purchase.payment_status, AITokenPurchase.PaymentStatus.FAILED)

    @override_settings(FAPSHI_API_USER="apiuser", FAPSHI_API_KEY="apikey")
    @patch("core.fapshi_utils.create_payment")
    def test_fapshi_checkout_uses_admin_token_rate_in_xaf(self, create_mock):
        settings = AITokenSettings.get_solo()
        settings.base_price_xaf = 1000
        settings.save()
        create_mock.return_value = {"success": True, "link": "https://fapshi.example/pay", "trans_id": "fp_tokens"}

        response = self.client.post(reverse("core:ai_token_fapshi_checkout"), {"token_amount": 15000, "next": "/write/1/"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://fapshi.example/pay")
        self.assertEqual(create_mock.call_args.kwargs["amount"], 3000)
        self.assertEqual(create_mock.call_args.kwargs["external_id"], str(AITokenPurchase.objects.latest("pk").pk))
        self.assertEqual(create_mock.call_args.kwargs["message"], "Purchase: Reepls AI Tokens")

    @override_settings(FAPSHI_API_USER="", FAPSHI_API_KEY="")
    @patch("core.fapshi_utils.create_payment")
    def test_fapshi_checkout_requires_gateway_credentials(self, create_mock):
        response = self.client.post(reverse("core:ai_token_fapshi_checkout"), {"token_amount": 5000, "next": "/write/1/"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/write/1/")
        create_mock.assert_not_called()
        purchase = AITokenPurchase.objects.latest("pk")
        self.assertEqual(purchase.payment_status, AITokenPurchase.PaymentStatus.FAILED)

    @patch("core.fapshi_utils.is_payment_pending", return_value=True)
    @patch("core.fapshi_utils.check_payment_status", return_value={"success": True, "status": "PENDING"})
    def test_fapshi_return_shows_pending_poll_page(self, status_mock, pending_mock):
        purchase = AITokenPurchase.objects.create(
            user=self.user,
            token_amount=5000,
            amount_xaf=1000,
            amount_eur=Decimal("1.53"),
            payment_method=AITokenPurchase.PaymentMethod.FAPSHI,
            payment_status=AITokenPurchase.PaymentStatus.PENDING,
            payment_transaction_id="fp_pending",
            return_path="/write/1/",
        )

        response = self.client.get(reverse("core:ai_token_fapshi_return", args=[purchase.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirming Mobile Money")
        self.assertContains(response, reverse("core:ai_token_purchase_status", args=[purchase.pk]))
        self.assertContains(response, "Mobile Money (OM/MOMO)")

    @override_settings(STRIPE_SECRET_KEY="sk_test")
    @patch("stripe.checkout.Session.retrieve")
    def test_stripe_success_credits_tokens_once(self, retrieve_mock):
        session = Mock()
        session.payment_status = "paid"
        session.payment_intent = "pi_123"
        retrieve_mock.return_value = session
        purchase = AITokenPurchase.objects.create(
            user=self.user,
            token_amount=15000,
            amount_xaf=3000,
            amount_eur=Decimal("6.00"),
            payment_method=AITokenPurchase.PaymentMethod.STRIPE,
            payment_status=AITokenPurchase.PaymentStatus.PENDING,
            payment_transaction_id="cs_123",
            return_path="/write/",
        )

        first = self.client.get(reverse("core:ai_token_stripe_success", args=[purchase.pk]), {"session_id": "cs_123"})
        second = self.client.get(reverse("core:ai_token_stripe_success", args=[purchase.pk]), {"session_id": "cs_123"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertContains(first, "AI tokens added")
        self.user.refresh_from_db()
        self.assertEqual(self.user.ai_token_wallet.balance, 15000)
