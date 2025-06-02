# Zoom Meeting Creator

A Flask web application that allows users to create instant meetings and schedule future meetings using Zoom's OAuth 2.0 API. Now with **secure credential management**, improved session handling, Bangladesh timezone (GMT+6) support, and role-based access!

## Features

- **🔐 Secure Credential Management**: No hardcoded API keys - instructors input their own Zoom credentials securely
- **👥 Role-based Access**: Separate interfaces for Admin and Student users
- **⚡ Instant Meeting Creation**: Create meetings that start immediately with one click
- **📅 Meeting Scheduling**: Schedule meetings for future dates and times with validation
- **🌏 Bangladesh Timezone Support**: All times displayed in Asia/Dhaka timezone (GMT+6)
- **🔑 Meeting Details**: Meeting ID and Password displayed for easy access
- **🔄 OAuth 2.0 Authentication**: Secure authentication with Zoom using OAuth 2.0
- **💾 Session Management**: Reliable session handling across authentication flow
- **🔄 Automatic Token Refresh**: Seamless token renewal for uninterrupted access
- **📱 Responsive UI**: Modern interface with loading indicators and copy functionality
- **📋 Meeting Management**: View, manage, and download attendance reports
- **🛡️ Security Features**: Session-based credential storage with easy clearing
- **📊 Error Handling**: Comprehensive error handling and logging
- **🏥 Health Monitoring**: Health check endpoint for monitoring

## Prerequisites

- Python 3.7+
- A Zoom Developer Account
- Registered Zoom OAuth App with proper credentials

## Dependencies

```
Flask==2.0.1
Flask-Session==0.4.0
requests==2.26.0
python-dotenv==0.19.1
```

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/smrafy20/Integrate-zoom-with-website.git
   
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install flask flask-session requests python-dotenv
   ```

4. Start the application:
   ```bash
   python main.py
   ```

5. Open your browser and navigate to `http://localhost:5000`

6. **First-time Setup**: When you first access the admin panel, you'll be prompted to enter your Zoom API credentials securely

## How to Use

### For Instructors (Admin Users)

1. **Navigate to Admin Panel**: Go to `http://localhost:5000/admin`
2. **Setup Credentials**: On first visit, click "Setup Credentials" to enter your Zoom API details
3. **Create Meetings**:
   - **Instant Meeting**: Click "Create Instant Meeting" for immediate meetings
   - **Scheduled Meeting**: Click "Schedule a Meeting" to plan future meetings
4. **Manage Meetings**: View all created meetings in the management table
5. **Download Reports**: Click the download button to get attendance reports (requires paid Zoom account)

### For Students

1. **Navigate to Student Panel**: Go to `http://localhost:5000/student`
2. **View Available Meetings**: See all meetings created by instructors
3. **Join Meetings**: Click "Join" to participate in meetings
4. **Copy Details**: Use copy buttons to get meeting IDs and passwords

### Credential Management

- **Update Credentials**: Click "Update Credentials" in the admin panel to change your API details
- **Clear Credentials**: Click "Clear" to remove credentials from your session (for security)
- **Session Expiry**: Credentials are automatically cleared when your session expires

## Setting Up Your Zoom App

1. Go to [Zoom App Marketplace](https://marketplace.zoom.us/) and sign in
2. Click "Develop" in the top-right and select "Build App"
3. Choose "OAuth" as the app type
4. Fill in the required App information:
   - App Name: "Zoom Meeting Creator" (or your choice)
   - App Type: "General App" 
   - Redirect URL: "http://localhost:5000/callback"
5. Add the following scopes:
   - `meeting:write:admin`
   - `meeting:write` 
6. Save your Client ID and Client Secret
7. **Important**: Keep your credentials secure - the application will prompt you to enter them when needed

## Project Structure

```
zoom-meeting-creator/
├── main.py                 # Main application file
├── README.md               # This file
├── requirements.txt        # Python dependencies (create this)
├── .env                    # Environment variables (create this)
├── flask_session/          # Session storage directory
├── templates/
│   ├── index.html          # Homepage template
│   ├── meeting.html        # Meeting created success page
│   └── schedule_form.html  # Meeting scheduling form
```

## Recent Updates

### Scheduling Feature
- Added ability to schedule meetings for future dates
- Implemented a user-friendly scheduling form
- Support for custom meeting topics and durations

### Bangladesh Timezone Support
- All scheduled meetings now use Asia/Dhaka timezone (GMT+6)
- Clear labeling of time inputs as Bangladesh time
- Proper time formatting for the Zoom API

### Session Handling Improvements
- Fixed issues with session data persistence during OAuth flow
- Added redundancy in meeting type storage
- Implemented state parameter verification for more reliable redirects

## Configuration Options

You can modify these parameters in `main.py`:

- `SESSION_TYPE`: Session storage type (default: filesystem)
- `SESSION_PERMANENT`: Whether sessions are persistent (default: True)
- `PERMANENT_SESSION_LIFETIME`: Session timeout in seconds (default: 3600)
- `debug`: Whether to run Flask in debug mode (default: True)

## API Endpoints

- `GET /`: Homepage with meeting creation options
- `GET /login`: Redirects to Zoom OAuth authorization
- `GET /callback`: OAuth callback handler
- `GET /create-meeting`: Creates and displays an instant meeting
- `GET /schedule-form`: Displays the meeting scheduling form
- `POST /schedule-meeting`: Creates a scheduled meeting
- `POST /api/create-meeting`: JSON API endpoint for meeting creation
- `GET /health`: Health check endpoint

## Troubleshooting

- **Authentication Failed**: Verify your Client ID and Secret
- **Meeting Creation Failed**: Check your Zoom account permissions
- **Session Issues**: Make sure the flask_session directory is writable
- **Connection Issues**: The application implements retry logic for failed requests
- **Check Logs**: Enable logging to troubleshoot connection problems

## Security Features

### 🔐 Secure Credential Management
- **No Hardcoded Credentials**: API keys are never stored in source code
- **Session-Based Storage**: Credentials are stored securely in user sessions only
- **Automatic Cleanup**: Credentials are cleared when sessions expire or manually cleared
- **Input Validation**: Credentials are validated before use
- **Easy Management**: Simple interface to update or clear credentials

### 🛡️ Additional Security Considerations
- **HTTPS Required**: Deploy with HTTPS in production environments
- **Session Security**: Session data is stored on the filesystem by default
- **Rate Limiting**: Consider implementing rate limiting to avoid hitting Zoom API limits
- **Access Control**: Role-based access separates admin and student functionality
- **Error Handling**: Comprehensive error handling prevents credential leakage

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
