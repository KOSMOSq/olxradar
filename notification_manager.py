import os
import html
import requests
import logging
from dotenv import load_dotenv
from utils import translate_text
import logging_config

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


class Messenger():
    """Class used to group the notification sending methods."""

    @staticmethod
    def generate_ad_message(ad: dict) -> str:
        """
        Generates the text of a Telegram notification for a single new ad.

        Args:
            ad (dict): A dictionary containing details about
            the ad - title, description, price and URL.

        Returns:
            str: The full text of the notification for this ad.
        """
        title = html.escape(ad["title"].strip())
        description = ad["description"].strip()[:150]
        translated = translate_text(description)
        if translated is None:
            translated = f"{description} (не удалось перевести)"
        description = html.escape(translated)
        price = html.escape(ad["price"].strip())
        if ad["source"] == "vinted":
            site = "Vinted"
            condition = html.escape(ad["status"])
            price_line = f"💰 {price} ({condition})" if condition else f"💰 {price}"
        else:
            site = "OLX"
            price_status = "торг уместен" if ad["is_negotiable"] else "цена окончательная"
            price_line = f"💰 {price} ({price_status})"
        url = ad["url"]

        description_block = f"📝 {description}...\n\n" if description else ""
        return (
            f"🛍 {site}\n\n"
            f"🔍 <b>{title}</b>\n\n"
            f"{price_line}\n\n"
            f"{description_block}"
            f"🔗 {url}"
        )

    @staticmethod
    def send_telegram_message(message: str) -> None:
        """
        Send a single message via Telegram.

        Args:
            message (str): Text of the message to be sent.

        Returns:
            None

        Raises:
            requests.exceptions.RequestException: In case an error is generated during the transmission.
        """
        endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        params = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            if response.json()["ok"]:
                logging.info("Telegram notification sent successfully")
            else:
                logging.error("Error sending Telegram notification")
        except requests.exceptions.RequestException as error:
            logging.error(f"Telegram connection error: {error}")

    @staticmethod
    def _get_telegram_bot_chats() -> list:
        """
        Helper function to get the details of all the chats in which
        a bot is participating.

        Returns:
            chats (list[dict]): A unique list of dictionaries, each continaing the details of
            a chat. For a private chat, the details are: 'id', 'type', 'first_name', 'last_name',
            'username'. For a group chat, the details are: 'id', 'type', 'title',
            'all_members_are_administrators'. In case of an error, it returns an emtpy list.
        """
        endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        try:
            response = requests.get(endpoint)
            response.raise_for_status()
            data = response.json()
            results = data.get("result", [])
            chats = []
            for result in results:
                chat = result.get("message", {}).get("chat")
                if chat not in chats:
                    chats.append(chat)
            return chats
        except requests.exceptions.RequestException as error:
            logging.error(f"Error getting Telegram bot chat data: {error}")
            return []
