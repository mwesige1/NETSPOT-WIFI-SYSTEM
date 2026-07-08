from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    path('',                          views.landing,      name='landing'),
    path('signup/',                   views.signup,       name='signup'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
]