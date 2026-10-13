import os
import time
import random
import re
import markdown
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.mail import send_mail
from django.conf import settings
from google import genai

def index(request):
    return render(request, "authentication/index.html")

def schools(request):
    if not request.user.is_authenticated:
        messages.info(request, "Please log in to access School & College Guidance.")
        return redirect("/signin/?next=/schools/")
    return render(request, "authentication/schools.html")

def counseling(request):
    if not request.user.is_authenticated:
        messages.info(request, "Please log in to access Personalized Career Counseling.")
        return redirect("/signin/?next=/selection/")
    return redirect("selection")

def signup(request):
    if request.user.is_authenticated:
        return redirect("selection")

    if request.method == "POST":
        fname = request.POST.get("fname", "").strip()
        lname = request.POST.get("lname", "").strip()
        email = request.POST.get("email", "").strip().lower()
        pass1 = request.POST.get("pass1", "")
        pass2 = request.POST.get("pass2", "")

        if not fname or not email or not pass1:
            messages.error(request, "Please fill in all required fields (Name, Email, Password).")
            return render(request, "authentication/signup.html", request.POST)

        if pass1 != pass2:
            messages.error(request, "Passwords do not match.")
            return render(request, "authentication/signup.html", request.POST)

        if len(pass1) < 6:
            messages.error(request, "Password must be at least 6 characters.")
            return render(request, "authentication/signup.html", request.POST)

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists. Please log in.")
            return redirect("signin")

        # Create unique username from email
        base_username = re.sub(r'[^a-zA-Z0-9_]', '', email.split('@')[0]) or "user"
        username = base_username
        counter = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        myuser = User.objects.create_user(
            username=username,
            email=email,
            password=pass1
        )
        myuser.first_name = fname
        myuser.last_name = lname
        myuser.save()

        # Generate OTP for immediate verification and login
        otp = f"{random.randint(100000, 999999):06d}"
        request.session['auth_otp'] = otp
        request.session['otp_user_id'] = myuser.id
        request.session['otp_email'] = email
        request.session['otp_next'] = "/selection/"
        request.session['otp_time'] = time.time()

        try:
            send_mail(
                subject="Welcome to Career Guidance - Verification OTP",
                message=f"Hello {fname},\n\nThank you for signing up with Career Guidance!\nYour 6-digit Verification OTP is: {otp}\n\nThis OTP is valid for 10 minutes.\n\nCareer Guidance Team",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@careerguidance.com"),
                recipient_list=[email],
                fail_silently=False
            )
            print(f"[OTP EMAIL SENT] To: {email} | OTP: {otp}")
        except Exception as e:
            print(f"[OTP EMAIL ERROR] Could not send to {email}: {e}")

        messages.success(request, f"Account created! A 6-digit OTP has been sent to {email}. Please check your inbox.")
        return redirect("verify_otp")

    return render(request, "authentication/signup.html")

def signin(request):
    if request.user.is_authenticated:
        return redirect("selection")

    if request.method == "POST":
        email_or_user = (request.POST.get("email") or request.POST.get("username") or "").strip()
        pass1 = request.POST.get("pass1", "")
        next_url = request.POST.get("next") or request.GET.get("next") or ""

        if not email_or_user or not pass1:
            messages.error(request, "Please enter both Email and Password.")
            return render(request, "authentication/signin.html", {"email": email_or_user, "next": next_url})

        # Match user by email or username
        user = User.objects.filter(email__iexact=email_or_user).first()
        if not user:
            user = User.objects.filter(username__iexact=email_or_user).first()

        if user is not None and user.check_password(pass1):
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact support.")
                return render(request, "authentication/signin.html", {"email": email_or_user, "next": next_url})

            # Generate 6-digit OTP
            otp = f"{random.randint(100000, 999999):06d}"
            request.session['auth_otp'] = otp
            request.session['otp_user_id'] = user.id
            request.session['otp_email'] = user.email or user.username
            request.session['otp_next'] = next_url
            request.session['otp_time'] = time.time()

            # Send Email
            try:
                send_mail(
                    subject="Career Guidance Login OTP",
                    message=f"Hello {user.first_name or user.username},\n\nYour OTP for logging into Career Guidance is: {otp}\n\nThis OTP is valid for 10 minutes.\n\nCareer Guidance Team",
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@careerguidance.com"),
                    recipient_list=[user.email] if user.email else [],
                    fail_silently=False
                )
                print(f"[OTP EMAIL SENT] To: {user.email} | OTP: {otp}")
            except Exception as e:
                print(f"[OTP EMAIL ERROR] Could not send to {user.email}: {e}")

            messages.info(request, f"A 6-digit OTP has been sent to your email ({user.email or user.username}). Please check your inbox.")
            return redirect("verify_otp")
        else:
            messages.error(request, "Invalid Email or Password. Please try again.")
            return render(request, "authentication/signin.html", {"email": email_or_user, "next": next_url})

    next_url = request.GET.get("next", "")
    return render(request, "authentication/signin.html", {"next": next_url})

def verify_otp(request):
    if request.user.is_authenticated:
        return redirect("selection")

    otp_expected = request.session.get("auth_otp")
    user_id = request.session.get("otp_user_id")
    email = request.session.get("otp_email", "")

    if not otp_expected or not user_id:
        messages.warning(request, "Session expired. Please log in again.")
        return redirect("signin")

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()
        if not entered_otp:
            # Handle split inputs (otp_1 to otp_6)
            entered_otp = "".join([request.POST.get(f"otp_{i}", "") for i in range(1, 7)]).strip()

        # Check expiration (10 minutes)
        otp_time = request.session.get("otp_time", 0)
        if time.time() - otp_time > 600:
            messages.error(request, "OTP has expired. Please click Resend OTP.")
            return render(request, "authentication/verify_otp.html", {"email": email})

        if entered_otp == otp_expected:
            try:
                user = User.objects.get(id=user_id)
                login(request, user)
                next_url = request.session.get("otp_next")

                # Clean session keys
                for key in ["auth_otp", "otp_user_id", "otp_email", "otp_next", "otp_time"]:
                    request.session.pop(key, None)

                messages.success(request, f"Login successful! Welcome to Career Guidance, {user.first_name or user.username}.")

                if next_url and next_url.startswith("/"):
                    return redirect(next_url)
                return redirect("selection")
            except User.DoesNotExist:
                messages.error(request, "User not found. Please register or sign in again.")
                return redirect("signin")
        else:
            messages.error(request, "Incorrect OTP. Please enter the valid 6-digit code.")
            return render(request, "authentication/verify_otp.html", {"email": email})

    return render(request, "authentication/verify_otp.html", {"email": email})

def resend_otp(request):
    user_id = request.session.get("otp_user_id")
    email = request.session.get("otp_email")

    if not user_id or not email:
        messages.warning(request, "Please enter your Email and Password to get an OTP.")
        return redirect("signin")

    otp = f"{random.randint(100000, 999999):06d}"
    request.session['auth_otp'] = otp
    request.session['otp_time'] = time.time()

    try:
        send_mail(
            subject="Career Guidance - Resent Login OTP",
            message=f"Your new OTP for Career Guidance is: {otp}\n\nValid for 10 minutes.\n\nCareer Guidance Team",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@careerguidance.com"),
            recipient_list=[email],
            fail_silently=False
        )
        print(f"[OTP EMAIL SENT] To: {email} | OTP: {otp}")
    except Exception as e:
        print(f"[OTP EMAIL ERROR] Could not send to {email}: {e}")

    messages.info(request, f"A new 6-digit OTP has been sent to {email}. Please check your inbox.")
    return redirect("verify_otp")

def selection(request):
    if not request.user.is_authenticated:
        messages.info(request, "Please log in to continue your career exploration.")
        return redirect("/signin/?next=/selection/")

    if request.method == "POST":

        role = request.POST.get("role")

        if role == "student":
            request.session["role"] = "student"
            return redirect("details")

        elif role == "parent":
            request.session["role"] = "parent"
            return redirect("details")

    return render(request, "authentication/selection.html")

def student_details(request):
    return redirect("details")

def generate_career_ai(prompt):

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise Exception("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    # Current stable Gemini models
    models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]

    last_error = None

    for model_name in models:

        for attempt in range(3):

            try:

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                if response.text:
                    return response.text

            except Exception as e:

                last_error = e
                error_text = str(e)

                print(
                    f"Gemini Error | Model: {model_name} | "
                    f"Attempt: {attempt + 1} | {error_text}"
                )

                # Retry for temporary server errors
                if "503" in error_text or "UNAVAILABLE" in error_text:

                    time.sleep(2 ** attempt)
                    continue

                break

    raise Exception(
        f"Gemini service failed after retries: {last_error}"
    )

def details(request):

    # ======================================
    # GET REQUEST
    # ======================================

    if request.method == "GET":

        try:
            step = int(request.GET.get("step", 1))
        except ValueError:
            step = 1

        if step < 1:
            step = 1

        if step > 6:
            step = 6

        return render(
            request,
            "authentication/details.html",
            {
                "step": step
            }
        )

    # ======================================
    # POST REQUEST
    # ======================================

    if request.method == "POST":

        try:
            current_step = int(
                request.POST.get("current_step", 1)
            )
        except ValueError:
            current_step = 1

        # ==================================
        # STEP 1 - NAME + GRADE
        # ==================================

        if current_step == 1:

            name = request.POST.get("name", "").strip()
            grade = request.POST.get("grade", "").strip()

            if not name:
                messages.error(
                    request,
                    "Please enter student's name."
                )
                return redirect("/details/?step=1")

            if not grade:
                messages.error(
                    request,
                    "Please select your class."
                )
                return redirect("/details/?step=1")

            request.session["name"] = name
            request.session["grade"] = grade

            return redirect("/details/?step=2")

        # ==================================
        # STEP 2 - BOARD
        # ==================================

        elif current_step == 2:

            board = request.POST.get("board", "").strip()

            if not board:
                messages.error(
                    request,
                    "Please select your board."
                )
                return redirect("/details/?step=2")

            request.session["board"] = board

            return redirect("/details/?step=3")

        # ==================================
        # STEP 3 - CITY
        # ==================================

        elif current_step == 3:

            city = request.POST.get("city", "").strip()

            if not city:
                messages.error(
                    request,
                    "Please enter your city."
                )
                return redirect("/details/?step=3")

            request.session["city"] = city

            return redirect("/details/?step=4")

        # ==================================
        # STEP 4 - BUDGET
        # ==================================

        elif current_step == 4:

            budget = request.POST.get("budget", "").strip()

            if not budget:
                messages.error(
                    request,
                    "Please select your annual education budget."
                )
                return redirect("/details/?step=4")

            request.session["budget"] = budget

            return redirect("/details/?step=5")

        # ==================================
        # STEP 5 - INTERESTS
        # ==================================

        elif current_step == 5:

            interests = request.POST.getlist("interests")

            if not interests:
                messages.error(
                    request,
                    "Please select at least one interest."
                )
                return redirect("/details/?step=5")

            if len(interests) > 5:
                messages.error(
                    request,
                    "You can select maximum 5 interests."
                )
                return redirect("/details/?step=5")

            request.session["interests"] = interests

            # IMPORTANT:
            # Step 5 ke baad AI call nahi hogi.
            # Pehle Step 6 marks page par jayega.

            return redirect("/details/?step=6")

        # ==================================
        # STEP 6 - MARKS + AI
        # ==================================

        elif current_step == 6:

            try:
                science = float(request.POST.get("science", 0))
                mathematics = float(request.POST.get("mathematics", 0))
                english = float(request.POST.get("english", 0))
                social_science = float(
                    request.POST.get("social_science", 0)
                )
                hindi = float(request.POST.get("hindi", 0))

            except (ValueError, TypeError):

                messages.error(
                    request,
                    "Please enter valid marks."
                )

                return redirect("/details/?step=6")

            # Validate marks

            marks_list = [
                science,
                mathematics,
                english,
                social_science,
                hindi
            ]

            if any(mark < 0 or mark > 100 for mark in marks_list):

                messages.error(
                    request,
                    "Marks must be between 0 and 100."
                )

                return redirect("/details/?step=6")

            # ==================================
            # CALCULATE TOTAL + PERCENTAGE
            # ==================================

            total_marks = (
                science
                + mathematics
                + english
                + social_science
                + hindi
            )

            max_marks = 500

            percentage = (
                total_marks / max_marks
            ) * 100

            # ==================================
            # SAVE MARKS IN SESSION
            # ==================================

            request.session["marks"] = {
                "Science": science,
                "Mathematics": mathematics,
                "English": english,
                "Social Science": social_science,
                "Hindi": hindi,
            }

            request.session["total_marks"] = total_marks
            request.session["max_marks"] = max_marks
            request.session["percentage"] = round(
                percentage,
                2
            )

            # ==================================
            # GET ALL STUDENT DATA
            # ==================================

            name = request.session.get("name", "")
            grade = request.session.get("grade", "")
            board = request.session.get("board", "")
            city = request.session.get("city", "")
            budget = request.session.get("budget", "")
            interests = request.session.get("interests", [])

            # ==================================
            # AI PROMPT
            # ==================================

            prompt = f"""
You are an expert career guidance counselor.

Analyze this student's actual academic profile and provide
personalized career guidance.

STUDENT INFORMATION

Name:
{name}

Class:
{grade}

Education Board:
{board}

City:
{city}

Annual Education Budget:
{budget}

Interests:
{", ".join(interests)}

ACADEMIC MARKS

Science: {science}/100
Mathematics: {mathematics}/100
English: {english}/100
Social Science: {social_science}/100
Hindi: {hindi}/100

Total Marks:
{total_marks}/500

Percentage:
{percentage:.2f}%

Provide the response in these sections:

1. Student Profile Analysis

2. Academic Performance Analysis

3. Subject-wise Strengths

4. Areas for Improvement

5. Recommended Stream
   Explain whether Science, Commerce or Arts/Humanities
   may suit the student and why.

6. Best Career Options
   Give several realistic options based on marks,
   interests, class, board, city and budget.

7. Why These Careers Fit

8. Recommended Courses / Degrees

9. Suitable Colleges
   Suggest realistic types of colleges and institutions
   considering the student's city and budget.

10. Skills to Develop

11. Entrance Exams / Certifications

12. Short-Term Roadmap
    6-12 months

13. Medium-Term Roadmap
    1-3 years

14. Long-Term Roadmap
    3-7 years

15. Project Suggestions

16. Backup Career Options

17. Final Personalized Advice

IMPORTANT:
- Use the student's actual marks.
- Consider the student's interests.
- Consider class and education board.
- Consider city.
- Consider annual budget.
- Do not give generic advice.
- Do not guarantee any career or salary.
- Clearly explain the reasoning behind recommendations.
"""

            # ==================================
            # GEMINI API KEY
            # ==================================

            api_key = getattr(
                settings,
                "GEMINI_API_KEY",
                None
            )

            if not api_key:

                messages.error(
                    request,
                    "Gemini API key is missing. Please check your API settings."
                )

                return redirect("/details/?step=6")

            # ==================================
            # GEMINI CLIENT
            # ==================================

            try:

                client = genai.Client(
                    api_key=api_key
                )

                # Gemini AI with automatic retry + fallback
                models = [
                    "gemini-2.5-flash",
                    "gemini-3.6-flash",
                    "gemini-3.5-flash",
                    "gemini-3.5-flash-lite",
                ]

                response = None
                last_error = None

                for model_name in models:
                    for attempt in range(3):
                        try:
                            print(f"Trying {model_name} - attempt {attempt + 1}")

                            response = client.models.generate_content(
                                model=model_name,
                                contents=prompt
                            )

                            if response and response.text:
                                print(f"SUCCESS: {model_name}")
                                break

                        except Exception as e:
                            last_error = e
                            error_text = str(e)

                            print(
                                f"FAILED: {model_name} "
                                f"attempt {attempt + 1}: {e}"
                            )

                            if "503" in error_text or "UNAVAILABLE" in error_text:
                                wait_time = 5 * (attempt + 1)
                                print(f"Waiting {wait_time} seconds...")
                                time.sleep(wait_time)
                                continue

                            break

                    if response and response.text:
                        break

                if not response or not response.text:
                    raise Exception(
                        f"All Gemini models failed. Last error: {last_error}"
                    )

                ai_answer = response.text


            except Exception as e:

                print("\n\n================ GEMINI ERROR ================")
                print("ERROR TYPE:", type(e).__name__)
                print("ERROR:", str(e))
                print("==============================================\n\n")

                messages.error(request, f"AI Error: {str(e)}")
                

                return redirect("/details/?step=6")

            # ==================================
            # SAVE AI RESULT
            # ==================================

            request.session["ai_answer"] = ai_answer
            request.session.modified = True

            messages.success(
                request,
                "Your career analysis is ready!"
            )

            return redirect("next")

    # ======================================
    # DEFAULT
    # ======================================

    return redirect("/details/?step=1")

def parent_details(request):
    return render(
        request,
        "authentication/details.html"
    )
def next(request):
    ai_answer = request.session.get("ai_answer", "")

    # AI answer ko headings ke basis par sections mein divide karna
    parts = re.split(r'(?m)^#{1,3}\s+', ai_answer)

    sections = []

    for part in parts:
        part = part.strip()

        if not part:
            continue

        lines = part.splitlines()

        if not lines:
            continue

        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        if not body:
            continue

        content = markdown.markdown(
            body,
            extensions=[
                "extra",
                "tables",
                "nl2br"
            ]
        )

        sections.append({
            "title": title,
            "content": content
        })

    # Student information
    student_name = request.session.get("name", "")
    grade = request.session.get("grade", "")
    board = request.session.get("board", "")
    city = request.session.get("city", "")
    budget = request.session.get("budget", "")
    interests = request.session.get("interests", "")

    # Marks
    science = request.session.get("science", 0)
    mathematics = request.session.get("mathematics", 0)
    english = request.session.get("english", 0)
    social_science = request.session.get("social_science", 0)
    hindi = request.session.get("hindi", 0)

    try:
        total_marks = (
            float(science)
            + float(mathematics)
            + float(english)
            + float(social_science)
            + float(hindi)
        )

        percentage = round((total_marks / 500) * 100, 2)

    except (ValueError, TypeError):
        total_marks = 0
        percentage = 0

    context = {
        "sections": sections,

        "student_name": student_name,
        "grade": grade,
        "board": board,
        "city": city,
        "budget": budget,
        "interests": interests,

        "science": science,
        "mathematics": mathematics,
        "english": english,
        "social_science": social_science,
        "hindi": hindi,

        "total_marks": total_marks,
        "percentage": percentage,
    }

    return render(
        request,
        "authentication/next.html",
        context
    )

    ai_answer = request.session.get("ai_answer", "")
    ai_result = markdown.markdown(ai_answer,extensions=["extra", "tables", "nl2br"])
    return render(request,"authentication/next.html",{"ai_result": ai_result})
def forgot_password(request):

    if request.method == "POST":

        username = request.POST.get("username")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        try:
            user = User.objects.get(username=username)

        except User.DoesNotExist:
            messages.error(request, "Username not found!")
            return redirect("forgot_password")

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match!")
            return redirect("forgot_password")

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters!")
            return redirect("forgot_password")

        user.set_password(new_password)
        user.save()

        messages.success(request, "Password changed successfully!")
        return redirect("signin")

    return render(request, "authentication/forgot_password.html")
def signout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("index")