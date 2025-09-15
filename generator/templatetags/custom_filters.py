from django import template

register = template.Library()

@register.filter
def split(value, delimiter):
    """Разделяет строку по разделителю"""
    if not value:
        return []
    return value.split(delimiter)

@register.filter
def get_first_text(value):
    """Получает первую версию текста (до первого разделителя)"""
    if not value:
        return ""
    parts = value.split("--- Перегенерация")
    return parts[0].strip()

@register.filter 
def count_versions(value):
    """Подсчитывает количество версий текста"""
    if not value:
        return 1
    return value.count("--- Перегенерация") + 1
