"""
Email Service for sending verification and notification emails.

Uses SMTP to send emails. Supports multiple providers (Gmail, SendGrid, etc.)
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Handles email sending operations."""
    
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.EMAIL_FROM
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text fallback (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Add text and HTML parts
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_verification_email(self, to_email: str, verification_link: str) -> bool:
        """Send email verification link."""
        subject = "Verify Your Email - Cloud Drive"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px;">
                <h2 style="color: #333;">Welcome to Cloud Drive!</h2>
                <p style="color: #666; line-height: 1.6;">
                    Thank you for signing up. Please verify your email address to activate your account.
                </p>
                <div style="margin: 30px 0;">
                    <a href="{verification_link}" 
                       style="background: #4285f4; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Verify Email Address
                    </a>
                </div>
                <p style="color: #999; font-size: 14px;">
                    Or copy and paste this link into your browser:<br>
                    <span style="color: #4285f4;">{verification_link}</span>
                </p>
                <p style="color: #999; font-size: 12px; margin-top: 30px;">
                    This link will expire in 24 hours. If you didn't create an account, 
                    you can safely ignore this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Welcome to Cloud Drive!
        
        Please verify your email address by clicking the link below:
        {verification_link}
        
        This link will expire in 24 hours.
        
        If you didn't create an account, you can safely ignore this email.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_lockout_notification(self, to_email: str, locked_until: str) -> bool:
        """Send account lockout notification."""
        subject = "Account Locked - Cloud Drive"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #fff3cd; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107;">
                <h2 style="color: #856404;">Account Temporarily Locked</h2>
                <p style="color: #856404; line-height: 1.6;">
                    Your account has been temporarily locked due to multiple failed login attempts.
                </p>
                <p style="color: #856404;">
                    <strong>Locked until:</strong> {locked_until}
                </p>
                <p style="color: #856404; font-size: 14px; margin-top: 20px;">
                    If this wasn't you, please reset your password immediately.
                </p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
    
    def send_magic_link_email(self, to_email: str, magic_link: str) -> bool:
        """Send magic link for passwordless login."""
        subject = "Sign in to Cloud Drive"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #f5f5f5; padding: 30px; border-radius: 8px;">
                <h2 style="color: #333;">Sign in to Cloud Drive</h2>
                <p style="color: #666; font-size: 16px; line-height: 1.6;">
                    Click the button below to securely sign in to your account.
                </p>
                <div style="margin: 30px 0;">
                    <a href="{magic_link}" 
                       style="background: #4285f4; color: white; padding: 14px 40px; 
                              text-decoration: none; border-radius: 4px; 
                              display: inline-block; font-size: 16px; font-weight: 500;">
                        Sign In to Cloud Drive
                    </a>
                </div>
                <p style="color: #999; font-size: 14px;">
                    This link will expire in 15 minutes.<br>
                    If you didn't request this, you can safely ignore this email.
                </p>
                <p style="color: #999; font-size: 12px; margin-top: 30px; word-break: break-all;">
                    Or copy and paste this link into your browser:<br>
                    <span style="color: #4285f4;">{magic_link}</span>
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Sign in to Cloud Drive
        
        Click the link below to sign in:
        {magic_link}
        
        This link will expire in 15 minutes.
        
        If you didn't request this, you can safely ignore this email.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)


# Singleton instance
email_service = EmailService()
