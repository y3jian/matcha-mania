CREATE TABLE IF NOT EXISTS matcha (
    id INT AUTO_INCREMENT PRIMARY KEY,
    store text NOT NULL,
    product_name text NOT NULL,
    size_grams int NOT NULL,
    price float NOT NULL,
    currency text NOT NULL,
    in_stock boolean NOT NULL,
    url text NOT NULL,
    region text,
    scraped_at datetime NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matcha_store ON matcha(store, product_name, size_grams, scraped_at);
CREATE INDEX IF NOT EXISTS idx_matcha_region ON matcha(region, scraped_at);

CREATE TABLE IF NOT EXISTS harvest_seasons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    country text NOT NULL,
    region text NOT NULL,
    flush text NOT NULL,
    flush_rank int NOT NULL,
    window_description text NOT NULL,
    start_month int NOT NULL,
    end_month int NOT NULL,
    quality_tier text NOT NULL,
    used_for_matcha boolean NOT NULL,
    lat float,
    lng float,
    notes text,
    source_url text NOT NULL,
    updated_at datetime NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_harvest_country_region ON harvest_seasons(country, region, flush_rank);
