from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("DELETE FROM django_migrations WHERE app='socialaccount' OR app='account'")
    print("Deleted socialaccount and account from migration history")
