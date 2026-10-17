import re
import logging
import logging_config
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from utils import get_impersonation_target


class VintedScraper:
    """Class used to scrape data from Vinted Poland."""

    netloc = "www.vinted.pl"
    schema = "https"

    def parse_content(self, target_url: str) -> BeautifulSoup:
        """
        Fetches and parses a page.

        Args:
            target_url (str): the URL to fetch.

        Returns:
            BeautifulSoup or None: the parsed page, or None on error.
        """
        try:
            r = requests.get(
                target_url, impersonate=get_impersonation_target(), timeout=60)
            r.raise_for_status()
        except RequestException as error:
            logging.error(f"Connection error: {error}")
        else:
            return BeautifulSoup(r.text, "html.parser")

    def scrape_ads_urls(self, target_url: str) -> set:
        """
        Collects the ad URLs from the first page of a Vinted catalog search.
        The search URL should be sorted by newest first (order=newest_first),
        so any new ad shows up on that first page.

        Args:
            target_url (str): a vinted.pl catalog search URL.

        Returns:
            set: canonical URLs of the ads on the page.

        Raises:
            ValueError: If the URL doesn't belong to vinted.pl.
        """
        if urlparse(target_url).netloc.removeprefix("www.") != self.netloc.removeprefix("www."):
            raise ValueError(
                f"Bad URL! This scraper is configured to process {self.netloc} links only.")
        parsed_content = self.parse_content(target_url)
        if parsed_content is None:
            return set()
        ads_links = set()
        for card in parsed_content.find_all(attrs={"data-testid": "grid-item"}):
            link = card.find("a", href=re.compile(r"/items/\d+"))
            if link is not None:
                path = urlparse(link["href"]).path
                ads_links.add(f"{self.schema}://{self.netloc}{path}")
        return ads_links

    def get_ad_data(self, ad_url: str) -> dict:
        """
        Extracts data from the page of a Vinted ad.

        Args:
            ad_url (str): the URL of the ad.

        Returns:
            dict or None: the scraped ad data, or None if the title or the
            price couldn't be found.
        """
        logging.info(f"Processing {ad_url}")
        content = self.parse_content(ad_url)
        if content is None:
            return None

        title_el = content.find("h1")
        title = title_el.get_text(strip=True) if title_el else None

        price_el = content.find(attrs={"data-testid": "item-price"})
        price = price_el.get_text(strip=True) if price_el else None

        status_el = content.find(attrs={"data-testid": "item-attributes-status"})
        status = status_el.get_text(strip=True).removeprefix("Stan").strip() if status_el else ""

        description_el = content.find(attrs={"itemprop": "description"})
        description = description_el.get_text(strip=True, separator="\n") if description_el else ""

        if title is None or price is None:
            return None
        return {
            "source": "vinted",
            "title": title,
            "price": price,
            "status": status,
            "url": ad_url,
            "description": description,
        }
