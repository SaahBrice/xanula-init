"""
Fapshi Mobile Money Payment Integration Utilities
Per Architecture Document Section 9 (Payment Processing)
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Fapshi API base URL
FAPSHI_BASE_URL = getattr(settings, 'FAPSHI_BASE_URL', 'https://api.fapshi.com')


def get_fapshi_headers():
    """
    Get authentication headers for Fapshi API requests.
    """
    return {
        'apiuser': settings.FAPSHI_API_USER,
        'apikey': settings.FAPSHI_API_KEY,
        'Content-Type': 'application/json',
    }


def create_payment(amount, email, redirect_url, user_id=None, external_id=None, message=None):
    """
    Create a Fapshi payment link (initiate-pay).
    
    Args:
        amount: Amount in XAF (minimum 100)
        email: Customer email address
        redirect_url: URL to redirect after payment
        user_id: Internal user ID for tracking
        external_id: Transaction/order ID for reconciliation
        message: Reason/description for payment
    
    Returns:
        dict: {
            'success': bool,
            'link': payment URL (if successful),
            'trans_id': transaction ID (if successful),
            'error': error message (if failed)
        }
    """
    endpoint = f"{FAPSHI_BASE_URL}/initiate-pay"
    
    payload = {
        'amount': int(amount),
        'email': email,
        'redirectUrl': redirect_url,
    }
    
    if user_id:
        payload['userId'] = str(user_id)
    if external_id:
        payload['externalId'] = str(external_id)
    if message:
        payload['message'] = message[:200]  # Truncate if too long
    
    try:
        logger.info(f"Fapshi initiate-pay: amount={amount}, email={email}")
        
        response = requests.post(
            endpoint,
            json=payload,
            headers=get_fapshi_headers(),
            timeout=30
        )
        
        logger.info(f"Fapshi response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Fapshi payment created: transId={data.get('transId')}")
            return {
                'success': True,
                'link': data.get('link'),
                'trans_id': data.get('transId'),
                'date_initiated': data.get('dateInitiated'),
            }
        else:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get('message', f'HTTP {response.status_code}')
            logger.error(f"Fapshi error: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
            }
            
    except requests.exceptions.Timeout:
        logger.error("Fapshi API timeout")
        return {
            'success': False,
            'error': 'Payment service timeout. Please try again.',
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Fapshi API error: {str(e)}")
        return {
            'success': False,
            'error': 'Payment service unavailable. Please try again later.',
        }
    except Exception as e:
        logger.error(f"Fapshi unexpected error: {str(e)}")
        return {
            'success': False,
            'error': 'An unexpected error occurred.',
        }


def check_payment_status(trans_id):
    """
    Check the status of a Fapshi payment transaction.
    
    Args:
        trans_id: Fapshi transaction ID
    
    Returns:
        dict: {
            'success': bool,
            'status': payment status (CREATED, PENDING, SUCCESSFUL, FAILED, EXPIRED),
            'data': full response data (if successful),
            'error': error message (if failed)
        }
    """
    endpoint = f"{FAPSHI_BASE_URL}/payment-status/{trans_id}"
    
    try:
        logger.info(f"Fapshi check status: transId={trans_id}")
        
        response = requests.get(
            endpoint,
            headers=get_fapshi_headers(),
            timeout=15
        )
        
        logger.info(f"Fapshi status response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'UNKNOWN')
            logger.info(f"Fapshi payment status: {status}")
            return {
                'success': True,
                'status': status,
                'data': data,
            }
        else:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get('message', f'HTTP {response.status_code}')
            logger.error(f"Fapshi status error: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
            }
            
    except requests.exceptions.Timeout:
        logger.error("Fapshi status check timeout")
        return {
            'success': False,
            'error': 'Status check timeout.',
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Fapshi status check error: {str(e)}")
        return {
            'success': False,
            'error': 'Unable to check payment status.',
        }
    except Exception as e:
        logger.error(f"Fapshi status unexpected error: {str(e)}")
        return {
            'success': False,
            'error': 'An unexpected error occurred.',
        }


def is_payment_successful(status):
    """
    Check if a Fapshi payment status indicates success.
    """
    return status == 'SUCCESSFUL'


def is_payment_pending(status):
    """
    Check if a Fapshi payment is still pending.
    """
    return status in ('CREATED', 'PENDING')


def is_payment_failed(status):
    """
    Check if a Fapshi payment has failed or expired.
    """
    return status in ('FAILED', 'EXPIRED')
