from django.urls import path, include

urlpatterns = [
    path('',          include('portal.urls', namespace='portal')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('network/',  include('network.urls', namespace='network')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
]