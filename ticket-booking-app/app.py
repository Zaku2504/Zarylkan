from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random
import string
import os
import re

from models import db, User, Airport, Airline, Flight, Booking, Payment, Banner
from sqlalchemy import text
from forms import LoginForm, RegistrationForm, FlightSearchForm, BookingForm, FlightForm, AirportForm, AirlineForm, BannerForm

def is_valid_email(email):
    """
    Проверяет валидность email адреса
    """
    if not email or not isinstance(email, str):
        return False
    
    # Базовая проверка через регулярное выражение
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return False
    
    # Дополнительные проверки
    if len(email) > 254:  # RFC 5321 ограничение
        return False
    
    local_part, domain_part = email.rsplit('@', 1)
    
    # Проверка локальной части
    if len(local_part) > 64:  # RFC 5321 ограничение
        return False
    
    # Проверка доменной части
    if len(domain_part) > 253:
        return False
    
    # Проверка на последовательные точки
    if '..' in email:
        return False
    
    # Проверка начала и конца
    if email.startswith('.') or email.endswith('.') or email.startswith('@') or email.endswith('@'):
        return False
    
    return True

def generate_seat_number(flight, seat_class):
    """
    Генерирует номер места для пассажира
    """
    # Определяем диапазон мест для каждого класса (более реалистично)
    total_seats = min(flight.total_seats, 200)  # Ограничиваем максимальное количество мест
    
    if seat_class == 'economy':
        start_row = 1
        end_row = int(total_seats * 0.8)  # 80% мест для эконом класса
        seats_per_row = 6  # A-F
    elif seat_class == 'business':
        start_row = int(total_seats * 0.8) + 1
        end_row = int(total_seats * 0.95)  # 15% мест для бизнес класса
        seats_per_row = 4  # A-D
    else:  # first class
        start_row = int(total_seats * 0.95) + 1
        end_row = total_seats  # 5% мест для первого класса
        seats_per_row = 2  # A-B
    
    # Получаем уже занятые места на этом рейсе для данного класса
    existing_seats = db.session.query(Booking.seat_number).join(Flight).filter(
        Booking.flight_id == flight.id,
        Booking.seat_class == seat_class,
        Booking.seat_number.isnot(None),
        Booking.seat_number != ''
    ).all()
    existing_seats = [seat[0] for seat in existing_seats]
    
    # Ищем свободное место в пределах класса
    for row in range(start_row, min(end_row + 1, start_row + 50)):  # Ограничиваем поиск 50 рядами
        for seat_letter in ['A', 'B', 'C', 'D', 'E', 'F'][:seats_per_row]:
            seat_number = f"{row}{seat_letter}"
            if seat_number not in existing_seats:
                return seat_number
    
    # Если все места в классе заняты, ищем в других классах
    for row in range(1, total_seats + 1):
        for seat_letter in ['A', 'B', 'C', 'D', 'E', 'F']:
            seat_number = f"{row}{seat_letter}"
            if seat_number not in existing_seats:
                return seat_number
    
    # Если все места заняты, возвращаем резервный номер
    return f"R{random.randint(100, 999)}"

def create_app():
    app = Flask(__name__)
    
    # Конфигурация
    app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ticket_booking.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Настройки для надежности
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 час
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 час
    
    # Инициализация расширений
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Глобальная обработка ошибок
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    def requires_role(role):
        """Декоратор для проверки роли пользователя"""
        def decorator(f):
            def decorated_function(*args, **kwargs):
                if not current_user.is_authenticated:
                    return redirect(url_for('auth.login'))
                if current_user.role != role:
                    flash('У вас нет прав для доступа к этой странице.', 'error')
                    return redirect(url_for('main.index'))
                return f(*args, **kwargs)
            decorated_function.__name__ = f.__name__
            return decorated_function
        return decorator
    
    # ОСНОВНЫЕ МАРШРУТЫ
    @app.route('/')
    def index():
        search_form = FlightSearchForm()
        # Получаем популярные направления
        recent_flights = Flight.query.filter(
            Flight.departure_time > datetime.utcnow()
        ).order_by(Flight.departure_time).limit(6).all()
        
        # Получаем активный рекламный баннер
        # Сначала пробуем найти баннер для главной страницы
        active_banner = Banner.query.filter(
            Banner.is_active == True,
            Banner.position == 'main'
        ).first()
        
        # Если нет баннера для главной, берем любой активный баннер
        if not active_banner:
            active_banner = Banner.query.filter(
                Banner.is_active == True
            ).first()
        
        # Упрощенная проверка активности - если баннер активен в БД, показываем его
        if active_banner and active_banner.is_active:
            # Проверяем только даты, если они установлены
            now = datetime.utcnow()
            if active_banner.start_date and now < active_banner.start_date:
                active_banner = None
            elif active_banner.end_date and now > active_banner.end_date:
                active_banner = None
        
        # Увеличиваем счетчик просмотров если баннер активен
        if active_banner:
            active_banner.increment_views()
        
        # Отладочная информация
        print(f"DEBUG: Найдено баннеров: {Banner.query.count()}")
        print(f"DEBUG: Активных баннеров: {Banner.query.filter_by(is_active=True).count()}")
        print(f"DEBUG: Баннеров для главной: {Banner.query.filter(Banner.is_active==True, Banner.position=='main').count()}")
        if active_banner:
            print(f"DEBUG: Показываем баннер: {active_banner.title} (ID: {active_banner.id})")
        else:
            print("DEBUG: Баннер не найден или неактивен")
        
        return render_template('index.html', form=search_form, recent_flights=recent_flights, banner=active_banner)
    
    @app.route('/search', methods=['GET', 'POST'])
    def search_flights():
        try:
            form = FlightSearchForm()
            flights = []
            
            # Если это GET запрос или форма не заполнена, показываем все доступные рейсы
            if request.method == 'GET' or not any([form.departure_city.data, form.arrival_city.data, form.departure_date.data]):
                print("DEBUG: Показываем все доступные рейсы")
                from sqlalchemy.orm import aliased
                
                dep_airport = aliased(Airport)
                arr_airport = aliased(Airport)
                
                # Показываем будущие рейсы с доступными местами
                query = Flight.query.join(dep_airport, Flight.departure_airport_id == dep_airport.id).add_columns(
                    dep_airport.city.label('dep_city')
                ).join(arr_airport, Flight.arrival_airport_id == arr_airport.id).add_columns(
                    arr_airport.city.label('arr_city')
                ).filter(
                    Flight.departure_time >= datetime.utcnow(),
                    Flight.available_seats > 0
                ).order_by(Flight.departure_time)
                
                flights = query.all()
                print(f"DEBUG: Найдено рейсов для отображения: {len(flights)}")
            
            elif form.validate_on_submit():
                print("DEBUG: Форма валидна, начинаем поиск")
                print(f"DEBUG: Данные формы - Откуда: {form.departure_city.data}, Куда: {form.arrival_city.data}, Дата: {form.departure_date.data}, Пассажиры: {form.passengers.data}")
                
                # Поиск рейсов с использованием alias для аэропортов
                from sqlalchemy.orm import aliased
                
                dep_airport = aliased(Airport)
                arr_airport = aliased(Airport)
                
                # Базовый запрос
                query = Flight.query.join(dep_airport, Flight.departure_airport_id == dep_airport.id).add_columns(
                    dep_airport.city.label('dep_city')
                ).join(arr_airport, Flight.arrival_airport_id == arr_airport.id).add_columns(
                    arr_airport.city.label('arr_city')
                )
                
                # Фильтр по дате (если указана)
                if form.departure_date.data:
                    print(f"DEBUG: Фильтр по дате: {form.departure_date.data}")
                    query = query.filter(
                        Flight.departure_time >= form.departure_date.data,
                        Flight.departure_time <= form.departure_date.data + timedelta(days=1)
                    )
                else:
                    # Если дата не указана, показываем будущие рейсы
                    print("DEBUG: Фильтр по будущим рейсам")
                    query = query.filter(Flight.departure_time >= datetime.utcnow())
                
                # Фильтр по количеству пассажиров (если указано)
                if form.passengers.data:
                    print(f"DEBUG: Фильтр по пассажирам: {form.passengers.data}")
                    query = query.filter(Flight.available_seats >= form.passengers.data)
                
                # Фильтр по городам (простой поиск по подстроке)
                if form.departure_city.data:
                    print(f"DEBUG: Фильтр по городу отправления: {form.departure_city.data}")
                    query = query.filter(dep_airport.city.ilike(f'%{form.departure_city.data}%'))
                if form.arrival_city.data:
                    print(f"DEBUG: Фильтр по городу прибытия: {form.arrival_city.data}")
                    query = query.filter(arr_airport.city.ilike(f'%{form.arrival_city.data}%'))
                
                # Сортируем по времени вылета
                query = query.order_by(Flight.departure_time)
                
                print(f"DEBUG: SQL запрос: {query}")
                flights = query.all()
                print(f"DEBUG: Найдено рейсов после фильтрации: {len(flights)}")
                
                # Если поиск не дал результатов, показываем все доступные рейсы
                if len(flights) == 0:
                    print("DEBUG: Поиск не дал результатов, показываем все доступные рейсы")
                    from sqlalchemy.orm import aliased
                    
                    dep_airport = aliased(Airport)
                    arr_airport = aliased(Airport)
                    
                    flights = Flight.query.join(dep_airport, Flight.departure_airport_id == dep_airport.id).add_columns(
                        dep_airport.city.label('dep_city')
                    ).join(arr_airport, Flight.arrival_airport_id == arr_airport.id).add_columns(
                        arr_airport.city.label('arr_city')
                    ).filter(
                        Flight.departure_time >= datetime.utcnow(),
                        Flight.available_seats > 0
                    ).order_by(Flight.departure_time).all()
            
            print(f"DEBUG: Итого найдено рейсов: {len(flights)}")
            for flight in flights:
                if hasattr(flight, 'Flight'):
                    print(f"DEBUG: Рейс {flight.Flight.flight_number}: {flight.dep_city} → {flight.arr_city}")
                else:
                    print(f"DEBUG: Рейс {flight.flight_number}: {getattr(flight, 'dep_city', 'N/A')} → {getattr(flight, 'arr_city', 'N/A')}")
            
            # Получаем активные баннеры для боковой панели
            all_banners = Banner.query.all()
            print(f"DEBUG: Всего баннеров в БД: {len(all_banners)}")
            
            sidebar_banners = Banner.query.filter(
                Banner.is_active == True,
                Banner.position == 'sidebar'
            ).order_by(Banner.priority.desc()).all()
            
            print(f"DEBUG: Найдено баннеров с position='sidebar' и is_active=True: {len(sidebar_banners)}")
            
            # Фильтруем баннеры по датам показа
            active_banners = [banner for banner in sidebar_banners if banner.is_currently_active()]
            print(f"DEBUG: Баннеров активных по датам: {len(active_banners)}")
            
            sidebar_banners = active_banners[:3]  # Ограничиваем до 3 баннеров
            print(f"DEBUG: Итого баннеров для отображения: {len(sidebar_banners)}")
            
            # Увеличиваем счетчик просмотров для показанных баннеров
            for banner in sidebar_banners:
                banner.increment_views()
            
            return render_template('search_results.html', form=form, flights=flights, banners=sidebar_banners)
        
        except Exception as e:
            print(f"Ошибка в поиске рейсов: {e}")
            flash('Произошла ошибка при поиске рейсов. Попробуйте еще раз.', 'error')
            return render_template('search_results.html', form=form, flights=[], banners=[])
    
    @app.route('/flight/<int:flight_id>')
    def flight_details(flight_id):
        flight = Flight.query.get_or_404(flight_id)
        return render_template('flight_details.html', flight=flight)
    
    @app.route('/book/<int:flight_id>', methods=['GET', 'POST'])
    @login_required
    def book_flight(flight_id):
        try:
            flight = Flight.query.get_or_404(flight_id)
            
            # Проверяем, что рейс еще не вылетел
            if flight.departure_time <= datetime.utcnow():
                flash('Бронирование на этот рейс невозможно - рейс уже вылетел.', 'error')
                return redirect(url_for('search_flights'))
            
            # Проверяем доступность мест
            if flight.available_seats <= 0:
                flash('К сожалению, на этом рейсе нет свободных мест.', 'error')
                return redirect(url_for('search_flights'))
            
            form = BookingForm()
            
            if form.validate_on_submit():
                try:
                    # Дополнительная валидация email пассажира
                    if form.passenger_email.data and not is_valid_email(form.passenger_email.data):
                        flash('Введите корректный email адрес пассажира.', 'error')
                        return render_template('book_flight.html', flight=flight, form=form)
                    
                    # Генерация кода бронирования
                    booking_ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    
                    # Определение цены
                    price_map = {
                        'economy': flight.economy_price,
                        'business': flight.business_price or flight.economy_price * 2,
                        'first': flight.first_class_price or flight.economy_price * 3
                    }
                    price = price_map.get(form.seat_class.data, flight.economy_price)
                    
                    # Проверка доступности мест
                    if flight.available_seats <= 0:
                        flash('К сожалению, на этом рейсе нет свободных мест.', 'error')
                        return render_template('book_flight.html', flight=flight, form=form)
                    
                    # Автоматическое назначение места
                    seat_number = generate_seat_number(flight, form.seat_class.data)
                    
                    # Создание бронирования
                    booking = Booking(
                        booking_reference=booking_ref,
                        user_id=current_user.id,
                        flight_id=flight.id,
                        passenger_first_name=form.passenger_first_name.data,
                        passenger_last_name=form.passenger_last_name.data,
                        passenger_email=form.passenger_email.data,
                        passenger_phone=form.passenger_phone.data,
                        seat_class=form.seat_class.data,
                        seat_number=seat_number,
                        price_paid=price,
                        baggage_count=form.baggage_count.data or 1,
                        meal_preference=form.meal_preference.data,
                        special_requests=form.special_requests.data
                    )
                    
                    db.session.add(booking)
                    
                    # Уменьшение доступных мест
                    flight.available_seats -= 1
                    
                    db.session.commit()
                    
                    flash(f'Бронирование успешно создано! Код: {booking_ref}, Место: {seat_number}', 'success')
                    return redirect(url_for('profile'))
                except Exception as e:
                    db.session.rollback()
                    flash('Произошла ошибка при создании бронирования. Попробуйте еще раз.', 'error')
                    return render_template('book_flight.html', flight=flight, form=form)
            
            return render_template('book_flight.html', flight=flight, form=form)
        
        except Exception as e:
            print(f"Ошибка в бронировании: {e}")
            flash('Произошла ошибка при загрузке страницы бронирования.', 'error')
            return redirect(url_for('search_flights'))
    
    @app.route('/profile')
    @login_required
    def profile():
        bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.booking_date.desc()).all()
        return render_template('profile.html', bookings=bookings, now=datetime.utcnow())
    
    # АВТОРИЗАЦИЯ
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            
            if user and user.check_password(form.password.data):
                login_user(user)
                next_page = request.args.get('next')
                flash(f'Добро пожаловать, {user.first_name}!', 'success')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            
            flash('Неверный логин или пароль.', 'error')
        
        return render_template('login.html', form=form)
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        form = RegistrationForm()
        if form.validate_on_submit():
            try:
                # Дополнительная валидация email
                if not is_valid_email(form.email.data):
                    flash('Введите корректный email адрес.', 'error')
                    return render_template('register.html', form=form)
                
                # Проверка уникальности
                if User.query.filter_by(username=form.username.data).first():
                    flash('Пользователь с таким логином уже существует.', 'error')
                    return render_template('register.html', form=form)
                
                if User.query.filter_by(email=form.email.data).first():
                    flash('Пользователь с таким email уже существует.', 'error')
                    return render_template('register.html', form=form)
                
                user = User(
                    username=form.username.data,
                    email=form.email.data,
                    first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    phone=form.phone.data,
                    role=form.role.data
                )
                user.set_password(form.password.data)
                
                db.session.add(user)
                db.session.commit()
                
                flash('Регистрация прошла успешно! Теперь вы можете войти в систему.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash('Произошла ошибка при регистрации. Попробуйте еще раз.', 'error')
                return render_template('register.html', form=form)
        
        return render_template('register.html', form=form)
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы вышли из системы.', 'info')
        return redirect(url_for('index'))
    
    @app.route('/clear-session')
    def clear_session():
        """Принудительная очистка сессии"""
        logout_user()
        flash('Сессия очищена.', 'info')
        return redirect(url_for('index'))
    
    # АДМИН ПАНЕЛЬ
    @app.route('/admin')
    @login_required
    def admin_dashboard():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        # Статистика
        now = datetime.utcnow()
        
        # Общая статистика
        total_flights = Flight.query.count()
        active_flights = Flight.query.filter(Flight.departure_time > now).count()
        completed_flights = Flight.query.filter(Flight.departure_time <= now).count()
        
        # Статистика бронирований
        total_bookings = Booking.query.count()
        total_passengers = total_bookings  # Каждое бронирование = 1 пассажир
        
        # Общий доход
        total_revenue = db.session.query(db.func.sum(Booking.price_paid)).scalar() or 0
        
        recent_bookings = Booking.query.order_by(Booking.booking_date.desc()).limit(10).all()
        
        return render_template('admin/dashboard.html', 
                             total_flights=total_flights, 
                             active_flights=active_flights,
                             completed_flights=completed_flights,
                             total_bookings=total_bookings,
                             total_passengers=total_passengers,
                             total_revenue=total_revenue,
                             recent_bookings=recent_bookings)
    
    @app.route('/admin/api/statistics')
    @login_required
    def admin_statistics_api():
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        period = request.args.get('period', 'all')
        now = datetime.utcnow()
        
        # Определяем временные рамки
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        else:  # all
            start_date = datetime.min
        
        # Статистика рейсов
        total_flights = Flight.query.count()
        active_flights = Flight.query.filter(Flight.departure_time > now).count()
        completed_flights = Flight.query.filter(Flight.departure_time <= now).count()
        
        # Статистика бронирований за период
        bookings_query = Booking.query.filter(Booking.booking_date >= start_date)
        total_bookings = bookings_query.count()
        total_passengers = total_bookings  # Каждое бронирование = 1 пассажир
        total_revenue = db.session.query(db.func.sum(Booking.price_paid)).filter(
            Booking.booking_date >= start_date
        ).scalar() or 0
        
        return jsonify({
            'total_flights': total_flights,
            'active_flights': active_flights,
            'completed_flights': completed_flights,
            'total_bookings': total_bookings,
            'total_passengers': int(total_passengers),
            'total_revenue': float(total_revenue)
        })
    
    # АДМИНИСТРИРОВАНИЕ РЕЙСОВ
    
    @app.route('/admin/flights')
    @login_required
    def admin_flights():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        flights = Flight.query.order_by(Flight.departure_time.desc()).all()
        return render_template('admin/flights.html', flights=flights)
    
    @app.route('/admin/flight/add', methods=['GET', 'POST'])
    @login_required
    def admin_add_flight():
        if not (current_user.is_admin() or current_user.is_manager()):
            flash('У вас нет прав для добавления рейсов.', 'error')
            return redirect(url_for('index'))
        
        form = FlightForm()
        form.departure_airport_id.choices = [(a.id, f"{a.code} - {a.city}") for a in Airport.query.all()]
        form.arrival_airport_id.choices = [(a.id, f"{a.code} - {a.city}") for a in Airport.query.all()]
        
        # Ограничиваем выбор авиакомпании для менеджеров
        if current_user.is_admin():
            form.airline_id.choices = [(a.id, f"{a.code} - {a.name}") for a in Airline.query.all()]
        else:
            # Менеджер может добавлять рейсы только для своей авиакомпании
            if current_user.company_id:
                airline = Airline.query.get(current_user.company_id)
                if airline:
                    form.airline_id.choices = [(airline.id, f"{airline.code} - {airline.name}")]
                    form.airline_id.data = airline.id
                else:
                    flash('Ошибка: авиакомпания не найдена.', 'error')
                    return redirect(url_for('manager_flights'))
        
        if form.validate_on_submit():
            try:
                # Определяем авиакомпанию для нового рейса
                airline_id = form.airline_id.data if current_user.is_admin() else current_user.company_id
                
                flight = Flight(
                    flight_number=form.flight_number.data,
                    departure_airport_id=form.departure_airport_id.data,
                    arrival_airport_id=form.arrival_airport_id.data,
                    airline_id=airline_id,
                    departure_time=form.departure_time.data,
                    arrival_time=form.arrival_time.data,
                    aircraft_type=form.aircraft_type.data,
                    total_seats=form.total_seats.data,
                    available_seats=form.available_seats.data,
                    economy_price=form.economy_price.data,
                    business_price=form.business_price.data,
                    first_class_price=form.first_class_price.data,
                    status=form.status.data
                )
                
                db.session.add(flight)
                db.session.commit()
                
                flash('Рейс успешно добавлен!', 'success')
                
                # Редирект зависит от роли пользователя
                if current_user.is_admin():
                    return redirect(url_for('admin_flights'))
                else:
                    return redirect(url_for('manager_flights'))
                    
            except Exception as e:
                db.session.rollback()
                flash('Произошла ошибка при добавлении рейса. Проверьте данные.', 'error')
            return redirect(url_for('admin_flights'))
        
        return render_template('admin/add_flight.html', form=form)
    
    @app.route('/admin/flight/edit/<int:flight_id>', methods=['GET', 'POST'])
    @login_required
    def admin_edit_flight(flight_id):
        if not (current_user.is_admin() or current_user.is_manager()):
            flash('У вас нет прав для редактирования рейсов.', 'error')
            return redirect(url_for('index'))
        
        flight = Flight.query.get_or_404(flight_id)
        
        # Проверяем права на редактирование рейса
        if current_user.is_manager() and flight.airline_id != current_user.company_id:
            flash('У вас нет прав на редактирование этого рейса.', 'error')
            return redirect(url_for('manager_flights'))
        form = FlightForm(obj=flight)
        form.departure_airport_id.choices = [(a.id, f"{a.code} - {a.city}") for a in Airport.query.all()]
        form.arrival_airport_id.choices = [(a.id, f"{a.code} - {a.city}") for a in Airport.query.all()]
        
        # Ограничиваем выбор авиакомпании для менеджеров
        if current_user.is_admin():
            form.airline_id.choices = [(a.id, f"{a.code} - {a.name}") for a in Airline.query.all()]
        else:
            # Менеджер может редактировать только свою авиакомпанию
            if current_user.company_id:
                airline = Airline.query.get(current_user.company_id)
                if airline:
                    form.airline_id.choices = [(airline.id, f"{airline.code} - {airline.name}")]
                    form.airline_id.data = airline.id
                else:
                    flash('Ошибка: авиакомпания не найдена.', 'error')
                    return redirect(url_for('manager_flights'))
        
        if form.validate_on_submit():
            try:
                # Обновляем данные рейса
                flight.flight_number = form.flight_number.data
                flight.departure_airport_id = form.departure_airport_id.data
                flight.arrival_airport_id = form.arrival_airport_id.data
                
                # Менеджер не может изменить авиакомпанию
                if current_user.is_admin():
                    flight.airline_id = form.airline_id.data
                flight.departure_time = form.departure_time.data
                flight.arrival_time = form.arrival_time.data
                flight.aircraft_type = form.aircraft_type.data
                flight.total_seats = form.total_seats.data
                flight.available_seats = form.available_seats.data
                flight.economy_price = form.economy_price.data
                flight.business_price = form.business_price.data
                flight.first_class_price = form.first_class_price.data
                flight.status = form.status.data
                
                db.session.commit()
                
                flash(f'Рейс {flight.flight_number} успешно обновлен!', 'success')
                
                # Редирект зависит от роли пользователя
                if current_user.is_admin():
                    return redirect(url_for('admin_flights'))
                else:
                    return redirect(url_for('manager_flights'))
                
            except Exception as e:
                db.session.rollback()
                flash('Произошла ошибка при обновлении рейса. Проверьте данные.', 'error')
        
        return render_template('admin/edit_flight.html', form=form, flight=flight)
    
    @app.route('/admin/flight/delete/<int:flight_id>', methods=['POST'])
    @login_required
    def admin_delete_flight(flight_id):
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            flight = Flight.query.get_or_404(flight_id)
            
            # Проверяем, есть ли бронирования на этот рейс
            bookings_count = Booking.query.filter_by(flight_id=flight_id).count()
            
            if bookings_count > 0:
                flash(f'Невозможно удалить рейс {flight.flight_number}. На него есть {bookings_count} бронирований.', 'error')
                return redirect(url_for('admin_flights'))
            
            flight_info = f"{flight.flight_number} ({flight.departure_airport.code} → {flight.arrival_airport.code})"
            db.session.delete(flight)
            db.session.commit()
            
            flash(f'Рейс "{flight_info}" успешно удален!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при удалении рейса. Попробуйте еще раз.', 'error')
        
        return redirect(url_for('admin_flights'))
    
    @app.route('/admin/flight/toggle-status/<int:flight_id>', methods=['POST'])
    @login_required
    def admin_toggle_flight_status(flight_id):
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            flight = Flight.query.get_or_404(flight_id)
            
            # Переключаем статус рейса
            status_transitions = {
                'scheduled': 'boarding',
                'boarding': 'departed', 
                'departed': 'arrived',
                'arrived': 'completed',
                'completed': 'scheduled',
                'cancelled': 'scheduled'
            }
            
            new_status = status_transitions.get(flight.status, 'scheduled')
            old_status = flight.status
            flight.status = new_status
            
            db.session.commit()
            
            flash(f'Статус рейса {flight.flight_number} изменен: {old_status} → {new_status}', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при изменении статуса рейса.', 'error')
        
        return redirect(url_for('admin_flights'))
    
    @app.route('/api/flight/<int:flight_id>/details')
    @login_required
    def api_flight_details(flight_id):
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            flight = Flight.query.get_or_404(flight_id)
            
            # Получаем детальную информацию
            bookings = Booking.query.filter_by(flight_id=flight_id).all()
            total_revenue = sum(booking.price_paid for booking in bookings)
            #"c:\Users\Муса\OneDrive\Desktop\new shit\ticket-booking-app"
            # Статистика по классам обслуживания
            class_stats = {}
            for booking in bookings:
                seat_class = booking.seat_class
                if seat_class not in class_stats:
                    class_stats[seat_class] = {'count': 0, 'revenue': 0}
                class_stats[seat_class]['count'] += 1
                class_stats[seat_class]['revenue'] += booking.price_paid
            
            # Последние бронирования
            recent_bookings = Booking.query.filter_by(flight_id=flight_id)\
                .order_by(Booking.booking_date.desc()).limit(5).all()
            
            details = {
                'flight': {
                    'id': flight.id,
                    'flight_number': flight.flight_number,
                    'departure_airport': {
                        'code': flight.departure_airport.code,
                        'name': flight.departure_airport.name,
                        'city': flight.departure_airport.city
                    },
                    'arrival_airport': {
                        'code': flight.arrival_airport.code,
                        'name': flight.arrival_airport.name,
                        'city': flight.arrival_airport.city
                    },
                    'airline': {
                        'code': flight.airline.code,
                        'name': flight.airline.name
                    },
                    'departure_time': flight.departure_time.strftime('%d.%m.%Y %H:%M'),
                    'arrival_time': flight.arrival_time.strftime('%d.%m.%Y %H:%M'),
                    'duration': str(flight.arrival_time - flight.departure_time),
                    'aircraft_type': flight.aircraft_type,
                    'status': flight.status,
                    'total_seats': flight.total_seats,
                    'available_seats': flight.available_seats,
                    'booked_seats': flight.total_seats - flight.available_seats,
                    'occupancy_percent': round(((flight.total_seats - flight.available_seats) / flight.total_seats * 100) if flight.total_seats > 0 else 0, 1),
                    'economy_price': float(flight.economy_price),
                    'business_price': float(flight.business_price) if flight.business_price else None,
                    'first_class_price': float(flight.first_class_price) if flight.first_class_price else None
                },
                'statistics': {
                    'total_bookings': len(bookings),
                    'total_revenue': float(total_revenue),
                    'average_ticket_price': float(total_revenue / len(bookings)) if bookings else 0,
                    'class_breakdown': class_stats
                },
                'recent_bookings': [
                    {
                        'id': booking.id,
                        'booking_reference': booking.booking_reference,
                        'passenger_name': f"{booking.passenger_first_name} {booking.passenger_last_name}",
                        'seat_class': booking.seat_class,
                        'price_paid': float(booking.price_paid),
                        'booking_date': booking.booking_date.strftime('%d.%m.%Y %H:%M'),
                        'status': booking.status
                    } for booking in recent_bookings
                ]
            }
            
            return jsonify(details)
            
        except Exception as e:
            return jsonify({'error': 'Ошибка получения данных'}), 500
    
    @app.route('/admin/airports')
    @login_required
    def admin_airports():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        airports = Airport.query.order_by(Airport.city).all()
        return render_template('admin/airports.html', airports=airports)
    
    @app.route('/admin/add_airport', methods=['POST'])
    @login_required
    def admin_add_airport():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            # Получаем данные из формы
            code = request.form.get('code', '').strip().upper()
            name = request.form.get('name', '').strip()
            city = request.form.get('city', '').strip()
            country = request.form.get('country', '').strip()
            
            # Валидация данных
            if not all([code, name, city, country]):
                flash('Все поля обязательны для заполнения!', 'error')
                return redirect(url_for('admin_airports'))
            
            if len(code) != 3:
                flash('IATA код должен состоять из 3 букв!', 'error')
                return redirect(url_for('admin_airports'))
            
            # Проверка уникальности кода
            existing_airport = Airport.query.filter_by(code=code).first()
            if existing_airport:
                flash(f'Аэропорт с кодом "{code}" уже существует!', 'error')
                return redirect(url_for('admin_airports'))
            
            # Создание нового аэропорта
            airport = Airport(
                code=code,
                name=name,
                city=city,
                country=country
            )
            
            db.session.add(airport)
            db.session.commit()
            
            flash(f'Аэропорт "{name}" ({code}) успешно добавлен!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при добавлении аэропорта. Проверьте данные.', 'error')
        
        return redirect(url_for('admin_airports'))
    
    @app.route('/admin/delete_airport/<int:airport_id>', methods=['POST'])
    @login_required
    def admin_delete_airport(airport_id):
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            airport = Airport.query.get_or_404(airport_id)
            
            # Проверяем, есть ли рейсы, связанные с этим аэропортом
            flights_count = Flight.query.filter(
                (Flight.departure_airport_id == airport_id) | 
                (Flight.arrival_airport_id == airport_id)
            ).count()
            
            if flights_count > 0:
                flash(f'Невозможно удалить аэропорт "{airport.city} ({airport.code})". С ним связано {flights_count} рейсов.', 'error')
                return redirect(url_for('admin_airports'))
            
            airport_info = f"{airport.city} ({airport.code})"
            db.session.delete(airport)
            db.session.commit()
            
            flash(f'Аэропорт "{airport_info}" успешно удален!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при удалении аэропорта. Попробуйте еще раз.', 'error')
        
        return redirect(url_for('admin_airports'))
    
    @app.route('/admin/users')
    @login_required
    def admin_users():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        # Получаем параметр фильтра из URL
        role_filter = request.args.get('role', 'all')
        
        # Применяем фильтр
        if role_filter == 'all':
            users = User.query.order_by(User.created_at.desc()).all()
        else:
            users = User.query.filter_by(role=role_filter).order_by(User.created_at.desc()).all()
        
        # Статистика для отображения
        total_users = User.query.count()
        admin_count = User.query.filter_by(role='admin').count()
        manager_count = User.query.filter_by(role='manager').count()
        user_count = User.query.filter_by(role='user').count()
        
        return render_template('admin/users.html', 
                             users=users, 
                             current_filter=role_filter,
                             total_users=total_users,
                             admin_count=admin_count,
                             manager_count=manager_count,
                             user_count=user_count)
    
    @app.route('/api/user/<int:user_id>/details')
    @login_required
    def api_user_details(user_id):
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            user = User.query.get_or_404(user_id)
            
            # Получаем детальную информацию о бронированиях
            bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.booking_date.desc()).all()
            total_spent = sum(booking.price_paid for booking in bookings)
            
            # Статистика по статусам бронирований
            status_stats = {}
            for booking in bookings:
                status = booking.status
                if status not in status_stats:
                    status_stats[status] = {'count': 0, 'amount': 0}
                status_stats[status]['count'] += 1
                status_stats[status]['amount'] += booking.price_paid
            
            # Любимые направления
            destinations = {}
            for booking in bookings:
                route = f"{booking.flight.departure_airport.city} → {booking.flight.arrival_airport.city}"
                if route not in destinations:
                    destinations[route] = 0
                destinations[route] += 1
            
            # Топ-3 направления
            top_destinations = sorted(destinations.items(), key=lambda x: x[1], reverse=True)[:3]
            
            details = {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone': user.phone,
                    'role': user.role,
                    'created_at': user.created_at.strftime('%d.%m.%Y %H:%M'),
                    'is_active': True  # В будущем можно добавить поле активности
                },
                'statistics': {
                    'total_bookings': len(bookings),
                    'total_spent': float(total_spent),
                    'average_booking_value': float(total_spent / len(bookings)) if bookings else 0,
                    'status_breakdown': status_stats,
                    'favorite_destinations': top_destinations
                },
                'recent_bookings': [
                    {
                        'id': booking.id,
                        'booking_reference': booking.booking_reference,
                        'flight_number': booking.flight.flight_number,
                        'route': f"{booking.flight.departure_airport.city} → {booking.flight.arrival_airport.city}",
                        'departure_time': booking.flight.departure_time.strftime('%d.%m.%Y %H:%M'),
                        'seat_class': booking.seat_class,
                        'price_paid': float(booking.price_paid),
                        'booking_date': booking.booking_date.strftime('%d.%m.%Y %H:%M'),
                        'status': booking.status,
                        'passenger_name': f"{booking.passenger_first_name} {booking.passenger_last_name}"
                    } for booking in bookings[:10]  # Последние 10 бронирований
                ]
            }
            
            return jsonify(details)
            
        except Exception as e:
            return jsonify({'error': 'Ошибка получения данных пользователя'}), 500
    
    @app.route('/admin/user/<int:user_id>/change-role', methods=['POST'])
    @login_required
    def admin_change_user_role(user_id):
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            user = User.query.get_or_404(user_id)
            new_role = request.form.get('new_role')
            reason = request.form.get('reason', '')
            
            if user.role == 'admin':
                flash('Нельзя изменить роль администратора.', 'error')
                return redirect(url_for('admin_users'))
            
            if new_role not in ['user', 'manager']:
                flash('Некорректная роль.', 'error')
                return redirect(url_for('admin_users'))
            
            old_role = user.role
            user.role = new_role
            db.session.commit()
            
            flash(f'Роль пользователя {user.username} изменена: {old_role} → {new_role}', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при изменении роли пользователя.', 'error')
        
        return redirect(url_for('admin_users'))
    
    @app.route('/admin/user/<int:user_id>/toggle-status', methods=['POST'])
    @login_required
    def admin_toggle_user_status(user_id):
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            user = User.query.get_or_404(user_id)
            
            if user.role == 'admin':
                flash('Нельзя заблокировать администратора.', 'error')
                return redirect(url_for('admin_users'))
            
            # Переключаем статус активности пользователя
            if user.is_active:
                user.block_user()
                action = 'заблокирован'
                status_class = 'warning'
            else:
                user.unblock_user()
                action = 'разблокирован'
                status_class = 'success'
            
            db.session.commit()
            flash(f'Пользователь {user.username} ({user.first_name} {user.last_name}) {action}.', status_class)
            
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла ошибка при изменении статуса пользователя: {str(e)}', 'error')
        
        return redirect(url_for('admin_users'))
    
    # МЕНЕДЖЕР ПАНЕЛЬ
    @app.route('/manager')
    @login_required
    def manager_dashboard():
        if not (current_user.is_admin() or current_user.is_manager()):
            flash('У вас нет прав менеджера.', 'error')
            return redirect(url_for('index'))
        
        # Получаем временной фильтр
        time_filter = request.args.get('period', 'all')
        now = datetime.utcnow()
        
        # Определяем временной диапазон
        if time_filter == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif time_filter == 'week':
            start_date = now - timedelta(days=7)
            end_date = now
        elif time_filter == 'month':
            start_date = now - timedelta(days=30)
            end_date = now
        else:  # all
            start_date = None
            end_date = None
        
        # Базовые запросы в зависимости от роли
        if current_user.is_admin():
            # Админ видит всю статистику
            base_flight_query = Flight.query
            base_booking_query = Booking.query
        elif current_user.is_manager() and current_user.company_id:
            # Менеджер видит только статистику своей авиакомпании
            base_flight_query = Flight.query.filter_by(airline_id=current_user.company_id)
            base_booking_query = Booking.query.join(Flight).filter(Flight.airline_id == current_user.company_id)
        else:
            base_flight_query = Flight.query.filter_by(id=0)  # Пустой запрос
            base_booking_query = Booking.query.filter_by(id=0)  # Пустой запрос
        
        # Общая статистика рейсов
        total_flights = base_flight_query.count()
        active_flights = base_flight_query.filter(Flight.departure_time >= now).count()
        completed_flights = base_flight_query.filter(Flight.departure_time < now).count()
        
        # Статистика бронирований с временным фильтром
        if start_date and end_date:
            filtered_bookings = base_booking_query.filter(
                Booking.booking_date >= start_date,
                Booking.booking_date <= end_date
            )
        else:
            filtered_bookings = base_booking_query
        
        total_passengers = filtered_bookings.count()
        total_revenue = db.session.query(db.func.sum(Booking.price_paid)).filter(
            Booking.id.in_([b.id for b in filtered_bookings])
        ).scalar() or 0
        
        # Статистика по статусам бронирований
        confirmed_bookings = filtered_bookings.filter_by(status='confirmed').count()
        cancelled_bookings = filtered_bookings.filter_by(status='cancelled').count()
        refunded_bookings = filtered_bookings.filter_by(status='refunded').count()
        
        # Последние бронирования
        recent_bookings = base_booking_query.order_by(Booking.booking_date.desc()).limit(10).all()
        
        return render_template('manager/dashboard.html',
                             total_flights=total_flights,
                             active_flights=active_flights,
                             completed_flights=completed_flights,
                             total_passengers=total_passengers,
                             total_revenue=total_revenue,
                             confirmed_bookings=confirmed_bookings,
                             cancelled_bookings=cancelled_bookings,
                             refunded_bookings=refunded_bookings,
                             recent_bookings=recent_bookings,
                             current_period=time_filter,
                             now=now)
    
    @app.route('/manager/api/statistics')
    @login_required
    def manager_statistics_api():
        if not (current_user.is_admin() or current_user.is_manager()):
            return jsonify({'error': 'Нет прав доступа'}), 403
        
        period = request.args.get('period', 'all')
        now = datetime.utcnow()
        
        # Определяем временной диапазон
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'week':
            start_date = now - timedelta(days=7)
            end_date = now
        elif period == 'month':
            start_date = now - timedelta(days=30)
            end_date = now
        else:  # all
            start_date = None
            end_date = None
        
        # Базовые запросы в зависимости от роли
        if current_user.is_admin():
            base_flight_query = Flight.query
            base_booking_query = Booking.query
        elif current_user.is_manager() and current_user.company_id:
            base_flight_query = Flight.query.filter_by(airline_id=current_user.company_id)
            base_booking_query = Booking.query.join(Flight).filter(Flight.airline_id == current_user.company_id)
        else:
            base_flight_query = Flight.query.filter_by(id=0)
            base_booking_query = Booking.query.filter_by(id=0)
        
        # Статистика рейсов
        total_flights = base_flight_query.count()
        active_flights = base_flight_query.filter(Flight.departure_time >= now).count()
        completed_flights = base_flight_query.filter(Flight.departure_time < now).count()
        
        # Статистика бронирований с временным фильтром
        if start_date and end_date:
            filtered_bookings = base_booking_query.filter(
                Booking.booking_date >= start_date,
                Booking.booking_date <= end_date
            )
        else:
            filtered_bookings = base_booking_query
        
        total_passengers = filtered_bookings.count()
        total_revenue = db.session.query(db.func.sum(Booking.price_paid)).filter(
            Booking.id.in_([b.id for b in filtered_bookings])
        ).scalar() or 0
        
        # Статистика по статусам
        confirmed_bookings = filtered_bookings.filter_by(status='confirmed').count()
        cancelled_bookings = filtered_bookings.filter_by(status='cancelled').count()
        refunded_bookings = filtered_bookings.filter_by(status='refunded').count()
        
        return jsonify({
            'total_flights': total_flights,
            'active_flights': active_flights,
            'completed_flights': completed_flights,
            'total_passengers': total_passengers,
            'total_revenue': float(total_revenue),
            'confirmed_bookings': confirmed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'refunded_bookings': refunded_bookings,
            'period': period
        })
    
    @app.route('/manager/flights')
    @login_required
    def manager_flights():
        if not (current_user.is_admin() or current_user.is_manager()):
            flash('У вас нет прав менеджера.', 'error')
            return redirect(url_for('index'))
        
        # Получаем рейсы для менеджера
        if current_user.is_admin():
            # Админ видит все рейсы
            flights = Flight.query.order_by(Flight.departure_time.desc()).all()
        else:
            # Менеджер видит только рейсы своей авиакомпании
            if not current_user.company_id:
                flash('У вас не назначена авиакомпания.', 'error')
                return redirect(url_for('manager_dashboard'))
            
            flights = Flight.query.filter_by(airline_id=current_user.company_id).order_by(Flight.departure_time.desc()).all()
        
        return render_template('manager/flights.html', flights=flights)
    
    @app.route('/manager/passengers')
    @login_required
    def manager_passengers():
        if not (current_user.is_admin() or current_user.is_manager()):
            flash('У вас нет прав менеджера.', 'error')
            return redirect(url_for('index'))
        
        # Фильтр по рейсу
        flight_id = request.args.get('flight')
        
        # Получаем рейсы для фильтра
        if current_user.is_admin():
            # Админ видит все рейсы
            flights = Flight.query.order_by(Flight.departure_time.desc()).all()
        else:
            # Менеджер видит только рейсы своей авиакомпании
            if not current_user.company_id:
                flash('У вас не назначена авиакомпания.', 'error')
                return redirect(url_for('manager_dashboard'))
            
            flights = Flight.query.filter_by(airline_id=current_user.company_id).order_by(Flight.departure_time.desc()).all()
        
        # Получаем бронирования
        if current_user.is_admin():
            bookings_query = Booking.query.join(Flight)
        else:
            # Только бронирования на рейсы авиакомпании менеджера
            bookings_query = Booking.query.join(Flight).filter(Flight.airline_id == current_user.company_id)
        
        if flight_id:
            bookings_query = bookings_query.filter(Booking.flight_id == flight_id)
        
        passengers = bookings_query.order_by(Booking.booking_date.desc()).all()
        
        return render_template('manager/passengers.html', 
                             passengers=passengers, 
                             flights=flights)
    
    @app.route('/manager/add-flight', methods=['GET', 'POST'])
    @login_required
    def manager_add_flight():
        if not (current_user.is_admin() or current_user.is_manager()):
            flash('У вас нет прав менеджера.', 'error')
            return redirect(url_for('index'))
        
        form = FlightForm()
        form.departure_airport_id.choices = [(a.id, f"{a.code} - {a.city}") for a in Airport.query.all()]
        form.arrival_airport_id.choices = [(a.id, f"{a.code} - {a.city}") for a in Airport.query.all()]
        
        # Ограничиваем выбор авиакомпании для менеджеров
        if current_user.is_admin():
            form.airline_id.choices = [(a.id, f"{a.code} - {a.name}") for a in Airline.query.all()]
        else:
            # Менеджер может добавлять рейсы только для своей авиакомпании
            if current_user.company_id:
                airline = Airline.query.get(current_user.company_id)
                if airline:
                    form.airline_id.choices = [(airline.id, f"{airline.code} - {airline.name}")]
                    form.airline_id.data = airline.id
        
        if form.validate_on_submit():
            try:
                flight = Flight(
                    flight_number=form.flight_number.data,
                    departure_airport_id=form.departure_airport_id.data,
                    arrival_airport_id=form.arrival_airport_id.data,
                    airline_id=form.airline_id.data,
                    departure_time=form.departure_time.data,
                    arrival_time=form.arrival_time.data,
                    aircraft_type=form.aircraft_type.data,
                    total_seats=form.total_seats.data,
                    available_seats=form.available_seats.data,
                    economy_price=form.economy_price.data,
                    business_price=form.business_price.data,
                    first_class_price=form.first_class_price.data,
                    status=form.status.data
                )
                
                db.session.add(flight)
                db.session.commit()
                
                flash(f'Рейс {flight.flight_number} успешно добавлен!', 'success')
                
                # Редирект зависит от роли пользователя
                if current_user.is_admin():
                    return redirect(url_for('admin_flights'))
                else:
                    return redirect(url_for('manager_flights'))
                
            except Exception as e:
                db.session.rollback()
                flash('Произошла ошибка при добавлении рейса. Проверьте данные.', 'error')
        
        return render_template('manager/add_flight.html', form=form)
    
    @app.route('/manager/edit-flight/<int:flight_id>', methods=['GET', 'POST'])
    @login_required
    def manager_edit_flight(flight_id):
        if not (current_user.is_admin() or current_user.is_manager()):
            flash('У вас нет прав менеджера.', 'error')
            return redirect(url_for('index'))
        
        flight = Flight.query.get_or_404(flight_id)
        
        # Проверяем права на редактирование рейса
        if not current_user.is_admin() and flight.airline_id != current_user.company_id:
            flash('У вас нет прав на редактирование этого рейса.', 'error')
            return redirect(url_for('manager_flights'))
        
        form = FlightForm(obj=flight)
        form.departure_airport_id.choices = [(a.id, f"{a.code} - {a.city}") for a in Airport.query.all()]
        form.arrival_airport_id.choices = [(a.id, f"{a.code} - {a.city}") for a in Airport.query.all()]
        
        # Ограничиваем выбор авиакомпании для менеджеров
        if current_user.is_admin():
            form.airline_id.choices = [(a.id, f"{a.code} - {a.name}") for a in Airline.query.all()]
        else:
            # Менеджер может редактировать только свою авиакомпанию
            if current_user.company_id:
                airline = Airline.query.get(current_user.company_id)
                if airline:
                    form.airline_id.choices = [(airline.id, f"{airline.code} - {airline.name}")]
                    form.airline_id.data = airline.id
        
        if form.validate_on_submit():
            try:
                # Обновляем данные рейса
                flight.flight_number = form.flight_number.data
                flight.departure_airport_id = form.departure_airport_id.data
                flight.arrival_airport_id = form.arrival_airport_id.data
                
                # Менеджер не может изменить авиакомпанию
                if current_user.is_admin():
                    flight.airline_id = form.airline_id.data
                flight.departure_time = form.departure_time.data
                flight.arrival_time = form.arrival_time.data
                flight.aircraft_type = form.aircraft_type.data
                flight.total_seats = form.total_seats.data
                flight.available_seats = form.available_seats.data
                flight.economy_price = form.economy_price.data
                flight.business_price = form.business_price.data
                flight.first_class_price = form.first_class_price.data
                flight.status = form.status.data
                
                db.session.commit()
                
                flash(f'Рейс {flight.flight_number} успешно обновлен!', 'success')
                
                # Редирект зависит от роли пользователя
                if current_user.is_admin():
                    return redirect(url_for('admin_flights'))
                else:
                    return redirect(url_for('manager_flights'))
                
            except Exception as e:
                db.session.rollback()
                flash('Произошла ошибка при обновлении рейса. Проверьте данные.', 'error')
        
        return render_template('manager/edit_flight.html', form=form, flight=flight)
    
    @app.route('/manager/flight/delete/<int:flight_id>', methods=['POST'])
    @login_required
    def manager_delete_flight(flight_id):
        if not (current_user.is_admin() or current_user.is_manager()):
            flash('У вас нет прав менеджера.', 'error')
            return redirect(url_for('index'))
        
        flight = Flight.query.get_or_404(flight_id)
        
        # Проверяем права на удаление рейса
        if not current_user.is_admin() and flight.airline_id != current_user.company_id:
            flash('У вас нет прав на удаление этого рейса.', 'error')
            return redirect(url_for('manager_flights'))
        
        # Проверяем, есть ли бронирования на этот рейс
        bookings_count = Booking.query.filter_by(flight_id=flight_id).count()
        if bookings_count > 0:
            flash(f'Нельзя удалить рейс {flight.flight_number}. На него есть бронирования ({bookings_count}).', 'error')
            return redirect(url_for('manager_flights'))
        
        db.session.delete(flight)
        db.session.commit()
        
        flash(f'Рейс {flight.flight_number} успешно удален.', 'success')
        return redirect(url_for('manager_flights'))
    
    # API для менеджеров
    @app.route('/manager/api/booking/<int:booking_id>/details')
    @login_required
    def manager_booking_details(booking_id):
        if not (current_user.is_admin() or current_user.is_manager()):
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        booking = Booking.query.get_or_404(booking_id)
        
        return jsonify({
            'passenger_first_name': booking.passenger_first_name,
            'passenger_last_name': booking.passenger_last_name,
            'passenger_email': booking.passenger_email,
            'passenger_phone': booking.passenger_phone,
            'flight_number': booking.flight.flight_number,
            'departure_city': booking.flight.departure_airport.city,
            'arrival_city': booking.flight.arrival_airport.city,
            'departure_time': booking.flight.departure_time.strftime('%d.%m.%Y %H:%M'),
            'seat_class': booking.seat_class,
            'seat_number': booking.seat_number,
            'baggage_count': booking.baggage_count,
            'price_paid': booking.price_paid,
            'status': booking.status,
            'booking_date': booking.booking_date.strftime('%d.%m.%Y %H:%M')
        })
    
    @app.route('/admin/assign-seats')
    @login_required
    def admin_assign_seats():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        # Находим все бронирования без номеров мест
        bookings_without_seats = Booking.query.filter(
            (Booking.seat_number.is_(None)) | (Booking.seat_number == '')
        ).all()
        
        updated_count = 0
        for booking in bookings_without_seats:
            try:
                seat_number = generate_seat_number(booking.flight, booking.seat_class)
                booking.seat_number = seat_number
                updated_count += 1
            except Exception as e:
                print(f"Ошибка при назначении места для бронирования {booking.id}: {e}")
                continue
        
        db.session.commit()
        flash(f'Назначено мест: {updated_count}', 'success')
        return redirect(url_for('admin_dashboard'))
    
    @app.route('/api/banner/<int:banner_id>/click', methods=['POST'])
    def track_banner_click(banner_id):
        """Отслеживание кликов по баннеру"""
        try:
            banner = Banner.query.get_or_404(banner_id)
            banner.increment_clicks()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/admin/create-test-banner')
    @login_required
    def admin_create_test_banner():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            # Проверяем, есть ли уже тестовый баннер
            existing_banner = Banner.query.filter_by(title='Специальное предложение!').first()
            if existing_banner:
                flash('Тестовый баннер уже существует!', 'info')
                return redirect(url_for('admin_banners'))
            
            # Создаем тестовый баннер
            test_banner = Banner(
                title='Специальное предложение!',
                description='Скидка 20% на все рейсы до конца месяца. Бронируйте прямо сейчас!',
                image_url='https://via.placeholder.com/300x100/007bff/ffffff?text=Скидка+20%',
                link_url='https://example.com/promo',
                position='main',
                is_active=True,
                start_date=None,
                end_date=None,
                views_count=0,
                clicks_count=0,
                created_by=current_user.id
            )
            
            db.session.add(test_banner)
            db.session.commit()
            
            flash('Тестовый баннер успешно создан!', 'success')
            return redirect(url_for('admin_banners'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании баннера: {str(e)}', 'error')
            return redirect(url_for('admin_banners'))
    
    @app.route('/admin/activate-all-banners')
    @login_required
    def admin_activate_all_banners():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            # Активируем все баннеры и убираем ограничения по датам
            banners = Banner.query.all()
            activated_count = 0
            
            for banner in banners:
                banner.is_active = True
                banner.start_date = None  # Убираем ограничение по дате начала
                banner.end_date = None    # Убираем ограничение по дате окончания
                banner.position = 'main'  # Устанавливаем позицию для главной страницы
                activated_count += 1
            
            db.session.commit()
            
            flash(f'Активировано баннеров: {activated_count}', 'success')
            return redirect(url_for('admin_banners'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при активации баннеров: {str(e)}', 'error')
            return redirect(url_for('admin_banners'))
    
    # API для автодополнения городов
    @app.route('/api/cities')
    def api_cities():
        query = request.args.get('q', '').strip()
        if len(query) < 1:  # Уменьшаем минимальную длину запроса
            return jsonify([])
        
        # Ищем города, нечувствительно к регистру
        # Используем несколько вариантов поиска
        query_lower = query.lower()
        
        # Основной поиск с LOWER()
        cities = db.session.query(Airport.city).filter(
            db.func.lower(Airport.city).like(f'%{query_lower}%')
        ).distinct().limit(15).all()
        
        # Если ничего не найдено, пробуем альтернативные варианты
        if not cities:
            # Поиск с разными вариантами регистра
            cities = db.session.query(Airport.city).filter(
                Airport.city.ilike(f'%{query}%')
            ).distinct().limit(15).all()
        
        # Если все еще ничего не найдено, пробуем частичный поиск
        if not cities and len(query) > 1:
            cities = db.session.query(Airport.city).filter(
                db.func.lower(Airport.city).like(f'%{query_lower[:2]}%')
            ).distinct().limit(15).all()
        
        # Возвращаем города, отсортированные по релевантности
        city_list = [city[0] for city in cities]
        
        # Сортируем: сначала точные совпадения, затем начинающиеся с запроса
        def sort_key(city):
            city_lower = city.lower()
            query_lower = query.lower()
            if city_lower == query_lower:
                return 0  # Точное совпадение
            elif city_lower.startswith(query_lower):
                return 1  # Начинается с запроса
            else:
                return 2  # Содержит запрос
        
        city_list.sort(key=sort_key)
        
        # Отладочная информация
        print(f"DEBUG: Поиск города '{query}', найдено: {len(city_list)}")
        if city_list:
            print(f"DEBUG: Первые результаты: {city_list[:3]}")
        
        return jsonify(city_list)
    
    @app.route('/admin/debug-cities')
    @login_required
    def admin_debug_cities():
        if not current_user.is_admin():
            flash('У вас нет прав администратора.', 'error')
            return redirect(url_for('index'))
        
        try:
            # Получаем все города из базы
            all_cities = db.session.query(Airport.city).distinct().all()
            cities_list = [city[0] for city in all_cities]
            
            return jsonify({
                'total_cities': len(cities_list),
                'cities': cities_list[:20],  # Показываем первые 20
                'sample': cities_list[:5] if cities_list else []
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # Инициализация базы данных
    def init_database():
        with app.app_context():
            db.create_all()
            
            # Создание админа (хардкод как запрошено)
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    email='admin@ticketbooking.com',
                    first_name='Администратор',
                    last_name='Системы',
                    role='admin'
                )
                admin.set_password('admin123')  # Измените пароль в продакшене!
                db.session.add(admin)
            
            # Добавление тестовых данных если их нет
            if Airport.query.count() == 0:
                add_sample_data()
            
            db.session.commit()
    
    def add_sample_data():
        # Аэропорты
        airports = [
            Airport(code='SVO', name='Шереметьево', city='Москва', country='Россия'),
            Airport(code='DME', name='Домодедово', city='Москва', country='Россия'),
            Airport(code='LED', name='Пулково', city='Санкт-Петербург', country='Россия'),
            Airport(code='AER', name='Сочи', city='Сочи', country='Россия'),
            Airport(code='KGD', name='Храброво', city='Калининград', country='Россия'),
        ]
        
        for airport in airports:
            db.session.add(airport)
        
        # Авиакомпании
        airlines = [
            Airline(code='SU', name='Аэрофлот'),
            Airline(code='S7', name='S7 Airlines'),
            Airline(code='FV', name='Россия'),
        ]
        
        for airline in airlines:
            db.session.add(airline)
        
        db.session.commit()
        
        # Рейсы
        flights = [
            Flight(
                flight_number='SU1234',
                departure_airport_id=1, arrival_airport_id=3,
                airline_id=1,
                departure_time=datetime.utcnow() + timedelta(days=1, hours=10),
                arrival_time=datetime.utcnow() + timedelta(days=1, hours=12, minutes=30),
                economy_price=8500, business_price=25000,
                aircraft_type='Boeing 737'
            ),
            Flight(
                flight_number='S7456',
                departure_airport_id=3, arrival_airport_id=1,
                airline_id=2,
                departure_time=datetime.utcnow() + timedelta(days=2, hours=14),
                arrival_time=datetime.utcnow() + timedelta(days=2, hours=16, minutes=20),
                economy_price=9200, business_price=28000,
                aircraft_type='Airbus A320'
            ),
        ]
        
        for flight in flights:
            db.session.add(flight)
        
        db.session.commit()
    
    # Управление назначениями менеджеров
    @app.route('/admin/manager-assignments')
    @login_required
    def admin_manager_assignments():
        if not current_user.is_admin():
            flash('Доступ запрещен', 'error')
            return redirect(url_for('index'))
        
        # Получаем всех менеджеров и авиакомпании
        managers = User.query.filter_by(role='manager').all()
        airlines = Airline.query.all()
        
        # Статистика
        total_managers = len(managers)
        assigned_managers = len([m for m in managers if m.company_id])
        unassigned_managers = total_managers - assigned_managers
        
        return render_template('admin/manager_assignments.html', 
                             managers=managers, 
                             airlines=airlines,
                             total_managers=total_managers,
                             assigned_managers=assigned_managers,
                             unassigned_managers=unassigned_managers)

    @app.route('/admin/airlines')
    @login_required
    def admin_airlines():
        if not current_user.is_admin():
            flash('Доступ запрещен', 'error')
            return redirect(url_for('index'))
        
        # Получаем все авиакомпании с дополнительной информацией
        airlines = Airline.query.all()
        
        # Создаем словарь менеджеров для каждой авиакомпании
        airline_managers = {}
        for airline in airlines:
            managers = User.query.filter_by(company_id=airline.id, role='manager').all()
            airline_managers[airline.id] = managers[0] if managers else None
        
        # Получаем неназначенных менеджеров
        unassigned_managers = User.query.filter_by(role='manager', company_id=None).all()
        
        # Подсчитываем статистику
        airlines_with_managers = 0
        airlines_without_managers = 0
        total_flights = 0
        
        for airline in airlines:
            # Проверяем наличие менеджера
            if airline_managers.get(airline.id):
                airlines_with_managers += 1
            else:
                airlines_without_managers += 1
            
            # Подсчитываем рейсы
            if airline.flights:
                total_flights += len(airline.flights)
        
        return render_template('admin/airlines.html',
                             airlines=airlines,
                             airline_managers=airline_managers,
                             unassigned_managers=unassigned_managers,
                             airlines_with_managers=airlines_with_managers,
                             airlines_without_managers=airlines_without_managers,
                             total_flights=total_flights)

    @app.route('/admin/assign-manager', methods=['POST'])
    @login_required
    def assign_manager():
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            manager_id = request.form.get('manager_id')
            company_id = request.form.get('company_id')
            
            if not manager_id or not company_id:
                flash('Не указан менеджер или компания', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            manager = User.query.get_or_404(manager_id)
            company = Airline.query.get_or_404(company_id)
            
            if manager.role != 'manager':
                flash('Пользователь не является менеджером', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            # Проверяем, не назначен ли уже менеджер к другой компании
            if manager.company_id and manager.company_id != int(company_id):
                old_company = Airline.query.get(manager.company_id)
                flash(f'Менеджер уже назначен к компании {old_company.name}', 'warning')
            
            manager.company_id = company_id
            db.session.commit()
            
            flash(f'Менеджер {manager.first_name} {manager.last_name} назначен к компании {company.name}', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка назначения: {str(e)}', 'error')
        
        return redirect(url_for('admin_manager_assignments'))

    @app.route('/admin/create-manager', methods=['POST'])
    @login_required
    def create_manager():
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            # Получаем данные из формы
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            phone = request.form.get('phone', '').strip()
            password = request.form.get('password', '')
            company_id = request.form.get('company_id')
            
            # Валидация
            if not all([username, email, first_name, last_name, password]):
                flash('Заполните все обязательные поля', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            # Валидация email
            if not is_valid_email(email):
                flash('Введите корректный email адрес', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            if len(password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            # Проверяем уникальность
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    flash(f'Пользователь с логином "{username}" уже существует', 'error')
                else:
                    flash(f'Пользователь с email "{email}" уже существует', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            # Проверяем, что авиакомпания существует (если указана)
            if company_id:
                company = Airline.query.get(company_id)
                if not company:
                    flash('Указанная авиакомпания не найдена', 'error')
                    return redirect(url_for('admin_manager_assignments'))
            
            # Создаем нового менеджера
            new_manager = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone if phone else None,
                role='manager',
                company_id=int(company_id) if company_id else None
            )
            new_manager.set_password(password)
            
            db.session.add(new_manager)
            db.session.commit()
            
            # Сообщение об успехе
            success_msg = f'Менеджер {first_name} {last_name} (@{username}) успешно создан'
            if company_id:
                company = Airline.query.get(company_id)
                success_msg += f' и назначен к компании {company.name}'
            
            flash(success_msg, 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка создания менеджера: {str(e)}', 'error')
        
        return redirect(url_for('admin_manager_assignments'))

    @app.route('/admin/create-airline', methods=['POST'])
    @login_required
    def create_airline():
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            # Получаем данные из формы
            airline_name = request.form.get('airline_name', '').strip()
            airline_code = request.form.get('airline_code', '').strip().upper()
            country = request.form.get('country', '').strip()
            
            # Данные менеджера (опционально)
            create_manager = request.form.get('create_manager') == 'on'
            manager_username = request.form.get('manager_username', '').strip()
            manager_email = request.form.get('manager_email', '').strip()
            manager_first_name = request.form.get('manager_first_name', '').strip()
            manager_last_name = request.form.get('manager_last_name', '').strip()
            manager_phone = request.form.get('manager_phone', '').strip()
            manager_password = request.form.get('manager_password', '')
            
            # Валидация основных данных авиакомпании
            if not all([airline_name, airline_code, country]):
                flash('Заполните все обязательные поля авиакомпании', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            if len(airline_code) != 3:
                flash('Код авиакомпании должен состоять из 3 символов (IATA код)', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            # Проверяем уникальность авиакомпании
            existing_airline = Airline.query.filter(
                (Airline.name == airline_name) | (Airline.code == airline_code)
            ).first()
            
            if existing_airline:
                if existing_airline.name == airline_name:
                    flash(f'Авиакомпания с названием "{airline_name}" уже существует', 'error')
                else:
                    flash(f'Авиакомпания с кодом "{airline_code}" уже существует', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            # Валидация данных менеджера (если создаем)
            if create_manager:
                if not all([manager_username, manager_email, manager_first_name, manager_last_name, manager_password]):
                    flash('Заполните все обязательные поля менеджера', 'error')
                    return redirect(url_for('admin_manager_assignments'))
                
                # Валидация email менеджера
                if not is_valid_email(manager_email):
                    flash('Введите корректный email адрес для менеджера', 'error')
                    return redirect(url_for('admin_manager_assignments'))
                
                if len(manager_password) < 6:
                    flash('Пароль менеджера должен содержать минимум 6 символов', 'error')
                    return redirect(url_for('admin_manager_assignments'))
                
                # Проверяем уникальность менеджера
                existing_manager = User.query.filter(
                    (User.username == manager_username) | (User.email == manager_email)
                ).first()
                
                if existing_manager:
                    if existing_manager.username == manager_username:
                        flash(f'Пользователь с логином "{manager_username}" уже существует', 'error')
                    else:
                        flash(f'Пользователь с email "{manager_email}" уже существует', 'error')
                    return redirect(url_for('admin_manager_assignments'))
            
            # Создаем авиакомпанию
            new_airline = Airline(
                name=airline_name,
                code=airline_code,
                country=country
            )
            
            db.session.add(new_airline)
            db.session.flush()  # Получаем ID авиакомпании
            
            # Создаем менеджера, если требуется
            new_manager = None
            if create_manager:
                new_manager = User(
                    username=manager_username,
                    email=manager_email,
                    first_name=manager_first_name,
                    last_name=manager_last_name,
                    phone=manager_phone if manager_phone else None,
                    role='manager',
                    company_id=new_airline.id
                )
                new_manager.set_password(manager_password)
                db.session.add(new_manager)
            
            db.session.commit()
            
            # Сообщение об успехе
            success_msg = f'Авиакомпания "{airline_name}" ({airline_code}) успешно создана'
            if new_manager:
                success_msg += f' вместе с менеджером {manager_first_name} {manager_last_name} (@{manager_username})'
            
            flash(success_msg, 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка создания авиакомпании: {str(e)}', 'error')
        
        return redirect(url_for('admin_manager_assignments'))

    @app.route('/admin/unassign-manager/<int:manager_id>', methods=['POST'])
    @login_required
    def unassign_manager(manager_id):
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            manager = User.query.get_or_404(manager_id)
            
            if manager.role != 'manager':
                flash('Пользователь не является менеджером', 'error')
                return redirect(url_for('admin_manager_assignments'))
            
            company_name = None
            if manager.company_id:
                company = Airline.query.get(manager.company_id)
                company_name = company.name if company else 'Неизвестная компания'
            
            manager.company_id = None
            db.session.commit()
            
            if company_name:
                flash(f'Менеджер {manager.first_name} {manager.last_name} отключен от компании {company_name}', 'success')
            else:
                flash(f'Менеджер {manager.first_name} {manager.last_name} не был назначен к компании', 'info')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка снятия назначения: {str(e)}', 'error')
        
        return redirect(url_for('admin_manager_assignments'))

    @app.route('/admin/api/manager-assignments')
    @login_required
    def api_manager_assignments():
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            managers = User.query.filter_by(role='manager').all()
            airlines = Airline.query.all()
            
            # Формируем данные для API
            managers_data = []
            for manager in managers:
                company_name = None
                if manager.company_id:
                    company = Airline.query.get(manager.company_id)
                    company_name = company.name if company else None
                
                managers_data.append({
                    'id': manager.id,
                    'username': manager.username,
                    'first_name': manager.first_name,
                    'last_name': manager.last_name,
                    'email': manager.email,
                    'company_id': manager.company_id,
                    'company_name': company_name,
                    'created_at': manager.created_at.strftime('%d.%m.%Y') if manager.created_at else None
                })
            
            airlines_data = [{
                'id': airline.id,
                'name': airline.name,
                'code': airline.code,
                'country': airline.country
            } for airline in airlines]
            
            return jsonify({
                'managers': managers_data,
                'airlines': airlines_data,
                'statistics': {
                    'total_managers': len(managers),
                    'assigned_managers': len([m for m in managers if m.company_id]),
                    'unassigned_managers': len([m for m in managers if not m.company_id]),
                    'total_airlines': len(airlines)
                }
            })
            
        except Exception as e:
            return jsonify({'error': f'Ошибка получения данных: {str(e)}'}), 500

    # АДМИНИСТРИРОВАНИЕ РЕКЛАМНЫХ БАННЕРОВ
    @app.route('/admin/banners')
    @login_required
    def admin_banners():
        if not current_user.is_admin():
            flash('Доступ запрещен', 'error')
            return redirect(url_for('index'))
        
        # Получаем все баннеры
        banners = Banner.query.order_by(Banner.priority.desc(), Banner.created_at.desc()).all()
        
        # Статистика
        total_banners = len(banners)
        active_banners = len([b for b in banners if b.is_currently_active()])
        total_views = sum(b.views_count for b in banners)
        total_clicks = sum(b.clicks_count for b in banners)
        
        return render_template('admin/banners.html', 
                             banners=banners,
                             total_banners=total_banners,
                             active_banners=active_banners,
                             total_views=total_views,
                             total_clicks=total_clicks)
    
    @app.route('/admin/banner/create', methods=['POST'])
    @login_required
    def create_banner():
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            # Получаем данные из формы
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            image_url = request.form.get('image_url', '').strip()
            link_url = request.form.get('link_url', '').strip()
            position = request.form.get('position', 'main')
            priority = int(request.form.get('priority', 0))
            
            # Даты показа (опционально)
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            # Валидация
            if not all([title, image_url]):
                flash('Заполните обязательные поля: заголовок и URL изображения', 'error')
                return redirect(url_for('admin_banners'))
            
            # Парсим даты
            start_date = None
            end_date = None
            
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash('Неверный формат даты начала', 'error')
                    return redirect(url_for('admin_banners'))
            
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash('Неверный формат даты окончания', 'error')
                    return redirect(url_for('admin_banners'))
            
            # Проверяем даты
            if start_date and end_date and start_date >= end_date:
                flash('Дата начала должна быть раньше даты окончания', 'error')
                return redirect(url_for('admin_banners'))
            
            # Создаем баннер
            banner = Banner(
                title=title,
                description=description if description else None,
                image_url=image_url,
                link_url=link_url if link_url else None,
                position=position,
                priority=priority,
                start_date=start_date,
                end_date=end_date,
                created_by=current_user.id
            )
            
            db.session.add(banner)
            db.session.commit()
            
            flash(f'Баннер "{title}" успешно создан!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка создания баннера: {str(e)}', 'error')
        
        return redirect(url_for('admin_banners'))
    
    @app.route('/admin/banner/toggle/<int:banner_id>', methods=['POST'])
    @login_required
    def toggle_banner(banner_id):
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            banner = Banner.query.get_or_404(banner_id)
            banner.is_active = not banner.is_active
            banner.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            status = "активирован" if banner.is_active else "деактивирован"
            flash(f'Баннер "{banner.title}" {status}', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка изменения статуса баннера: {str(e)}', 'error')
        
        return redirect(url_for('admin_banners'))
    
    @app.route('/admin/banner/delete/<int:banner_id>', methods=['POST'])
    @login_required
    def delete_banner(banner_id):
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            banner = Banner.query.get_or_404(banner_id)
            banner_title = banner.title
            
            db.session.delete(banner)
            db.session.commit()
            
            flash(f'Баннер "{banner_title}" успешно удален', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка удаления баннера: {str(e)}', 'error')
        
        return redirect(url_for('admin_banners'))
    
    @app.route('/admin/banner/edit/<int:banner_id>', methods=['POST'])
    @login_required
    def edit_banner(banner_id):
        if not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        try:
            banner = Banner.query.get_or_404(banner_id)
            
            # Получаем данные из формы
            banner.title = request.form.get('title', '').strip()
            banner.description = request.form.get('description', '').strip() or None
            banner.image_url = request.form.get('image_url', '').strip()
            banner.link_url = request.form.get('link_url', '').strip() or None
            banner.position = request.form.get('position', 'main')
            banner.priority = int(request.form.get('priority', 0))
            banner.updated_at = datetime.utcnow()
            
            # Даты показа
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            # Валидация
            if not all([banner.title, banner.image_url]):
                flash('Заполните обязательные поля: заголовок и URL изображения', 'error')
                return redirect(url_for('admin_banners'))
            
            # Парсим даты
            if start_date_str:
                try:
                    banner.start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash('Неверный формат даты начала', 'error')
                    return redirect(url_for('admin_banners'))
            else:
                banner.start_date = None
            
            if end_date_str:
                try:
                    banner.end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash('Неверный формат даты окончания', 'error')
                    return redirect(url_for('admin_banners'))
            else:
                banner.end_date = None
            
            # Проверяем даты
            if banner.start_date and banner.end_date and banner.start_date >= banner.end_date:
                flash('Дата начала должна быть раньше даты окончания', 'error')
                return redirect(url_for('admin_banners'))
            
            db.session.commit()
            
            flash(f'Баннер "{banner.title}" успешно обновлен!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления баннера: {str(e)}', 'error')
        
        return redirect(url_for('admin_banners'))
    
    @app.route('/banner/click/<int:banner_id>')
    def banner_click(banner_id):
        """Обработка клика по баннеру и перенаправление"""
        try:
            banner = Banner.query.get_or_404(banner_id)
            
            # Увеличиваем счетчик кликов
            banner.increment_clicks()
            
            # Перенаправляем по ссылке баннера
            if banner.link_url:
                return redirect(banner.link_url)
            else:
                return redirect(url_for('index'))
                
        except Exception:
            return redirect(url_for('index'))
    
    # Регистрация декоратора в Jinja2
    app.jinja_env.globals.update(requires_role=requires_role)
    
    def migrate_database():
        """Добавляет недостающие колонки в базу данных"""
        try:
            # Проверяем существующие колонки
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(booking)"))
                columns = [column[1] for column in result.fetchall()]
                
                # Добавляем колонку cancelled_at
                if 'cancelled_at' not in columns:
                    conn.execute(text('ALTER TABLE booking ADD COLUMN cancelled_at DATETIME'))
                    print("✓ Добавлена колонка cancelled_at")
                
                # Добавляем колонку cancellation_reason
                if 'cancellation_reason' not in columns:
                    conn.execute(text('ALTER TABLE booking ADD COLUMN cancellation_reason VARCHAR(100)'))
                    print("✓ Добавлена колонка cancellation_reason")
                    
                conn.commit()
                
        except Exception as e:
            print(f"Ошибка миграции: {e}")
    
    # Выполняем миграцию при запуске
    with app.app_context():
        migrate_database()
    
    @app.route('/booking/<int:booking_id>/cancel')
    @login_required
    def cancel_booking(booking_id):
        """Страница отмены бронирования"""
        booking = Booking.query.get_or_404(booking_id)
        
        # Проверяем, что пользователь может отменить это бронирование
        if booking.user_id != current_user.id and not current_user.is_admin():
            flash('У вас нет прав для отмены этого бронирования.', 'error')
            return redirect(url_for('profile'))
        
        # Проверяем, можно ли отменить
        if not booking.can_be_cancelled() and booking.status == 'confirmed':
            flash('Бронирование нельзя отменить менее чем за 24 часа до вылета.', 'error')
            return redirect(url_for('profile'))
        
        if booking.status in ['cancelled', 'refunded']:
            flash('Бронирование уже отменено.', 'info')
            return redirect(url_for('profile'))
        
        return render_template('cancel_booking.html', booking=booking)
    
    @app.route('/booking/<int:booking_id>/details')
    @login_required
    def booking_details(booking_id):
        """Получение деталей бронирования в JSON формате"""
        booking = Booking.query.get_or_404(booking_id)
        
        # Проверяем права доступа
        if booking.user_id != current_user.id and not current_user.is_admin():
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        # Подготавливаем данные для JSON
        booking_data = {
            'id': booking.id,
            'booking_reference': booking.booking_reference,
            'status': booking.status,
            'booking_date': booking.booking_date.strftime('%d.%m.%Y %H:%M'),
            'passenger': {
                'first_name': booking.passenger_first_name,
                'last_name': booking.passenger_last_name,
                'email': booking.passenger_email,
                'phone': booking.passenger_phone
            },
            'flight': {
                'number': booking.flight.flight_number,
                'airline': booking.flight.airline.name,
                'aircraft_type': booking.flight.aircraft_type,
                'departure': {
                    'airport': booking.flight.departure_airport.name,
                    'city': booking.flight.departure_airport.city,
                    'code': booking.flight.departure_airport.code,
                    'time': booking.flight.departure_time.strftime('%d.%m.%Y %H:%M')
                },
                'arrival': {
                    'airport': booking.flight.arrival_airport.name,
                    'city': booking.flight.arrival_airport.city,
                    'code': booking.flight.arrival_airport.code,
                    'time': booking.flight.arrival_time.strftime('%d.%m.%Y %H:%M')
                },
                'duration': str(booking.flight.duration).split('.')[0]  # Убираем микросекунды
            },
            'seat': {
                'class': booking.seat_class,
                'number': booking.seat_number,
                'class_display': {
                    'economy': 'Эконом',
                    'business': 'Бизнес',
                    'first': 'Первый'
                }.get(booking.seat_class, booking.seat_class)
            },
            'price': booking.price_paid,
            'services': {
                'baggage_count': booking.baggage_count,
                'meal_preference': booking.meal_preference,
                'special_requests': booking.special_requests
            },
            'cancellation': {
                'can_be_cancelled': booking.can_be_cancelled(),
                'can_be_refunded': booking.can_be_refunded(),
                'cancellation_type': booking.get_cancellation_type(),
                'time_until_departure': booking.get_time_until_departure(),
                'cancelled_at': booking.cancelled_at.strftime('%d.%m.%Y %H:%M') if booking.cancelled_at else None,
                'cancellation_reason': booking.cancellation_reason
            }
        }
        
        return jsonify(booking_data)
    
    @app.route('/booking/<int:booking_id>/cancel', methods=['POST'])
    @login_required
    def process_cancellation(booking_id):
        """Обработка отмены бронирования"""
        booking = Booking.query.get_or_404(booking_id)
        
        # Проверяем права
        if booking.user_id != current_user.id and not current_user.is_admin():
            flash('У вас нет прав для отмены этого бронирования.', 'error')
            return redirect(url_for('profile'))
        
        # Проверяем статус
        if booking.status in ['cancelled', 'refunded']:
            flash('Бронирование уже отменено.', 'info')
            return redirect(url_for('profile'))
        
        try:
            # Определяем тип отмены
            cancellation_type = booking.get_cancellation_type()
            reason = request.form.get('reason', 'Отмена пользователем')
            
            # Обновляем статус бронирования
            if cancellation_type == 'refund':
                booking.status = 'refunded'
                flash(f'Бронирование отменено с возвратом средств. Сумма к возврату: {booking.price_paid:.0f} ₽', 'success')
            else:
                booking.status = 'cancelled'
                flash('Бронирование отменено без возврата средств (менее 24 часов до вылета).', 'warning')
            
            booking.cancelled_at = datetime.utcnow()
            booking.cancellation_reason = reason
            
            # Освобождаем место в рейсе
            booking.flight.available_seats += 1
            
            db.session.commit()
            
            return redirect(url_for('profile'))
            
        except Exception as e:
            db.session.rollback()
            flash('Произошла ошибка при отмене бронирования.', 'error')
            return redirect(url_for('cancel_booking', booking_id=booking_id))
    
    @app.route('/init-data')
    def init_data():
        """Initialize test data"""
        try:
            # Check if data already exists
            if User.query.count() > 0:
                return jsonify({'message': 'Data already exists!', 'status': 'exists'})
            
            # Add test users
            admin = User(
                username='admin',
                email='admin@example.com',
                first_name='Админ',
                last_name='Системы',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Add airports
            airports_data = [
                {'code': 'SVO', 'name': 'Шереметьево', 'city': 'Москва', 'country': 'Россия'},
                {'code': 'LED', 'name': 'Пулково', 'city': 'Санкт-Петербург', 'country': 'Россия'},
                {'code': 'DME', 'name': 'Домодедово', 'city': 'Москва', 'country': 'Россия'},
                {'code': 'ROV', 'name': 'Платов', 'city': 'Ростов-на-Дону', 'country': 'Россия'},
                {'code': 'KRR', 'name': 'Пашковский', 'city': 'Краснодар', 'country': 'Россия'}
            ]
            
            airports = []
            for airport_data in airports_data:
                airport = Airport(**airport_data)
                airports.append(airport)
                db.session.add(airport)
            
            # Add airlines
            airlines_data = [
                {'code': 'SU', 'name': 'Аэрофлот', 'country': 'Россия'},
                {'code': 'FV', 'name': 'Россия', 'country': 'Россия'},
                {'code': 'U6', 'name': 'Уральские авиалинии', 'country': 'Россия'}
            ]
            
            airlines = []
            for airline_data in airlines_data:
                airline = Airline(**airline_data)
                airlines.append(airline)
                db.session.add(airline)
            
            db.session.commit()
            
            # Add manager
            manager = User(
                username='manager',
                email='manager@airline.com',
                first_name='Менеджер',
                last_name='Авиакомпании',
                role='manager',
                company_id=airlines[0].id  # Аэрофлот
            )
            manager.set_password('manager123')
            db.session.add(manager)
            
            # Add regular user
            user = User(
                username='user',
                email='user@example.com',
                first_name='Иван',
                last_name='Петров',
                role='user'
            )
            user.set_password('user123')
            db.session.add(user)
            
            db.session.commit()
            
            # Add flights
            from datetime import datetime, timedelta
            base_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            flights_data = [
                {
                    'flight_number': 'SU100',
                    'departure_airport_id': airports[0].id,
                    'arrival_airport_id': airports[1].id,
                    'airline_id': airlines[0].id,
                    'departure_time': base_time + timedelta(hours=8),
                    'arrival_time': base_time + timedelta(hours=10),
                    'aircraft_type': 'Boeing 737',
                    'total_seats': 180,
                    'available_seats': 150,
                    'economy_price': 8500,
                    'business_price': 15000,
                    'status': 'scheduled'
                },
                {
                    'flight_number': 'SU200',
                    'departure_airport_id': airports[0].id,
                    'arrival_airport_id': airports[3].id,
                    'airline_id': airlines[0].id,
                    'departure_time': base_time + timedelta(hours=12),
                    'arrival_time': base_time + timedelta(hours=15, minutes=30),
                    'aircraft_type': 'Airbus A320',
                    'total_seats': 180,
                    'available_seats': 120,
                    'economy_price': 12000,
                    'business_price': 20000,
                    'status': 'scheduled'
                }
            ]
            
            flights = []
            for flight_data in flights_data:
                flight = Flight(**flight_data)
                flights.append(flight)
                db.session.add(flight)
            
            db.session.commit()
            
            # Add bookings
            bookings_data = [
                {
                    'booking_reference': 'ABC123',
                    'user_id': user.id,
                    'flight_id': flights[0].id,
                    'passenger_first_name': 'Иван',
                    'passenger_last_name': 'Петров',
                    'passenger_email': 'ivan.petrov@example.com',
                    'passenger_phone': '+7-900-123-45-67',
                    'seat_class': 'economy',
                    'seat_number': '12A',
                    'price_paid': 8500,
                    'status': 'confirmed',
                    'booking_date': base_time - timedelta(hours=2),
                    'baggage_count': 1
                },
                {
                    'booking_reference': 'DEF456',
                    'user_id': user.id,
                    'flight_id': flights[1].id,
                    'passenger_first_name': 'Мария',
                    'passenger_last_name': 'Сидорова',
                    'passenger_email': 'maria.sidorova@example.com',
                    'passenger_phone': '+7-900-234-56-78',
                    'seat_class': 'business',
                    'seat_number': '3B',
                    'price_paid': 20000,
                    'status': 'confirmed',
                    'booking_date': base_time - timedelta(hours=5),
                    'baggage_count': 2
                }
            ]
            
            for booking_data in bookings_data:
                booking = Booking(**booking_data)
                db.session.add(booking)
            
            # Add test banner
            test_banner = Banner(
                title='Специальное предложение!',
                description='Скидка 20% на все рейсы до конца месяца. Бронируйте прямо сейчас!',
                image_url='https://via.placeholder.com/300x100/007bff/ffffff?text=Скидка+20%',
                link_url='https://example.com/promo',
                position='main',
                is_active=True,
                start_date=None,  # Баннер активен сразу
                end_date=None,    # Без ограничения по времени
                views_count=0,
                clicks_count=0,
                created_by=admin.id
            )
            db.session.add(test_banner)
            
            db.session.commit()
            
            return jsonify({
                'message': 'Test data added successfully!',
                'status': 'success',
                'data': {
                    'users': User.query.count(),
                    'airports': Airport.query.count(),
                    'airlines': Airline.query.count(),
                    'flights': Flight.query.count(),
                    'bookings': Booking.query.count()
                },
                'accounts': {
                    'admin': 'admin / admin123',
                    'manager': 'manager / manager123',
                    'user': 'user / user123'
                }
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e), 'status': 'error'})
    
    return app, init_database

if __name__ == '__main__':
    app, init_db = create_app()
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)