#!/usr/bin/env python
"""
Migration script to upload existing local media files to Cloudinary.

This script will:
1. Find all Book records with local files (manuscripts, ebooks, audiobooks, covers, QR codes)
2. Find all User records with local profile pictures
3. Upload each file to Cloudinary with the same path
4. The database paths remain unchanged - Cloudinary uses the same structure

Run with: python migrate_to_cloudinary.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import cloudinary
import cloudinary.uploader
from django.conf import settings
from pathlib import Path

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
)

MEDIA_ROOT = Path(settings.MEDIA_ROOT)


def get_resource_type(file_path):
    """Determine Cloudinary resource type based on file extension."""
    ext = Path(file_path).suffix.lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']:
        return 'image'
    elif ext in ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.mp4', '.webm']:
        return 'video'
    else:
        # For PDFs, DOCX, EPUB, TXT, etc.
        return 'raw'


def upload_file_to_cloudinary(file_field, model_name, field_name):
    """
    Upload a single file to Cloudinary.
    Returns True if successful, False otherwise.
    """
    if not file_field or not file_field.name:
        return False
    
    # Get the local file path
    # Some file names may include 'media/' prefix, some may not
    file_name = file_field.name
    if file_name.startswith('media/') or file_name.startswith('media\\'):
        # Remove 'media/' prefix since MEDIA_ROOT already points to media folder
        file_name_for_path = file_name[6:]  # Remove 'media/'
    else:
        file_name_for_path = file_name
    
    local_path = MEDIA_ROOT / file_name_for_path
    
    if not local_path.exists():
        print(f"  ⚠️  File not found locally: {local_path}")
        return False
    
    # Check if already a Cloudinary URL (skip if already migrated)
    if file_field.name.startswith('http'):
        print(f"  ✓  Already on Cloudinary: {file_field.name[:50]}...")
        return True
    
    try:
        resource_type = get_resource_type(str(local_path))
        
        # Use the same path structure as the public_id
        # The public_id must match EXACTLY what django-cloudinary-storage expects
        # django-cloudinary-storage prepends 'media/' to all file paths (its TAG)
        # Convert Windows backslashes to forward slashes for Cloudinary
        # Remove file extension for the public_id (Cloudinary adds it back)
        public_id = file_field.name.replace('\\', '/')
        # Remove file extension
        if '.' in public_id:
            public_id = public_id.rsplit('.', 1)[0]
        
        # Add 'media/' prefix if not already present (to match django-cloudinary-storage TAG)
        if not public_id.startswith('media/'):
            public_id = 'media/' + public_id
        
        # Sanitize public_id - remove or replace invalid characters
        # Cloudinary public_id cannot contain certain special characters
        import re
        # Replace problematic characters with underscores (but keep / for paths)
        public_id = re.sub(r'[^\w\-_/.]', '_', public_id)
        
        print(f"  📤 Uploading: {file_field.name}")
        print(f"      Resource type: {resource_type}, Public ID: {public_id}")
        
        result = cloudinary.uploader.upload(
            str(local_path),
            public_id=public_id,
            resource_type=resource_type,
            type='upload',  # Ensures public access (not 'authenticated')
            overwrite=True,
            invalidate=True,
        )
        
        print(f"  ✅ Uploaded successfully: {result.get('secure_url', '')[:60]}...")
        return True
        
    except Exception as e:
        print(f"  ❌ Error uploading {file_field.name}: {e}")
        return False


def migrate_books():
    """Migrate all Book file fields to Cloudinary."""
    from core.models import Book
    
    books = Book.objects.all()
    total = books.count()
    
    print(f"\n📚 Migrating {total} books...")
    print("=" * 60)
    
    success_count = 0
    error_count = 0
    
    file_fields = ['manuscript_file', 'ebook_file', 'audiobook_file', 'cover_image', 'qr_code']
    
    for i, book in enumerate(books, 1):
        print(f"\n[{i}/{total}] Book: {book.title[:40]}...")
        
        for field_name in file_fields:
            file_field = getattr(book, field_name, None)
            if file_field and file_field.name:
                result = upload_file_to_cloudinary(file_field, 'Book', field_name)
                if result:
                    success_count += 1
                else:
                    error_count += 1
    
    print(f"\n📚 Books migration complete: {success_count} success, {error_count} errors")
    return success_count, error_count


def migrate_users():
    """Migrate all User profile pictures to Cloudinary."""
    from users.models import User
    
    users = User.objects.exclude(profile_picture='').exclude(profile_picture__isnull=True)
    total = users.count()
    
    print(f"\n👤 Migrating {total} user profile pictures...")
    print("=" * 60)
    
    success_count = 0
    error_count = 0
    
    for i, user in enumerate(users, 1):
        print(f"\n[{i}/{total}] User: {user.email[:30]}...")
        
        if user.profile_picture and user.profile_picture.name:
            result = upload_file_to_cloudinary(user.profile_picture, 'User', 'profile_picture')
            if result:
                success_count += 1
            else:
                error_count += 1
    
    print(f"\n👤 Users migration complete: {success_count} success, {error_count} errors")
    return success_count, error_count


def main():
    """Main migration function."""
    print("=" * 60)
    print("🚀 CLOUDINARY MIGRATION SCRIPT")
    print("=" * 60)
    print(f"Cloud Name: {settings.CLOUDINARY_STORAGE['CLOUD_NAME']}")
    print(f"Media Root: {MEDIA_ROOT}")
    print("=" * 60)
    
    # Confirm before proceeding
    response = input("\n⚠️  This will upload all local media files to Cloudinary. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    # Migrate books
    book_success, book_errors = migrate_books()
    
    # Migrate users
    user_success, user_errors = migrate_users()
    
    # Final summary
    print("\n" + "=" * 60)
    print("📊 MIGRATION SUMMARY")
    print("=" * 60)
    print(f"Books: {book_success} files uploaded, {book_errors} errors")
    print(f"Users: {user_success} files uploaded, {user_errors} errors")
    print(f"Total: {book_success + user_success} files uploaded, {book_errors + user_errors} errors")
    print("=" * 60)
    
    if book_errors + user_errors == 0:
        print("✅ Migration completed successfully!")
    else:
        print("⚠️  Migration completed with some errors. Check the output above.")


if __name__ == '__main__':
    main()
