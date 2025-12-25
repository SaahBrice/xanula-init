#!/usr/bin/env python
"""
Configure CORS rules on Backblaze B2 bucket to allow PDF.js and other
client-side libraries to fetch files from the bucket.

Run this once to set up CORS for your bucket.
"""

import os
import sys
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

import boto3
from botocore.config import Config
from django.conf import settings


def configure_cors():
    """Configure CORS rules on the Backblaze B2 bucket."""
    
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version='s3v4'),
    )
    
    # CORS configuration - Backblaze B2 requires simpler rules
    cors_configuration = {
        'CORSRules': [
            {
                'AllowedHeaders': ['*'],
                'AllowedMethods': ['GET', 'HEAD', 'PUT'],
                'AllowedOrigins': ['*'],  # Allow all origins
                'ExposeHeaders': ['Content-Length', 'Content-Type', 'ETag'],
                'MaxAgeSeconds': 3600
            }
        ]
    }
    
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    print(f"Configuring CORS for bucket: {bucket_name}")
    print(f"Endpoint: {settings.AWS_S3_ENDPOINT_URL}")
    print(f"\nCORS Rules:")
    print(json.dumps(cors_configuration, indent=2))
    
    try:
        s3_client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_configuration
        )
        print(f"\n✅ CORS rules successfully applied to bucket '{bucket_name}'!")
    except Exception as e:
        print(f"\n❌ Error applying CORS rules: {e}")
        return False
    
    # Verify the CORS rules were applied
    try:
        response = s3_client.get_bucket_cors(Bucket=bucket_name)
        print("\n📋 Current CORS rules on bucket:")
        print(json.dumps(response.get('CORSRules', []), indent=2))
    except Exception as e:
        print(f"\nCouldn't verify CORS rules: {e}")
    
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("🌐 BACKBLAZE B2 CORS CONFIGURATION")
    print("=" * 60)
    configure_cors()
