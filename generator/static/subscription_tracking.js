/**
 * Скрипт для отслеживания кликов по кнопке "Купить доступ"
 * Автоматически логирует все клики по ссылкам на Telegram бота
 */

(function() {
    'use strict';
    
    // Определяем название страницы на основе URL
    function getPageName() {
        const path = window.location.pathname;
        if (path.includes('profile')) return 'profile';
        if (path.includes('wall')) return 'wall';
        if (path.includes('gigagenerator') || path.includes('index')) return 'generator';
        if (path.includes('landing') || path === '/') return 'landing';
        if (path.includes('token-required')) return 'token_required';
        if (path.includes('limit-exceeded')) return 'limit_exceeded';
        if (path.includes('invalid-token')) return 'invalid_token';
        if (path.includes('edit-profile')) return 'edit_profile';
        if (path.includes('home')) return 'home';
        return 'unknown';
    }
    
    // Функция для отправки данных о клике
    function trackClick(event) {
        const link = event.currentTarget;
        const href = link.getAttribute('href');
        
        // Проверяем, что это ссылка на Telegram бота
        if (!href || !href.includes('t.me/Ghostcopywriterregistration_bot')) {
            return; // Не отслеживаем другие ссылки
        }
        
        // Отправляем данные на сервер
        fetch('/api/track-subscription-click/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                page_url: window.location.href,
                page_name: getPageName()
            })
        }).catch(function(error) {
            // Игнорируем ошибки - не прерываем переход по ссылке
            console.log('Click tracking error (ignored):', error);
        });
    }
    
    // Функция для получения CSRF токена
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    // Инициализация отслеживания после загрузки DOM
    function initTracking() {
        // Находим все ссылки на Telegram бота
        const links = document.querySelectorAll('a[href*="t.me/Ghostcopywriterregistration_bot"]');
        
        // Добавляем обработчик клика к каждой ссылке
        links.forEach(function(link) {
            link.addEventListener('click', trackClick);
        });
        
        // Также отслеживаем динамически добавленные ссылки через MutationObserver
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) { // Element node
                        const newLinks = node.querySelectorAll ? 
                            node.querySelectorAll('a[href*="t.me/Ghostcopywriterregistration_bot"]') : [];
                        newLinks.forEach(function(link) {
                            link.addEventListener('click', trackClick);
                        });
                        
                        // Проверяем сам узел, если это ссылка
                        if (node.tagName === 'A' && node.href && node.href.includes('t.me/Ghostcopywriterregistration_bot')) {
                            node.addEventListener('click', trackClick);
                        }
                    }
                });
            });
        });
        
        // Начинаем наблюдение за изменениями в DOM
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    // Запускаем инициализацию
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTracking);
    } else {
        initTracking();
    }
})();
