import unittest
from datetime import datetime, timedelta, timezone

from backend.notification_templates import (
    IN_APP_BODY_LIMIT,
    TELEGRAM_CAPTION_LIMIT,
    TELEGRAM_MESSAGE_LIMIT,
    build_sample_payloads,
    build_telegram_message,
    compose_batch_alert,
    compose_filter_match,
    compose_system_message,
    resolve_telegram_payload,
    telegram_html_to_plain,
    usable_thumbnail,
)


def make_articles(count, prefix="Article"):
    return [
        {"title": f"{prefix} {i}", "link": f"https://example.com/{i}"}
        for i in range(1, count + 1)
    ]


class TelegramComposerTests(unittest.TestCase):
    def test_line_breaks_preserved_as_paragraphs(self):
        message = build_telegram_message(
            "🎯 AI breakthrough",
            "Matched filters: AI\n\nResearchers published a new paper.\n\nSource: The Hindu",
            "https://example.com/a",
            button_url="https://example.com/a",
        )

        self.assertIn("<b>🎯 AI breakthrough</b>", message)
        self.assertIn("Matched filters: AI\n\nResearchers", message)
        self.assertIn("\n\nSource: The Hindu", message)
        # https link rides the inline button, so no duplicated text link
        self.assertNotIn("<a href=", message)

    def test_escapes_html_in_user_content(self):
        message = build_telegram_message(
            'Title with <b>tags</b> & "quotes"',
            "Body with <script>alert(1)</script>",
        )

        self.assertIn(
            "<b>Title with &lt;b&gt;tags&lt;/b&gt; &amp; &quot;quotes&quot;</b>", message
        )
        self.assertIn("Body with &lt;script&gt;alert(1)&lt;/script&gt;", message)
        self.assertNotIn("<script>", message)

    def test_footer_and_publish_label_render_italic(self):
        message = build_telegram_message(
            "T",
            "Body",
            footer="Source: The Hindu",
            published_label="Today at 09:14 PM (IST)",
        )

        self.assertIn("Body\n\n<i>Source: The Hindu</i>", message)
        self.assertIn("<i>Today at 09:14 PM (IST)</i>", message)

    def test_http_link_falls_back_to_text_link_with_button_label(self):
        message = build_telegram_message(
            "T",
            link="http://app.local/feeds?category=tech",
            button_text="Open in newsy",
        )

        self.assertIn(
            '<a href="http://app.local/feeds?category=tech">Open in newsy</a>', message
        )

    def test_relative_article_links_render_as_plain_text(self):
        message = build_telegram_message(
            "T",
            articles=[{"title": "One", "link": "/feeds"}, {"title": "Two"}],
        )

        self.assertIn("1. One", message)
        self.assertIn("2. Two", message)
        self.assertNotIn("<a href=", message)


class FitAwareListTests(unittest.TestCase):
    def test_twenty_short_articles_all_fit_in_text_message(self):
        articles = make_articles(20)
        message = build_telegram_message("S: 20 new articles", articles=articles)

        self.assertIn("20. <a href=", message)
        self.assertIn(">Article 20</a>", message)
        self.assertLessEqual(len(message), TELEGRAM_MESSAGE_LIMIT)

    def test_overflow_marker_and_limits_for_huge_batches(self):
        articles = [
            {"title": f"A very long article title number {i} " + "x" * 120,
             "link": f"https://example.com/{i}/with/a/fairly/long/slug"}
            for i in range(1, 36)
        ]
        message = build_telegram_message("S: 35 new articles", articles=articles)

        self.assertLessEqual(len(message), TELEGRAM_MESSAGE_LIMIT)
        self.assertRegex(message, r"…\+\d+ more")
        self.assertTrue(message.startswith("<b>S: 35 new articles</b>"))

    def test_caption_limit_trims_body_but_keeps_header(self):
        message = build_telegram_message(
            "Header stays",
            "y" * (TELEGRAM_MESSAGE_LIMIT + 1000),
            limit=TELEGRAM_CAPTION_LIMIT,
        )

        self.assertLessEqual(len(message), TELEGRAM_CAPTION_LIMIT)
        self.assertTrue(message.startswith("<b>Header stays</b>"))


class ResolvePayloadTests(unittest.TestCase):
    def test_small_batch_with_thumbnail_uses_photo(self):
        resolved = resolve_telegram_payload(
            "S: 3 new articles",
            link="https://app.example.com/feeds",
            articles=make_articles(3),
            thumbnail_url="https://cdn.example.com/photo.jpg",
        )

        self.assertTrue(resolved["as_photo"])
        self.assertEqual(resolved["thumbnail_url"], "https://cdn.example.com/photo.jpg")
        self.assertLessEqual(len(resolved["text"]), TELEGRAM_CAPTION_LIMIT)

    def test_large_batch_with_thumbnail_falls_back_to_text(self):
        resolved = resolve_telegram_payload(
            "S: 20 new articles",
            link="https://app.example.com/feeds",
            articles=make_articles(20),
            thumbnail_url="https://cdn.example.com/photo.jpg",
        )

        self.assertFalse(resolved["as_photo"])
        self.assertIsNone(resolved["thumbnail_url"])
        self.assertIn(">Article 20</a>", resolved["text"])

    def test_https_link_becomes_inline_button(self):
        resolved = resolve_telegram_payload(
            "T", link="https://example.com/article"
        )

        self.assertEqual(resolved["button_url"], "https://example.com/article")
        self.assertNotIn("<a href=", resolved["text"])

    def test_http_link_stays_a_text_link(self):
        resolved = resolve_telegram_payload(
            "T", link="http://app.local/feeds?category=tech"
        )

        self.assertIsNone(resolved["button_url"])
        self.assertIn(
            '<a href="http://app.local/feeds?category=tech">Open article</a>',
            resolved["text"],
        )


class ComposeTemplateTests(unittest.TestCase):
    def test_batch_sorted_newest_first_and_push_body(self):
        now = datetime.now(timezone.utc)
        composed = compose_batch_alert(
            "TechCrunch",
            [
                {"title": "Older", "link": "https://e.com/1",
                 "published_dt": now - timedelta(hours=2), "published": "Yesterday"},
                {"title": "Newest", "link": "https://e.com/2",
                 "published_dt": now, "published": "Today at 09:00 PM (IST)"},
            ],
            "/feeds?category=tech",
        )

        self.assertEqual(composed["title"], "TechCrunch: 2 new articles")
        self.assertTrue(composed["body"].startswith("1. Newest"))
        self.assertEqual(composed["push_body"], "Latest: Newest")
        self.assertEqual(
            composed["telegram"]["published_label"], "Today at 09:00 PM (IST)"
        )

    def test_batch_in_app_body_lists_titles_with_overflow_marker(self):
        composed = compose_batch_alert(
            "S",
            [
                {"title": f"Article {i} " + "t" * 120, "link": f"https://e.com/{i}"}
                for i in range(1, 21)
            ],
            "/feeds",
        )

        self.assertLessEqual(len(composed["body"]), IN_APP_BODY_LIMIT + 20)
        self.assertIn("1. Article 1", composed["body"])
        self.assertRegex(composed["body"], r"…\+\d+ more")

    def test_batch_overflow_marker_accounts_for_every_article(self):
        composed = compose_batch_alert(
            "S",
            [
                {"title": f"Article {i} " + "t" * 120, "link": f"https://e.com/{i}"}
                for i in range(1, 21)
            ],
            "/feeds",
        )

        lines = composed["body"].split("\n")
        shown = sum(1 for line in lines if line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")) or line[:3].rstrip(".").isdigit())
        marker = next(line for line in lines if line.startswith("…+"))
        hidden = int(marker.split("+")[1].split()[0])

        self.assertEqual(shown + hidden, 20)

    def test_batch_singular_title_for_one_article(self):
        composed = compose_batch_alert(
            "S", [{"title": "Only one", "link": "https://e.com/1"}], "/feeds"
        )

        self.assertEqual(composed["title"], "S: 1 new article")

    def test_filter_match_sections(self):
        composed = compose_filter_match(
            "Chip milestone", "semis, policy", "Excerpt here.", "The Hindu",
            "https://www.thehindu.com/x",
        )

        self.assertEqual(composed["title"], "🎯 Chip milestone")
        self.assertIn(
            "Matched filters: semis, policy\n\nExcerpt here.\n\nSource: The Hindu",
            composed["body"],
        )
        self.assertEqual(composed["telegram"]["button_text"], "Read article")

    def test_system_message_passthrough(self):
        composed = compose_system_message("Connected", "All set.", "/feeds")

        self.assertEqual(composed["kind"], "system")
        self.assertEqual(composed["title"], "Connected")
        self.assertEqual(composed["body"], "All set.")


class SampleAndHelperTests(unittest.TestCase):
    def test_sample_payloads_cover_all_styles(self):
        samples = build_sample_payloads("https://app.example.com/feeds")

        self.assertEqual(
            set(samples), {"batch_alert", "filter_match", "system"}
        )
        for payload in samples.values():
            resolved = resolve_telegram_payload(
                payload["title"],
                payload["body"],
                payload.get("app_link"),
                articles=payload.get("telegram", {}).get("articles"),
                published_label=payload.get("telegram", {}).get("published_label"),
                thumbnail_url=payload.get("telegram", {}).get("thumbnail_url"),
                button_text=payload.get("telegram", {}).get(
                    "button_text", "Open article"
                ),
            )
            self.assertLessEqual(len(resolved["text"]), TELEGRAM_MESSAGE_LIMIT)

    def test_usable_thumbnail_rejects_placeholders_and_relative_urls(self):
        self.assertIsNone(usable_thumbnail(None))
        self.assertIsNone(usable_thumbnail("/static/img.png"))
        self.assertIsNone(
            usable_thumbnail("https://via.placeholder.com/400x300.png?text=No+Image")
        )
        self.assertEqual(
            usable_thumbnail("https://cdn.example.com/photo.jpg"),
            "https://cdn.example.com/photo.jpg",
        )

    def test_html_to_plain_strips_tags_and_unescapes(self):
        plain = telegram_html_to_plain(
            "<b>Title &amp; more</b>\n\n"
            '<a href="https://x.com">Open article</a>'
        )

        self.assertEqual(plain, "Title & more\n\nOpen article")


if __name__ == "__main__":
    unittest.main()
