from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.contrib.auth.models import User         
from django.contrib import messages                                                                                                                                                                                                                                                                                                                                                                                                                                           
from django.contrib.auth import authenticate,login,logout
from google import genai
from django.conf import settings
import os
import time
from django.shortcuts import redirect, render
from django.contrib import messages
from django.conf import settings
from google import genai

import markdown
from django.shortcuts import render
from django.contrib.auth import update_session_auth_hash

def index(request):
    return render(request, "authentication/index.html")

# Create your views here.
def signup(request):

    if request.method=="POST":
        username=request.POST['username']
        fname=request.POST['fname']
        lname=request.POST['lname']
        pass1=request.POST['pass1']
        pass2=request.POST['pass2']

        if pass1 != pass2:
            messages.error(request, "Passwords do not match.")
            return redirect('signup')

        myuser = User.objects.create_user(
            username=username,
            password=pass1
        )
        myuser.first_name=fname
        myuser.last_name=lname

        myuser.save()

        messages.success(request,"your Account Has been Suceessfully")

        return redirect('index')
    return render(request,'authentication/signup.html')

def signin(request):

    if request.method == "POST":

        username = request.POST.get("username")
        pass1 = request.POST.get("pass1")

        user = authenticate(
            username=username,
            password=pass1
        )

        if user is not None:
            login(request, user)

            # Login ke baad DIRECT selection page
            return redirect("selection")

        else:
            messages.error(request, "Invalid username or password.")
            return redirect("signin")

    return render(request, "authentication/signin.html")
def selection(request):

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

        if step > 5:
            step = 5

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
        # STEP 1 - GRADE
        # ==================================

        if current_step == 1:

            grade = request.POST.get("grade")

            if not grade:
                messages.error(
                    request,
                    "Please select your grade."
                )

                return redirect("/details/?step=1")

            request.session["grade"] = grade

            return redirect("/details/?step=2")

        # ==================================
        # STEP 2 - BOARD
        # ==================================

        elif current_step == 2:

            board = request.POST.get("board")

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

            city = request.POST.get("city")

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

            budget = request.POST.get("budget")

            if not budget:
                messages.error(
                    request,
                    "Please select your annual fee budget."
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

            # Save interests
            request.session["interests"] = interests

            # ==================================
            # GET ALL DATA
            # ==================================

            grade = request.session.get("grade", "")
            board = request.session.get("board", "")
            city = request.session.get("city", "")
            budget = request.session.get("budget", "")

            # ==================================
            # CREATE AI PROMPT
            # ==================================

            prompt = f"""
You are an expert career guidance counselor.

Analyze the student's actual information and provide
personalized career guidance.

STUDENT INFORMATION:

Grade/Class:
{grade}

Education Board:
{board}

City:
{city}

Annual Education Budget:
{budget}

Interests:
{", ".join(interests)}

Give the student:

1. Student Profile Analysis
2. Academic and Personal Strengths
3. Areas for Improvement
4. Best Suitable Career Options
5. Why each career is suitable
6. Recommended Courses or Degrees
7. Skills the student should develop
8. Short-Term Career Roadmap (6-12 months)
9. Medium-Term Career Roadmap (1-3 years)
10. Long-Term Career Roadmap (3-7 years)
11. Entrance Exams or Certifications
12. Project Suggestions
13. Final Personalized Career Advice

IMPORTANT:

- Analyze the actual information.
- Do not give generic career advice.
- Consider grade/class.
- Consider education board.
- Consider interests.
- Consider budget.
- Consider city.
- Give realistic career options.
- Do not guarantee any career.
"""

            # ==================================
            # CHECK API KEY
            # ==================================

            api_key = getattr(
                settings,
                "GEMINI_API_KEY",
                None
            )

            if not api_key:

                print("ERROR: GEMINI_API_KEY is missing.")

                messages.error(
                    request,
                    "Gemini API key is missing. Please check your .env file."
                )

                return redirect(
                    "/details/?step=5"
                )

            # ==================================
            # CREATE GEMINI CLIENT
            # ==================================

            try:

                client = genai.Client(
                    api_key=api_key
                )

            except Exception as e:

                print("GEMINI CLIENT ERROR:")
                print(e)

                messages.error(
                    request,
                    "Gemini API configuration error."
                )

                return redirect(
                    "/details/?step=5"
                )

            # ==================================
            # AI GENERATION
            # ==================================

            ai_answer = None

            # Current available models
            models = [
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite"
            ]

            for model_name in models:

                print("--------------------------------")
                print("Trying model:", model_name)

                for attempt in range(2):

                    try:

                        print(
                            "Attempt:",
                            attempt + 1
                        )

                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt
                        )

                        if response and response.text:

                            ai_answer = response.text

                            print(
                                "SUCCESS:",
                                model_name
                            )

                            break

                    except Exception as e:

                        error_text = str(e)

                        print(
                            "FAILED:",
                            model_name
                        )

                        print(
                            "ERROR:",
                            error_text
                        )

                        # 503 = temporary service overload
                        if "503" in error_text:

                            if attempt == 0:

                                print(
                                    "503 received. Waiting 3 seconds..."
                                )

                                time.sleep(3)

                            continue

                        # 429 = rate limit
                        elif "429" in error_text:

                            print(
                                "429 rate limit received."
                            )

                            time.sleep(5)

                            continue

                        # Other errors
                        else:

                            print(
                                "Non-retryable error."
                            )

                            break

                # If successful, stop trying other models
                if ai_answer:

                    break

            # ==================================
            # IF ALL MODELS FAILED
            # ==================================

            if not ai_answer:

                print("--------------------------------")
                print("ALL GEMINI MODELS FAILED")
                print("--------------------------------")

                messages.error(
                    request,
                    "AI service is temporarily unavailable. Please try again after a moment."
                )

                return redirect(
                    "/details/?step=5"
                )

            # ==================================
            # SAVE AI ANSWER
            # ==================================

            request.session["ai_answer"] = ai_answer

            # Make sure session is saved
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
    return redirect('/signin/')