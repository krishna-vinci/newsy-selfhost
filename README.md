## YouTube Workflow App

**Note:** As this is a development preview, everything isn't straightforward, and you should know exactly what you're doing. The intention is to add more features with suggestions and contributions.

**New integration added ntfy for push notifications per category. install ntfy using docker, add url in .env eg url: http://192.168.0.101:3000/feeds-(category_name)**
![2025-03-22 13 27 54](https://github.com/user-attachments/assets/d604da5c-092a-4003-8ac6-e1faf67a9e7c)


This application aggregates content from various sources, processes articles, and provides an interactive interface for managing projects and media. It combines a powerful FastAPI backend with a modern, dynamic frontend built using HTMX, Tailwind CSS, and Alpine.js.

### Features
![CleanShot 2025-03-18 at 23 43 32@2x](https://github.com/user-attachments/assets/4c82c6be-3613-4ba4-84b8-0cb7a08c5d74)

![CleanShot 2025-03-18 at 23 45 28@2x](https://github.com/user-attachments/assets/85df9fd8-1caf-4920-ba31-efbf063f3ed6)
![CleanShot 2025-03-18 at 23 58 50@2x](https://github.com/user-attachments/assets/91804197-d595-453d-8a85-8dfcfba099e3)
![CleanShot 2025-03-19 at 00 02 48@2x](https://github.com/user-attachments/assets/d6d69b19-bc06-4814-9e43-9238041f4521)

![CleanShot 2025-03-19 at 00 03 31@2x](https://github.com/user-attachments/assets/7144fe16-e437-47da-a9f2-480c5027033b)

![CleanShot 2025-03-19 at 00 08 38@2x](https://github.com/user-attachments/assets/4e547f0f-bce2-40f6-823e-ef8bedb10edc)


#### Content Aggregation & Feeds

- Aggregates content from multiple sources via RSS feeds.
- **Adding Feeds:**
  - Feeds are defined in a JSON-like structure in your `main.py` file (both under `RSS_FEED_URLS` and `FEED_CATEGORIES`). To add a new feed, simply edit these JSON structures with the new feed name and URL.
  - **Sources can be either:**
    - **Direct News Source URLs:** Many news websites provide their own RSS feeds.
    - **RSS Aggregator Apps:** Tools like Inoreader can help generate RSS URLs for sites that don’t natively offer them.

#### Article Processing

- Extracts full article content using Newspaper3k.
- Converts HTML articles to Markdown for cleaner display.
- Provides endpoints for both full-text (Markdown) and full HTML articles.

#### Daily Reporting

- Automatically compiles and appends daily reports (in Markdown) from newly aggregated articles.
- Prevents duplicate entries by checking the report file before appending.

#### Project Management

- Organize content by creating projects.
- Save articles with rich Markdown formatting directly to a project.
- (articles get uppended to md file in the project you add article)
- Upload additional files and integrate with Metube for video management.

#### Image/Video Integration

- Integrates with Pixabay to search and download images or videos for your projects.

#### Interactive Frontend

- Utilizes HTMX for dynamic content loading and modal interactions.
- Responsive design with Tailwind CSS and Alpine.js.
- Multiple views (card, headline, and column) for an enhanced user experience.

#### Scheduled Updates

- Uses APScheduler to refresh RSS feeds and update the database every 5 minutes.

#### Containerized Deployment

- Fully containerized using Docker Compose, ensuring easy deployment and reproducibility.
- Uses environment variables (via a `.env` file) to configure every crucial aspect of the app.

#### Configuration Management

- All settings (paths, API keys, URLs, and database credentials) are stored in a `.env` file and accessed via a dedicated `config.py` module.
- This makes it easy to run the app on any device or environment.

#### External Integrations

- **RSS Bridge:** Retrieves feeds in a consistent format.
- **Metube:** Provides a video hosting/control interface.
- **Pixabay:** Searches and downloads media for projects.

### Prerequisites

Before installing the app, ensure you have the following installed and set up:

1. **Docker & Docker Compose**
   - Install Docker and Docker Compose.
2. **RSS Bridge**
   - Deploy an instance of RSS Bridge accessible at the URL defined in your `.env` file (e.g., `192.168.0.122:3333`).
3. **Metube**
   - Deploy or install Metube (or your equivalent video management tool) and ensure it’s accessible as defined in your `.env` file (e.g., `http://192.168.0.114:8081`).
4. **.env File**
   - Create a `.env` file in the project root based on the provided `.env.example` file. Update the configuration values as needed.

### Installation Instructions

#### Clone the Repository

```bash
git clone https://github.com/krishna-vinci/youtube.git
cd youtube
```

#### Configure Environment Variables

Rename the example file:

```bash
cp .env.example .env
```

Edit the `.env` file to update the following:

- **Database Settings:** `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`, `POSTGRES_HOST_PORT` (all can be default and no need to edit)
- **FastAPI Settings:** `FASTAPI_HOST_PORT` (can be default)
- **Other Services:** `PIXABAY_API_KEY`, `RSSBRIDGE_HOST`, `METUBE_URL`, `NITTER_URL`
- **Paths:** `HOST_YOUTUBE_DATA`, `PROJECTS_ROOT`, `DAILY_REPORT_DIR`

#### Build and Run Containers

```bash
docker compose up --build

```

With the `restart: unless-stopped` policy in place, Docker will automatically restart your containers if they stop unexpectedly.

#### Verify the Setup

Check container logs to ensure that:

- PostgreSQL initializes and uses the named volume (`postgres_data`) to persist data.
- FastAPI starts correctly.

Open your browser and navigate to:

```
http://localhost:<FASTAPI_HOST_PORT>
```

(Replace `<FASTAPI_HOST_PORT>` with the port defined in your `.env` file.)

#### Ensure External Services are Running

Confirm that your RSS Bridge and Metube instances are accessible at the URLs specified in your `.env` file.

### How to Add Feeds

For beginners, here’s how you can add or update feeds:

1. **Locate the Feed Configuration:**

   - Open `main.py` and find the JSON-like dictionaries for feeds: `RSS_FEED_URLS` and `FEED_CATEGORIES`.

2. **Add a New Feed:**

   - Example: Adding a new Reddit feed:

   ```python
   RSS_FEED_URLS["reddit"].append({
       "name": "r/NewFeed",
       "url": f"http://{Config.RSSBRIDGE_HOST}/?action=display&bridge=RedditBridge&context=single&r=NewFeed&f=&score=&d=hot&search=&frontend=https%3A%2F%2Fold.reddit.com&format=Atom"
   })
   ```

3. **Feed URL Sources:**

   - **Directly from News Sites:** Many news sites offer their own RSS feeds.
   - **Using RSS Apps:** If a site doesn’t offer an RSS feed, you can use apps like Inoreader to generate one. Simply copy the feed URL provided by Inoreader and add it to your configuration.



### test