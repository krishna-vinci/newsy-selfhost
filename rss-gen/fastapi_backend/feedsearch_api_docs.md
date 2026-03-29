# Feedsearch API

An API service for searching websites for RSS, Atom, and JSON feeds.

Feedsearch provides a simple API for searching websites for RSS, Atom, and JSON feeds.

The long-term goal of Feedsearch is to provide a comprehensive, publicly accessible repository of feed information by saving the location and metadata of all crawled feeds.

## API Usage

Make a `GET` request to `https://feedsearch.dev/api/v1/search` with a `url` value in the querystring containing the URL you'd like to search:

```bash
curl -X GET "https://feedsearch.dev/api/v1/search?url=arstechnica.com"
```

*   When the scheme (e.g. `https://`) is not provided in the `url` value, the scheme will default to `http://`.
*   A request URL that contains only the domain and no path (e.g. `http://example.com` or `example.com`) will always return **all previously found feeds** associated with that domain.
*   A request URL that contains a path (e.g. `https://example.com/test`, or `example.com/rss.xml`) will return **only those feeds found from that particular crawl**.
*   An individual feed can be crawled by passing in the full URL to that feed. If you know the specific location of a feed, but that feed doesn't appear in the results for a domain, then please query the feed's specific URL. The API will associate the feed with its root domain, and will then return the feed upon subsequent queries for that domain.

## Query Parameters

The Feedsearch API accepts the following query parameters:

*   **`url`**: The URL to search. Will return 400 Bad Request if not sent.
*   **`info`**: Returns all feed metadata as below. Defaults True. If False, only found URLs are returned, and all other values will be empty or default.
*   **`favicon`**: Returns the favicon as a Data Uri. Defaults False.
*   **`skip_crawl`**: By default, the queried URL will be crawled if it has not been crawled in the past week. Set this value to True if you wish to always skip the crawl and return only saved feeds. Defaults False.
*   **`opml`**: Return the feeds as an OPML XML string. Defaults False.

```bash
curl "https://feedsearch.dev/api/v1/search?url=arstechnica.com&info=true&favicon=false&opml=false&skip_crawl=false"
```

## API Response

The Feedsearch API returns a list of found feeds in JSON format, with attached metadata about the feed.

*   `bozo`: Set to 1 when feed data is not well formed or may not be a feed. Defaults 0.
*   `content_length`: Length of the feed in bytes.
*   `content_type`: Content-Type/Media-Type value of the returned feed.
*   `description`: Feed description.
*   `favicon`: URL of feed or site Favicon
*   `favicon_data_uri`: Data Uri of the Favicon.
*   `hubs`: List of Websub hubs for the feed if available.
*   `is_podcast`: True if the feed contains valid podcast elements and enclosures.
*   `is_push`: True if the feed contains valid Websub data.
*   `item_count`: Number of items in the feed.
*   `last_seen`: Date that the feed was last seen by the crawler.
*   `last_updated`: Date of the latest entry in the feed, at the time the feed was last crawled.
*   `score`: Computed relevance of feed url value to requested search URL. May be safely ignored.
*   `self_url`: The `rel="self"` value returned from feed links. May be different from feed url.
*   `site_name`: Name of the feed's website.
*   `site_url`: URL of the feed's website.
*   `title`: Feed Title.
*   `url`: URL link to the feed.
*   `velocity`: A calculation of the mean number of items per day at the time the feed was fetched.
*   `version`: Detected feed type version (e.g. "rss20", "atom10", "https://jsonfeed.org/version/1").

### Example Response

```json
[
  {
    "bozo": 0,
    "content_length": 82139,
    "content_type": "text/xml; charset=UTF-8",
    "description": "Serving the Technologist for more than a decade. IT news, reviews, and analysis.",
    "favicon": "https://cdn.arstechnica.net/favicon.ico",
    "favicon_data_uri": "data:image/png;base64,AAABAAMAIC...",
    "hubs": [
      "http://pubsubhubbub.appspot.com/"
    ],
    "is_podcast": false,
    "is_push": true,
    "item_count": 20,
    "last_seen": "2019-07-05T19:00:00+00:00",
    "last_updated": "2019-07-05T16:00:30+00:00",
    "score": 27,
    "self_url": "http://feeds.arstechnica.com/arstechnica/index",
    "site_name": "Ars Technica",
    "site_url": "https://arstechnica.com/",
    "title": "Ars Technica",
    "url": "http://feeds.arstechnica.com/arstechnica/index",
    "velocity": 7.827,
    "version": "rss20"
  }
]
```

## Attribution

If you provide results powered by Feedsearch, then you should provide an attribution link that is visible to your user on the search and results page.

```html
<a href="https://feedsearch.dev" title="Feedsearch">powered by Feedsearch</a>
```

## Further Information

Feedsearch extends the Feedsearch-Crawler library (available as a Python package on PyPI), by providing a public API and storing crawl results for public consumption.

Documentation and source code for the crawler can be found at the [Feedsearch-Crawler GitHub repository](https://github.com/DBeath/feedsearch-crawler).

Feedsearch acts as a Web crawler. It only crawls a site in response to a direct request, not as an automated crawler. It's designed to be as selective as possible in which URLs it crawls while looking for feeds, and stores information on crawled paths in order to reduce the load on crawled sites as much as possible. It does not attempt to bypass privacy pages, captchas, or any other anti-crawling measures.

Feedsearch was originally written to power the RSS feed search function at [Auctorial](https://auctorial.com).

If you have any issues with our crawling, or just wish to get in touch, please contact `support@auctorial.com`
