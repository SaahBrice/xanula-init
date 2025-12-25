"""
URL configuration for xanula_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    
    # Internationalization (language switching)
    path("i18n/", include("django.conf.urls.i18n")),
    
    # Authentication (django-allauth)
    path("accounts/", include("allauth.urls")),
    
    # Core app (book-related functionality) - must be before PWA for homepage
    path("", include("core.urls")),
    
    # PWA
    path("pwa/", include(("pwa.urls", "pwa"), namespace="pwa")),
    
    # Users app (account-related functionality)
    # path("users/", include("users.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    
    # Custom view to serve foliate-js with correct MIME type for ES modules
    from django.http import HttpResponse, Http404
    import os
    
    def serve_js_module(request, path):
        """Serve JavaScript files with correct Content-Type for ES modules"""
        base_path = settings.STATICFILES_DIRS[0] / 'js' / 'foliate-js'
        file_path = base_path / path
        
        # Security: prevent directory traversal
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(base_path.resolve())):
                raise Http404("File not found")
        except (ValueError, OSError):
            raise Http404("File not found")
        
        if file_path.exists() and file_path.is_file():
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Determine MIME type
            if str(file_path).endswith('.mjs') or str(file_path).endswith('.js'):
                content_type = 'application/javascript'
            else:
                content_type = 'application/octet-stream'
            
            response = HttpResponse(content, content_type=content_type)
            response['Cache-Control'] = 'no-cache'
            return response
        
        raise Http404("File not found")
    
    urlpatterns.insert(0, path('static/js/foliate-js/<path:path>', serve_js_module))

