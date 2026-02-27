from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.conf import settings
from decimal import Decimal


class UserProfile(models.Model):
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('JPY', 'Japanese Yen (¥)'),
        ('KES', 'Kenyan Shilling (KSh)'),
        ('NGN', 'Nigerian Naira (₦)'),
    ]
    TIMEZONE_CHOICES = [
        ('UTC', 'UTC'),
        ('Africa/Nairobi', 'Africa/Nairobi (EAT)'),
        ('Africa/Lagos', 'Africa/Lagos (WAT)'),
        ('America/New_York', 'America/New_York (EST)'),
        ('America/Los_Angeles', 'America/Los_Angeles (PST)'),
        ('Europe/London', 'Europe/London (GMT)'),
        ('Asia/Tokyo', 'Asia/Tokyo (JST)'),
    ]
    NUMBER_FORMAT_CHOICES = [
        ('1,234.56', '1,234.56'),
        ('1.234,56', '1.234,56'),
        ('1 234.56', '1 234.56'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    preferred_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC')
    number_format = models.CharField(max_length=10, choices=NUMBER_FORMAT_CHOICES, default='1,234.56')

    show_portfolio_chart = models.BooleanField(default=True)
    show_allocation = models.BooleanField(default=True)
    show_recent_activity = models.BooleanField(default=True)
    show_top_holdings = models.BooleanField(default=True)

    two_factor_enabled = models.BooleanField(default=False)
    is_pro = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} Profile'


class Coin(models.Model):
    coingecko_id = models.CharField(max_length=100, unique=True)
    symbol = models.CharField(max_length=20, db_index=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    current_price = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    market_cap = models.BigIntegerField(null=True, blank=True)
    market_cap_rank = models.IntegerField(null=True, blank=True)
    total_volume = models.BigIntegerField(null=True, blank=True)

    price_change_1h = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    price_change_24h = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    price_change_7d = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    ath = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    ath_date = models.DateTimeField(null=True, blank=True)
    atl = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True)
    atl_date = models.DateTimeField(null=True, blank=True)

    circulating_supply = models.DecimalField(max_digits=30, decimal_places=4, null=True, blank=True)
    total_supply = models.DecimalField(max_digits=30, decimal_places=4, null=True, blank=True)
    max_supply = models.DecimalField(max_digits=30, decimal_places=4, null=True, blank=True)

    description = models.TextField(blank=True, default='')
    image_url = models.URLField(max_length=500, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['market_cap_rank']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.coingecko_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.symbol.upper()})'


class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios')
    name = models.CharField(max_length=100, default='My Portfolio')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')

    def __str__(self):
        return f'{self.user.username} — {self.name}'


class Holding(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings')
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE, related_name='holdings')
    quantity = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'))
    avg_buy_price = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'))
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('portfolio', 'coin')

    @property
    def current_value(self):
        if self.coin.current_price:
            return self.quantity * self.coin.current_price
        return Decimal('0')

    @property
    def cost_basis(self):
        return self.quantity * self.avg_buy_price

    @property
    def unrealized_pnl(self):
        return self.current_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self):
        if self.cost_basis and self.cost_basis != 0:
            return (self.unrealized_pnl / self.cost_basis) * 100
        return Decimal('0')

    def __str__(self):
        return f'{self.portfolio.user.username} — {self.coin.symbol.upper()}'


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('receive', 'Receive'),
        ('send', 'Send'),
    ]

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='transactions')
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=30, decimal_places=10)
    price_per_coin = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'))
    fee = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal('0'))
    exchange = models.CharField(max_length=100, blank=True, default='')
    wallet = models.CharField(max_length=200, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    transacted_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transacted_at']

    @property
    def total_value(self):
        return self.quantity * self.price_per_coin

    def __str__(self):
        return f'{self.transaction_type.upper()} {self.quantity} {self.coin.symbol.upper()}'


class Alert(models.Model):
    CONDITION_CHOICES = [
        ('above', 'Price Above'),
        ('below', 'Price Below'),
        ('change_up', '% Change Up'),
        ('change_down', '% Change Down'),
    ]
    FREQUENCY_CHOICES = [
        ('once', 'Once'),
        ('always', 'Always'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE, related_name='alerts')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    target_value = models.DecimalField(max_digits=30, decimal_places=10)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='once')
    is_active = models.BooleanField(default=True)
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} — {self.coin.symbol.upper()} {self.condition} {self.target_value}'


class AlertSettings(models.Model):
    FREQUENCY_CHOICES = [
        ('instant', 'Instant'),
        ('hourly', 'Hourly Digest'),
        ('daily', 'Daily Digest'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='alert_settings')
    email_notifications = models.BooleanField(default=True)
    browser_notifications = models.BooleanField(default=False)
    notification_frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='instant')
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} Alert Settings'


class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlist')
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE, related_name='watchlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'coin')

    def __str__(self):
        return f'{self.user.username} watching {self.coin.symbol.upper()}'
