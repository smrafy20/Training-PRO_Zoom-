from flask import Flask, redirect, url_for, request, session, render_template, jsonify
import requests
import base64
import time
import logging
import io
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask_session import Session
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] ='S1J8Qov9f3F0HnajIaGhnOIowzVSs27n' # Set a secret key for session management
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True  # Make sessions persistent
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session timeout
Session(app)

# Default redirect URI - instructors can modify this if needed
DEFAULT_REDIRECT_URI = 'http://localhost:5000/callback'

# Zoom OAuth URLs
AUTH_URL = 'https://zoom.us/oauth/authorize'
TOKEN_URL = 'https://zoom.us/oauth/token'
MEETING_URL = 'https://api.zoom.us/v2/users/me/meetings'
REPORT_URL = 'https://api.zoom.us/v2/report/meetings/{meetingId}/participants'

# Store meetings in memory (in a real app, you'd use a database)
meetings = []

# Constants for validation
MIN_MEETING_DURATION = 15  # minutes
MAX_MEETING_DURATION = 480  # minutes (8 hours)
MAX_STORED_MEETINGS = 10

# Configure requests session with retry logic
def get_requests_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        backoff_factor=0.5
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# Helper functions for credentials management
def get_zoom_credentials():
    """Get Zoom credentials from session"""
    client_id = session.get('zoom_client_id')
    client_secret = session.get('zoom_client_secret')
    redirect_uri = session.get('zoom_redirect_uri', DEFAULT_REDIRECT_URI)
    return client_id, client_secret, redirect_uri

def require_zoom_credentials(f):
    """Decorator to ensure Zoom credentials are available in session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_id, client_secret, redirect_uri = get_zoom_credentials()
        if not client_id or not client_secret:
            return redirect(url_for('credentials_form'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator to require auth
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# New home route for role selection
@app.route('/')
def home():
    return render_template('home.html')

# Admin route (existing index page)
@app.route('/admin')
def admin():
    return render_template('index.html', meetings=meetings)

# Student route
@app.route('/student')
def student():
    return render_template('student.html', meetings=meetings)

# Credentials form route
@app.route('/credentials-form')
def credentials_form():
    return render_template('credentials_form.html')

# Handle credentials submission
@app.route('/save-credentials', methods=['POST'])
def save_credentials():
    client_id = request.form.get('client_id', '').strip()
    client_secret = request.form.get('client_secret', '').strip()
    redirect_uri = request.form.get('redirect_uri', DEFAULT_REDIRECT_URI).strip()

    # Validate required fields
    if not client_id or not client_secret:
        return render_template('error.html',
                             error_title="Missing Credentials",
                             error_message="Both Client ID and Client Secret are required."), 400

    # Basic validation for Client ID format (should be alphanumeric)
    if not client_id.replace('_', '').replace('-', '').isalnum():
        return render_template('error.html',
                             error_title="Invalid Client ID",
                             error_message="Client ID format appears to be invalid."), 400

    # Store credentials in session
    session['zoom_client_id'] = client_id
    session['zoom_client_secret'] = client_secret
    session['zoom_redirect_uri'] = redirect_uri
    session['credentials_set'] = True

    logger.info("Zoom credentials saved to session successfully")

    # Redirect back to admin page
    return redirect(url_for('admin'))

@app.route('/login')
@require_zoom_credentials
def login():
    # Get meeting type from query parameters (instant or scheduled)
    meeting_type = request.args.get('type', 'instant')

    # Store meeting type in session for later use
    session['meeting_type'] = meeting_type
    # Extra safeguard: store in a separate key to double-check later
    session['requested_meeting_type'] = meeting_type

    # Get credentials from session
    client_id, client_secret, redirect_uri = get_zoom_credentials()

    # Redirect user to Zoom's authorization page
    auth_url = f"{AUTH_URL}?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={meeting_type}"
    logger.info(f"Redirecting to Zoom authentication for {meeting_type} meeting")
    return redirect(auth_url)

@app.route('/callback')
def callback():
    start_time = time.time()
    code = request.args.get('code')
    state = request.args.get('state')  # Get the state parameter that includes meeting type

    if not code:
        logger.error("No authorization code received")
        return "Authorization failed", 400

    # Get credentials from session
    client_id, client_secret, redirect_uri = get_zoom_credentials()
    if not client_id or not client_secret:
        return redirect(url_for('credentials_form'))

    try:
        # Get access token using the code
        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri
        }
        headers = {
            'Authorization': f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        logger.info("Requesting access token")
        http_session = get_requests_session()
        response = http_session.post(TOKEN_URL, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        session['access_token'] = token_data.get('access_token')
        session['refresh_token'] = token_data.get('refresh_token', '')
        session['token_expiry'] = time.time() + token_data.get('expires_in', 3600)
        
        logger.info(f"Token obtained successfully in {time.time() - start_time:.2f} seconds")
        
        # Check for meeting type in multiple places to ensure consistency
        # 1. Check state parameter from URL (most reliable)
        # 2. Check requested_meeting_type from session (backup)
        # 3. Fall back to meeting_type from session
        meeting_type = None
        
        if state and state in ['instant', 'scheduled']:
            meeting_type = state
            logger.info(f"Using meeting type '{meeting_type}' from state parameter")
        elif 'requested_meeting_type' in session:
            meeting_type = session.get('requested_meeting_type')
            logger.info(f"Using meeting type '{meeting_type}' from requested_meeting_type in session")
        else:
            meeting_type = session.get('meeting_type', 'instant')
            logger.info(f"Using meeting type '{meeting_type}' from meeting_type in session")
        
        # Re-save the confirmed meeting type to both session variables
        session['meeting_type'] = meeting_type
        session['requested_meeting_type'] = meeting_type
        
        # Redirect based on the meeting type
        if meeting_type == 'scheduled':
            logger.info("Redirecting to schedule form")
            return redirect(url_for('schedule_form'))
        else: # Default to instant meeting
            logger.info("Redirecting to create instant meeting")
            return redirect(url_for('create_meeting'))
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Token request failed: {str(e)}")
        error_message = str(e)
        # Try to get more specific error details from Zoom response
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                error_message = f"{error_details.get('reason', e.response.text)} (Status Code: {e.response.status_code})"
                logger.error(f"Zoom API Error Details: {error_details}")
            except ValueError:
                 error_message = f"{e.response.text} (Status Code: {e.response.status_code})"
        return f"Failed to get access token: {error_message}", 500

def add_meeting_to_storage(meeting_data, meeting_type, topic=None, start_time=None, duration=40, password=None):
    """Helper function to add a meeting to the storage list"""
    new_meeting = {
        'meeting_id': meeting_data.get('id'),
        'uuid': meeting_data.get('uuid'),
        'join_url': meeting_data.get('join_url'),
        'start_url': meeting_data.get('start_url'),
        'meeting_type': meeting_type,
        'topic': topic or meeting_data.get('topic', 'My Meeting'),
        'start_time': start_time or ('Now' if meeting_type == 'Instant' else meeting_data.get('start_time')),
        'duration': duration,
        'password': password or meeting_data.get('password', ''),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    meetings.insert(0, new_meeting)

    # Keep only last MAX_STORED_MEETINGS meetings
    if len(meetings) > MAX_STORED_MEETINGS:
        meetings.pop()

    return new_meeting

def refresh_token_if_needed():
    """Refresh the access token if it's expired or about to expire"""
    if 'token_expiry' in session and session['token_expiry'] - time.time() < 300:  # Less than 5 minutes left
        if 'refresh_token' in session:
            # Get credentials from session
            client_id, client_secret, redirect_uri = get_zoom_credentials()
            if not client_id or not client_secret:
                logger.error("Cannot refresh token: Zoom credentials not found in session")
                return False

            try:
                logger.info("Refreshing access token")
                payload = {
                    'grant_type': 'refresh_token',
                    'refresh_token': session['refresh_token']
                }
                headers = {
                    'Authorization': f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                http_session = get_requests_session()
                response = http_session.post(TOKEN_URL, data=payload, headers=headers, timeout=10)
                response.raise_for_status()
                
                token_data = response.json()
                session['access_token'] = token_data.get('access_token')
                session['refresh_token'] = token_data.get('refresh_token', session['refresh_token'])
                session['token_expiry'] = time.time() + token_data.get('expires_in', 3600)
                logger.info("Token refreshed successfully")
                return True
            except Exception as e:
                logger.error(f"Token refresh failed: {str(e)}")
                return False
    return True

@app.route('/create-meeting')
@require_auth
def create_meeting():
    """Creates an instant meeting using the Zoom API."""
    if not refresh_token_if_needed():
        return redirect(url_for('login'))

    access_token = session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    payload = {
        'topic': 'Instant Meeting',
        'type': 1,  # 1 for Instant Meeting
        'settings': {
            'join_before_host': True,
            'mute_upon_entry': True,
            'participant_video': True,
            'host_video': True,
            'auto_recording': 'none'
        }
    }

    try:
        logger.info("Attempting to create instant meeting")
        http_session = get_requests_session()
        response = http_session.post(MEETING_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        meeting_data = response.json()
        logger.info(f"Instant meeting created successfully: ID {meeting_data.get('id')}")

        # Store meeting details using helper function
        new_meeting = add_meeting_to_storage(
            meeting_data=meeting_data,
            meeting_type='Instant',
            topic=meeting_data.get('topic', 'Instant Meeting'),
            start_time='Now',
            duration=meeting_data.get('duration', 40)
        )

        return render_template('meeting.html',
                               meeting_type='Instant',
                               meeting_id=new_meeting['meeting_id'],
                               password=new_meeting['password'],
                               start_url=new_meeting['start_url'],
                               join_url=new_meeting['join_url'])

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create instant meeting: {str(e)}")
        error_message = f"Failed to create meeting: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
             try:
                 error_details = e.response.json()
                 error_message += f" - Details: {error_details.get('message', e.response.text)}"
             except ValueError:
                 error_message += f" - Details: {e.response.text}"
        return render_template('error.html', error_title="Meeting Creation Failed", error_message=error_message)
    except Exception as e:
        logger.error(f"An unexpected error occurred during meeting creation: {str(e)}", exc_info=True)
        return render_template('error.html', error_title="Unexpected Error", error_message=f"An unexpected error occurred: {str(e)}")

# Add route for scheduling form
@app.route('/schedule-form')
@require_auth
def schedule_form():
    # Simple route to render the scheduling form
    return render_template('schedule_form.html')

# Add route to handle scheduled meeting creation
@app.route('/schedule-meeting', methods=['POST'])
@require_auth
def schedule_meeting():
    start_time = time.time()
    
    if not refresh_token_if_needed():
        # If token refresh fails, redirect to login
        return redirect(url_for('login'))

    access_token = session.get('access_token')
    
    # Get data from form with validation
    topic = request.form.get('topic', 'My Scheduled Meeting').strip()
    start_time_str = request.form.get('start_time')

    # Validate required fields
    if not topic:
        return render_template('error.html',
                             error_title="Missing Information",
                             error_message="Meeting topic is required."), 400

    if not start_time_str:
        return render_template('error.html',
                             error_title="Missing Information",
                             error_message="Start time is required."), 400

    # Validate and parse duration
    try:
        duration = int(request.form.get('duration', 40))
        if duration < MIN_MEETING_DURATION or duration > MAX_MEETING_DURATION:
            raise ValueError(f"Duration must be between {MIN_MEETING_DURATION} and {MAX_MEETING_DURATION} minutes")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid duration received: {request.form.get('duration')}")
        return render_template('error.html',
                             error_title="Invalid Duration",
                             error_message=f"Duration must be a number between {MIN_MEETING_DURATION} and {MAX_MEETING_DURATION} minutes."), 400

    # Validate and format start time for the Bangladesh timezone (Asia/Dhaka)
    try:
        # Parse the datetime-local input string (which comes in local time)
        start_datetime = datetime.fromisoformat(start_time_str)

        # Validate that the meeting is scheduled for the future
        current_time = datetime.now()
        if start_datetime <= current_time:
            return render_template('error.html',
                                 error_title="Invalid Time",
                                 error_message="Meeting must be scheduled for a future date and time."), 400

        # Format for Zoom API - remove the Z suffix since we're specifying timezone separately
        formatted_start_time = start_datetime.strftime('%Y-%m-%dT%H:%M:%S')
        display_start_time = start_datetime.strftime('%Y-%m-%d %I:%M %p')
        logger.info(f"Scheduling meeting at {formatted_start_time} in Asia/Dhaka timezone")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid start time format received: {start_time_str}, Error: {str(e)}")
        return render_template('error.html',
                             error_title="Invalid Time Format",
                             error_message="Invalid start time format. Please use the date/time picker and try again."), 400

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "topic": topic,
        "type": 2,  # 2 = Scheduled Meeting
        "start_time": formatted_start_time,
        "duration": duration, # Duration in minutes
        "timezone": "Asia/Dhaka", # Specify timezone, adjust as needed
        "settings": {
            "join_before_host": False,
            "waiting_room": True,
            "mute_upon_entry": False,
            "auto_recording": "none" # Example setting
        }
    }

    try:
        logger.info(f"Creating Scheduled Zoom meeting: Topic='{topic}', Start='{formatted_start_time}', Duration={duration}")
        http_session = get_requests_session()
        response = http_session.post(MEETING_URL, json=data, headers=headers, timeout=15) # Increased timeout slightly
        response.raise_for_status()
        
        meeting_data = response.json()
        join_url = meeting_data.get('join_url')
        start_url = meeting_data.get('start_url') # Host start URL
        meeting_id = meeting_data.get('id')
        password = meeting_data.get('password', '')  # Get password from meeting data

        # Store meeting for student access using helper function
        new_meeting = add_meeting_to_storage(
            meeting_data=meeting_data,
            meeting_type='Scheduled',
            topic=topic,
            start_time=display_start_time,
            duration=duration,
            password=password
        )

        logger.info(f"Scheduled Meeting created successfully in {time.time() - start_time:.2f} seconds")
        
        # Render the same meeting template, but pass scheduled details
        return render_template('meeting.html', 
                             meeting_type='Scheduled',
                             topic=topic,
                             display_start_time=display_start_time,
                             duration=duration,
                             join_url=join_url, 
                             start_url=start_url,
                             meeting_id=meeting_id,
                             password=password)  # Pass password to template
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Scheduled Meeting creation failed: {str(e)}")
        error_message = "Failed to create scheduled meeting. Please try again."
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                error_message = f"{error_details.get('message', 'Unknown error occurred')} (Code: {error_details.get('code', 'N/A')})"
            except ValueError: # Handle cases where response is not JSON
                error_message = f"HTTP Error {e.response.status_code}: {e.response.text[:200]}"
        return render_template('error.html',
                             error_title="Meeting Creation Failed",
                             error_message=error_message), 500
    except Exception as e:
        logger.error(f"Unexpected error in schedule_meeting: {str(e)}", exc_info=True)
        return render_template('error.html',
                             error_title="Unexpected Error",
                             error_message="An unexpected error occurred while creating the meeting. Please try again."), 500

@app.route('/api/create-meeting', methods=['POST'])
@require_auth
def api_create_meeting():
    """API endpoint for creating meetings via AJAX"""
    if not refresh_token_if_needed():
        return jsonify({"error": "Authentication required"}), 401
    
    access_token = session.get('access_token')
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "topic": "My Instant Meeting",
        "type": 1,  # 1 = Instant Meeting
        "settings": {
            "join_before_host": True,
            "waiting_room": False,
            "mute_upon_entry": False
        }
    }

    try:
        http_session = get_requests_session()
        response = http_session.post(MEETING_URL, json=data, headers=headers, timeout=10)
        response.raise_for_status()
        
        meeting_data = response.json()
        
        # Store meeting for student access using helper function
        add_meeting_to_storage(
            meeting_data=meeting_data,
            meeting_type='Instant',
            topic=data['topic'],
            start_time='Now',
            duration=40
        )
            
        return jsonify({
            "success": True,
            "join_url": meeting_data.get('join_url'),
            "start_url": meeting_data.get('start_url'),
            "meeting_id": meeting_data.get('id')
        })
    
    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_message = e.response.text
        return jsonify({"error": error_message}), 500

def get_meeting_participants(meeting_id):
    """Fetches participant report for a given meeting ID."""
    if not refresh_token_if_needed():
        logger.error("Authentication required or token refresh failed.")
        return None, "Authentication required or token refresh failed."

    access_token = session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}
    url = REPORT_URL.format(meetingId=meeting_id)
    params = {'page_size': 300} # Get up to 300 participants per page

    participants = []
    try:
        logger.info(f"Fetching participant report for meeting ID: {meeting_id}")
        http_session = get_requests_session()

        while url:
            response = http_session.get(url, headers=headers, params=params, timeout=15)

            # Check for specific Zoom errors before raising for status
            if not response.ok: # Check if status code indicates an error (e.g., 4xx, 5xx)
                try:
                    error_data = response.json()
                    error_code = error_data.get('code')
                    error_message_detail = error_data.get('message', '')

                    # Specific check for Paid Account Required error
                    # Zoom might use code 200, 3000, or others, or rely on message text.
                    # Checking the message is often more reliable for this specific error.
                    if "Only available for Paid" in error_message_detail or "not support API call" in error_message_detail:
                         logger.warning(f"Report access denied for meeting {meeting_id}: Requires Paid/ZMP account.")
                         return None, "Accessing attendance reports via API requires a Paid Zoom account (Pro, Business, etc.). Please upgrade your Zoom plan or check attendance manually within the Zoom portal."
                    elif error_code == 3001: # Report not ready yet
                        logger.warning(f"Report for meeting {meeting_id} not available yet.")
                        return None, "Meeting report is not available yet. Please try again later."
                    else:
                        logger.error(f"Zoom API error fetching report: Code {error_code}, Message: {error_message_detail}")
                        # Return a generic but informative message
                        return None, f"Zoom API error occurred while fetching the report. (Code: {error_code})"

                except ValueError: # If response is not JSON
                    logger.error(f"Zoom API error fetching report: Status {response.status_code}, Response: {response.text}")
                    response.raise_for_status() # Raise the original HTTP error

            # If response was OK (2xx)
            data = response.json()
            participants.extend(data.get('participants', []))

            # Handle pagination
            next_page_token = data.get('next_page_token')
            if next_page_token:
                params['next_page_token'] = next_page_token
            else:
                url = None # No more pages

        logger.info(f"Successfully fetched {len(participants)} participant records.")
        return participants, None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch participant report: {str(e)}")
        error_message = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_message = e.response.text
        return None, f"Failed to fetch report: {error_message}"
    except Exception as e:
         logger.error(f"An unexpected error occurred fetching participants: {str(e)}")
         return None, f"An unexpected error occurred: {str(e)}"


def generate_attendance_pdf(participants_data, meeting_id, meeting_topic, meeting_start_time):
    """Generates a PDF attendance report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Zoom Meeting Attendance Report", styles['h1']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Meeting Topic:</b> {meeting_topic or 'N/A'}", styles['Normal']))
    story.append(Paragraph(f"<b>Meeting ID:</b> {meeting_id}", styles['Normal']))
    story.append(Paragraph(f"<b>Scheduled Start:</b> {meeting_start_time or 'N/A'}", styles['Normal']))
    story.append(Spacer(1, 24))

    if not participants_data:
        story.append(Paragraph("No participant data found for this meeting.", styles['Normal']))
        doc.build(story)
        buffer.seek(0)
        return buffer

    # Prepare data for the table
    data = [['Name', 'Join Time', 'Leave Time', 'Duration (Minutes)']]
    for p in participants_data:
        try:
            # Zoom API times are often in UTC (ISO 8601 format)
            join_time_dt = datetime.fromisoformat(p['join_time'].replace('Z', '+00:00'))
            leave_time_dt = datetime.fromisoformat(p['leave_time'].replace('Z', '+00:00'))
            # Convert to local time (e.g., GMT+6 for Bangladesh) - simplistic offset
            local_join_time = join_time_dt + timedelta(hours=6)
            local_leave_time = leave_time_dt + timedelta(hours=6)

            join_time_str = local_join_time.strftime('%Y-%m-%d %H:%M:%S')
            leave_time_str = local_leave_time.strftime('%Y-%m-%d %H:%M:%S')
            duration_minutes = p.get('duration', 0) // 60 # Duration is in seconds
        except (ValueError, KeyError) as e:
             logger.warning(f"Could not parse time/duration for participant {p.get('name', 'Unknown')}: {e}")
             join_time_str = "Invalid"
             leave_time_str = "Invalid"
             duration_minutes = "N/A"


        data.append([
            p.get('name', 'Unknown User'),
            join_time_str,
            leave_time_str,
            str(duration_minutes)
        ])

    # Create and style the table
    table = Table(data)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    table.setStyle(style)
    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/report/<meeting_id>')
@require_auth
def download_report(meeting_id):
    """Fetches participant data and returns a PDF report."""
    logger.info(f"Request received for report of meeting ID: {meeting_id}")

    # Find meeting details (topic, start time) from your stored list
    # NOTE: This relies on the 'meetings' list still having the data.
    # A database lookup would be more robust.
    meeting_info = next((m for m in meetings if str(m.get('meeting_id')) == str(meeting_id)), None)
    if not meeting_info:
         # Attempt to fetch details if not in memory? (More complex)
         logger.warning(f"Meeting info for ID {meeting_id} not found in memory.")
         # return f"Meeting details not found for ID {meeting_id}. Report cannot be generated.", 404
         # For now, proceed without topic/start time if not found
         meeting_topic = "Unknown"
         meeting_start_time = "Unknown"
    else:
        meeting_topic = meeting_info.get('topic')
        meeting_start_time = meeting_info.get('start_time') # Assumes 'start_time' is stored nicely

    participants, error = get_meeting_participants(meeting_id)

    if error:
        # Return an HTML error page instead of just text
        return render_template('error.html', error_title="Report Error", error_message=error), 500

    if participants is None: # Should be covered by error, but double-check
         return render_template('error.html', error_title="Report Error", error_message="Could not retrieve participant data."), 500


    pdf_buffer = generate_attendance_pdf(participants, meeting_id, meeting_topic, meeting_start_time)

    if not pdf_buffer:
         return render_template('error.html', error_title="PDF Error", error_message="Failed to generate PDF report."), 500


    return pdf_buffer.getvalue(), 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'attachment; filename="attendance_report_{meeting_id}.pdf"'
    }

# Clear credentials from session
@app.route('/clear-credentials')
def clear_credentials():
    session.pop('zoom_client_id', None)
    session.pop('zoom_client_secret', None)
    session.pop('zoom_redirect_uri', None)
    session.pop('credentials_set', None)
    session.pop('access_token', None)
    session.pop('refresh_token', None)
    session.pop('token_expiry', None)
    logger.info("Zoom credentials cleared from session")
    return redirect(url_for('admin'))

# Clear meetings (for testing/demo purposes)
@app.route('/clear-meetings')
def clear_meetings():
    global meetings
    meetings = []
    return redirect('/student')

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
