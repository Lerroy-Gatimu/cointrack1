from django.contrib import admin
from .models import UserProfile, Coin, Portfolio, Holding, Transaction, Alert, AlertSettings, Watchlist


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'preferred_currency', 'is_pro', 'two_factor_enabled', 'created_at']
    list_filter = ['preferred_currency', 'is_pro', 'two_factor_enabled']
    search_fields = ['user__username', 'user__email']


@admin.register(Coin)
class CoinAdmin(admin.ModelAdmin):
    list_display = ['name', 'symbol', 'market_cap_rank', 'current_price', 'price_change_24h', 'last_updated']
    list_filter = ['market_cap_rank']
    search_fields = ['name', 'symbol', 'coingecko_id']
    prepopulated_fields = {'slug': ('coingecko_id',)}
    ordering = ['market_cap_rank']


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'is_default', 'created_at']
    list_filter = ['is_default']
    search_fields = ['user__username', 'name']


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'coin', 'quantity', 'avg_buy_price', 'updated_at']
    search_fields = ['portfolio__user__username', 'coin__name', 'coin__symbol']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'coin', 'transaction_type', 'quantity', 'price_per_coin', 'transacted_at']
    list_filter = ['transaction_type']
    search_fields = ['portfolio__user__username', 'coin__name', 'coin__symbol']
    ordering = ['-transacted_at']


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['user', 'coin', 'condition', 'target_value', 'is_active', 'triggered_at']
    list_filter = ['condition', 'is_active', 'frequency']
    search_fields = ['user__username', 'coin__symbol']


@admin.register(AlertSettings)
class AlertSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_notifications', 'browser_notifications', 'notification_frequency']


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'coin', 'added_at']
    search_fields = ['user__username', 'coin__symbol']
