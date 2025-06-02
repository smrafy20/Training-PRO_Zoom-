# Zoom Meeting Intregation with Training PRO

A Flask web application for creating instant and scheduled Zoom meetings. Features secure credential management - no more hardcoded API keys!

## ✨ Recent Updates

- **🔐 Secure Credentials**: Enter your Zoom API credentials safely through the web interface
- **🐛 Bug Fixes**: Fixed scheduled meeting creation errors
- **�️ Enhanced Security**: Credentials stored in session only, never in code files

## Features

- Create instant meetings or schedule future meetings
- Secure credential input (no hardcoded API keys)
- Bangladesh timezone support (GMT+6)
- Meeting management with attendance reports
- Copy meeting IDs and passwords easily
- Role-based access for Admin and Students

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
   git clone https://github.com/smrafy20/Training-PRO_Zoom-.git
   
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

6. **First-time Setup**: Go to `/admin` and enter your Zoom API credentials when prompted

## Quick Start

1. **Admin Panel**: Go to `http://localhost:5000/admin`
2. **Enter Credentials**: Click "Setup Credentials" and enter your Zoom API details
3. **Create Meetings**: Choose instant or scheduled meetings
4. **Student Access**: Students can view and join meetings at `http://localhost:5000/student`

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
7. Enter these credentials in the web application when prompted

## Security

- **No Hardcoded Keys**: API credentials are entered through the web interface
- **Session Storage**: Credentials stored securely in your browser session only
- **Easy Management**: Update or clear credentials anytime from the admin panel
- **Safe for GitHub**: No sensitive data in source code

## Troubleshooting

- **Authentication Failed**: Check your Zoom Client ID and Secret
- **Meeting Creation Failed**: Verify your Zoom account has meeting creation permissions
- **Scheduled Meeting Errors**: Ensure the meeting time is in the future

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
