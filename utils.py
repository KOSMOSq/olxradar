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


def _translate_google(text: str, source_lang: str, target_lang: str, client: str) -> str:
    """Translates via Google's public web endpoint with the given client id."""
    response = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": client, "sl": source_lang, "tl": target_lang,
                "dt": "t", "q": text},
        timeout=15)
    response.raise_for_status()
    segments = response.json()[0]
    return "".join(segment[0] for segment in segments if segment[0])


def _translate_mymemory(text: str, source_lang: str, target_lang: str) -> str:
    """Translates via the free MyMemory API (a different service, as a fallback)."""
    source = "Autodetect" if source_lang == "auto" else source_lang
    response = requests.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": f"{source}|{target_lang}"},
        timeout=15)
    response.raise_for_status()
    data = response.json()
    if str(data.get("responseStatus")) != "200":
        raise ValueError(f"MyMemory error: {data.get('responseDetails')}")
    return data["responseData"]["translatedText"]


def translate_text(text: str, source_lang: str = "auto", target_lang: str = "ru") -> str:
    """
    Translates text without an API key. Google's free endpoint rate-limits
    (HTTP 429), especially on the shared IPs of CI runners, so several
    providers are tried in turn: Google with two different client ids (each
    has its own quota), then MyMemory.

    Args:
        text (str): text to translate.
        source_lang (str): source language code (default: auto-detect).
        target_lang (str): target language code (default: Russian).

    Returns:
        str or None: the translated text, or None if every provider failed.
        An empty input is returned unchanged.
    """
    if not text:
        return text
    providers = [
        ("google/gtx", lambda: _translate_google(text, source_lang, target_lang, "gtx")),
        ("google/dict-chrome-ex", lambda: _translate_google(text, source_lang, target_lang, "dict-chrome-ex")),
        ("mymemory", lambda: _translate_mymemory(text, source_lang, target_lang)),
    ]
    for name, translate in providers:
        try:
            result = translate()
            if result:
                return result
        except (requests.exceptions.RequestException, ValueError, IndexError, KeyError) as error:
            logging.error(f"Translation error ({name}): {error}")
    return None


def extract_ad_id(url: str) -> tuple:
    """
    Extracts the site-specific ad ID from an ad URL. Both OLX and Vinted put
    the ad title in the URL, which changes whenever the seller edits the
    title, so the ID is the only stable way to recognize the same ad.

    Args:
        url (str): the ad URL.

    Returns:
        tuple or None: ("vinted" | "olx", id), or None if the URL isn't
        a recognized ad URL.
    """
    match = re.search(r"/items/(\d+)", url)
    if match:
        return ("vinted", match.group(1))
    match = re.search(r"-ID([A-Za-z0-9]+)\.html", url)
    if match:
        return ("olx", match.group(1))
    return None


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
