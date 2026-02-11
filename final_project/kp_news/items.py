import scrapy


class KpNewsItem(scrapy.Item):
    # Required fields
    title = scrapy.Field()
    description = scrapy.Field()
    article_text = scrapy.Field()
    publication_datetime = scrapy.Field()
    keywords = scrapy.Field()
    authors = scrapy.Field()
    source_url = scrapy.Field()

    # Optional fields
    header_photo_url = scrapy.Field()
    header_photo_base64 = scrapy.Field()
