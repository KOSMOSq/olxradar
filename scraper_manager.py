import re
import time
import random
import logging
from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
import logging_config
from multiprocessing import Pool
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from bs4 import BeautifulSoup, ResultSet, Tag
from utils import get_impersonation_target


class OlxScraper:
    """Class used to scrape data from OLX Poland."""

    # Text OLX shows when it runs out of ads matching the requested location
    # and starts padding the results with ads from anywhere in the country.
    LOCATION_BOUNDARY_MARKER = "w tej lokalizacji"

    def __init__(self):
        self.netloc = "www.olx.pl"
        self.schema = "https"
        self.current_page = 1
        self.last_page = None
        self.reached_location_boundary = False

    def parse_content(self, target_url: str) -> BeautifulSoup:
        """
        Parse content from a given URL.

        Args:
            target_url (str): A string representing the URL to be processed.

        Returns:
            BeautifulSoup: An object representing the processed content,
            or None in case of error.
        """
        try:
            r = requests.get(
                target_url, impersonate=get_impersonation_target(), timeout=60)
            r.raise_for_status()
        except RequestException as error:
            logging.error(f"Connection error: {error}")
        else:
            parsed_content = BeautifulSoup(r.text, "html.parser")
            return parsed_content

    def get_ads(self, parsed_content: BeautifulSoup) -> ResultSet[Tag]:
        """
        Returns the ads found on the parsed web page that actually match the
        requested location.

        Args:
            parsed_content (BeautifulSoup): a BeautifulSoup object created as
            a result of parsing the web page.

        Returns:
            ResultSet[Tag]: A ResultSet containing the HTML tags of the
            matching ads. If OLX ran out of local results and padded the
            page with ads from other locations, those are excluded and
            self.reached_location_boundary is set to True.
        """
        if parsed_content is None:
            return None
        self.reached_location_boundary = False
        container = parsed_content.find(
            "div", class_="listing-grid-container") or parsed_content
        boundary = container.find(
            "p", string=lambda t: t and self.LOCATION_BOUNDARY_MARKER in t)
        if boundary is None:
            return container.find_all(attrs={"data-testid": "l-card"})
        self.reached_location_boundary = True
        ads = []
        for element in container.descendants:
            if element is boundary:
                break
            if isinstance(element, Tag) and element.get("data-testid") == "l-card":
                ads.append(element)
        return ads

    def get_last_page(self, parsed_content: BeautifulSoup) -> int:
        """
        Returns the number of the last page available for processing.

        Args:
            parsed_content (BeautifulSoup): a BeautifulSoup object created
            as a result of parsing the web page.

        Returns:
            int: The number of the last page available for parsing. If
            there is no paging or the parsed object is None, it will return None.
        """
        if parsed_content is None:
            return None
        pagination = parsed_content.find(attrs={"data-testid": "pagination-wrapper"})
        if pagination is None:
            return None
        page_numbers = []
        for link in pagination.find_all("a", href=True):
            if link.get("data-testid") == "pagination-forward":
                continue
            match = re.search(r"[?&]page=(\d+)", link["href"])
            if match:
                page_numbers.append(int(match.group(1)))
        if page_numbers:
            return max(page_numbers)
        return None

    def scrape_ads_urls(self, target_url: str) -> list:
        """
        Scrapes the URLs of all valid ads present on an OLX page. Search all relevant
        URLs of the ads and adds them to a set. Parses all pages, from first to last.

        Args:
            target_url (str): URL of the OLX page to start the search from.

        Returns:
            list: a list of relevant URLs of the ads found on the page.

        Raises:
            ValueError: If the URL is invalid or does not belong to the specified domain.
        """
        ads_links = set()
        if self._normalize_netloc(urlparse(target_url).netloc) != self._normalize_netloc(self.netloc):
            raise ValueError(
                f"Bad URL! OLXRadar is configured to process {self.netloc} links only.")
        while True:
            url = self.set_page(target_url, self.current_page)
            parsed_content = self.parse_content(url)
            self.last_page = self.get_last_page(parsed_content)
            ads = self.get_ads(parsed_content)
            if ads is None:
                return ads_links
            for ad in ads:
                link = ad.find("a", attrs={"data-testid": "card-title-link"})
                if link is not None and link.has_attr("href"):
                    link_href = link["href"]
                    if not self.is_internal_url(link_href, self.netloc):
                        continue
                    if self.is_relative_url(link_href):
                        link_href = f"{self.schema}://{self.netloc}{link_href}"
                    ads_links.add(self.strip_query(link_href))
            if self.reached_location_boundary:
                break
            if self.last_page is None or self.current_page >= self.last_page:
                break
            self.current_page += 1
            # Small delay between page requests so we don't hammer the server
            time.sleep(random.uniform(1, 2))
        return ads_links

    def _normalize_netloc(self, netloc: str) -> str:
        """Strips a leading 'www.' so 'olx.pl' and 'www.olx.pl' compare equal."""
        return netloc[4:] if netloc.startswith("www.") else netloc

    def set_page(self, target_url: str, page: int) -> str:
        """
        Sets (or overwrites) the "page" query parameter of a target URL,
        preserving any other filters already present in it (e.g. price
        range, category, location, sorting).

        Args:
            target_url (str): the search URL to monitor, with or without
            its own filter query string.
            page (int): the page number to request.

        Returns:
            str: the URL with the "page" parameter set to the given value.
        """
        parsed = urlparse(target_url)
        query_params = parse_qs(parsed.query)
        query_params["page"] = [str(page)]
        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    def strip_query(self, url: str) -> str:
        """
        Removes the query string and fragment from a URL. OLX tags every
        ad link on the search results page with tracking parameters (e.g.
        "?search_reason=search|organic"), so ads must be stripped down to
        their canonical URL before being compared against or stored in
        the database - otherwise the same ad would be treated as "new"
        every time OLX changes the tracking value.

        Args:
            url (str): the URL to clean.

        Returns:
            str: the URL without its query string and fragment.
        """
        return urlparse(url)._replace(query="", fragment="").geturl()

    def is_internal_url(self, url: str, domain: str) -> bool:
        """
        Checks if the URL has the same domain as the page it was taken from.

        Args:
            url (str): the URL to check.
            domain (str): Domain of the current page.

        Returns:
            bool: True if the URL is an internal link, False otherwise.
        """
        # URL starts with "/"
        if self.is_relative_url(url):
            return True
        parsed_url = urlparse(url)
        if self._normalize_netloc(parsed_url.netloc) == self._normalize_netloc(domain):
            return True
        return False

    def is_relative_url(self, url: str) -> bool:
        """
        Check if the given url is relative or absolute.

        Args:
            url (str): url to check.

        Returns:
            True if the url is relative, otherwise False.
        """

        parsed_url = urlparse(url)
        if not parsed_url.netloc:
            return True
        if re.search(r"^\/[\w.\-\/]+", url):
            return True
        return False

    def get_ad_data(self, ad_url: str) -> dict[str]:
        """
        Extracts data from the HTML page of the ad.

        Args:
            ad_url (str): the URL of the ad.

        Returns:
            dict or None: A dictionary containing the scraped ad data
            or None if the required information is missing.
        """
        logging.info(f"Processing {ad_url}")
        content = self.parse_content(ad_url)

        if content is None:
            return None

        title = None
        title_el = content.find(attrs={"data-testid": "offer_title"})
        if title_el:
            title = title_el.get_text(strip=True)

        price = None
        is_negotiable = False
        price_container = content.find(attrs={"data-testid": "ad-price-container"})
        if price_container:
            price_el = price_container.find("h3")
            if price_el:
                price = price_el.get_text(strip=True)
            note_el = price_container.find("p")
            if note_el and "negocjacji" in note_el.get_text(strip=True).lower():
                is_negotiable = True

        description = None
        description_el = content.find(attrs={"data-testid": "ad_description"})
        if description_el:
            heading = description_el.find("h3")
            if heading:
                heading.extract()
            description = description_el.get_text(strip=True, separator="\n")

        if any(item is None for item in [title, price, description]):
            return None
        ad_data = {
            "title": title,
            "price": price,
            "is_negotiable": is_negotiable,
            "url": ad_url,
            "description": description
        }
        return ad_data
