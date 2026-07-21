from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('',          include('portal.urls', namespace='portal')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('network/',  include('network.urls', namespace='network')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
]



urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)