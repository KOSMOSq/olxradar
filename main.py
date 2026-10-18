import os
import time
import logging
import logging_config
from multiprocessing import Pool
from urllib.parse import urlparse
from scraper_manager import OlxScraper
from vinted_scraper import VintedScraper
from database_manager import DatabaseManager
from notification_manager import Messenger
from utils import BASE_DIR, parse_price_value

# OLX only: its search URL doesn't filter by price (see main()). Vinted's
# search URL carries its own price filter.
MIN_PRICE = 1500
MAX_PRICE = 1900
EXCLUDED_TITLE_KEYWORDS = ["portal"]

SCRAPERS = {
    "olx.pl": OlxScraper(),
    "vinted.pl": VintedScraper(),
}
db = DatabaseManager()


def get_scraper(target_url: str):
    """
    Returns the scraper that handles the site a URL belongs to,
    or None if the site isn't supported.
    """
    domain = urlparse(target_url).netloc.removeprefix("www.")
    return SCRAPERS.get(domain)


def load_target_urls() -> list:
    """
    Fetch the list of URLs to monitor from the file 'target_urls.txt',
    which is located in the same directory as the script.

    Returns:
        list: list of URLs from which to collect data. If the
        file does not exist, it creates it and returns an empty list.

    """
    file_path = os.path.join(BASE_DIR, "target_urls.txt")
    user_message = f"The file 'target_urls.txt' has been created. Add " \
        + f"in it at least one URL to monitor for new ads. Add 1 URL per line."
    try:
        with open(file_path) as f:
            target_urls = [line.strip() for line in f]
    except FileNotFoundError:
        logging.info(user_message)
        open(file_path, "w").close()
        target_urls = []
    if not target_urls:
        logging.info(user_message)
    return target_urls


def get_new_ads_urls(all_urls: list) -> list:
    """
    Returns a list of new ad URLs (not found in the database). 

    Args:
        all_urls (list): list of URLs to be matched against the database.

    Returns:
        new_urls (list): List of URLs not found in the database.
    """
    new_urls = []
    if all_urls:
        for url in all_urls:
            if not db.url_exists(url):
                new_urls.append(url)
    return new_urls


def get_new_ads_urls_for_url(target_url: str) -> list:
    """
    Extracts ads for a specific URL and filters out previously processed ads.

    Args:
        target_url (str): A string representing the URL for which new ads should be retrieved.

    Returns:
        List[str]: A list of URLs representing new ads retrieved from the monitored URL.
    """

    scraper = get_scraper(target_url)
    if scraper is None:
        logging.error(f"Unsupported site in target URL: {target_url}")
        return []
    try:
        ads_urls = scraper.scrape_ads_urls(target_url)
    except ValueError as error:
        logging.error(error)
        return []
    return get_new_ads_urls(ads_urls)


def main() -> None:
    """
    Main function. Collects and processes ads
    and sends notifications by Telegram.
    """

    target_urls = load_target_urls()
    for target_url in target_urls:
        scraper = get_scraper(target_url)
        if scraper is None:
            logging.error(f"Unsupported site in target URL: {target_url}")
            continue

        # First time a site is monitored: record what is already listed
        # without notifying, so only ads posted from now on are sent.
        site_prefix = f"https://{scraper.netloc}/"
        is_first_run = db.count_urls_with_prefix(site_prefix) == 0

        new_ads_urls = get_new_ads_urls_for_url(target_url)
        if not new_ads_urls:
            continue
        if is_first_run:
            for url in new_ads_urls:
                db.add_url(url)
            continue

        # Process ads in parallel, for increased speed
        with Pool(10) as pool:
            new_ads = pool.map(scraper.get_ad_data, new_ads_urls)
        new_ads = list(filter(None, new_ads))

        for ad in new_ads:
            # The OLX target URL no longer filters by price on OLX's side (an
            # unfiltered, newest-first query may be less affected by
            # backend/index lag), so apply the price range ourselves.
            if ad["source"] == "olx":
                price_value = parse_price_value(ad["price"])
                if price_value is not None and not (MIN_PRICE <= price_value <= MAX_PRICE):
                    continue
            title_lower = ad["title"].lower()
            if any(keyword in title_lower for keyword in EXCLUDED_TITLE_KEYWORDS):
                continue
            message = Messenger.generate_ad_message(ad)
            Messenger.send_telegram_message(message)
            # Avoid hitting Telegram's rate limit when several ads are found at once
            time.sleep(1)

        # Add the processed ads to database
        for url in new_ads_urls:
            db.add_url(url)


if __name__ == "__main__":
    main()
