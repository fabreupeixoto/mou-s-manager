"""
Test SMTP email configuration and send a test email.

Usage: python test_smtp.py
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


def test_smtp():
    """Test SMTP connection and send a test email."""
    
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT', '587')
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    smtp_from = os.getenv('SMTP_FROM')
    smtp_to = os.getenv('SMTP_TO')
    
    print("📧 SMTP Configuration Test")
    print("=" * 50)
    print(f"Server: {smtp_server}")
    print(f"Port: {smtp_port}")
    print(f"From: {smtp_from}")
    print(f"To: {smtp_to}")
    print("=" * 50)
    
    if not all([smtp_server, smtp_username, smtp_password, smtp_from, smtp_to]):
        print("❌ Error: Missing SMTP configuration in .env file")
        print("\nPlease edit .env and fill in:")
        print("  - SMTP_USERNAME")
        print("  - SMTP_PASSWORD (use App Password for Gmail)")
        print("  - SMTP_FROM")
        print("  - SMTP_TO")
        return False
    
    # Test email content
    subject = "✅ USJ MOU Dashboard - Test Email"
    
    body = """
    <html>
    <body>
    <h2>✅ SMTP Test Successful!</h2>
    <p>This is a test email from the <strong>USJ MOU Dashboard</strong>.</p>
    
    <h3>Configuration Details:</h3>
    <ul>
        <li><strong>SMTP Server:</strong> {smtp_server}</li>
        <li><strong>SMTP Port:</strong> {smtp_port}</li>
        <li><strong>From:</strong> {smtp_from}</li>
        <li><strong>To:</strong> {smtp_to}</li>
    </ul>
    
    <h3>Next Steps:</h3>
    <p>The email notification system is working correctly. The dashboard will now:</p>
    <ol>
        <li>Check daily at 9:00 AM for MOUs expiring within 3 months</li>
        <li>Send an email digest with expiring MOUs</li>
    </ol>
    
    <p><small>This is an automated message from the USJ MOU Dashboard.</small></p>
    </body>
    </html>
    """.format(smtp_server=smtp_server, smtp_port=smtp_port, smtp_from=smtp_from, smtp_to=smtp_to)
    
    try:
        print("\n📤 Sending test email...")
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = smtp_to
        
        msg.attach(MIMEText(body, 'html'))
        
        # Connect and send
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        print("✅ Test email sent successfully!")
        print(f"   Check inbox at: {smtp_to}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("❌ SMTP Authentication Error")
        print("\nPossible causes:")
        print("  1. Wrong password (for Gmail, use App Password, not regular password)")
        print("  2. 2FA not enabled (required for Gmail App Passwords)")
        print("  3. Less secure apps not allowed")
        print("\nFor Gmail:")
        print("  1. Go to https://myaccount.google.com/apppasswords")
        print("  2. Create an App Password for 'Mail'")
        print("  3. Use that 16-character password in .env")
        return False
        
    except smtplib.SMTPConnectError as e:
        print(f"❌ SMTP Connection Error: {e}")
        print("\nPossible causes:")
        print("  1. Wrong SMTP server address")
        print("  2. Wrong port (try 587 for TLS or 465 for SSL)")
        print("  3. Firewall blocking connection")
        return False
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False


if __name__ == '__main__':
    test_smtp()
