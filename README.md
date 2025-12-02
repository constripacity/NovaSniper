# 🎯 NovaSniper v2.0

Multi-platform price tracking service with real-time alerts.

## Features
- Multi-platform: Amazon, eBay, Walmart, Best Buy, Target
- Multi-channel notifications: Email, Discord, Telegram, SMS, Slack, Webhooks
- User authentication (JWT + API keys)
- Price history tracking
- Watchlists
- Admin dashboard
- Docker support

## Quick Start
```bash
git clone https://github.com/constripacity/NovaSniper.git
cd NovaSniper
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Visit http://localhost:8000/dashboard

## API Docs
http://localhost:8000/docs
