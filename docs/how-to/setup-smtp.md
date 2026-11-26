for email smtp to work what i need to add in .env file ?

Great question! Here's what you need to add to your `.env` file for email functionality:

## Required SMTP Configuration

Add these variables to your `backend/.env` file:

```env
# Email Configuration (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password-here
EMAIL_FROM=noreply@yourdomain.com
EMAIL_FROM_NAME=RAG Chatbot SaaS

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:3000

# Email Feature Flags (Optional)
ENABLE_EMAIL_VERIFICATION=True
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
PASSWORD_RESET_TOKEN_EXPIRE_HOURS=1
```

## Setup Instructions

### Option 1: Gmail (Recommended for Testing)

1. **Enable 2-Factor Authentication** on your Gmail account:
   - Go to: https://myaccount.google.com/security
   - Enable "2-Step Verification"

2. **Generate App Password**:
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and your device
   - Click "Generate"
   - Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

3. **Update .env**:
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=youremail@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop  # Remove spaces from app password
   EMAIL_FROM=youremail@gmail.com
   ```

### Option 2: Outlook/Hotmail

```env
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=youremail@outlook.com
SMTP_PASSWORD=your-password
EMAIL_FROM=youremail@outlook.com
```

### Option 3: SendGrid (Production)

1. Sign up at https://sendgrid.com
2. Create an API key
3. Configure:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
EMAIL_FROM=noreply@yourdomain.com
```

### Option 4: Mailtrap (Development/Testing)

1. Sign up at https://mailtrap.io
2. Get credentials from inbox settings
3. Configure:

```env
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=2525
SMTP_USER=your-mailtrap-username
SMTP_PASSWORD=your-mailtrap-password
EMAIL_FROM=test@example.com
```

**Mailtrap advantage**: Catches all emails in a test inbox (no real emails sent)

## Testing Email Configuration

### Method 1: Quick Test Script

Create `backend/test_email.py`:

```python
import asyncio
from app.services.email_service import send_email
from app.config import settings

async def test():
    print(f"Testing email with SMTP: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
    print(f"From: {settings.EMAIL_FROM}")
    print(f"User: {settings.SMTP_USER}")
    
    result = await send_email(
        to_email="your-test-email@gmail.com",  # Change this!
        subject="Test Email from RAG Chatbot",
        html_content="<h1>Hello!</h1><p>This is a test email.</p>",
        text_content="Hello! This is a test email."
    )
    
    if result:
        print("✅ Email sent successfully!")
    else:
        print("❌ Failed to send email. Check the logs above.")

if __name__ == "__main__":
    asyncio.run(test())
```

Run it:
```bash
cd backend
python test_email.py
```

### Method 2: Test Registration

1. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```

2. Register a new user (email will be sent):
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com",
       "password": "TestPass123",
       "full_name": "Test User"
     }'
   ```

3. Check your email inbox for verification email

## Troubleshooting

### Common Issues

**1. "SMTPAuthenticationError"**
   - **Gmail**: Make sure you're using an App Password, not your regular password
   - **Gmail**: Ensure 2FA is enabled
   - **Other**: Check username and password are correct

**2. "SMTPServerDisconnected"**
   - Check SMTP_HOST and SMTP_PORT are correct
   - Try port 465 with SSL instead of 587 with TLS

**3. "Connection refused"**
   - Check your firewall/antivirus isn't blocking SMTP ports
   - Try disabling VPN if you're using one

**4. "Email not received"**
   - Check spam/junk folder
   - Verify EMAIL_FROM is correct
   - For Gmail, check "Less secure app access" (if not using App Password)

**5. "SSL/TLS error"**
   - Try changing SMTP_PORT from 587 to 465
   - Or set `SMTP_TLS=False` in config if using port 465

## For Development: Disable Email Verification

If you don't want to set up SMTP during development, you can disable email verification:

```env
# Disable email verification for testing
ENABLE_EMAIL_VERIFICATION=False
```

Then users will be automatically verified upon registration.

Or manually verify in database:
```sql
UPDATE users SET is_verified = true WHERE email = 'test@example.com';
```

## Complete .env Example

Here's a complete example with all email-related settings:

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_db_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_chatbot

# Security
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this

# OpenAI
OPENAI_API_KEY=sk-your-openai-key

# Email (Gmail Example)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youremail@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_TLS=True
EMAIL_FROM=youremail@gmail.com
EMAIL_FROM_NAME=RAG Chatbot Platform

# Frontend
FRONTEND_URL=http://localhost:3000

# Optional: Email Settings
ENABLE_EMAIL_VERIFICATION=True
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
PASSWORD_RESET_TOKEN_EXPIRE_HOURS=1

# Optional: Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

## Quick Start (Gmail)

1. ✅ Enable 2FA on Gmail
2. ✅ Generate App Password
3. ✅ Add to .env (remove spaces from app password)
4. ✅ Set SMTP_USER to your Gmail address
5. ✅ Set EMAIL_FROM to your Gmail address
6. ✅ Restart server
7. ✅ Test registration

That's it! Your emails should now work. Let me know if you run into any issues! 📧