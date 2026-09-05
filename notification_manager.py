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
        description = html.escape(translate_text(description))
        price = html.escape(ad["price"].strip())
        price_status = "торг уместен" if ad["is_negotiable"] else "цена окончательная"
        url = ad["url"]

        return (
            f"🔍 <b>{title}</b>\n\n"
            f"💰 {price} ({price_status})\n\n"
            f"📝 {description}...\n\n"
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
