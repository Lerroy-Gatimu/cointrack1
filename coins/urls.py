from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('password-reset/', views.password_reset_view, name='password_reset'),

    # Core pages
    path('', views.dashboard_view, name='dashboard'),
    path('portfolio/', views.portfolio_view, name='portfolio'),
    path('markets/', views.markets_view, name='markets'),
    path('transactions/', views.transactions_view, name='transactions'),
    path('alerts/', views.alerts_view, name='alerts'),
    path('settings/', views.settings_view, name='settings'),

    # Coin detail
    path('coin/<slug:slug>/', views.coin_detail_view, name='coin_detail'),

    # Holdings
    path('portfolio/add/', views.add_holding_view, name='add_holding'),
    path('portfolio/delete/<int:holding_id>/', views.delete_holding_view, name='delete_holding'),
    path('portfolio/export/', views.export_csv_view, name='export_csv'),

    # Transactions
    path('transactions/add/', views.add_transaction_view, name='add_transaction'),
    path('transactions/delete/<int:tx_id>/', views.delete_transaction_view, name='delete_transaction'),
    path('transactions/export/', views.export_transactions_csv_view, name='export_transactions_csv'),

    # Alerts
    path('alerts/add/', views.add_alert_view, name='add_alert'),
    path('alerts/settings/', views.update_alert_settings_view, name='update_alert_settings'),

    # Settings actions
    path('settings/profile/', views.update_profile_view, name='update_profile'),
    path('settings/password/', views.change_password_view, name='change_password'),
    path('settings/2fa/setup/', views.setup_2fa_view, name='setup_2fa'),
    path('settings/2fa/disable/', views.disable_2fa_view, name='disable_2fa'),
    path('settings/sessions/revoke/', views.revoke_all_sessions_view, name='revoke_all_sessions'),
    path('settings/preferences/', views.update_preferences_view, name='update_preferences'),
    path('settings/api-key/', views.add_api_key_view, name='add_api_key'),
    path('settings/upgrade/', views.upgrade_view, name='upgrade'),
    path('settings/clear-holdings/', views.clear_holdings_view, name='clear_holdings'),
    path('settings/delete-account/', views.delete_account_view, name='delete_account'),

    # Static pages
    path('terms/', views.terms_view, name='terms'),
    path('privacy/', views.privacy_view, name='privacy'),

    # AJAX
    path('watchlist/toggle/<int:coin_id>/', views.toggle_watchlist_view, name='toggle_watchlist'),
]
