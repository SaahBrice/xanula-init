#!/usr/bin/env python
"""
Migration script to upload existing local media files to Backblaze B2.

This script:
1. Finds all local media files in Book and User models
2. Uploads them to Backblaze B2 using boto3
3. No database changes needed (django-storages handles URL generation)

Usage:
    python migrate_to_backblaze.py
"""

import os
import sys
import mimetypes

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

import boto3
from botocore.config import Config
from django.conf import settings
from core.models import Book
from users.models import User


def get_s3_client():
    """Create a boto3 S3 client for Backblaze B2."""
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version='s3v4'),
    )


def upload_file_to_b2(s3_client, local_path, remote_key):
    """Upload a file to Backblaze B2."""
    try:
        # Guess content type
        content_type, _ = mimetypes.guess_type(str(local_path))
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # Upload with public-read ACL
        s3_client.upload_file(
            str(local_path),
            settings.AWS_STORAGE_BUCKET_NAME,
            remote_key,
            ExtraArgs={
                'ContentType': content_type,
                'ACL': 'public-read',
            }
        )
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def migrate_file_field(s3_client, file_field, stats):
    """Migrate a single file field to B2."""
    if not file_field or not file_field.name:
        return
    
    # Construct local path
    local_path = settings.MEDIA_ROOT / file_field.name.lstrip('media/')
    
    # If file_field.name starts with 'media/', strip it
    if file_field.name.startswith('media/'):
        remote_key = file_field.name
    else:
        remote_key = f"media/{file_field.name}"
    
    # Normalize path separators
    remote_key = remote_key.replace('\\', '/')
    
    if not os.path.exists(local_path):
        print(f"  ⚠️ File not found locally: {local_path}")
        stats['skipped'] += 1
        return
    
    print(f"  📤 Uploading: {file_field.name}")
    print(f"      -> B2 key: {remote_key}")
    
    if upload_file_to_b2(s3_client, local_path, remote_key):
        print(f"  ✅ Success!")
        stats['success'] += 1
    else:
        stats['errors'] += 1


def main():
    print("=" * 60)
    print("🚀 BACKBLAZE B2 MIGRATION SCRIPT")
    print("=" * 60)
    print(f"Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"Endpoint: {settings.AWS_S3_ENDPOINT_URL}")
    print(f"Media Root: {settings.MEDIA_ROOT}")
    print()
    
    # Confirm
    confirm = input("Proceed with migration? (y/n): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        return
    
    s3_client = get_s3_client()
    stats = {'success': 0, 'errors': 0, 'skipped': 0}
    
    # Migrate Book files
    print("\n" + "=" * 60)
    print("📚 MIGRATING BOOK FILES")
    print("=" * 60)
    
    for book in Book.objects.all():
        print(f"\nBook: {book.title[:40]}...")
        migrate_file_field(s3_client, book.manuscript_file, stats)
        migrate_file_field(s3_client, book.ebook_file, stats)
        migrate_file_field(s3_client, book.audiobook_file, stats)
        migrate_file_field(s3_client, book.cover_image, stats)
        if book.qr_code:
            migrate_file_field(s3_client, book.qr_code, stats)
    
    # Migrate User profile pictures
    print("\n" + "=" * 60)
    print("👤 MIGRATING USER PROFILE PICTURES")
    print("=" * 60)
    
    for user in User.objects.exclude(profile_picture='').exclude(profile_picture__isnull=True):
        print(f"\nUser: {user.email[:30]}...")
        migrate_file_field(s3_client, user.profile_picture, stats)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 MIGRATION SUMMARY")
    print("=" * 60)
    print(f"✅ Success: {stats['success']}")
    print(f"❌ Errors: {stats['errors']}")
    print(f"⚠️ Skipped (file not found): {stats['skipped']}")
    print()
    print("Migration complete!")


if __name__ == '__main__':
    main()
