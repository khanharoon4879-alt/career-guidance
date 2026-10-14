import time
import random
import re
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth import login
from .email_service import dispatch_otp_email

def _get_request_data(request):
    """Safely extracts data from JSON body or POST form data."""
    if request.content_type == "application/json":
        try:
            return json.loads(request.body.decode("utf-8"))
        except Exception:
            return {}
    return request.POST.dict()

@csrf_exempt
def api_send_otp(request):
    """
    REST API Endpoint: /api/auth/send-otp/
    Accepts: { email, password, action: 'signin'|'signup', fname, lname }
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Only POST requests allowed."}, status=405)

    data = _get_request_data(request)
    action = data.get("action", "signin")
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or data.get("pass1") or ""

    if not email:
        return JsonResponse({"status": "error", "message": "Email is required."}, status=400)

    # Clean domain typos like gmil.com -> gmail.com
    if email.endswith("@gmil.com"):
        email = email.replace("@gmil.com", "@gmail.com")

    # SIGNUP FLOW
    if action == "signup":
        fname = (data.get("fname") or "").strip()
        lname = (data.get("lname") or "").strip()
        pass2 = data.get("pass2", "")

        if not fname or not password:
            return JsonResponse({"status": "error", "message": "First Name and Password are required."}, status=400)

        if pass2 and password != pass2:
            return JsonResponse({"status": "error", "message": "Passwords do not match."}, status=400)

        if len(password) < 6:
            return JsonResponse({"status": "error", "message": "Password must be at least 6 characters."}, status=400)

        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({"status": "error", "message": "An account with this email already exists. Please Sign In."}, status=400)

        # Generate unique username
        base_username = re.sub(r'[^a-zA-Z0-9_]', '', email.split('@')[0]) or "user"
        username = base_username
        c = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base_username}{c}"
            c += 1

        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = fname
        user.last_name = lname
        user.save()
        user_name = fname
        user_id = user.id

    # SIGNIN FLOW
    else:
        if not password:
            return JsonResponse({"status": "error", "message": "Password is required."}, status=400)

        # Lookup user by email or username or prefix
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.filter(username__iexact=email).first()
        if not user and "@" in email:
            prefix = email.split("@")[0]
            user = User.objects.filter(username__iexact=prefix).first()

        if not user or not user.check_password(password):
            return JsonResponse({"status": "error", "message": "Invalid Email or Password. Please try again."}, status=401)

        if not user.is_active:
            return JsonResponse({"status": "error", "message": "This account is inactive. Please contact support."}, status=403)

        user_name = user.first_name or user.username
        user_id = user.id
        if not user.email:
            user.email = email
            user.save()

    # Generate 6-digit OTP
    otp = f"{random.randint(100000, 999999):06d}"
    request.session['auth_otp'] = otp
    request.session['otp_user_id'] = user_id
    request.session['otp_email'] = email
    request.session['otp_time'] = time.time()
    request.session['otp_next'] = data.get("next") or "/selection/"

    # Dispatch email via REST API / SMTP
    success, channel, err = dispatch_otp_email(
        to_email=email,
        otp=otp,
        user_name=user_name,
        purpose="Sign In" if action == "signin" else "Registration"
    )

    if success:
        request.session.pop("otp_hint", None)
        return JsonResponse({
            "status": "success",
            "message": f"6-digit OTP sent to {email}! Please check your Inbox and Spam folder.",
            "email": email,
            "channel": channel,
            "redirect_url": "/verify-otp/"
        })
    else:
        # Fallback when cloud provider (Render free tier) blocks SMTP ports
        request.session['otp_hint'] = otp
        return JsonResponse({
            "status": "success",
            "message": f"OTP generated! (Cloud SMTP restricted. For testing: OTP is {otp})",
            "email": email,
            "otp_hint": otp,
            "channel": "fallback",
            "redirect_url": "/verify-otp/"
        })

@csrf_exempt
def api_verify_otp(request):
    """
    REST API Endpoint: /api/auth/verify-otp/
    Accepts: { otp: '123456' }
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Only POST requests allowed."}, status=405)

    data = _get_request_data(request)
    entered_otp = str(data.get("otp", "")).strip()

    expected_otp = request.session.get("auth_otp")
    user_id = request.session.get("otp_user_id")

    if not expected_otp or not user_id:
        return JsonResponse({"status": "error", "message": "Session expired. Please sign in again."}, status=400)

    # Check 10-minute expiry
    otp_time = request.session.get("otp_time", 0)
    if time.time() - otp_time > 600:
        return JsonResponse({"status": "error", "message": "OTP has expired. Please click Resend OTP."}, status=400)

    if entered_otp != str(expected_otp):
        return JsonResponse({"status": "error", "message": "Incorrect OTP. Please enter the valid 6-digit code."}, status=400)

    try:
        user = User.objects.get(id=user_id)
        login(request, user)
        next_url = request.session.get("otp_next") or "/selection/"

        # Clear session OTP
        for k in ["auth_otp", "otp_user_id", "otp_email", "otp_time", "otp_next", "otp_hint"]:
            request.session.pop(k, None)

        return JsonResponse({
            "status": "success",
            "message": f"Welcome back, {user.first_name or user.username}!",
            "redirect_url": next_url
        })
    except User.DoesNotExist:
        return JsonResponse({"status": "error", "message": "User not found."}, status=404)

@csrf_exempt
def api_resend_otp(request):
    """
    REST API Endpoint: /api/auth/resend-otp/
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Only POST requests allowed."}, status=405)

    user_id = request.session.get("otp_user_id")
    email = request.session.get("otp_email")

    if not user_id or not email:
        return JsonResponse({"status": "error", "message": "No active session found. Please sign in again."}, status=400)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"status": "error", "message": "User not found."}, status=404)

    otp = f"{random.randint(100000, 999999):06d}"
    request.session['auth_otp'] = otp
    request.session['otp_time'] = time.time()

    success, channel, err = dispatch_otp_email(
        to_email=email,
        otp=otp,
        user_name=user.first_name or user.username,
        purpose="Resent Verification"
    )

    if success:
        request.session.pop("otp_hint", None)
        return JsonResponse({
            "status": "success",
            "message": f"New OTP sent to {email}! Please check your Inbox and Spam folder.",
            "channel": channel
        })
    else:
        request.session['otp_hint'] = otp
        return JsonResponse({
            "status": "success",
            "message": f"New OTP generated! (For testing: OTP is {otp})",
            "otp_hint": otp,
            "channel": "fallback"
        })
