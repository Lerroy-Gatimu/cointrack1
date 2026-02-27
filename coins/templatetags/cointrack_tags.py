from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()


@register.filter
def split(value, delimiter=','):
    """Split a string by a delimiter. Usage: {{ "a,b,c"|split:"," }}"""
    if value is None:
        return []
    return str(value).split(delimiter)


@register.filter
def index(lst, i):
    """Get item by index. Usage: {{ mylist|index:0 }}"""
    try:
        return lst[int(i)]
    except (IndexError, TypeError, ValueError):
        return ''


@register.filter
def mul(value, arg):
    """Multiply. Usage: {{ value|mul:100 }}"""
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def div(value, arg):
    """Divide. Usage: {{ value|div:100 }}"""
    try:
        return float(value) / float(arg)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def sub(value, arg):
    """Subtract. Usage: {{ value|sub:arg }}"""
    try:
        return float(value) - float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def pct(value, total):
    """Percentage. Usage: {{ value|pct:total }}"""
    try:
        return round(float(value) / float(total) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def abs_val(value):
    """Absolute value. Usage: {{ value|abs_val }}"""
    try:
        return abs(float(value))
    except (TypeError, ValueError):
        return 0


@register.filter
def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@register.filter
def currency(value, symbol='$'):
    """Format as currency. Usage: {{ value|currency:"$" }}"""
    try:
        return f'{symbol}{float(value):,.2f}'
    except (TypeError, ValueError):
        return f'{symbol}0.00'


@register.filter
def positive(value):
    """Return True if value > 0."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False
