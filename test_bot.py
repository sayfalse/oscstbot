import unittest
import os
import sys

# Add E:\mint to system path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import (
    is_safe_username,
    is_safe_email,
    is_safe_url,
    is_authorized,
    strip_ansi,
    ALLOWED_USERS
)

class TestMINTBot(unittest.TestCase):

    def test_safe_username(self):
        # Valid usernames
        self.assertTrue(is_safe_username("john_doe"))
        self.assertTrue(is_safe_username("alice.smith"))
        self.assertTrue(is_safe_username("user-name"))
        self.assertTrue(is_safe_username("@elonmusk"))
        
        # Invalid / dangerous usernames
        self.assertFalse(is_safe_username(""))
        self.assertFalse(is_safe_username("john; rm -rf /"))
        self.assertFalse(is_safe_username("john & whoami"))
        self.assertFalse(is_safe_username("john|uname"))
        self.assertFalse(is_safe_username("john`id`"))
        self.assertFalse(is_safe_username("john$((1+1))"))
        self.assertFalse(is_safe_username("john "))

    def test_safe_email(self):
        # Valid emails
        self.assertTrue(is_safe_email("john.doe@example.com"))
        self.assertTrue(is_safe_email("alice+spam@gmail.com"))
        
        # Invalid / dangerous emails
        self.assertFalse(is_safe_email(""))
        self.assertFalse(is_safe_email("john@example.com; rm -rf /"))
        self.assertFalse(is_safe_email("john@example.com & whoami"))
        self.assertFalse(is_safe_email("john@example.com|uname"))
        self.assertFalse(is_safe_email("john@example.com`id`"))
        self.assertFalse(is_safe_email("john@example.com "))

    def test_safe_url(self):
        # Valid URLs
        self.assertTrue(is_safe_url("https://www.instagram.com/safreenzara/"))
        self.assertTrue(is_safe_url("https://tiktok.com/@username/video/12345?query=value&another=1"))
        self.assertTrue(is_safe_url("https://x.com/username"))
        
        # Invalid / dangerous URLs
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url("https://instagram.com/safreenzara/; rm -rf /"))
        self.assertFalse(is_safe_url("https://instagram.com/safreenzara/ & whoami"))
        self.assertFalse(is_safe_url("https://instagram.com/safreenzara/|uname"))
        self.assertFalse(is_safe_url("https://instagram.com/safreenzara/`id`"))
        self.assertFalse(is_safe_url("https://instagram.com/safreenzara/ "))
        self.assertFalse(is_safe_url("https://instagram.com/safreenzara/\""))
        self.assertFalse(is_safe_url("https://instagram.com/safreenzara/'"))
        self.assertFalse(is_safe_url("https://instagram.com/safreenzara/\\"))

    def test_strip_ansi(self):
        colored_text = "\x1b[31mRed Text\x1b[0m and \x1b[32mGreen Text\x1b[0m"
        self.assertEqual(strip_ansi(colored_text), "Red Text and Green Text")

    def test_authorization(self):
        # Temporarily manipulate ALLOWED_USERS for testing
        global ALLOWED_USERS
        
        # Test case 1: Whitelist is empty (public bot)
        original_whitelist = set(ALLOWED_USERS)
        ALLOWED_USERS.clear()
        self.assertTrue(is_authorized(123456))
        self.assertTrue(is_authorized(987654))
        
        # Test case 2: Whitelist has items (private bot)
        ALLOWED_USERS.add(123456)
        self.assertTrue(is_authorized(123456))
        self.assertFalse(is_authorized(987654))
        
        # Restore original whitelist
        ALLOWED_USERS.clear()
        ALLOWED_USERS.update(original_whitelist)

if __name__ == "__main__":
    unittest.main()
