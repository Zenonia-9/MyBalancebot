# My Balance - Personal Finance Tracker

A lightweight Telegram bot and web interface for tracking personal finances with multi-currency support and timezone awareness.

## Features

### 🤖 Telegram Bot Commands
- `/in <amount> [note]` - Add income (supports shorthand like 10k, 1m)
- `/out <amount> [note]` - Add expense
- `/balance` - Check current balance
- `/history` - View transaction history with pagination
- `/delete [id]` - Delete transactions (interactive UI)
- `/summary [period]` - Get financial summaries (day/week/month/year/all)
- `/export` - Export your data as CSV
- `/import` - Import data from CSV
- `/start` - Welcome message with web app link

### 🌐 Web Interface
- **Responsive design** with dark/light theme support
- **Real-time balance** tracking with income/expense breakdown
- **Transaction management** - add, view, delete with confirmation
- **Financial summaries** with monthly/yearly breakdown charts
- **User settings** - customize currency and timezone
- **Mobile-optimized** interface perfect for Telegram WebApp

### 💡 Key Features
- **Multi-currency support** - MMK, USD, THB, etc.
- **Timezone awareness** - Automatic detection and IANA timezone support
- **Shorthand amounts** - Supports 10k, 1m notation
- **Pagination** - Navigate through large transaction histories
- **Interactive UI** - Delete with confirmation modals
- **Data export/import** - Backup and restore your financial data

## Quick Start

### Prerequisites
- Python 3.8+
- Telegram Bot Token
- Allowed user IDs (for security)

### Setup
1. **Clone the repository**
   ```bash
   git clone https://github.com/Zenonia-9/MyBalancebot/new/v2.0
   cd my-balance
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   Create `.env` file:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   ALLOWED_USERS=123456789,987654321
   DATABASE_URL=data/finance.db
   WEBHOOK_URL=https://your-domain.com
   PORT=8443
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

## Configuration

### Environment Variables
- `BOT_TOKEN` - Your Telegram bot token
- `ALLOWED_USERS` - Comma-separated list of allowed Telegram user IDs
- `DATABASE_URL` - SQLite database path (default: `data/finance.db`)
- `WEBHOOK_URL` - Your Railway/production URL for webhooks
- `PORT` - Port number (default: 8443)

### Database
Uses **SQLite** by default (perfect for small-scale usage). The database is automatically created with:
- `transactions` table for storing income/expense records
- `user_settings` table for currency and timezone preferences

## Deployment

### Railway Deployment (Recommended)
1. **Connect your Railway account**
   ```bash
   railway login
   railway init
   ```

2. **Deploy**
   ```bash
   railway up
   ```

### Manual Deployment
- Set up environment variables
- Use `gunicorn` for production deployment:
  ```bash
  gunicorn -w 4 -b 0.0.0.0:8443 main:flask_app
  ```

## Usage Examples

### Telegram Commands
```bash
/in 50k Salary
/in 100000 Annual bonus
/out 2k Coffee
/out 50000 Rent
/balance
/history
/summary month
/delete 123
```

### Web Interface
- Click "📱 Open App" in Telegram for mobile-friendly access
- Use settings button (⚙️) to customize currency and timezone
- Navigate between Add, History, and Summary tabs

## File Structure
```
├── main.py              # Main Flask application
├── config.py            # Configuration and environment variables
├── db.py               # Database operations
├── handlers.py         # Telegram bot handlers
├── demo.py             # Demo data generator
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
├── static/             # CSS/JS files
└── data/              # Database storage
```

## Resource Requirements

### For 2-3 Users (Perfect for Railway Free Tier)
- **RAM**: ~50-100MB
- **Storage**: < 10MB
- **CPU**: Minimal usage
- **Bandwidth**: < 1GB/month

### Dependencies
- `python-telegram-bot[webhooks]` - Telegram bot framework
- `flask[async]` - Web framework
- `gunicorn` - Production WSGI server
- `nest_asyncio` - Async loop handling
- `python-dotenv` - Environment variable management

## Security Features
- **User whitelisting** - Only allowed users can access the bot
- **Input validation** - Secure amount parsing and validation
- **Transaction ownership** - Users can only delete their own transactions
- **Environment variables** - Sensitive data stored securely

## Troubleshooting

### Common Issues
1. **Bot not responding**: Check BOT_TOKEN and ALLOWED_USERS
2. **Database errors**: Ensure data/ directory exists and is writable
3. **Webhook issues**: Verify WEBHOOK_URL is accessible and correct
4. **Permission denied**: Check file permissions for database

## Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License
This project is open source and available under the MIT License.

Built with ❤️ for personal finance tracking
