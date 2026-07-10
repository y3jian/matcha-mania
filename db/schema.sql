CREATE TABLE IF NOT EXISTS matcha (
    id INT AUTO_INCREMENT PRIMARY KEY,
    store text NOT NULL,
    product_name text NOT NULL,
    variant_label text,
    size_grams int NOT NULL,
    price float NOT NULL,
    currency text NOT NULL,
    in_stock boolean NOT NULL,
    url text NOT NULL,
    region text,
    grade text,
    cultivar text,
    scraped_at datetime NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matcha_store ON matcha(store, product_name, size_grams, scraped_at);
CREATE INDEX IF NOT EXISTS idx_matcha_region ON matcha(region, scraped_at);

-- A pantry item is a physical tin you own — independent of what's currently being
-- scraped/tracked (you may own tins from untracked or discontinued products). `url` is an
-- optional link back to a tracked product, used only to seed grade/cultivar/region and to
-- power the "similar matcha" recommender; it is not required and not kept in sync.
CREATE TABLE IF NOT EXISTS pantry_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_name text NOT NULL,
    store text,
    url text,
    size_grams int NOT NULL,
    grade text,
    cultivar text,
    region text,
    acquired_date date NOT NULL,
    opened_date date,
    finished_date date,
    notes text
);

CREATE TABLE IF NOT EXISTS usage_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pantry_item_id INT NOT NULL,
    grams_used float NOT NULL,
    logged_at datetime NOT NULL,
    FOREIGN KEY (pantry_item_id) REFERENCES pantry_items(id)
);

CREATE INDEX IF NOT EXISTS idx_usage_log_item ON usage_log(pantry_item_id, logged_at);

-- Photos live on disk under web/data/photos/ (servable directly as static files); this
-- table only tracks metadata. A visual quality record, chronological per tin and across
-- the whole pantry.
CREATE TABLE IF NOT EXISTS photo_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pantry_item_id INT NOT NULL,
    filename text NOT NULL,
    caption text,
    taken_at datetime NOT NULL,
    FOREIGN KEY (pantry_item_id) REFERENCES pantry_items(id)
);

CREATE INDEX IF NOT EXISTS idx_photo_log_item ON photo_log(pantry_item_id, taken_at);

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
