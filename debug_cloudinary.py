#!/usr/bin/env python
"""Compare DB paths with Cloudinary public_ids to find mismatches."""

import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

import cloudinary
import cloudinary.api
from django.conf import settings
from core.models import Book

cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
)

print("=" * 80)
print("CLOUDINARY VS DATABASE PATH COMPARISON")
print("=" * 80)

# Get all raw resources from Cloudinary
print("\n--- RAW RESOURCES IN CLOUDINARY ---")
raw_resources = []
try:
    result = cloudinary.api.resources(type='upload', resource_type='raw', max_results=100)
    for r in result.get('resources', []):
        raw_resources.append(r['public_id'])
        print(f"Cloudinary: {r['public_id']}")
except Exception as e:
    print(f"Error: {e}")

# Get all ebook paths from DB
print("\n--- EBOOK PATHS IN DATABASE ---")
for book in Book.objects.filter(ebook_file__isnull=False).exclude(ebook_file=''):
    db_path = book.ebook_file.name
    print(f"DB: {db_path}")
    
    # Check if it matches with extension
    normalized_db = "media/" + db_path if not db_path.startswith('media/') else db_path
    found = False
    for cloudinary_path in raw_resources:
        if cloudinary_path.startswith(normalized_db):
            print(f"  -> MATCHES: {cloudinary_path}")
            found = True
            break
    if not found:
        print(f"  -> NOT FOUND in Cloudinary!")

# Get all manuscript paths from DB
print("\n--- MANUSCRIPT PATHS IN DATABASE ---")
for book in Book.objects.filter(manuscript_file__isnull=False).exclude(manuscript_file=''):
    db_path = book.manuscript_file.name
    print(f"DB: {db_path}")
    
    # Check if it matches with extension
    normalized_db = "media/" + db_path if not db_path.startswith('media/') else db_path
    found = False
    for cloudinary_path in raw_resources:
        if cloudinary_path.startswith(normalized_db):
            print(f"  -> MATCHES: {cloudinary_path}")
            found = True
            break
    if not found:
        print(f"  -> NOT FOUND in Cloudinary!")

print("\n" + "=" * 80)
