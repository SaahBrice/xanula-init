from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin for the User model.
    Configured for email-based authentication.
    """
    
    # List display
    list_display = (
        'email',
        'display_name',
        'earnings_balance',
        'is_staff',
        'is_active',
        'date_joined',
    )
    
    list_filter = (
        'is_staff',
        'is_superuser',
        'is_active',
        'date_joined',
    )
    
    search_fields = (
        'email',
        'display_name',
        'bio',
    )
    
    ordering = ('-date_joined',)
    
    # Remove username from fieldsets, add custom fields
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        (_('Personal info'), {
            'fields': ('display_name', 'bio', 'profile_picture')
        }),
        (_('Balance & Referral'), {
            'fields': ('earnings_balance', 'referral_code'),
            'description': 'User balance and referral code. Balance is editable.',
        }),
        (_('Wishlist'), {
            'fields': ('wishlist',),
            'classes': ('collapse',),
        }),
        (_('OAuth info'), {
            'fields': ('google_account_id',),
            'classes': ('collapse',),
        }),
        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            ),
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined')
        }),
    )
    
    filter_horizontal = ('wishlist', 'groups', 'user_permissions')
    
    # Fields for creating a new user in admin
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'display_name',
                'password1',
                'password2',
                'is_staff',
                'is_active',
            ),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')
