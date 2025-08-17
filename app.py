from flask import Flask, render_template, make_response
import requests
from datetime import datetime, timedelta
import pytz
from astral import LocationInfo
from astral.sun import sun
from astral.moon import phase

app = Flask(__name__)

def get_moon_phase_name(phase_value):
    """
    Determines the moon phase name based on the phase value.
    The phase value is between 0 and 27.99, where:
    0 = New Moon
    7 = First Quarter
    14 = Full Moon
    21 = Last Quarter
    """
    # Convert to a 0-28 range
    if phase_value < 1.75 or phase_value > 26.25:
        return "New Moon"
    elif 1.75 <= phase_value < 5.25:
        return "Waxing Crescent"
    elif 5.25 <= phase_value < 8.75:
        return "First Quarter"
    elif 8.75 <= phase_value < 12.25:
        return "Waxing Gibbous"
    elif 12.25 <= phase_value < 15.75:
        return "Full Moon"
    elif 15.75 <= phase_value < 19.25:
        return "Waning Gibbous"
    elif 19.25 <= phase_value < 22.75:
        return "Last Quarter"
    else:  # 22.75 <= phase_value < 26.25
        return "Waning Crescent"

def get_weather_data():
    try:
        # Get coordinates for zip code 03833 (Exeter, NH)
        lat, lon = 42.9814, -70.9462  # Coordinates for 03833
        print(f"Fetching weather data for coordinates: {lat}, {lon}")
        # Add a user agent and timestamp to prevent caching
        current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        headers = {
            'User-Agent': f'(Weather Dashboard, julie@example.com, timestamp={current_timestamp})',
            'Accept': 'application/geo+json',
            'Cache-Control': 'no-cache'
        }
        
        point_url = f"https://api.weather.gov/points/{lat},{lon}"
        response = requests.get(point_url, headers=headers)
        if response.status_code != 200:
            print(f"Error getting points data: {response.status_code}")
            print(f"Response: {response.text}")
            response.raise_for_status()
        grid_data = response.json()
        
        # Get forecast data
        forecast_url = grid_data['properties']['forecast']
        forecast_response = requests.get(forecast_url, headers=headers)
        if forecast_response.status_code != 200:
            print(f"Error getting forecast: {forecast_response.status_code}")
            print(f"Response: {forecast_response.text}")
            forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        # Get additional weather data (includes humidity)
        hourly_url = grid_data['properties']['forecastHourly']
        hourly_response = requests.get(hourly_url, headers=headers)
        if hourly_response.status_code != 200:
            print(f"Error getting hourly data: {hourly_response.status_code}")
            print(f"Response: {hourly_response.text}")
            hourly_response.raise_for_status()
        hourly_data = hourly_response.json()
        
        # Calculate sunrise and sunset times for Exeter, NH
        location = LocationInfo("Exeter", "USA", "US/Eastern", lat, lon)
        s = sun(location.observer, date=datetime.now())
        
        # Convert UTC times to local timezone
        eastern = pytz.timezone('America/New_York')
        sunrise = s['sunrise'].replace(tzinfo=pytz.UTC).astimezone(eastern)
        sunset = s['sunset'].replace(tzinfo=pytz.UTC).astimezone(eastern)
        
        # Print current temperature from hourly data for debugging
        current_temp = hourly_data['properties']['periods'][0]['temperature']
        current_forecast = hourly_data['properties']['periods'][0]['shortForecast']
        print(f"Current temperature from API: {current_temp}°F, Condition: {current_forecast}")
        print(f"First forecast period: {forecast_data['properties']['periods'][0]['temperature']}°F, {forecast_data['properties']['periods'][0]['shortForecast']}")
        
        # Calculate moon phase
        today = datetime.now()
        moon_phase_value = phase(today)
        moon_phase_name = get_moon_phase_name(moon_phase_value)
        
        return {
            'forecast': forecast_data['properties']['periods'],
            'hourly': hourly_data['properties']['periods'],
            'humidity': hourly_data['properties']['periods'][0]['relativeHumidity']['value'],
            'astronomy': {
                'sunrise': sunrise.strftime('%I:%M %p'),
                'sunset': sunset.strftime('%I:%M %p'),
                'moon_phase': moon_phase_name
            }
        }
    except Exception as e:
        print(f"Error in get_weather_data: {str(e)}")
        raise

@app.route('/')
def index():
    try:
        # Add no-cache headers to prevent browser caching
        response = None
        
        weather_data = get_weather_data()
        forecast_periods = weather_data['forecast']
        hourly_data = weather_data['hourly']
        
        # Use the first hourly period for current conditions (more accurate)
        current = {
            'temperature': hourly_data[0]['temperature'],
            'temperatureUnit': hourly_data[0]['temperatureUnit'],
            'shortForecast': hourly_data[0]['shortForecast'],
            'windSpeed': hourly_data[0]['windSpeed'],
            'windDirection': hourly_data[0]['windDirection'],
            'humidity': weather_data['humidity']
        }
        
        # Calculate a time exactly 6 hours in the future
        now = datetime.now(pytz.timezone('America/New_York'))
        target_time = now + timedelta(hours=6)
        
        # Find the forecast period closest to 6 hours from now
        closest_index = 0
        smallest_diff = float('inf')
        
        for i, period in enumerate(hourly_data):
            period_time = datetime.strptime(period['startTime'], '%Y-%m-%dT%H:%M:%S%z')
            time_diff = abs((period_time - target_time).total_seconds())
            
            if time_diff < smallest_diff:
                smallest_diff = time_diff
                closest_index = i
        
        # Use the forecast period closest to 6 hours from now
        if closest_index < len(hourly_data):
            future = {
                'temperature': hourly_data[closest_index]['temperature'],
                'temperatureUnit': hourly_data[closest_index]['temperatureUnit'],
                'shortForecast': hourly_data[closest_index]['shortForecast'],
                'windSpeed': hourly_data[closest_index]['windSpeed'],
                'windDirection': hourly_data[closest_index]['windDirection'],
                'time': datetime.strptime(hourly_data[closest_index]['startTime'], '%Y-%m-%dT%H:%M:%S%z').strftime('%I:%M %p')
            }
        else:
            # Fallback if no hourly data available
            future = current.copy()
            
        # Skip today and get the next 4 days
        forecast = []
        start_idx = 2  # Start from tomorrow (index 2) since index 0 is today and index 1 is tonight
        for i in range(start_idx, len(forecast_periods)-1, 2):  # Step by 2 to get day/night pairs
            if len(forecast) >= 4:  # Stop once we have 4 days
                break
            day_data = forecast_periods[i]
            night_data = forecast_periods[i + 1]
            # Make sure day temperature is higher than night temperature
            high_temp = max(day_data['temperature'], night_data['temperature'])
            low_temp = min(day_data['temperature'], night_data['temperature'])
            forecast_day = {
                'name': day_data['name'],
                'shortForecast': day_data['shortForecast'],
                'high_temp': high_temp,
                'low_temp': low_temp,
                'temperatureUnit': day_data['temperatureUnit']
            }
            forecast.append(forecast_day)
        
        response = make_response(render_template('index.html', 
                             current=current,
                             future=future,  # Add the future (6-hour) forecast data
                             forecast=forecast,
                             astronomy=weather_data['astronomy']))
        
        # Add no-cache headers
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        print(f"Error: {str(e)}")  # Print the error to console
        response = make_response(render_template('index.html', error=str(e)))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

if __name__ == '__main__':
    app.run(debug=True)
