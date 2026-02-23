"""Tests for intent classifier utilities."""

from src.agents.nodes.classifier import (
    extract_amount,
    extract_email,
    extract_order_number,
)


class TestExtractOrderNumber:
    """Tests for order number extraction."""

    def test_with_hash(self):
        assert extract_order_number("Where is order #1234?") == "1234"

    def test_without_hash(self):
        assert extract_order_number("Order 1234 status") == "1234"

    def test_with_order_prefix(self):
        assert extract_order_number("I placed order #5678 last week") == "5678"

    def test_order_number_colon(self):
        assert extract_order_number("Order number: 9999") == "9999"

    def test_no_order_number(self):
        assert extract_order_number("Where is my package?") is None

    def test_short_number_ignored(self):
        # Numbers less than 4 digits should be ignored
        assert extract_order_number("I ordered 3 items") is None

    def test_long_order_number(self):
        assert extract_order_number("Order #123456789") == "123456789"


class TestExtractEmail:
    """Tests for email extraction."""

    def test_simple_email(self):
        assert extract_email("My email is test@example.com") == "test@example.com"

    def test_email_with_plus(self):
        assert extract_email("Contact me at user+tag@gmail.com") == "user+tag@gmail.com"

    def test_no_email(self):
        assert extract_email("I don't have email access") is None

    def test_multiple_emails(self):
        # Returns first match
        result = extract_email("From a@b.com to c@d.com")
        assert result == "a@b.com"


class TestExtractAmount:
    """Tests for dollar amount extraction."""

    def test_simple_amount(self):
        assert extract_amount("I want a refund of $50") == 50.0

    def test_decimal_amount(self):
        assert extract_amount("The item was $29.99") == 29.99

    def test_no_amount(self):
        assert extract_amount("I want my money back") is None

    def test_multiple_amounts(self):
        # Returns first match
        assert extract_amount("From $10 to $50") == 10.0
