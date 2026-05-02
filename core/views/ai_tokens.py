from decimal import Decimal, ROUND_HALF_UP
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from ..ai_tokens import (
    credit_token_purchase,
    ensure_wallet,
    get_purchase_options,
    price_for_tokens,
    token_status,
)
from ..models import AITokenPurchase

logger = logging.getLogger(__name__)


def _safe_return_path(request, value=""):
    fallback = reverse("write:landing")
    if value and value.startswith("/"):
        return value
    return fallback


def _redirect_after_purchase(request, purchase, success=True):
    if success:
        messages.success(request, f"{purchase.token_amount:,} Reepls AI tokens added to your account.")
    else:
        messages.error(request, "Token payment was not completed. Please try again.")
    return redirect(_safe_return_path(request, purchase.return_path))


def _method_label(purchase):
    if purchase.payment_method == AITokenPurchase.PaymentMethod.FAPSHI:
        return "Mobile Money (OM/MOMO)"
    if purchase.payment_method == AITokenPurchase.PaymentMethod.STRIPE:
        return "Card"
    return purchase.get_payment_method_display()


def _success_context(request, purchase, success=True, error_message=""):
    wallet = ensure_wallet(request.user, grant_if_needed=False)
    return {
        "purchase": purchase,
        "success": success,
        "error_message": error_message,
        "payment_method_label": _method_label(purchase),
        "token_status": token_status(wallet),
        "return_path": _safe_return_path(request, purchase.return_path),
    }


@login_required
@require_GET
def ai_token_status_api(request):
    wallet = ensure_wallet(request.user, grant_if_needed=False)
    return JsonResponse({
        "status": "ok",
        "token_status": token_status(wallet),
        "purchase_options": get_purchase_options(),
    })


def _create_pending_purchase(request, method):
    token_amount, amount_xaf, amount_eur = price_for_tokens(request.POST.get("token_amount"))
    return AITokenPurchase.objects.create(
        user=request.user,
        token_amount=token_amount,
        amount_xaf=amount_xaf,
        amount_eur=amount_eur,
        payment_method=method,
        return_path=_safe_return_path(request, request.POST.get("next", "")),
    )


@login_required
@require_POST
def create_ai_token_stripe_checkout(request):
    import stripe

    purchase = _create_pending_purchase(request, AITokenPurchase.PaymentMethod.STRIPE)
    if not getattr(settings, "STRIPE_SECRET_KEY", ""):
        logger.error("AI token Stripe checkout blocked: missing STRIPE_SECRET_KEY")
        purchase.payment_status = AITokenPurchase.PaymentStatus.FAILED
        purchase.save(update_fields=["payment_status", "updated_at"])
        messages.error(request, "Card payment is not configured. Add STRIPE_SECRET_KEY, then try again.")
        return redirect(purchase.return_path)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    domain = request.build_absolute_uri("/").rstrip("/")
    success_url = f"{domain}{reverse('core:ai_token_stripe_success', args=[purchase.pk])}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{domain}{purchase.return_path}"

    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": f"{purchase.token_amount:,} Reepls AI tokens",
                    "description": "AI writing credits for Reepls AI Editor",
                    },
                    "unit_amount": int((Decimal(purchase.amount_eur) * 100).to_integral_value(rounding=ROUND_HALF_UP)),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "ai_token_purchase_id": str(purchase.pk),
                "user_id": str(request.user.pk),
                "token_amount": str(purchase.token_amount),
            },
        )
    except Exception:
        purchase.payment_status = AITokenPurchase.PaymentStatus.FAILED
        purchase.save(update_fields=["payment_status", "updated_at"])
        messages.error(request, "Card payment could not be started. Please try Fapshi or try again later.")
        return redirect(purchase.return_path)

    purchase.payment_transaction_id = checkout_session.id
    purchase.save(update_fields=["payment_transaction_id", "updated_at"])
    return redirect(checkout_session.url)


@login_required
@require_GET
def ai_token_stripe_success(request, purchase_id):
    import stripe

    purchase = get_object_or_404(AITokenPurchase, pk=purchase_id, user=request.user)
    if purchase.credited_at:
        return render(request, "core/ai_token_success.html", _success_context(request, purchase, success=True))

    session_id = request.GET.get("session_id") or purchase.payment_transaction_id
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return render(
            request,
            "core/ai_token_success.html",
            _success_context(
                request,
                purchase,
                success=False,
                error_message="Unable to verify card payment yet. If you were charged, please contact support.",
            ),
        )

    if getattr(session, "payment_status", "") == "paid":
        purchase.payment_transaction_id = getattr(session, "payment_intent", "") or session_id
        purchase.payment_status = AITokenPurchase.PaymentStatus.COMPLETED
        purchase.save(update_fields=["payment_transaction_id", "payment_status", "updated_at"])
        credit_token_purchase(purchase)
        purchase.refresh_from_db()
        return render(request, "core/ai_token_success.html", _success_context(request, purchase, success=True))

    purchase.payment_status = AITokenPurchase.PaymentStatus.FAILED
    purchase.save(update_fields=["payment_status", "updated_at"])
    return render(
        request,
        "core/ai_token_success.html",
        _success_context(request, purchase, success=False, error_message="Card payment was not completed."),
    )


@login_required
@require_POST
def create_ai_token_fapshi_checkout(request):
    from .. import fapshi_utils

    purchase = _create_pending_purchase(request, AITokenPurchase.PaymentMethod.FAPSHI)
    domain = request.build_absolute_uri("/").rstrip("/")

    if not getattr(settings, "FAPSHI_API_USER", "") or not getattr(settings, "FAPSHI_API_KEY", ""):
        logger.error("AI token Fapshi checkout blocked: missing FAPSHI_API_USER or FAPSHI_API_KEY")
        purchase.payment_status = AITokenPurchase.PaymentStatus.FAILED
        purchase.save(update_fields=["payment_status", "updated_at"])
        messages.error(
            request,
            "Mobile Money is not configured. Add FAPSHI_API_USER and FAPSHI_API_KEY, then try again.",
        )
        return redirect(purchase.return_path)

    return_url = f"{domain}/ai-tokens/fapshi/return/{purchase.pk}/"
    result = fapshi_utils.create_payment(
        amount=int(purchase.amount_xaf),
        email=request.user.email,
        redirect_url=return_url,
        user_id=str(request.user.pk),
        external_id=str(purchase.pk),
        message="Purchase: Reepls AI Tokens",
    )

    if result.get("success") and result.get("link") and result.get("trans_id"):
        purchase.payment_transaction_id = result["trans_id"]
        purchase.save(update_fields=["payment_transaction_id", "updated_at"])
        logger.info("AI token Fapshi checkout created for purchase %s, redirecting to %s", purchase.pk, result["link"])
        return redirect(result["link"])

    logger.error("AI token Fapshi checkout failed for purchase %s: %s", purchase.pk, result.get("error", "Missing payment link or transaction id"))
    if result.get("success"):
        result["error"] = "Payment gateway returned an incomplete checkout response."
    purchase.payment_status = AITokenPurchase.PaymentStatus.FAILED
    purchase.save(update_fields=["payment_status", "updated_at"])
    messages.error(
        request,
        f"Mobile Money payment could not be started. {result.get('error', 'Please try card payment.')}",
    )
    return redirect(purchase.return_path)


@login_required
@require_GET
def ai_token_fapshi_return(request, purchase_id):
    from .. import fapshi_utils

    purchase = get_object_or_404(AITokenPurchase, pk=purchase_id, user=request.user)
    if purchase.credited_at:
        return render(request, "core/ai_token_success.html", _success_context(request, purchase, success=True))

    trans_id = request.GET.get("transId") or purchase.payment_transaction_id
    result = fapshi_utils.check_payment_status(trans_id) if trans_id else {"success": False}
    if result.get("success") and fapshi_utils.is_payment_successful(result.get("status")):
        purchase.payment_status = AITokenPurchase.PaymentStatus.COMPLETED
        purchase.save(update_fields=["payment_status", "updated_at"])
        credit_token_purchase(purchase)
        purchase.refresh_from_db()
        return render(request, "core/ai_token_success.html", _success_context(request, purchase, success=True))
    if result.get("success") and fapshi_utils.is_payment_pending(result.get("status")):
        return render(
            request,
            "core/ai_token_pending.html",
            {
                "purchase": purchase,
                "payment_method_label": _method_label(purchase),
                "return_path": _safe_return_path(request, purchase.return_path),
            },
        )

    purchase.payment_status = AITokenPurchase.PaymentStatus.FAILED
    purchase.save(update_fields=["payment_status", "updated_at"])
    return render(
        request,
        "core/ai_token_success.html",
        _success_context(request, purchase, success=False, error_message="Mobile Money payment failed or expired."),
    )


@login_required
@require_GET
def ai_token_success_page(request, purchase_id):
    purchase = get_object_or_404(AITokenPurchase, pk=purchase_id, user=request.user)
    success = purchase.payment_status == AITokenPurchase.PaymentStatus.COMPLETED and purchase.credited_at
    return render(
        request,
        "core/ai_token_success.html",
        _success_context(
            request,
            purchase,
            success=bool(success),
            error_message="" if success else "Payment is not completed yet.",
        ),
    )


@login_required
@require_GET
def check_ai_token_purchase_status_api(request, purchase_id):
    from .. import fapshi_utils

    purchase = get_object_or_404(AITokenPurchase, pk=purchase_id, user=request.user)
    if purchase.credited_at:
        wallet = ensure_wallet(request.user, grant_if_needed=False)
        return JsonResponse({
            "status": "completed",
            "token_status": token_status(wallet),
            "redirect_url": reverse("core:ai_token_success", args=[purchase.pk]),
        })

    if not purchase.payment_transaction_id:
        return JsonResponse({"status": "error", "message": "No payment reference."}, status=400)

    result = fapshi_utils.check_payment_status(purchase.payment_transaction_id)
    if result.get("success") and fapshi_utils.is_payment_successful(result.get("status")):
        purchase.payment_status = AITokenPurchase.PaymentStatus.COMPLETED
        purchase.save(update_fields=["payment_status", "updated_at"])
        wallet, _, status = credit_token_purchase(purchase)
        return JsonResponse({
            "status": "completed",
            "token_status": status,
            "redirect_url": reverse("core:ai_token_success", args=[purchase.pk]),
        })
    if result.get("success") and fapshi_utils.is_payment_pending(result.get("status")):
        return JsonResponse({"status": "pending", "message": "Payment is still pending."})

    purchase.payment_status = AITokenPurchase.PaymentStatus.FAILED
    purchase.save(update_fields=["payment_status", "updated_at"])
    return JsonResponse({"status": "failed", "message": "Payment failed or expired."})
