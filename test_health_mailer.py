import json
from io import BytesIO
from unittest import TestCase, mock

import health_mailer


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class HealthMailerTests(TestCase):
    @mock.patch("health_mailer.urllib.request.urlopen")
    def test_fetch_count_reads_nested_list(self, urlopen):
        payload = {"data": {"articles": [{"id": 1}, {"id": 2}]}}
        urlopen.return_value = FakeResponse(json.dumps(payload).encode())
        self.assertEqual(
            health_mailer.fetch_count("https://example.com", ("data", "articles")),
            2,
        )

    @mock.patch("health_mailer.fetch_count", side_effect=OSError("offline"))
    def test_check_source_reports_failure_without_secret_details(self, _fetch):
        line, healthy = health_mailer.check_source(
            "测试来源", "https://example.com", ("data", "items")
        )
        self.assertFalse(healthy)
        self.assertEqual(line, "测试来源：异常（OSError）")

    @mock.patch("health_mailer.send_report")
    @mock.patch("health_mailer.state_summary", return_value="历史记录：正常")
    @mock.patch("health_mailer.check_source")
    def test_main_sends_healthy_summary(self, check_source, _state, send_report):
        check_source.side_effect = [
            ("官方新币公告：正常（本次读取 20 条）", True),
            ("币安华语广场：正常（本次读取 15 条）", True),
        ]
        health_mailer.main()
        body, healthy = send_report.call_args.args
        self.assertTrue(healthy)
        self.assertIn("两个数据源均正常", body)


if __name__ == "__main__":
    import unittest

    unittest.main()
