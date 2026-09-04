#!/bin/bash

# USJ MOU Dashboard - Quick Deploy Script
# Run this on your Ubuntu/Debian server

set -e

echo "🚀 USJ MOU Dashboard - Quick Deployment"
echo "========================================"

# Configuration
APP_DIR="/var/www/mou-dashboard"
APP_NAME="mou-dashboard"
USER="www-data"

echo ""
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx git wkhtmltopdf postgresql postgresql-contrib libpq-dev

echo ""
echo "📁 Creating application directory..."
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

echo ""
echo "⚙️  Setting up Python virtual environment..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

echo ""
echo "📥 Installing Python dependencies..."
if [ -f requirements-prod.txt ]; then
    pip install -r requirements-prod.txt
elif [ -f requirements.txt ]; then
    pip install -r requirements.txt
    pip install gunicorn
fi

echo ""
echo "🔧 Configuring environment..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "⚠️  Please edit .env with your production settings!"
        echo "   nano .env"
    fi
fi

echo ""
echo "🗄️  Setting up PostgreSQL database..."
DB_NAME="mou_dashboard"
DB_USER="mou_user"
DB_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 16)

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

echo "Database credentials:"
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo "  Password: $DB_PASS"
echo "  URL:      postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME"

# Update .env with DATABASE_URL
if [ -f .env ]; then
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME|" .env
else
    if [ -f .env.example ]; then
        cp .env.example .env
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME|" .env
    fi
fi

echo ""
echo "🗄️  Initializing application database..."
python3 -c "from app import db, app; app.app_context().push(); db.create_all()"

echo ""
echo "🔌 Configuring systemd service..."
sudo bash -c "cat > /etc/systemd/system/$APP_NAME.service << 'EOF'
[Unit]
Description=USJ MOU Dashboard
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment=\"PATH=$APP_DIR/venv/bin\"
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 3 --bind unix:$APP_DIR/$APP_NAME.sock app:app
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable $APP_NAME

echo ""
echo "🌐 Configuring nginx..."
DOMAIN=$(whiptail --inputbox "Enter your domain name (or press Enter for IP):" 8 78 --title "Domain Configuration" 3>&1 1>&2 2>&3)

if [ -z "$DOMAIN" ]; then
    DOMAIN=$(hostname -I | awk '{print $1}')
fi

sudo bash -c "cat > /etc/nginx/sites-available/$APP_NAME << EOF
server {
    listen 80;
    server_name $DOMAIN;

    access_log /var/log/nginx/$APP_NAME.access.log;
    error_log /var/log/nginx/$APP_NAME.error.log;

    client_max_body_size 10M;

    location / {
        proxy_pass http://unix:$APP_DIR/$APP_NAME.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }

    location /static {
        alias $APP_DIR/static;
        expires 30d;
        add_header Cache-Control \"public, immutable\";
    }
}
EOF"

sudo ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo ""
echo "🔥 Starting services..."
sudo systemctl start $APP_NAME
sudo systemctl restart nginx

echo ""
echo "📅 Setting up email notifications..."
read -p "Set up daily email notifications via cron? (y/n): " setup_cron
if [ "$setup_cron" = "y" ] || [ "$setup_cron" = "Y" ]; then
    # Install cron job
    crontab mou-dashboard.cron
    echo "✅ Cron job installed (daily at 9:00 AM)"
    echo "   View with: crontab -l"
    echo "   Logs: /var/log/mou-dashboard-notifications.log"
else
    echo "⚠️  Skipping cron setup"
    echo "   Email notifications will still work via APScheduler (built into Flask)"
fi

echo ""
echo "📊 Checking status..."
sudo systemctl status $APP_NAME --no-pager -l

echo ""
echo "========================================"
echo "✅ Deployment Complete!"
echo ""
echo "📍 Your dashboard should be available at:"
echo "   http://$DOMAIN"
echo ""
echo "📝 Next steps:"
echo "   1. Edit .env with your production settings"
echo "   2. Upload your CSV data or import from Google Sheets"
echo "   3. Set up SSL: sudo certbot --nginx -d $DOMAIN"
echo "   4. Configure firewall: sudo ufw allow 'Nginx Full'"
echo ""
echo "🔍 Useful commands:"
echo "   View logs: sudo journalctl -u $APP_NAME -f"
echo "   Restart:   sudo systemctl restart $APP_NAME"
echo "   Status:    sudo systemctl status $APP_NAME"
echo "========================================"
