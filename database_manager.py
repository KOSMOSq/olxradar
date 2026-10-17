import sqlite3
import os
from utils import BASE_DIR


class DatabaseManager():
    """Class responsible for the interactions with the database."""

    def __init__(self) -> None:
        """
        Init a new DB object and create the 'ads' table, if it doesn't exist.
        """
        self.DB = os.path.join(BASE_DIR, "database.db")
        self.conn = sqlite3.connect(self.DB)
        self.cursor = self.conn.cursor()
        sql_create_table = """
            CREATE TABLE IF NOT EXISTS ads (
                id          INTEGER     PRIMARY KEY     AUTOINCREMENT,
                url         TEXT        NOT NULL
            );
            """
        self.cursor.execute(sql_create_table)
        self.cursor.close()
        self.conn.commit()

    def url_exists(self, url: str) -> bool:
        """
        Returns True if an entry with the specified url exists
        in the database, otherwise False.

        Args:
            url (str): the url to check.

        Returns:
            bool: True if an entry with the specified url exists in
            the database, otherwise False.
        """
        self.conn = sqlite3.connect(self.DB)
        self.cursor = self.conn.cursor()
        sql_command = "SELECT url FROM ads WHERE url = ?"
        self.cursor.execute(sql_command, (url,))
        result = self.cursor.fetchone()
        self.cursor.close()
        self.conn.commit()
        self.conn.close()
        if result:
            return True
        return False

    def count_urls_with_prefix(self, prefix: str) -> int:
        """
        Returns how many stored ad URLs start with the given prefix
        (e.g. "https://www.vinted.pl/"), i.e. how many ads from one
        site have already been seen.

        Args:
            prefix (str): the start of the URLs to count.

        Returns:
            int: the number of matching entries.
        """
        self.conn = sqlite3.connect(self.DB)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            "SELECT COUNT(*) FROM ads WHERE url LIKE ?", (prefix + "%",))
        count = self.cursor.fetchone()[0]
        self.cursor.close()
        self.conn.close()
        return count

    def add_url(self, url: str) -> None:
        """
        Adds a new entry with the specified url to the 'ads' table.

        Args:
            url (str): a string representing the URL of the item.

        Returns:
            None
        """
        self.conn = sqlite3.connect(self.DB)
        self.cursor = self.conn.cursor()

        sql = "INSERT INTO ads (url) VALUES(?)"
        self.cursor.execute(sql, (url,))
        self.cursor.close()
        self.conn.commit()
        self.conn.close()
