from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.mubil.models import ContactLead


class ContactSubmitTests(TestCase):
    def test_validation_failure(self):
        resp = self.client.post(
            reverse("mubil:contact"),
            data={"name": "", "email": "test@example.com", "message": "Hi"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Necesitamos al menos")
        self.assertEqual(ContactLead.objects.count(), 0)

    @mock.patch("django.core.mail.EmailMessage.send")
    def test_successful_submission_saves_to_db(self, mock_send):
        resp = self.client.post(
            reverse("mubil:contact"),
            data={
                "name": "Test User",
                "email": "test@example.com",
                "entity": "My Company",
                "profile": "flota",
                "message": "Hello, I want to learn more about the platform.",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Test User")  # Rendered thanks message contains name

        # Verify db persistence
        self.assertEqual(ContactLead.objects.count(), 1)
        lead = ContactLead.objects.first()
        self.assertEqual(lead.name, "Test User")
        self.assertEqual(lead.email, "test@example.com")
        self.assertEqual(lead.entity, "My Company")
        self.assertEqual(lead.profile, "flota")
        self.assertEqual(
            lead.message, "Hello, I want to learn more about the platform."
        )

        mock_send.assert_called_once()
