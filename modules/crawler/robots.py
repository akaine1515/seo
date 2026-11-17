
import requests

from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin


class RobotsManager:
    """
    Manages robots.txt retrieval and crawling permissions.

    Security policy:
    - HTTP 200: Parse robots.txt rules.
    - HTTP 404: No robots.txt file; allow crawling.
    - HTTP 401/403: Deny crawling.
    - Server errors and connection failures: Deny crawling.
    """

    def __init__(
        self,
        base_url,
        user_agent="SEOIntelligenceBot",
        timeout=15
    ):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout

        self.robots_url = urljoin(
            self.base_url + "/",
            "robots.txt"
        )

        self.parser = RobotFileParser()
        self.parser.set_url(self.robots_url)

        self.available = False
        self.allowed = False
        self.status_code = None
        self.error = None

        self._load()

    # -----------------------------------------
    # LOAD ROBOTS.TXT
    # -----------------------------------------

    def _load(self):
        headers = {
            "User-Agent": self.user_agent
        }

        try:
            response = requests.get(
                self.robots_url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )

            self.status_code = response.status_code

            # Robots file does not exist.
            # According to the crawler policy,
            # a 404 means there are no published rules.
            if response.status_code == 404:
                self.available = True
                self.allowed = True

                self.parser.parse([])

                print(
                    "[ROBOTS] robots.txt not found (404). "
                    "Crawling is allowed."
                )

                return

            # Authentication or access denied.
            if response.status_code in (401, 403):
                self.error = (
                    f"robots.txt access denied: "
                    f"HTTP {response.status_code}"
                )

                self.available = False
                self.allowed = False

                print(f"[ROBOTS BLOCKED] {self.error}")
                return

            # Server errors or unexpected HTTP errors.
            if response.status_code >= 400:
                self.error = (
                    f"HTTP error: {response.status_code}"
                )

                self.available = False
                self.allowed = False

                print(f"[ROBOTS ERROR] {self.error}")
                return

            # Parse successful response.
            self.parser.parse(
                response.text.splitlines()
            )

            self.available = True
            self.allowed = True

            print(
                f"[ROBOTS] Successfully loaded: "
                f"{self.robots_url}"
            )

        except requests.exceptions.Timeout:
            self.error = "robots.txt request timed out"
            self.available = False
            self.allowed = False

            print(f"[ROBOTS ERROR] {self.error}")

        except requests.exceptions.RequestException as error:
            self.error = str(error)
            self.available = False
            self.allowed = False

            print(
                f"[ROBOTS ERROR] Could not retrieve "
                f"robots.txt: {error}"
            )

        except Exception as error:
            self.error = str(error)
            self.available = False
            self.allowed = False

            print(f"[ROBOTS ERROR] {error}")

    # -----------------------------------------
    # CHECK CRAWLING PERMISSION
    # -----------------------------------------

    def can_fetch(self, url):
        """
        Check whether the configured crawler
        is allowed to access a specific URL.
        """

        if not self.available or not self.allowed:
            return False

        try:
            return self.parser.can_fetch(
                self.user_agent,
                url
            )

        except Exception as error:
            print(
                f"[ROBOTS CHECK ERROR] {url}: {error}"
            )

            return False

    # -----------------------------------------
    # GET SITEMAP URLS
    # -----------------------------------------

    def get_sitemaps(self):
        """
        Return sitemap URLs declared in robots.txt.
        """

        if not self.available:
            return []

        try:
            return self.parser.site_maps() or []

        except Exception:
            return []

    # -----------------------------------------
    # STATUS INFORMATION
    # -----------------------------------------

    def get_status(self):
        """
        Return robots.txt diagnostic information.
        """

        return {
            "robots_url": self.robots_url,
            "available": self.available,
            "allowed": self.allowed,
            "status_code": self.status_code,
            "error": self.error,
        }
