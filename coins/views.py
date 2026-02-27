from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import csv
import json

from .models import (
    UserProfile, Coin, Portfolio, Holding,
    Transaction, Alert, AlertSettings, Watchlist
)


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _get_default_portfolio(user):
    portfolio, created = Portfolio.objects.get_or_create(
        user=user,
        is_default=True,
        defaults={'name': 'My Portfolio'}
    )
    return portfolio


# ─────────────────────────────────────────────
#  Auth
# ─────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            _get_or_create_profile(user)
            _get_default_portfolio(user)
            return redirect('dashboard')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'cointrack/login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        currency = request.POST.get('currency', 'USD')

        if password != password2:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
        else:
            user = User.objects.create_user(
                username=username, email=email,
                password=password, first_name=first_name, last_name=last_name
            )
            profile = UserProfile.objects.create(user=user, preferred_currency=currency)
            Portfolio.objects.create(user=user, name='My Portfolio', is_default=True)
            AlertSettings.objects.create(user=user)
            login(request, user)
            messages.success(request, f'Welcome, {first_name or username}!')
            return redirect('dashboard')
    return render(request, 'cointrack/register.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def password_reset_view(request):
    submitted = False
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        submitted = True
        # In production: integrate django.contrib.auth password reset flow
        # For now just show success UI
    return render(request, 'cointrack/password_reset.html', {'submitted': submitted})


# ─────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────

@login_required
def dashboard_view(request):
    portfolio = _get_default_portfolio(request.user)
    holdings = portfolio.holdings.select_related('coin').all()

    total_value = sum(h.current_value for h in holdings)
    total_cost = sum(h.cost_basis for h in holdings)
    total_unrealized_pnl = total_value - total_cost
    total_pnl_pct = (total_unrealized_pnl / total_cost * 100) if total_cost else Decimal('0')

    recent_transactions = portfolio.transactions.select_related('coin').order_by('-transacted_at')[:10]

    top_holdings = sorted(holdings, key=lambda h: h.current_value, reverse=True)[:5]

    # Allocation data for chart
    allocation = []
    if total_value:
        for h in top_holdings:
            pct = (h.current_value / total_value * 100) if total_value else 0
            allocation.append({
                'symbol': h.coin.symbol.upper(),
                'name': h.coin.name,
                'value': float(h.current_value),
                'pct': float(pct),
            })

    top_coins = Coin.objects.exclude(current_price__isnull=True).order_by('market_cap_rank')[:5]

    context = {
        'portfolio': portfolio,
        'holdings': holdings,
        'total_value': total_value,
        'total_cost': total_cost,
        'total_unrealized_pnl': total_unrealized_pnl,
        'total_pnl_pct': total_pnl_pct,
        'recent_transactions': recent_transactions,
        'top_holdings': top_holdings,
        'allocation': json.dumps(allocation),
        'top_coins': top_coins,
        'all_coins': Coin.objects.all().order_by('name'),
    }
    return render(request, 'cointrack/dashboard.html', context)


# ─────────────────────────────────────────────
#  Portfolio / Holdings
# ─────────────────────────────────────────────

@login_required
def portfolio_view(request):
    portfolio = _get_default_portfolio(request.user)
    holdings = portfolio.holdings.select_related('coin').all()

    total_value = sum(h.current_value for h in holdings)
    total_cost = sum(h.cost_basis for h in holdings)
    total_pnl = total_value - total_cost
    roi = (total_pnl / total_cost * 100) if total_cost else Decimal('0')

    context = {
        'portfolio': portfolio,
        'holdings': holdings,
        'total_value': total_value,
        'total_cost': total_cost,
        'total_pnl': total_pnl,
        'roi': roi,
        'all_coins': Coin.objects.all().order_by('name'),
    }
    return render(request, 'cointrack/portfolio.html', context)


@login_required
@require_POST
def add_holding_view(request):
    portfolio = _get_default_portfolio(request.user)
    coin_id = request.POST.get('coin_id')
    quantity = request.POST.get('quantity', '0')
    avg_price = request.POST.get('avg_price', '0')
    notes = request.POST.get('notes', '')

    try:
        coin = get_object_or_404(Coin, id=coin_id)
        qty = Decimal(quantity)
        price = Decimal(avg_price)

        holding, created = Holding.objects.get_or_create(
            portfolio=portfolio, coin=coin,
            defaults={'quantity': qty, 'avg_buy_price': price, 'notes': notes}
        )
        if not created:
            # Weighted average
            total_qty = holding.quantity + qty
            if total_qty > 0:
                holding.avg_buy_price = (
                    (holding.quantity * holding.avg_buy_price + qty * price) / total_qty
                )
            holding.quantity = total_qty
            holding.notes = notes or holding.notes
            holding.save()
        messages.success(request, f'Added {coin.symbol.upper()} to portfolio.')
    except (InvalidOperation, ValueError) as e:
        messages.error(request, f'Invalid values: {e}')
    return redirect('portfolio')


@login_required
@require_POST
def delete_holding_view(request, holding_id):
    portfolio = _get_default_portfolio(request.user)
    holding = get_object_or_404(Holding, id=holding_id, portfolio=portfolio)
    symbol = holding.coin.symbol.upper()
    holding.delete()
    messages.success(request, f'Removed {symbol} from portfolio.')
    return redirect('portfolio')


@login_required
def export_csv_view(request):
    portfolio = _get_default_portfolio(request.user)
    holdings = portfolio.holdings.select_related('coin').all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="portfolio.csv"'
    writer = csv.writer(response)
    writer.writerow(['Coin', 'Symbol', 'Quantity', 'Avg Buy Price', 'Current Price', 'Value', 'P&L', 'P&L %'])
    for h in holdings:
        writer.writerow([
            h.coin.name, h.coin.symbol.upper(),
            h.quantity, h.avg_buy_price,
            h.coin.current_price or 0,
            h.current_value, h.unrealized_pnl, round(h.unrealized_pnl_pct, 2)
        ])
    return response


# ─────────────────────────────────────────────
#  Markets
# ─────────────────────────────────────────────

@login_required
def markets_view(request):
    coins = Coin.objects.exclude(current_price__isnull=True).order_by('market_cap_rank')
    watchlist_ids = set(
        Watchlist.objects.filter(user=request.user).values_list('coin_id', flat=True)
    )
    total_market_cap = sum(c.market_cap or 0 for c in coins)

    context = {
        'coins': coins,
        'watchlist_ids': watchlist_ids,
        'total_market_cap': total_market_cap,
    }
    return render(request, 'cointrack/markets.html', context)


@login_required
def coin_detail_view(request, slug):
    coin = get_object_or_404(Coin, slug=slug)
    portfolio = _get_default_portfolio(request.user)
    try:
        holding = Holding.objects.get(portfolio=portfolio, coin=coin)
    except Holding.DoesNotExist:
        holding = None

    in_watchlist = Watchlist.objects.filter(user=request.user, coin=coin).exists()

    context = {
        'coin': coin,
        'holding': holding,
        'in_watchlist': in_watchlist,
        'all_coins': Coin.objects.all().order_by('name'),
    }
    return render(request, 'cointrack/coin_detail.html', context)


# ─────────────────────────────────────────────
#  Transactions
# ─────────────────────────────────────────────

@login_required
def transactions_view(request):
    portfolio = _get_default_portfolio(request.user)
    txns = portfolio.transactions.select_related('coin').all()

    # Filters
    tx_type = request.GET.get('type', '')
    coin_filter = request.GET.get('coin', '')
    search = request.GET.get('search', '')

    if tx_type:
        txns = txns.filter(transaction_type=tx_type)
    if coin_filter:
        txns = txns.filter(coin__symbol__iexact=coin_filter)
    if search:
        txns = txns.filter(coin__name__icontains=search)

    total_bought = sum(
        t.total_value for t in txns if t.transaction_type in ('buy', 'receive')
    )
    total_sold = sum(
        t.total_value for t in txns if t.transaction_type in ('sell', 'send')
    )

    context = {
        'transactions': txns,
        'total_bought': total_bought,
        'total_sold': total_sold,
        'realized_pnl': total_sold - total_bought,
        'tx_count': txns.count(),
        'all_coins': Coin.objects.all().order_by('name'),
        'filter_type': tx_type,
        'filter_coin': coin_filter,
    }
    return render(request, 'cointrack/transactions.html', context)


@login_required
@require_POST
def add_transaction_view(request):
    portfolio = _get_default_portfolio(request.user)
    coin_id = request.POST.get('coin_id')
    tx_type = request.POST.get('transaction_type', 'buy')
    quantity = request.POST.get('quantity', '0')
    price = request.POST.get('price_per_coin', '0')
    fee = request.POST.get('fee', '0')
    exchange = request.POST.get('exchange', '')
    notes = request.POST.get('notes', '')
    transacted_at = request.POST.get('transacted_at') or timezone.now()

    try:
        coin = get_object_or_404(Coin, id=coin_id)
        qty = Decimal(quantity)
        unit_price = Decimal(price)
        tx_fee = Decimal(fee)

        with db_transaction.atomic():
            Transaction.objects.create(
                portfolio=portfolio, coin=coin,
                transaction_type=tx_type, quantity=qty,
                price_per_coin=unit_price, fee=tx_fee,
                exchange=exchange, notes=notes,
                transacted_at=transacted_at
            )
            # Update holding
            holding, created = Holding.objects.get_or_create(
                portfolio=portfolio, coin=coin,
                defaults={'quantity': Decimal('0'), 'avg_buy_price': Decimal('0')}
            )
            if tx_type in ('buy', 'receive'):
                total_qty = holding.quantity + qty
                if total_qty > 0:
                    holding.avg_buy_price = (
                        (holding.quantity * holding.avg_buy_price + qty * unit_price) / total_qty
                    )
                holding.quantity = total_qty
            elif tx_type in ('sell', 'send'):
                holding.quantity = max(Decimal('0'), holding.quantity - qty)
            holding.save()
            if holding.quantity == 0:
                holding.delete()

        messages.success(request, 'Transaction recorded.')
    except (InvalidOperation, ValueError) as e:
        messages.error(request, f'Error: {e}')
    return redirect('transactions')


@login_required
@require_POST
def delete_transaction_view(request, tx_id):
    portfolio = _get_default_portfolio(request.user)
    tx = get_object_or_404(Transaction, id=tx_id, portfolio=portfolio)
    tx.delete()
    messages.success(request, 'Transaction deleted.')
    return redirect('transactions')


@login_required
def export_transactions_csv_view(request):
    portfolio = _get_default_portfolio(request.user)
    txns = portfolio.transactions.select_related('coin').all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Coin', 'Symbol', 'Quantity', 'Price', 'Fee', 'Total', 'Exchange'])
    for t in txns:
        writer.writerow([
            t.transacted_at.strftime('%Y-%m-%d %H:%M'),
            t.transaction_type,
            t.coin.name, t.coin.symbol.upper(),
            t.quantity, t.price_per_coin, t.fee, t.total_value, t.exchange
        ])
    return response


# ─────────────────────────────────────────────
#  Alerts
# ─────────────────────────────────────────────

@login_required
def alerts_view(request):
    user_alerts = Alert.objects.filter(user=request.user).select_related('coin').order_by('-created_at')
    triggered = user_alerts.filter(triggered_at__isnull=False, is_active=True)
    active = user_alerts.filter(triggered_at__isnull=True, is_active=True)

    try:
        alert_settings = request.user.alert_settings
    except AlertSettings.DoesNotExist:
        alert_settings = AlertSettings.objects.create(user=request.user)

    context = {
        'alerts': active,
        'triggered_alerts': triggered,
        'alert_settings': alert_settings,
        'all_coins': Coin.objects.all().order_by('name'),
    }
    return render(request, 'cointrack/alerts.html', context)


@login_required
@require_POST
def add_alert_view(request):
    coin_id = request.POST.get('coin_id')
    condition = request.POST.get('condition', 'above')
    target = request.POST.get('target_value', '0')
    frequency = request.POST.get('frequency', 'once')

    try:
        coin = get_object_or_404(Coin, id=coin_id)
        Alert.objects.create(
            user=request.user, coin=coin,
            condition=condition,
            target_value=Decimal(target),
            frequency=frequency,
        )
        messages.success(request, f'Alert set for {coin.symbol.upper()}.')
    except (InvalidOperation, ValueError) as e:
        messages.error(request, f'Error: {e}')
    return redirect('alerts')


@login_required
@require_POST
def update_alert_settings_view(request):
    settings_obj, _ = AlertSettings.objects.get_or_create(user=request.user)
    settings_obj.email_notifications = request.POST.get('email_notifications') == 'on'
    settings_obj.browser_notifications = request.POST.get('browser_notifications') == 'on'
    settings_obj.notification_frequency = request.POST.get('notification_frequency', 'instant')
    settings_obj.save()
    messages.success(request, 'Notification settings updated.')
    return redirect('alerts')


# ─────────────────────────────────────────────
#  Settings
# ─────────────────────────────────────────────

@login_required
def settings_view(request):
    profile = _get_or_create_profile(request.user)
    context = {'profile': profile}
    return render(request, 'cointrack/settings.html', context)


@login_required
@require_POST
def update_profile_view(request):
    user = request.user
    profile = _get_or_create_profile(user)

    user.first_name = request.POST.get('first_name', user.first_name)
    user.last_name = request.POST.get('last_name', user.last_name)
    new_username = request.POST.get('username', user.username).strip()
    new_email = request.POST.get('email', user.email).strip()

    if new_username != user.username and User.objects.filter(username=new_username).exists():
        messages.error(request, 'Username already taken.')
        return redirect('settings')
    if new_email != user.email and User.objects.filter(email=new_email).exists():
        messages.error(request, 'Email already in use.')
        return redirect('settings')

    user.username = new_username
    user.email = new_email
    user.save()

    profile.bio = request.POST.get('bio', profile.bio)
    if request.FILES.get('avatar'):
        profile.avatar = request.FILES['avatar']
    profile.save()

    messages.success(request, 'Profile updated.')
    return redirect('settings')


@login_required
@require_POST
def change_password_view(request):
    user = request.user
    current = request.POST.get('current_password', '')
    new_pw = request.POST.get('new_password', '')
    new_pw2 = request.POST.get('new_password2', '')

    if not user.check_password(current):
        messages.error(request, 'Current password is incorrect.')
    elif new_pw != new_pw2:
        messages.error(request, 'New passwords do not match.')
    elif len(new_pw) < 8:
        messages.error(request, 'Password must be at least 8 characters.')
    else:
        user.set_password(new_pw)
        user.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Password changed successfully.')
    return redirect('settings')


@login_required
@require_POST
def setup_2fa_view(request):
    profile = _get_or_create_profile(request.user)
    profile.two_factor_enabled = True
    profile.save()
    messages.success(request, '2FA enabled.')
    return redirect('settings')


@login_required
@require_POST
def disable_2fa_view(request):
    profile = _get_or_create_profile(request.user)
    profile.two_factor_enabled = False
    profile.save()
    messages.success(request, '2FA disabled.')
    return redirect('settings')


@login_required
@require_POST
def revoke_all_sessions_view(request):
    from django.contrib.sessions.backends.db import SessionStore
    request.session.flush()
    login(request, request.user)
    messages.success(request, 'All other sessions revoked.')
    return redirect('settings')


@login_required
@require_POST
def update_preferences_view(request):
    profile = _get_or_create_profile(request.user)
    profile.preferred_currency = request.POST.get('currency', profile.preferred_currency)
    profile.timezone = request.POST.get('timezone', profile.timezone)
    profile.number_format = request.POST.get('number_format', profile.number_format)
    profile.show_portfolio_chart = request.POST.get('show_portfolio_chart') == 'on'
    profile.show_allocation = request.POST.get('show_allocation') == 'on'
    profile.show_recent_activity = request.POST.get('show_recent_activity') == 'on'
    profile.show_top_holdings = request.POST.get('show_top_holdings') == 'on'
    profile.save()
    messages.success(request, 'Preferences saved.')
    return redirect('settings')


@login_required
@require_POST
def add_api_key_view(request):
    # Placeholder — real implementation would store encrypted API keys
    exchange = request.POST.get('exchange', '')
    messages.success(request, f'{exchange} API key connected.')
    return redirect('settings')


@login_required
@require_POST
def upgrade_view(request):
    profile = _get_or_create_profile(request.user)
    profile.is_pro = True
    profile.save()
    messages.success(request, 'Upgraded to Pro!')
    return redirect('settings')


@login_required
@require_POST
def clear_holdings_view(request):
    portfolio = _get_default_portfolio(request.user)
    portfolio.holdings.all().delete()
    messages.success(request, 'All holdings cleared.')
    return redirect('portfolio')


@login_required
@require_POST
def delete_account_view(request):
    password = request.POST.get('password', '')
    if request.user.check_password(password):
        request.user.delete()
        messages.success(request, 'Account deleted.')
        return redirect('login')
    messages.error(request, 'Incorrect password.')
    return redirect('settings')


# ─────────────────────────────────────────────
#  Static pages
# ─────────────────────────────────────────────

def terms_view(request):
    return render(request, 'cointrack/terms.html')


def privacy_view(request):
    return render(request, 'cointrack/privacy.html')


# ─────────────────────────────────────────────
#  AJAX / API helpers
# ─────────────────────────────────────────────

@login_required
def toggle_watchlist_view(request, coin_id):
    coin = get_object_or_404(Coin, id=coin_id)
    wl, created = Watchlist.objects.get_or_create(user=request.user, coin=coin)
    if not created:
        wl.delete()
        return JsonResponse({'status': 'removed'})
    return JsonResponse({'status': 'added'})
