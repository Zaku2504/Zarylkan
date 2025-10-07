// Основной JavaScript файл для приложения бронирования билетов

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация всех компонентов
    initDateInputs();
    initCityAutocomplete();
    initFormValidation();
    initFlightSearch();
    initBookingForms();
    initTooltips();
});

// Настройка полей даты
function initDateInputs() {
    const departureDate = document.querySelector('input[name="departure_date"]');
    const returnDate = document.querySelector('input[name="return_date"]');
    
    if (departureDate) {
        // Установка минимальной даты (сегодня)
        const now = new Date();
        const formatted = now.toISOString().slice(0, 16);
        departureDate.min = formatted;
        
        // При изменении даты вылета, обновляем минимальную дату возврата
        departureDate.addEventListener('change', function() {
            if (returnDate && this.value) {
                returnDate.min = this.value;
                // Очистка даты возврата если она раньше новой даты вылета
                if (returnDate.value && returnDate.value < this.value) {
                    returnDate.value = '';
                }
            }
        });
    }
}

// Автодополнение для городов
function initCityAutocomplete() {
    const cityInputs = document.querySelectorAll('#departure-city, #arrival-city, input[name="departure_city"], input[name="arrival_city"]');
    
    cityInputs.forEach(input => {
        if (input) {
            setupCityAutocomplete(input);
        }
    });
}

function setupCityAutocomplete(input) {
    let timeout;
    let currentSuggestions = [];
    
    // Создание контейнера для предложений
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'autocomplete-suggestions';
    suggestionsContainer.style.cssText = `
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #ddd;
        border-top: none;
        border-radius: 0 0 8px 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        max-height: 200px;
        overflow-y: auto;
        z-index: 1000;
        display: none;
    `;
    
    // Обертка для относительного позиционирования
    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    wrapper.appendChild(suggestionsContainer);
    
    input.addEventListener('input', function() {
        clearTimeout(timeout);
        const query = this.value.trim();
        
        if (query.length < 1) {  // Уменьшаем минимальную длину
            hideSuggestions();
            return;
        }
        
        timeout = setTimeout(() => {
            fetchCitySuggestions(query, suggestionsContainer, input);
        }, 150);  // Уменьшаем задержку для более быстрого отклика
    });
    
    input.addEventListener('blur', function() {
        // Задержка для обработки клика по предложению
        setTimeout(() => hideSuggestions(), 150);
    });
    
    input.addEventListener('focus', function() {
        if (currentSuggestions.length > 0 && this.value.length >= 1) {
            suggestionsContainer.style.display = 'block';
        }
    });
    
    // Добавляем поддержку клавиатуры
    input.addEventListener('keydown', function(e) {
        const items = suggestionsContainer.querySelectorAll('.autocomplete-item');
        if (items.length === 0) return;
        
        let currentIndex = -1;
        items.forEach((item, index) => {
            if (item.classList.contains('selected')) {
                currentIndex = index;
            }
        });
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                currentIndex = Math.min(currentIndex + 1, items.length - 1);
                updateSelection(items, currentIndex);
                break;
            case 'ArrowUp':
                e.preventDefault();
                currentIndex = Math.max(currentIndex - 1, -1);
                updateSelection(items, currentIndex);
                break;
            case 'Enter':
                e.preventDefault();
                if (currentIndex >= 0 && currentIndex < items.length) {
                    items[currentIndex].click();
                }
                break;
            case 'Escape':
                hideSuggestions();
                break;
        }
    });
    
    function hideSuggestions() {
        suggestionsContainer.style.display = 'none';
    }
    
    function updateSelection(items, selectedIndex) {
        items.forEach((item, index) => {
            item.classList.toggle('selected', index === selectedIndex);
            if (index === selectedIndex) {
                item.style.backgroundColor = '#007bff';
                item.style.color = 'white';
                item.style.transform = 'translateX(2px)';
            } else {
                item.style.backgroundColor = 'transparent';
                item.style.color = 'inherit';
                item.style.transform = 'translateX(0)';
            }
        });
    }
    
    function fetchCitySuggestions(query, container, targetInput) {
        fetch(`/api/cities?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(cities => {
                currentSuggestions = cities;
                displaySuggestions(cities, container, targetInput);
            })
            .catch(error => {
                console.error('Ошибка получения городов:', error);
            });
    }
    
    function displaySuggestions(cities, container, targetInput) {
        container.innerHTML = '';
        
        if (cities.length === 0) {
            const noResults = document.createElement('div');
            noResults.className = 'autocomplete-item text-muted';
            noResults.style.cssText = 'padding: 12px; font-style: italic;';
            noResults.textContent = 'Города не найдены';
            container.appendChild(noResults);
            container.style.display = 'block';
            return;
        }
        
        cities.forEach(city => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.style.cssText = `
                padding: 12px;
                cursor: pointer;
                border-bottom: 1px solid #f0f0f0;
                transition: all 0.2s ease;
                border-radius: 0;
                font-size: 14px;
            `;
            
            // Добавляем hover эффект
            item.addEventListener('mouseenter', function() {
                if (!this.classList.contains('selected')) {
                    this.style.backgroundColor = '#f8f9fa';
                    this.style.transform = 'translateX(2px)';
                }
            });
            
            item.addEventListener('mouseleave', function() {
                if (!this.classList.contains('selected')) {
                    this.style.backgroundColor = 'transparent';
                    this.style.transform = 'translateX(0)';
                }
            });
            item.textContent = city;
            
            item.addEventListener('click', function(e) {
                e.preventDefault();
                targetInput.value = city;
                container.style.display = 'none';
                targetInput.focus();
                
                // Триггерим событие input для обновления формы
                targetInput.dispatchEvent(new Event('input', { bubbles: true }));
            });
            
            container.appendChild(item);
        });
        
        container.style.display = 'block';
    }
}

// Валидация форм
function initFormValidation() {
    const forms = document.querySelectorAll('form[data-validate="true"], .needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
    
    // Валидация пароля в реальном времени
    const passwordConfirm = document.querySelector('input[name="password2"]');
    const password = document.querySelector('input[name="password"]');
    
    if (passwordConfirm && password) {
        passwordConfirm.addEventListener('input', function() {
            if (this.value !== password.value) {
                this.setCustomValidity('Пароли не совпадают');
                this.classList.add('is-invalid');
            } else {
                this.setCustomValidity('');
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            }
        });
    }
}

// Поиск рейсов
function initFlightSearch() {
    const searchForm = document.querySelector('form[action*="search"]');
    
    if (searchForm) {
        searchForm.addEventListener('submit', function(event) {
            const departureCity = this.querySelector('input[name="departure_city"]');
            const arrivalCity = this.querySelector('input[name="arrival_city"]');
            
            if (departureCity && arrivalCity && 
                departureCity.value.toLowerCase() === arrivalCity.value.toLowerCase()) {
                event.preventDefault();
                showAlert('Город отправления и назначения не могут совпадать', 'warning');
                return false;
            }
            
            // Показать индикатор загрузки
            showLoadingSpinner();
        });
    }
}

// Формы бронирования
function initBookingForms() {
    const bookingForm = document.querySelector('form[action*="book"]');
    
    if (bookingForm) {
        // Автозаполнение данных пассажира из профиля пользователя
        const userFirstName = document.querySelector('meta[name="user-first-name"]');
        const userLastName = document.querySelector('meta[name="user-last-name"]');
        const userEmail = document.querySelector('meta[name="user-email"]');
        
        const passengerFirstName = bookingForm.querySelector('input[name="passenger_first_name"]');
        const passengerLastName = bookingForm.querySelector('input[name="passenger_last_name"]');
        const passengerEmail = bookingForm.querySelector('input[name="passenger_email"]');
        
        if (userFirstName && passengerFirstName && !passengerFirstName.value) {
            passengerFirstName.value = userFirstName.content;
        }
        if (userLastName && passengerLastName && !passengerLastName.value) {
            passengerLastName.value = userLastName.content;
        }
        if (userEmail && passengerEmail && !passengerEmail.value) {
            passengerEmail.value = userEmail.content;
        }
        
        // Расчет цены в зависимости от класса
        const seatClassSelect = bookingForm.querySelector('select[name="seat_class"]');
        const priceDisplay = document.querySelector('.price-display');
        
        if (seatClassSelect && priceDisplay) {
            seatClassSelect.addEventListener('change', updatePrice);
            updatePrice(); // Инициальный расчет
        }
    }
}

function updatePrice() {
    const seatClass = document.querySelector('select[name="seat_class"]').value;
    const basePrice = parseFloat(document.querySelector('[data-base-price]')?.dataset.basePrice || 0);
    const businessPrice = parseFloat(document.querySelector('[data-business-price]')?.dataset.businessPrice || 0);
    const firstPrice = parseFloat(document.querySelector('[data-first-price]')?.dataset.firstPrice || 0);
    
    let finalPrice = basePrice;
    
    switch(seatClass) {
        case 'business':
            finalPrice = businessPrice || (basePrice * 2);
            break;
        case 'first':
            finalPrice = firstPrice || (basePrice * 3);
            break;
        default:
            finalPrice = basePrice;
    }
    
    const priceDisplay = document.querySelector('.price-display');
    if (priceDisplay) {
        priceDisplay.textContent = `${Math.round(finalPrice)} ₽`;
    }
}

// Инициализация всплывающих подсказок
function initTooltips() {
    // Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Утилиты
function showAlert(message, type = 'info') {
    const alertContainer = document.querySelector('.alert-container') || document.body;
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.appendChild(alert);
    
    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

function showLoadingSpinner() {
    const spinner = document.createElement('div');
    spinner.id = 'loading-spinner';
    spinner.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(255,255,255,0.8);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
    `;
    spinner.innerHTML = `
        <div class="spinner">
            <div class="text-center">
                <i class="fas fa-plane fa-2x text-primary mb-3"></i>
                <div>Поиск рейсов...</div>
            </div>
        </div>
    `;
    
    document.body.appendChild(spinner);
}

function hideLoadingSpinner() {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.remove();
    }
}

// AJAX функции
function makeAjaxRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    return fetch(url, options)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .catch(error => {
            console.error('AJAX Error:', error);
            showAlert('Произошла ошибка при выполнении запроса', 'danger');
            throw error;
        });
}

// Функции для работы с бронированиями
function cancelBooking(bookingReference) {
    if (!confirm(`Вы уверены, что хотите отменить бронирование ${bookingReference}?`)) {
        return;
    }
    
    makeAjaxRequest(`/api/booking/${bookingReference}/cancel`, 'POST')
        .then(response => {
            if (response.success) {
                showAlert('Бронирование успешно отменено', 'success');
                // Обновить страницу или удалить элемент
                location.reload();
            } else {
                showAlert(response.message || 'Ошибка при отмене бронирования', 'danger');
            }
        })
        .catch(error => {
            showAlert('Не удалось отменить бронирование', 'danger');
        });
}

// Форматирование валюты
function formatCurrency(amount, currency = '₽') {
    return new Intl.NumberFormat('ru-RU').format(amount) + ' ' + currency;
}

// Форматирование даты
function formatDate(date, format = 'short') {
    const options = format === 'short' 
        ? { day: '2-digit', month: '2-digit', year: 'numeric' }
        : { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        };
    
    return new Intl.DateTimeFormat('ru-RU', options).format(new Date(date));
}

// Обработка ошибок глобально
window.addEventListener('error', function(event) {
    console.error('JavaScript Error:', event.error);
    // В продакшене можно отправлять ошибки на сервер
});

// Обработка необработанных промисов
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled Promise Rejection:', event.reason);
    event.preventDefault();
});

// Экспорт функций для использования в других скриптах
window.AirBookApp = {
    showAlert,
    showLoadingSpinner,
    hideLoadingSpinner,
    makeAjaxRequest,
    formatCurrency,
    formatDate,
    cancelBooking
};