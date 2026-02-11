import re
from urllib.parse import urljoin

import scrapy

from kp_news.items import KpNewsItem


def clean_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split())


def clean_join(values):
    return clean_text(" ".join(v for v in values if clean_text(v)))


class KpRuSpider(scrapy.Spider):
    name = "kp_ru"
    allowed_domains = ["kp.ru", "www.kp.ru"]
    start_urls = ["https://www.kp.ru/online/"]

    custom_settings = {
        "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": None,
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.use_playwright_requests = bool(
            crawler.settings.getbool("USE_PLAYWRIGHT_REQUESTS", True)
        )
        if getattr(spider, "max_articles", None) is None:
            spider.max_articles = int(crawler.settings.getint("MAX_ARTICLES", 1000))
        return spider

    def __init__(self, max_articles=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if max_articles is not None:
            self.max_articles = int(max_articles)
        else:
            self.max_articles = None
        self.collected_links = 0
        self.parsed_articles = 0
        self.seen_links = set()
        self.use_playwright_requests = True

    def _request_meta(self):
        return {"playwright": True} if self.use_playwright_requests else {}

    def _is_article_url(self, url):
        if not url:
            return False
        if not (url.startswith("https://www.kp.ru/") or url.startswith("https://kp.ru/")):
            return False
        if any(part in url for part in ("/video/", "/photo/", "/radio/", "/afisha/")):
            return False
        # News-like URL patterns on kp.ru
        patterns = (
            r"/online/news/\d+/",
            r"/daily/\d{2}\.\d{2}\.\d{4}/\d+\d*/",
            r"/daily/theme/\d+/",
        )
        return any(re.search(pattern, url) for pattern in patterns)

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_online,
                meta=self._request_meta(),
            )

    def parse_online(self, response):
        link_xpaths = [
            "//a[contains(@href, '/daily/')]/@href",
            "//a[contains(@href, '/online/news/')]/@href",
            "//article//a[@href]/@href",
            "//main//a[@href]/@href",
        ]

        links = []
        for xpath in link_xpaths:
            links.extend(response.xpath(xpath).getall())

        for href in links:
            if self.collected_links >= self.max_articles:
                break

            absolute_url = urljoin(response.url, href)
            if not self._is_article_url(absolute_url):
                continue
            if absolute_url in self.seen_links:
                continue

            self.seen_links.add(absolute_url)
            self.collected_links += 1
            yield scrapy.Request(
                url=absolute_url,
                callback=self.parse_article,
                meta=self._request_meta(),
            )

        if self.collected_links < self.max_articles:
            next_page = response.xpath(
                "//a[contains(@class,'pagination') or contains(., 'Следующая')]/@href"
            ).get()
            if next_page:
                yield scrapy.Request(
                    url=urljoin(response.url, next_page),
                    callback=self.parse_online,
                    meta=self._request_meta(),
                )

    def parse_article(self, response):
        self.parsed_articles += 1

        title = clean_text(
            response.xpath(
                "//h1/text() | //meta[@property='og:title']/@content | //title/text()"
            ).get()
        )

        description = clean_text(
            response.xpath(
                "//meta[@name='description']/@content | "
                "//meta[@property='og:description']/@content"
            ).get()
        )

        article_text_nodes = response.xpath(
            "//div[@data-gtm-el='content-body']//p//text() | "
            "//div[contains(@class,'article__text')]//p//text() | "
            "//div[contains(@class,'article-content')]//p//text() | "
            "//article//p//text()"
        ).getall()
        article_text = clean_join(article_text_nodes)

        publication_datetime = clean_text(
            response.xpath(
                "//time/@datetime | "
                "//meta[@property='article:published_time']/@content | "
                "//meta[@name='publish-date']/@content"
            ).get()
        )

        keywords_raw = response.xpath("//meta[@name='keywords']/@content").get()
        keywords = []
        if keywords_raw:
            keywords.extend([k.strip() for k in keywords_raw.split(",") if k.strip()])
        keywords.extend(
            [
                clean_text(v)
                for v in response.xpath(
                    "//a[contains(@href,'/tags/')]/text() | "
                    "//span[contains(@class,'tag')]//text()"
                ).getall()
                if clean_text(v)
            ]
        )
        keywords = list(dict.fromkeys(keywords))

        authors = [
            clean_text(v)
            for v in response.xpath(
                "//a[contains(@href,'/daily/author')]/text() | "
                "//span[contains(@class,'author')]//text() | "
                "//meta[@name='author']/@content"
            ).getall()
            if clean_text(v)
        ]
        authors = list(dict.fromkeys(authors))

        header_photo_url = clean_text(
            response.xpath(
                "//meta[@property='og:image']/@content | "
                "//figure//img/@src | "
                "//img[contains(@class,'article__image')]/@src"
            ).get()
        )
        if header_photo_url and header_photo_url.startswith("/"):
            header_photo_url = urljoin(response.url, header_photo_url)

        item = KpNewsItem(
            title=title,
            description=description,
            article_text=article_text,
            publication_datetime=publication_datetime,
            keywords=keywords,
            authors=authors,
            source_url=response.url,
            header_photo_url=header_photo_url,
            header_photo_base64="",
        )

        # Required fields fallback to avoid empty mandatory values after extraction.
        if not item["description"]:
            item["description"] = item["title"]
        if not item["article_text"]:
            item["article_text"] = item["description"] or item["title"]
        if not item["publication_datetime"]:
            text_dt = clean_text(
                response.xpath(
                    "//*[contains(@class,'date') or contains(@class,'time')]//text()"
                ).get()
            )
            item["publication_datetime"] = text_dt
        if not item["keywords"]:
            slug_parts = [p for p in re.split(r"[/_-]+", response.url) if p]
            item["keywords"] = slug_parts[-3:]
        if not item["authors"]:
            item["authors"] = ["kp.ru"]

        yield item

        # Continue crawling from discovered article links until target count.
        if self.collected_links >= self.max_articles:
            return
        extra_links = response.xpath("//a[@href]/@href").getall()
        for href in extra_links:
            if self.collected_links >= self.max_articles:
                break
            absolute_url = urljoin(response.url, href)
            if not self._is_article_url(absolute_url):
                continue
            if absolute_url in self.seen_links:
                continue
            self.seen_links.add(absolute_url)
            self.collected_links += 1
            yield scrapy.Request(
                url=absolute_url,
                callback=self.parse_article,
                meta=self._request_meta(),
            )
