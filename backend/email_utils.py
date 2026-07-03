import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@yourapp.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def send_password_reset_email(to_email: str, token: str) -> None:
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject="Reset your password — Finance App",
        html_content=f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;">
          <h2 style="color:#166534;margin-bottom:8px;">Reset your password</h2>
          <p style="color:#555;margin-bottom:24px;">
            Click the button below to set a new password. This link expires in 1 hour.
          </p>
          <a href="{reset_url}"
             style="display:inline-block;background:#166534;color:#fff;
                    text-decoration:none;padding:12px 24px;border-radius:8px;font-weight:600;">
            Reset password
          </a>
          <p style="color:#999;font-size:12px;margin-top:24px;">
            If you didn't request this, you can safely ignore this email.
          </p>
        </div>
        """,
    )
    client = SendGridAPIClient(SENDGRID_API_KEY)
    client.send(message)


def send_otp_email(to_email: str, code: str) -> None:
    # Dev fallback: without a SendGrid key, print the code so the flow is testable.
    if not SENDGRID_API_KEY:
        print(f"[dev] Email OTP for {to_email}: {code}")
        return
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject="Your sign-in code — Finance App",
        html_content=f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;">
          <h2 style="color:#166534;margin-bottom:8px;">Your sign-in code</h2>
          <p style="color:#555;margin-bottom:24px;">
            Enter this code to finish signing in. It expires in 10 minutes.
          </p>
          <div style="font-size:32px;font-weight:700;letter-spacing:8px;color:#1a1714;
                      background:#f0ebe1;border-radius:8px;padding:16px 24px;text-align:center;">
            {code}
          </div>
          <p style="color:#999;font-size:12px;margin-top:24px;">
            If you didn't try to sign in, change your password immediately.
          </p>
        </div>
        """,
    )
    client = SendGridAPIClient(SENDGRID_API_KEY)
    client.send(message)


def send_verification_email(to_email: str, token: str) -> None:
    verify_url = f"{FRONTEND_URL}/verify-email?token={token}"
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject="Verify your email — Finance App",
        html_content=f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;">
          <h2 style="color:#1D9E75;margin-bottom:8px;">Verify your email</h2>
          <p style="color:#555;margin-bottom:24px;">
            Click the button below to verify your email address and activate your account.
            This link expires in 24 hours.
          </p>
          <a href="{verify_url}"
             style="display:inline-block;background:#1D9E75;color:#fff;
                    text-decoration:none;padding:12px 24px;border-radius:8px;font-weight:600;">
            Verify email
          </a>
          <p style="color:#999;font-size:12px;margin-top:24px;">
            If you didn't create an account, you can safely ignore this email.
          </p>
        </div>
        """,
    )
    client = SendGridAPIClient(SENDGRID_API_KEY)
    client.send(message)
