import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_smtp():
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')

    print(f"--- SMTP Diagnostic ---")
    print(f"Server: {smtp_server}")
    print(f"Port: {smtp_port}")
    print(f"User: {smtp_user}")
    print(f"Password length: {len(smtp_password) if smtp_password else 0}")
    print(f"-----------------------\n")

    if not smtp_user or not smtp_password:
        print("[❌ ERROR] Missing credentials in .env file.")
        return

    try:
        print("Connecting to server...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(1)  # Show full SMTP logs
        
        print("Sending STARTTLS...")
        server.starttls()
        
        print("Logging in...")
        server.login(smtp_user, smtp_password)
        
        print("Login SUCCESS! Creating test message...")
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = smtp_user  # Send to self for test
        msg['Subject'] = "JoyHotels SMTP Test"
        msg.attach(MIMEText("If you see this, your SMTP configuration is working!", 'plain'))
        
        print("Sending message...")
        server.send_message(msg)
        server.quit()
        print("\n[✅ SUCCESS] Test email sent successfully!")
        
    except smtplib.SMTPAuthenticationError:
        print("\n[❌ AUTH ERROR] Gmail rejected the login.")
        print("REASON: This usually happens because:")
        print("1. You are using your real password instead of an 'App Password'.")
        print("2. 'Less secure app access' is disabled (Gmail requirement).")
        print("\nSOLUTION: Please generate a 'Google App Password' and use it instead.")
    except Exception as e:
        print(f"\n[❌ ERROR] Something went wrong: {e}")

if __name__ == "__main__":
    test_smtp()
