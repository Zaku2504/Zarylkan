from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='user')  # user, manager, admin
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    company_id = db.Column(db.Integer, db.ForeignKey('airline.id'), nullable=True)  # Для менеджеров
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Статус активности
    
    # Связи
    bookings = db.relationship('Booking', backref='user', lazy=True)
    company = db.relationship('Airline', backref='managers', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_manager(self):
        return self.role == 'manager'
    
    def is_user_active(self):
        """Проверяет, активен ли пользователь"""
        return self.is_active
    
    def block_user(self):
        """Блокирует пользователя"""
        self.is_active = False
    
    def unblock_user(self):
        """Разблокирует пользователя"""
        self.is_active = True

class Airport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(3), unique=True, nullable=False)  # IATA код
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    country = db.Column(db.String(50), nullable=False)
    
    # Связи с рейсами
    departure_flights = db.relationship('Flight', foreign_keys='Flight.departure_airport_id', backref='departure_airport', lazy=True)
    arrival_flights = db.relationship('Flight', foreign_keys='Flight.arrival_airport_id', backref='arrival_airport', lazy=True)

class Airline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(3), unique=True, nullable=False)  # IATA код авиакомпании
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(50), nullable=False)  # Страна авиакомпании
    
    # Связь с рейсами
    flights = db.relationship('Flight', backref='airline', lazy=True)

class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flight_number = db.Column(db.String(10), nullable=False)
    
    # Аэропорты
    departure_airport_id = db.Column(db.Integer, db.ForeignKey('airport.id'), nullable=False)
    arrival_airport_id = db.Column(db.Integer, db.ForeignKey('airport.id'), nullable=False)
    
    # Авиакомпания
    airline_id = db.Column(db.Integer, db.ForeignKey('airline.id'), nullable=False)
    
    # Время
    departure_time = db.Column(db.DateTime, nullable=False)
    arrival_time = db.Column(db.DateTime, nullable=False)
    
    # Информация о рейсе
    aircraft_type = db.Column(db.String(50))
    total_seats = db.Column(db.Integer, default=180)
    available_seats = db.Column(db.Integer, default=180)
    
    # Цены по классам
    economy_price = db.Column(db.Float, nullable=False)
    business_price = db.Column(db.Float)
    first_class_price = db.Column(db.Float)
    
    # Статус рейса
    status = db.Column(db.String(20), default='scheduled')  # scheduled, delayed, cancelled, boarding, departed
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь с бронированиями
    bookings = db.relationship('Booking', backref='flight', lazy=True)
    
    @property
    def duration(self):
        """Возвращает продолжительность полета"""
        return self.arrival_time - self.departure_time

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_reference = db.Column(db.String(6), unique=True, nullable=False)  # Код бронирования
    
    # Связи
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    
    # Информация о пассажире
    passenger_first_name = db.Column(db.String(50), nullable=False)
    passenger_last_name = db.Column(db.String(50), nullable=False)
    passenger_email = db.Column(db.String(120))
    passenger_phone = db.Column(db.String(20))
    
    # Детали бронирования
    seat_class = db.Column(db.String(20), default='economy')  # economy, business, first
    seat_number = db.Column(db.String(10))
    price_paid = db.Column(db.Float, nullable=False)
    
    # Статус и даты
    status = db.Column(db.String(20), default='confirmed')  # confirmed, cancelled, checked_in, refunded
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime)  # Дата отмены
    cancellation_reason = db.Column(db.String(100))  # Причина отмены
    
    # Дополнительные услуги
    baggage_count = db.Column(db.Integer, default=1)
    meal_preference = db.Column(db.String(50))
    special_requests = db.Column(db.Text)
    
    def can_be_cancelled(self):
        """Проверяет, можно ли отменить бронирование"""
        if self.status in ['cancelled', 'refunded']:
            return False
        
        # Проверяем время до вылета
        time_until_departure = self.flight.departure_time - datetime.utcnow()
        return time_until_departure.total_seconds() > 24 * 3600  # 24 часа
    
    def can_be_refunded(self):
        """Проверяет, можно ли вернуть деньги"""
        if self.status in ['cancelled', 'refunded']:
            return False
        
        # Возврат возможен только за 24+ часов до вылета
        time_until_departure = self.flight.departure_time - datetime.utcnow()
        return time_until_departure.total_seconds() > 24 * 3600
    
    def get_cancellation_type(self):
        """Возвращает тип отмены: 'refund' или 'no_refund'"""
        if self.can_be_refunded():
            return 'refund'
        else:
            return 'no_refund'
    
    def get_time_until_departure(self):
        """Возвращает время до вылета в часах"""
        time_until_departure = self.flight.departure_time - datetime.utcnow()
        return time_until_departure.total_seconds() / 3600

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))  # card, paypal, bank_transfer
    transaction_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь с бронированием
    booking = db.relationship('Booking', backref=db.backref('payments', lazy=True))

class Banner(db.Model):
    """Модель рекламного баннера"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)  # Заголовок баннера
    description = db.Column(db.Text)  # Описание (опционально)
    image_url = db.Column(db.String(500), nullable=False)  # URL изображения
    link_url = db.Column(db.String(500))  # Ссылка при клике (опционально)
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Активен ли баннер
    
    # Настройки показа
    start_date = db.Column(db.DateTime)  # Дата начала показа (опционально)
    end_date = db.Column(db.DateTime)    # Дата окончания показа (опционально)
    position = db.Column(db.String(50), default='main')  # Позиция: main, sidebar, header, footer
    priority = db.Column(db.Integer, default=0)  # Приоритет показа (больше = выше)
    
    # Статистика
    views_count = db.Column(db.Integer, default=0)  # Количество показов
    clicks_count = db.Column(db.Integer, default=0)  # Количество кликов
    
    # Системные поля
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # Кто создал
    
    # Связи
    creator = db.relationship('User', backref='created_banners', lazy=True)
    
    def is_currently_active(self):
        """Проверяет, активен ли баннер в данный момент"""
        if not self.is_active:
            return False
        
        now = datetime.utcnow()
        
        # Проверяем дату начала
        if self.start_date and now < self.start_date:
            return False
            
        # Проверяем дату окончания  
        if self.end_date and now > self.end_date:
            return False
            
        return True
    
    def get_click_rate(self):
        """Возвращает CTR (Click Through Rate) в процентах"""
        if self.views_count == 0:
            return 0
        return round((self.clicks_count / self.views_count) * 100, 2)
    
    def increment_views(self):
        """Увеличивает счетчик просмотров"""
        self.views_count += 1
        db.session.commit()
    
    def increment_clicks(self):
        """Увеличивает счетчик кликов"""
        self.clicks_count += 1
        db.session.commit()
    
    def to_dict(self):
        """Преобразует объект Banner в словарь для JSON сериализации"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'image_url': self.image_url,
            'link_url': self.link_url,
            'is_active': self.is_active,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'position': self.position,
            'priority': self.priority,
            'views_count': self.views_count,
            'clicks_count': self.clicks_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by
        }