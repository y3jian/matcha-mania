CREATE TABLE IF NOT EXISTS matcha (
    id INT AUTO_INCREMENT PRIMARY KEY,
    store text NOT NULL,
    product_name text NOT NULL,
    size_grams int NOT NULL,
    price float NOT NULL,
    currency text NOT NULL,
    in_stock boolean NOT NULL,
    url text NOT NULL,
    scraped_at datetime NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matcha_store ON matcha(store, product_name, size_grams, scraped_at);
