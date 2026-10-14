from django.contrib import admin
from django.urls import path,include
from . import views
from . import api_views

urlpatterns = [
    path("", views.index, name="index"),
    path("careers/", views.index, name="careers"),
    path("schools/", views.schools, name="schools"),
    path("counseling/", views.counseling, name="counseling"),
    path("signup/", views.signup, name="signup"),
    path("signin/", views.signin, name="signin"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("signout/", views.signout, name="signout"),
    path("selection/", views.selection, name="selection"),
    path("student_details/", views.student_details, name="student_details"),
    path("parent_details", views.parent_details, name="parent_details"),
    path("details/", views.details, name="details"),
    path("next/", views.next, name="next"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),

    # REST API Endpoints
    path("api/auth/send-otp/", api_views.api_send_otp, name="api_send_otp"),
    path("api/auth/verify-otp/", api_views.api_verify_otp, name="api_verify_otp"),
    path("api/auth/resend-otp/", api_views.api_resend_otp, name="api_resend_otp"),
]
