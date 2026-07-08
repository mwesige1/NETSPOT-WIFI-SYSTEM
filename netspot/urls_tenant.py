from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/',    auth_views.LoginView.as_view(template_name='tenants/login.html'), name='login'),
    path('logout/',   auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('',          include('portal.urls', namespace='portal')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('network/',  include('network.urls', namespace='network')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
]