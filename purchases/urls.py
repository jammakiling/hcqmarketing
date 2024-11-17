from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('purchases/', views.purchase_index, name='purchase_index'),
    path('add/', views.add_purchase, name='add_purchase'),
    path('change_status/<int:id>/', views.change_purchase_status, name='change_purchase_status'),
]