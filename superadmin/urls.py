from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('',                              views.dashboard,        name='dashboard'),
    path('applications/',                 views.applications,     name='applications'),
    path('applications/<int:tenant_id>/approve/', views.approve_tenant, name='approve'),
    path('applications/<int:tenant_id>/reject/',  views.reject_tenant,  name='reject'),
    path('tenants/',                      views.tenant_list,      name='tenant_list'),
    path('withdrawals/',                          views.withdrawal_queue,   name='withdrawal_queue'),
    path('withdrawals/<int:withdrawal_id>/approve/', views.approve_withdrawal, name='approve_withdrawal'),
    path('withdrawals/<int:withdrawal_id>/reject/',  views.reject_withdrawal,  name='reject_withdrawal'),
]