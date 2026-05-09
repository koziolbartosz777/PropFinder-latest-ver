from dotenv import load_dotenv

load_dotenv()

BOT_NAME = "ScraperMieszkan"

SPIDER_MODULES = ["ScraperMieszkan.spiders"]
NEWSPIDER_MODULE = "ScraperMieszkan.spiders"

ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS_PER_DOMAIN = 5

DEFAULT_REQUEST_HEADERS = {
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
}

DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "scrapy_user_agents.middlewares.RandomUserAgentMiddleware": 400,
}

ITEM_PIPELINES = {
    "ScraperMieszkan.pipelines.DatabasePipeline": 300,
}

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 5.0

FEED_EXPORT_ENCODING = "utf-8"
RETRY_ENABLED = True
RETRY_TIMES = 3
