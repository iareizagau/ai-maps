from django.urls import path
from django.http import HttpResponse

def index(request):
    return HttpResponse("Bidaiak Subdomain")

urlpatterns = [
    path('', index),
]
