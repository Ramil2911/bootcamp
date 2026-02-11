BOT_NAME = "kp_news"

SPIDER_MODULES = ["kp_news.spiders"]
NEWSPIDER_MODULE = "kp_news.spiders"

ROBOTSTXT_OBEY = True

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 1.0

MAX_ARTICLES = 1000

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000
PLAYWRIGHT_WAIT_UNTIL = "domcontentloaded"
USE_PLAYWRIGHT_REQUESTS = True

ITEM_PIPELINES = {
    "kp_news.pipelines.ValidationAndNormalizePipeline": 100,
    "kp_news.pipelines.PhotoDownloaderPipeline": 200,
    "kp_news.pipelines.MongoPipeline": 300,
}

MONGO_URI = "mongodb://localhost:27017"
MONGO_DATABASE = "kp_news"
MONGO_COLLECTION = "articles"

PHOTO_DOWNLOAD_TIMEOUT_SECONDS = 8
PHOTO_DOWNLOAD_MAX_BYTES = 5_000_000

FEED_EXPORT_ENCODING = "utf-8"
