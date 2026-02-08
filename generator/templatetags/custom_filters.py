from django import template

register = template.Library()


@register.filter
def media_urls_absolute(value, request):
    """Преобразует относительные URL изображений в абсолютные (для отображения и скачивания)."""
    if not value or not request:
        return value
    parts = [p.strip() for p in value.split('|') if p.strip()]
    if not parts:
        return value
    result = []
    for part in parts:
        if part.startswith('http://') or part.startswith('https://'):
            result.append(part)
        else:
            result.append(request.build_absolute_uri(part))
    return '|'.join(result)


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
