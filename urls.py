from django.contrib import admin
from django.urls import path,include
from . import views
from django.urls import path
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.index, name="index"),
    path("signup/", views.signup, name="signup"),
    path("signin/", views.signin, name="signin"),
    path("signout/", views.signout, name="signout"),
    path("selection/", views.selection, name="selection"),
    path("student_details/", views.student_details, name="student_details"),
    path("parent_details", views.parent_details, name="parent_details"),
    path("details/", views.details, name="details"),
    path( "next/",views.next,name="next"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),


]
