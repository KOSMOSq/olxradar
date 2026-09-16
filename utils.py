import os
import re
import random
import logging
import requests

# Absolute path of the project dir
BASE_DIR = os.path.realpath(os.path.dirname(__file__))


def get_impersonation_target() -> str:
    """
    Returns a randomly chosen browser name for curl_cffi to impersonate
    (matching TLS fingerprint, headers and HTTP/2 settings of a real
    browser), so requests aren't trivially flagged as coming from a
    Python script by OLX's WAF.

    Returns:
        str: a curl_cffi-supported browser impersonation target.
    """
    targets = ["chrome131", "chrome136", "chrome142", "firefox135", "firefox144"]
    return random.choice(targets)


def translate_text(text: str, source_lang: str = "pl", target_lang: str = "ru") -> str:
    """
    Translates text using Google Translate's public web endpoint (the same
    one translate.google.com itself uses), which requires no API key.

    Args:
        text (str): text to translate.
        source_lang (str): source language code (default: Polish).
        target_lang (str): target language code (default: Russian).

    Returns:
        str: the translated text, or the original text if translation fails.
    """
    if not text:
        return text
    endpoint = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": source_lang,
        "tl": target_lang,
        "dt": "t",
        "q": text,
    }
    try:
        response = requests.get(endpoint, params=params, timeout=15)
        response.raise_for_status()
        segments = response.json()[0]
        return "".join(segment[0] for segment in segments if segment[0])
    except (requests.exceptions.RequestException, ValueError, IndexError, KeyError) as error:
        logging.error(f"Translation error: {error}")
        return text


def parse_price_value(price: str) -> int:
    """
    Extracts the numeric value from an OLX price string (e.g. "1 200 zł").

    Args:
        price (str): the price text as scraped from the ad page.

    Returns:
        int or None: the price as an integer, or None if no digits were found.
    """
    digits = re.sub(r"[^\d]", "", price or "")
    return int(digits) if digits else None
