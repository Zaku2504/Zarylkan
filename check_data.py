import os
import sys

# Add ticket-booking-app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ticket-booking-app'))

try:
    from app import create_app, db
    from models import User, Airport, Airline, Flight, Booking
    
    app, init_db = create_app()
    
    with app.app_context():
        init_db()
        
        print("=== DATABASE STATUS ===")
        print(f"Users: {User.query.count()}")
        print(f"Airports: {Airport.query.count()}")
        print(f"Airlines: {Airline.query.count()}")
        print(f"Flights: {Flight.query.count()}")
        print(f"Bookings: {Booking.query.count()}")
        
        if User.query.count() == 0:
            print("\n❌ NO DATA FOUND!")
            print("You need to add test data first.")
        else:
            print("\n✅ Data exists!")
            
            # Show some sample data
            print("\n--- Sample Users ---")
            for user in User.query.limit(3):
                print(f"  {user.username} ({user.role})")
            
            print("\n--- Sample Flights ---")
            for flight in Flight.query.limit(3):
                print(f"  {flight.flight_number}: {flight.departure_airport.city} → {flight.arrival_airport.city}")
            
            print("\n--- Sample Bookings ---")
            for booking in Booking.query.limit(3):
                print(f"  {booking.booking_reference}: {booking.passenger_first_name} {booking.passenger_last_name}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
