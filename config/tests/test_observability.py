from django.test import TestCase
from django.urls import reverse


class CorrelationIDTests(TestCase):
    def test_response_gets_generated_correlation_id(self):
        response = self.client.get(reverse("home"))
        correlation_id = response.headers["X-Correlation-ID"]

        self.assertTrue(correlation_id)
        self.assertLessEqual(len(correlation_id), 128)

    def test_safe_incoming_correlation_id_is_preserved(self):
        response = self.client.get(
            reverse("home"),
            HTTP_X_CORRELATION_ID="client-request-123",
        )

        self.assertEqual(
            response.headers["X-Correlation-ID"],
            "client-request-123",
        )

    def test_invalid_incoming_correlation_id_is_replaced(self):
        response = self.client.get(
            reverse("home"),
            HTTP_X_CORRELATION_ID="not valid because spaces",
        )

        self.assertNotEqual(
            response.headers["X-Correlation-ID"],
            "not valid because spaces",
        )


class HealthCheckTests(TestCase):
    def test_health_check_exposes_component_status_and_duration(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"]["database"], "ok")
        self.assertEqual(payload["checks"]["storage"], "ok")
        self.assertEqual(payload["checks"]["cache"], "ok")
        self.assertGreaterEqual(payload["duration_ms"], 0)
        self.assertIn("release", payload)


class MetricsTests(TestCase):
    def test_metrics_endpoint_is_exposed(self):
        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["Content-Type"])
        self.assertIn(b"django_http_requests", response.content)

    def test_request_database_query_metric_is_exported(self):
        self.client.get(reverse("health"))
        response = self.client.get("/metrics")

        self.assertIn(b"vorneq_db_queries_total", response.content)
