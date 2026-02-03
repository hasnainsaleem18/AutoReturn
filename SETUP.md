# AutoReturn - Quick Setup Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Installation Steps

### 1. Clone or Navigate to the Project
```bash
cd /path/to/AutoReturn
```

### 2. (Optional) Create a Virtual Environment
It's recommended to use a virtual environment to isolate dependencies:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirement.txt
```

### 4. Set Up Gmail OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials (Desktop App)
5. Download the credentials file as `client_secret.json`
6. Place it in the `data/gmail_data/` directory:
   ```bash
   cp /path/to/downloaded/client_secret.json data/gmail_data/
   ```

### 5. Configure Slack (Optional)

If you want to use Slack integration:

1. Create a Slack App at [api.slack.com](https://api.slack.com/)
2. Get your Bot Token and User Token
3. Edit `config/settings.conf` and add your tokens:
   ```ini
   [slack]
   bot_token = xoxb-your-bot-token
   user_token = xoxp-your-user-token
   ```

### 6. Configure Ollama for AI Features (Optional)

If you want to use local AI analysis:

1. Install Ollama from [ollama.ai](https://ollama.ai/)
2. Pull a model:
   ```bash
   ollama pull llama2
   ```
3. The app will automatically use Ollama if it's running

### 7. Run the Application
```bash
python main.py
```

## First Run

On the first run:
1. The app will open the Gmail authentication dialog in your browser
2. Log in with your Google account
3. Grant the necessary permissions
4. A `token.json` file will be created in `data/gmail_data/`

## Project Structure

```
AutoReturn/
├── main.py                    # Run this to start the application
├── config/
│   └── settings.conf         # Edit this for configuration
├── data/
│   └── gmail_data/           # Place client_secret.json here
├── src/                      # Source code (don't modify unless you know what you're doing)
└── logs/                     # Application logs will appear here
```

## Troubleshooting

### Import Errors
If you see import errors, make sure you're running the app from the project root:
```bash
cd /path/to/AutoReturn
python main.py
```

### Gmail Authentication Issues
1. Delete `data/gmail_data/token.json`
2. Restart the app
3. Re-authenticate

### Slack Issues
1. Verify your tokens in `config/settings.conf`
2. Make sure your Slack app has the necessary permissions
3. Check the logs in `logs/` directory

### AI/Ollama Issues
1. Make sure Ollama is installed and running
2. Check that you've pulled a model: `ollama list`
3. The app will work without Ollama, but AI features will be disabled

## Running Tests

To run the test suite:
```bash
python tests/test_ollama.py
```

To run utility scripts:
```bash
python scripts/quick_test.py
python scripts/debug_slack_ai.py
```

## Updating

To update dependencies:
```bash
pip install -r requirement.txt --upgrade
```

## Support

For issues and questions:
1. Check the logs in `logs/` directory
2. Review the `README.md` for detailed documentation
3. Check the `MIGRATION_CHECKLIST.md` for structure information

---

**Happy Automating!** 🚀
