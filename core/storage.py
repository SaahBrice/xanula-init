"""
Custom Cloudinary storage backends for different file types.

django-cloudinary-storage's default MediaCloudinaryStorage treats all files as images.
We need different storage backends for:
- Images (covers, profile pictures, QR codes) - use 'image' resource type
- Documents (manuscripts, ebooks - PDF, EPUB, DOCX, TXT) - use 'raw' resource type  
- Audio/Video (audiobooks) - use 'video' resource type
"""

import cloudinary
import cloudinary.utils
from cloudinary_storage.storage import (
    MediaCloudinaryStorage,
    RawMediaCloudinaryStorage,
    VideoMediaCloudinaryStorage,
)
from django.conf import settings


def _ensure_cloudinary_config():
    """Ensure Cloudinary is configured from Django settings."""
    if not cloudinary.config().cloud_name:
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_STORAGE.get('CLOUD_NAME'),
            api_key=settings.CLOUDINARY_STORAGE.get('API_KEY'),
            api_secret=settings.CLOUDINARY_STORAGE.get('API_SECRET'),
        )


class ImageCloudinaryStorage(MediaCloudinaryStorage):
    """Storage for image files (covers, profile pictures, QR codes)."""
    pass  # Uses default image resource type


class RawCloudinaryStorage(RawMediaCloudinaryStorage):
    """
    Storage for raw/document files (PDFs, EPUB, DOCX, TXT).
    Queries Cloudinary to find the correct resource and returns its URL.
    """
    
    def url(self, name):
        """Get the Cloudinary URL for a raw file."""
        if not name:
            return ''
        
        _ensure_cloudinary_config()
        
        # Construct the public_id with media folder
        if name.startswith('media/') or name.startswith('media\\'):
            public_id = name.replace('\\', '/')
        else:
            public_id = f"media/{name}".replace('\\', '/')
        
        # Try to get the resource from Cloudinary to get correct URL
        import cloudinary.api
        
        # Try with the exact public_id first
        for try_id in [public_id, public_id + '.pdf', public_id + '.epub', public_id + '.txt', public_id + '.docx']:
            try:
                result = cloudinary.api.resource(try_id, resource_type='raw')
                # Found it! Return the secure URL
                return result.get('secure_url', '')
            except Exception:
                continue
        
        # Fallback: Return a standard URL (may not work if file doesn't exist)
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type='raw',
            type='upload',
            secure=True,
        )
        return url


class VideoCloudinaryStorage(VideoMediaCloudinaryStorage):
    """Storage for video/audio files (audiobooks, video content)."""
    pass  # Uses 'video' resource type from parent


