# Discord Bot for SMM Panel

A Discord bot that interfaces with an SMM panel API to manage orders and services.

## Features

- Admin authentication system
- Service listing and management
- Order placement and tracking
- Balance checking
- Order refill and cancellation
- Real-time status updates

## Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/discord-smm-bot.git
cd discord-smm-bot
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your credentials:

```env
DISCORD_TOKEN=your_discord_token
API_KEY=your_smm_panel_api_key
MONGODB_URI=your_mongodb_connection_string
```

## Deployment on Railway

1. Install Railway CLI:

```bash
npm i -g @railway/cli
```

2. Login to Railway:

```bash
railway login
```

3. Initialize project:

```bash
railway init
```

4. Set environment variables:

```bash
railway variables set DISCORD_TOKEN=your_discord_token
railway variables set API_KEY=your_smm_panel_api_key
railway variables set MONGODB_URI=your_mongodb_connection_string
```

5. Deploy:

```bash
railway up
```

## Commands

- `/login` - Login as admin
- `/services` - List available services
- `/order` - Place a new order
- `/status` - Check order status
- `/balance` - Check account balance
- `/refill` - Request order refill
- `/cancel` - Cancel an order

## Requirements

- Python 3.8+
- discord.py
- pymongo
- requests
- python-dotenv

## License

MIT
