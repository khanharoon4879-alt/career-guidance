import os
import json
import urllib.request
import urllib.error
from django.conf import settings
from django.core.mail import send_mail

def dispatch_otp_email(to_email, otp, user_name="Student", purpose="Account Verification"):
    """
    Multi-channel email delivery over HTTPS REST API & SMTP:
    1. Brevo REST API (HTTPS port 443 - never blocked by cloud firewalls)
    2. Resend REST API (HTTPS port 443)
    3. Django SMTP (smtp.gmail.com:587)
    Returns: (success: bool, delivery_method: str, error_msg: str)
    """
    subject = f"Career Guidance - {purpose} OTP: {otp}"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
            .card {{ max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
            .logo {{ font-size: 20px; font-weight: 800; color: #4f46e5; margin-bottom: 24px; display: inline-block; }}
            .title {{ font-size: 18px; font-weight: 700; color: #0f172a; margin-bottom: 12px; }}
            .text {{ font-size: 14px; color: #475569; line-height: 1.6; margin-bottom: 24px; }}
            .otp-box {{ background: #eff6ff; border: 2px dashed #6366f1; border-radius: 10px; padding: 18px; text-align: center; margin: 24px 0; }}
            .otp-code {{ font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #312e81; font-family: monospace; }}
            .footer {{ font-size: 12px; color: #94a3b8; text-align: center; margin-top: 28px; border-top: 1px solid #f1f5f9; padding-top: 16px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="logo">🎯 Career Guidance</div>
            <div class="title">{purpose}</div>
            <p class="text">Hello <strong>{user_name}</strong>,<br>Thank you for using Career Guidance! Use the 6-digit OTP code below to verify your request.</p>
            <div class="otp-box">
                <div class="otp-code">{otp}</div>
            </div>
            <p class="text" style="font-size: 13px;">⏱️ This verification code is valid for <strong>10 minutes</strong>. Do not share this OTP with anyone.</p>
            <div class="footer">
                Career Guidance Platform • Empowering your future<br>
                If you did not request this OTP, you can safely ignore this email.
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"Hello {user_name},\n\nYour Career Guidance {purpose} OTP is: {otp}\n\nValid for 10 minutes.\n\nCareer Guidance Team"

    # Channel 1: Brevo REST API (HTTPS Port 443)
    brevo_key = os.getenv("BREVO_API_KEY")
    if brevo_key:
        try:
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "accept": "application/json",
                "api-key": brevo_key,
                "content-type": "application/json"
            }
            payload = {
                "sender": {
                    "name": "Career Guidance",
                    "email": getattr(settings, "EMAIL_HOST_USER", "khanharoon4879@gmail.com")
                },
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_content
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=8) as res:
                if res.status in (200, 201):
                    print(f"[REST API EMAIL SENT - BREVO] To: {to_email} | OTP: {otp}", flush=True)
                    return True, "brevo_api", ""
        except Exception as e:
            print(f"[BREVO API ERROR] {e}", flush=True)

    # Channel 2: Resend REST API (HTTPS Port 443)
    resend_key = os.getenv("RESEND_API_KEY")
    if resend_key:
        try:
            url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": "Career Guidance <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=8) as res:
                if res.status in (200, 201):
                    print(f"[REST API EMAIL SENT - RESEND] To: {to_email} | OTP: {otp}", flush=True)
                    return True, "resend_api", ""
        except Exception as e:
            print(f"[RESEND API ERROR] {e}", flush=True)

    # Channel 3: Django SMTP EmailBackend
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", f"Career Guidance <{getattr(settings, 'EMAIL_HOST_USER', '')}>")
        send_mail(
            subject=subject,
            message=text_content,
            from_email=from_email,
            recipient_list=[to_email],
            fail_silently=False,
            html_message=html_content
        )
        print(f"[SMTP EMAIL SENT] To: {to_email} | OTP: {otp}", flush=True)
        return True, "smtp", ""
    except Exception as e:
        error_msg = str(e)
        print(f"[SMTP EMAIL BLOCKED/ERROR] Could not send to {to_email}: {error_msg}", flush=True)
        return False, "failed", error_msg
