from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, IntegerField, FloatField, TextAreaField, DateTimeLocalField, URLField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, NumberRange, Regexp
from datetime import datetime

class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class RegistrationForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('Имя', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Фамилия', validators=[DataRequired(), Length(max=50)])
    phone = StringField('Телефон', validators=[Optional(), Length(max=20), Regexp(r'^[\+]?[0-9\s\-\(\)]+$', message='Неверный формат телефона')])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Повторите пароль', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Роль', choices=[('user', 'Пассажир'), ('manager', 'Менеджер')], default='user')
    submit = SubmitField('Зарегистрироваться')

class FlightSearchForm(FlaskForm):
    departure_city = StringField('Откуда', validators=[Optional()])
    arrival_city = StringField('Куда', validators=[Optional()])
    departure_date = DateTimeLocalField('Дата вылета', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    return_date = DateTimeLocalField('Дата возвращения', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    passengers = IntegerField('Количество пассажиров', validators=[Optional(), NumberRange(min=1, max=9, message='Количество пассажиров должно быть от 1 до 9')], default=1)
    seat_class = SelectField('Класс', choices=[('economy', 'Эконом'), ('business', 'Бизнес'), ('first', 'Первый')], default='economy')
    submit = SubmitField('Найти рейсы')

class BookingForm(FlaskForm):
    passenger_first_name = StringField('Имя пассажира', validators=[DataRequired(), Length(max=50)])
    passenger_last_name = StringField('Фамилия пассажира', validators=[DataRequired(), Length(max=50)])
    passenger_email = StringField('Email пассажира', validators=[DataRequired(), Email()])
    passenger_phone = StringField('Телефон пассажира', validators=[Optional(), Length(max=20), Regexp(r'^[\+]?[0-9\s\-\(\)]+$', message='Неверный формат телефона')])
    seat_class = SelectField('Класс', choices=[('economy', 'Эконом'), ('business', 'Бизнес'), ('first', 'Первый')], default='economy')
    baggage_count = IntegerField('Количество багажа', validators=[Optional(), NumberRange(min=0, max=5, message='Количество багажа должно быть от 0 до 5')], default=1)
    meal_preference = SelectField('Питание', choices=[('', 'Стандартное'), ('vegetarian', 'Вегетарианское'), ('halal', 'Халяль'), ('kosher', 'Кошер')], default='')
    special_requests = TextAreaField('Особые пожелания', validators=[Optional()])
    submit = SubmitField('Забронировать')

class FlightForm(FlaskForm):
    flight_number = StringField('Номер рейса', validators=[DataRequired(), Length(max=10)])
    departure_airport_id = SelectField('Аэропорт вылета', coerce=int, validators=[DataRequired()])
    arrival_airport_id = SelectField('Аэропорт прибытия', coerce=int, validators=[DataRequired()])
    airline_id = SelectField('Авиакомпания', coerce=int, validators=[DataRequired()])
    departure_time = DateTimeLocalField('Время вылета', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    arrival_time = DateTimeLocalField('Время прибытия', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    aircraft_type = StringField('Тип самолета', validators=[Optional(), Length(max=50)])
    total_seats = IntegerField('Всего мест', validators=[DataRequired()], default=180)
    available_seats = IntegerField('Доступно мест', validators=[DataRequired()], default=180)
    economy_price = FloatField('Цена эконом', validators=[DataRequired()])
    business_price = FloatField('Цена бизнес', validators=[Optional()])
    first_class_price = FloatField('Цена первый класс', validators=[Optional()])
    status = SelectField('Статус', choices=[('scheduled', 'Запланирован'), ('delayed', 'Задержан'), ('cancelled', 'Отменен'), ('boarding', 'Посадка'), ('departed', 'Вылетел')], default='scheduled')
    submit = SubmitField('Сохранить рейс')

class AirportForm(FlaskForm):
    code = StringField('IATA код', validators=[DataRequired(), Length(min=3, max=3)])
    name = StringField('Название аэропорта', validators=[DataRequired(), Length(max=100)])
    city = StringField('Город', validators=[DataRequired(), Length(max=50)])
    country = StringField('Страна', validators=[DataRequired(), Length(max=50)])
    submit = SubmitField('Сохранить аэропорт')

class AirlineForm(FlaskForm):
    code = StringField('IATA код', validators=[DataRequired(), Length(min=2, max=3)])
    name = StringField('Название авиакомпании', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Сохранить авиакомпанию')

class BannerForm(FlaskForm):
    title = StringField('Заголовок баннера', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Описание', validators=[Optional(), Length(max=500)])
    image_url = URLField('URL изображения', validators=[Optional()])
    link_url = URLField('URL ссылки', validators=[Optional()])
    position = SelectField('Позиция', choices=[('main', 'Главная страница'), ('sidebar', 'Боковая панель')], default='main')
    is_active = BooleanField('Активен', default=True)
    start_date = DateTimeLocalField('Дата начала', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    end_date = DateTimeLocalField('Дата окончания', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    submit = SubmitField('Сохранить баннер')