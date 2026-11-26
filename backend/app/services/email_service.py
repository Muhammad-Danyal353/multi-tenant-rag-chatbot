"""
Email Service

Handles all email-related functionality:
- Email verification
- Password reset
- User invitations
- Notifications
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# EMAIL SENDING
# ============================================================================

async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Send an email using SMTP.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email content
        text_content: Plain text email content (optional)
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        message["To"] = to_email
        message["Subject"] = subject
        
        # Add plain text part if provided
        if text_content:
            text_part = MIMEText(text_content, "plain")
            message.attach(text_part)
        
        # Add HTML part
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            
            # Login if credentials are provided
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            server.send_message(message)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


# ============================================================================
# EMAIL TEMPLATES
# ============================================================================

def get_verification_email_template(
    full_name: str,
    verification_link: str
) -> tuple[str, str]:
    """
    Get email verification template.
    
    Args:
        full_name: User's full name
        verification_link: Verification link URL
        
    Returns:
        tuple: (html_content, text_content)
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #007bff;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: #666;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{settings.APP_NAME}</h1>
            </div>
            <div class="content">
                <h2>Welcome, {full_name}!</h2>
                <p>Thank you for registering with {settings.APP_NAME}.</p>
                <p>Please verify your email address by clicking the button below:</p>
                <p style="text-align: center;">
                    <a href="{verification_link}" class="button">Verify Email Address</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #007bff;">{verification_link}</p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't create an account, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 {settings.APP_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to {settings.APP_NAME}!
    
    Hi {full_name},
    
    Thank you for registering with {settings.APP_NAME}.
    
    Please verify your email address by clicking the link below:
    {verification_link}
    
    This link will expire in 24 hours.
    
    If you didn't create an account, please ignore this email.
    
    Best regards,
    The {settings.APP_NAME} Team
    """
    
    return html_content, text_content


def get_password_reset_email_template(
    full_name: str,
    reset_link: str
) -> tuple[str, str]:
    """
    Get password reset email template.
    
    Args:
        full_name: User's full name
        reset_link: Password reset link URL
        
    Returns:
        tuple: (html_content, text_content)
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #dc3545;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #dc3545;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: #666;
                font-size: 12px;
            }}
            .warning {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 10px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Password Reset Request</h1>
            </div>
            <div class="content">
                <h2>Hi {full_name},</h2>
                <p>We received a request to reset your password for your {settings.APP_NAME} account.</p>
                <p>Click the button below to reset your password:</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset Password</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #dc3545;">{reset_link}</p>
                <div class="warning">
                    <strong>Important:</strong> This link will expire in 1 hour for security reasons.
                </div>
                <p>If you didn't request a password reset, please ignore this email or contact support if you have concerns.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 {settings.APP_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Password Reset Request
    
    Hi {full_name},
    
    We received a request to reset your password for your {settings.APP_NAME} account.
    
    Click the link below to reset your password:
    {reset_link}
    
    IMPORTANT: This link will expire in 1 hour for security reasons.
    
    If you didn't request a password reset, please ignore this email or contact support if you have concerns.
    
    Best regards,
    The {settings.APP_NAME} Team
    """
    
    return html_content, text_content


def get_welcome_email_template(full_name: str) -> tuple[str, str]:
    """
    Get welcome email template (sent after email verification).
    
    Args:
        full_name: User's full name
        
    Returns:
        tuple: (html_content, text_content)
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #28a745;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #28a745;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: #666;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to {settings.APP_NAME}!</h1>
            </div>
            <div class="content">
                <h2>Hi {full_name},</h2>
                <p>Your email has been verified successfully! 🎉</p>
                <p>You now have full access to all features of {settings.APP_NAME}.</p>
                <p>Here's what you can do next:</p>
                <ul>
                    <li>Create your first chatbot</li>
                    <li>Upload knowledge base documents</li>
                    <li>Customize your bot's appearance</li>
                    <li>Embed the widget on your website</li>
                </ul>
                <p style="text-align: center;">
                    <a href="{settings.FRONTEND_URL}/dashboard" class="button">Go to Dashboard</a>
                </p>
                <p>If you have any questions, feel free to reach out to our support team.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 {settings.APP_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to {settings.APP_NAME}!
    
    Hi {full_name},
    
    Your email has been verified successfully! 🎉
    
    You now have full access to all features of {settings.APP_NAME}.
    
    Here's what you can do next:
    - Create your first chatbot
    - Upload knowledge base documents
    - Customize your bot's appearance
    - Embed the widget on your website
    
    Visit your dashboard: {settings.FRONTEND_URL}/dashboard
    
    If you have any questions, feel free to reach out to our support team.
    
    Best regards,
    The {settings.APP_NAME} Team
    """
    
    return html_content, text_content


def get_organization_invitation_template(
    inviter_name: str,
    organization_name: str,
    invitation_link: str,
    role: str
) -> tuple[str, str]:
    """
    Get organization invitation email template.
    
    Args:
        inviter_name: Name of the person who sent the invitation
        organization_name: Name of the organization
        invitation_link: Link to accept the invitation
        role: Role being assigned to the invitee
        
    Returns:
        tuple: (html_content, text_content)
    """
    # Capitalize the role for display
    display_role = role.capitalize()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #6f42c1;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #6f42c1;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: #666;
                font-size: 12px;
            }}
            .role-badge {{
                display: inline-block;
                padding: 5px 10px;
                background-color: #e9ecef;
                border-radius: 20px;
                font-weight: bold;
                color: #495057;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Organization Invitation</h1>
            </div>
            <div class="content">
                <h2>You've been invited!</h2>
                <p><strong>{inviter_name}</strong> has invited you to join <strong>{organization_name}</strong> on {settings.APP_NAME}.</p>
                <p>You've been invited as a <span class="role-badge">{display_role}</span></p>
                <p>Click the button below to accept the invitation:</p>
                <p style="text-align: center;">
                    <a href="{invitation_link}" class="button">Accept Invitation</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #6f42c1;">{invitation_link}</p>
                <p>This invitation will expire in 7 days.</p>
                <p>If you don't have an account yet, you'll be able to create one when accepting the invitation.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 {settings.APP_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Organization Invitation - {settings.APP_NAME}
    
    You've been invited!
    
    {inviter_name} has invited you to join {organization_name} on {settings.APP_NAME}.
    
    You've been invited as a {display_role}.
    
    Click the link below to accept the invitation:
    {invitation_link}
    
    This invitation will expire in 7 days.
    
    If you don't have an account yet, you'll be able to create one when accepting the invitation.
    
    Best regards,
    The {settings.APP_NAME} Team
    """
    
    return html_content, text_content


def get_organization_invitation_notification_template(
    inviter_name: str,
    organization_name: str
) -> tuple[str, str]:
    """
    Get notification email template for when a user is added to an organization.
    
    Args:
        inviter_name: Name of the person who added the user
        organization_name: Name of the organization
        
    Returns:
        tuple: (html_content, text_content)
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #6f42c1;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #6f42c1;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: #666;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Added to Organization</h1>
            </div>
            <div class="content">
                <h2>You've been added to a new organization!</h2>
                <p><strong>{inviter_name}</strong> has added you to <strong>{organization_name}</strong> on {settings.APP_NAME}.</p>
                <p>You can now access all the resources shared within this organization.</p>
                <p style="text-align: center;">
                    <a href="{settings.FRONTEND_URL}/dashboard" class="button">Go to Dashboard</a>
                </p>
                <p>If you believe this was done in error, please contact the organization administrator or our support team.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 {settings.APP_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Added to Organization - {settings.APP_NAME}
    
    You've been added to a new organization!
    
    {inviter_name} has added you to {organization_name} on {settings.APP_NAME}.
    
    You can now access all the resources shared within this organization.
    
    Visit your dashboard: {settings.FRONTEND_URL}/dashboard
    
    If you believe this was done in error, please contact the organization administrator or our support team.
    
    Best regards,
    The {settings.APP_NAME} Team
    """
    
    return html_content, text_content


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def send_verification_email(
    to_email: str,
    full_name: str,
    token: str
) -> bool:
    """
    Send email verification email.
    
    Args:
        to_email: Recipient email address
        full_name: User's full name
        token: Verification token
        
    Returns:
        bool: True if sent successfully
    """
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html_content, text_content = get_verification_email_template(full_name, verification_link)
    
    return await send_email(
        to_email=to_email,
        subject=f"Verify your email - {settings.APP_NAME}",
        html_content=html_content,
        text_content=text_content
    )


async def send_password_reset_email(
    to_email: str,
    full_name: str,
    token: str
) -> bool:
    """
    Send password reset email.
    
    Args:
        to_email: Recipient email address
        full_name: User's full name
        token: Password reset token
        
    Returns:
        bool: True if sent successfully
    """
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html_content, text_content = get_password_reset_email_template(full_name, reset_link)
    
    return await send_email(
        to_email=to_email,
        subject=f"Reset your password - {settings.APP_NAME}",
        html_content=html_content,
        text_content=text_content
    )


async def send_welcome_email(
    to_email: str,
    full_name: str
) -> bool:
    """
    Send welcome email after successful verification.
    
    Args:
        to_email: Recipient email address
        full_name: User's full name
        
    Returns:
        bool: True if sent successfully
    """
    html_content, text_content = get_welcome_email_template(full_name)
    
    return await send_email(
        to_email=to_email,
        subject=f"Welcome to {settings.APP_NAME}!",
        html_content=html_content,
        text_content=text_content
    )


async def send_organization_invitation(
    to_email: str,
    inviter_name: str,
    organization_name: str,
    invitation_token: str,
    role: str
) -> bool:
    """
    Send organization invitation email.
    
    Args:
        to_email: Recipient email address
        inviter_name: Name of the person who sent the invitation
        organization_name: Name of the organization
        invitation_token: Invitation token
        role: Role being assigned to the invitee
        
    Returns:
        bool: True if sent successfully
    """
    invitation_link = f"{settings.FRONTEND_URL}/accept-invitation?token={invitation_token}"
    html_content, text_content = get_organization_invitation_template(
        inviter_name, organization_name, invitation_link, role
    )
    
    return await send_email(
        to_email=to_email,
        subject=f"Invitation to join {organization_name} - {settings.APP_NAME}",
        html_content=html_content,
        text_content=text_content
    )


async def send_organization_invitation_notification(
    email: str,
    inviter_name: str,
    organization_name: str
) -> bool:
    """
    Send notification when a user is added to an organization.
    
    Args:
        email: Recipient email address
        inviter_name: Name of the person who added the user
        organization_name: Name of the organization
        
    Returns:
        bool: True if sent successfully
    """
    html_content, text_content = get_organization_invitation_notification_template(
        inviter_name, organization_name
    )
    
    return await send_email(
        to_email=email,
        subject=f"You've been added to {organization_name} - {settings.APP_NAME}",
        html_content=html_content,
        text_content=text_content
    )


# ============================================================================
# EMAIL SERVICE CLASS
# ============================================================================

class EmailService:
    """
    Service for handling email-related functionality.
    """
    
    async def send_verification_email(self, to_email: str, full_name: str, token: str) -> bool:
        """Send email verification email."""
        return await send_verification_email(to_email, full_name, token)
    
    async def send_password_reset_email(self, to_email: str, full_name: str, token: str) -> bool:
        """Send password reset email."""
        return await send_password_reset_email(to_email, full_name, token)
    
    async def send_welcome_email(self, to_email: str, full_name: str) -> bool:
        """Send welcome email after successful verification."""
        return await send_welcome_email(to_email, full_name)
    
    async def send_organization_invitation(
        self, to_email: str, inviter_name: str, organization_name: str, 
        invitation_token: str, role: str
    ) -> bool:
        """Send organization invitation email."""
        return await send_organization_invitation(
            to_email, inviter_name, organization_name, invitation_token, role
        )
    
    async def send_organization_invitation_notification(
        self, email: str, inviter_name: str, organization_name: str
    ) -> bool:
        """Send notification when a user is added to an organization."""
        return await send_organization_invitation_notification(
            email, inviter_name, organization_name
        )


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "send_email",
    "send_verification_email",
    "send_password_reset_email",
    "send_welcome_email",
    "send_organization_invitation",
    "send_organization_invitation_notification",
    "EmailService"
]