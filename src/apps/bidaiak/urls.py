from django.http import HttpResponse
from django.urls import path


def index(request):
    return HttpResponse("Bidaiak Subdomain")


urlpatterns = [
    path("", index),
]
