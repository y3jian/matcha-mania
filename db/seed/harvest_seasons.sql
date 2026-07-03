-- Researched matcha/tea harvest-season reference data.
-- Regional flush windows vary year to year with weather; treat start/end months as
-- typical ranges, not fixed dates. Minor/experimental producers (Taiwan, India, US,
-- Australia/NZ) are omitted because no sourced harvest-month data was found for them.
-- lat/lng are representative anchor points for the region (city/county centers, not
-- precise farm boundaries) and are NULL for rows that describe a flush nationwide
-- rather than a specific place.

INSERT INTO harvest_seasons
    (country, region, flush, flush_rank, window_description, start_month, end_month, quality_tier, used_for_matcha, lat, lng, notes, source_url, updated_at)
VALUES
    ('Japan', 'Kagoshima', 'ichibancha (first flush)', 1, 'early April - early May', 4, 5,
        'ceremonial (highest)', TRUE, 31.5966, 130.5571,
        'Warmest major producing region; earliest ichibancha start of the six prefectures. Surpassed Shizuoka as Japan''s top-producing prefecture by volume for the first time since 1991 (2025 harvest).',
        'https://ooika.co/learn/august-2025-matcha-report', '2026-07-03'),

    ('Japan', 'Shizuoka', 'ichibancha (first flush)', 1, 'late April - mid May', 4, 5,
        'ceremonial (highest)', TRUE, 34.9756, 138.3827,
        'Historic #1 producer by volume for 30+ years; 2025 yield fell ~19% year-on-year after low spring temperatures suppressed new-shoot growth.',
        'https://ooika.co/learn/august-2025-matcha-report', '2026-07-03'),

    ('Japan', 'Kyoto (Uji)', 'ichibancha (first flush)', 1, 'late April - early May, centered on the "88th night" (~May 1-2)', 4, 5,
        'ceremonial (premium)', TRUE, 34.8845, 135.7987,
        'Traditional home of tencha/matcha production; longest shading periods typically produce the most prized ceremonial grade. Premium lots are often aged over summer and released in autumn (kuradashi).',
        'https://wakokoro-tea.com/blogs/blog/japans-top-matcha-regions', '2026-07-03'),

    ('Japan', 'Fukuoka (Yame)', 'ichibancha (first flush)', 1, 'late April - mid May', 4, 5,
        'ceremonial (premium)', TRUE, 33.2028, 130.5639,
        'Known for deeply shaded tencha with pronounced umami and toastier notes than Uji.',
        'https://ooika.co/learn/matcha-regions-japan', '2026-07-03'),

    ('Japan', 'Aichi (Nishio)', 'ichibancha (first flush)', 1, 'late April - mid May', 4, 5,
        'ceremonial (premium)', TRUE, 34.8574, 137.0466,
        'Major tencha-specific growing area alongside Uji; much of its crop is grown expressly for matcha rather than leaf tea.',
        'https://ooika.co/learn/matcha-regions-japan', '2026-07-03'),

    ('Japan', 'Saitama', 'ichibancha (first flush)', 1, 'May', 5, 5,
        'ceremonial', TRUE, 35.8617, 139.6455,
        'Northernmost of the major producing prefectures; cooler climate pushes the first flush later than the other five regions. Was the only prefecture with a year-on-year yield increase in 2025.',
        'https://ooika.co/learn/august-2025-matcha-report', '2026-07-03'),

    ('Japan', 'nationwide (general)', 'nibancha (second flush)', 2, 'mid June - early July', 6, 7,
        'culinary (lower grade)', TRUE, NULL, NULL,
        'Stronger, more astringent character than ichibancha. Occasionally ground for lower-grade culinary matcha; more commonly sold as sencha or bancha.',
        'https://www.sugimotousa.com/blog/what-are-the-harvest-seasons-of-japanese-teas-and-how-do-they-affect-quality', '2026-07-03'),

    ('Japan', 'nationwide, southern regions only', 'sanbancha (third flush)', 3, 'late July - mid September', 7, 9,
        'culinary (bulk/bancha)', FALSE, NULL, NULL,
        'Skipped entirely in cooler regions to let plants recover before dormancy; typically processed into bancha or hojicha rather than matcha.',
        'https://www.sugimotousa.com/blog/what-are-the-harvest-seasons-of-japanese-teas-and-how-do-they-affect-quality', '2026-07-03'),

    ('Japan', 'nationwide, southern regions only', 'yonbancha / akibancha (autumn flush)', 4, 'September - November', 9, 11,
        'culinary (lowest grade)', FALSE, NULL, NULL,
        'Final harvest before winter dormancy; lowest quality tier, used for bulk bancha rather than matcha.',
        'https://www.sugimotousa.com/blog/what-are-the-harvest-seasons-of-japanese-teas-and-how-do-they-affect-quality', '2026-07-03'),

    ('China', 'Anhui', 'spring tea (pre-Qingming through pre-summer)', 1, 'mid March - early May, peak in April', 3, 5,
        'culinary / ready-to-drink', TRUE, 29.7147, 118.3376,
        'Largest-volume matcha-style powder producer; mostly culinary and RTD grade rather than shaded ceremonial tencha.',
        'https://en.people.cn/n3/2024/0410/c90000-20155126.html', '2026-07-03'),

    ('China', 'Zhejiang', 'spring tea (pre-Qingming through pre-summer)', 1, 'mid March - early May, peak in April', 3, 5,
        'culinary / ready-to-drink', TRUE, 30.2741, 120.1551,
        'Shares the same spring picking calendar as Anhui; best known for Longjing but also supplies matcha-style powder for culinary use.',
        'https://en.people.cn/n3/2024/0410/c90000-20155126.html', '2026-07-03'),

    ('South Korea', 'Boseong / Jeju / Hadong', 'ujeon (first flush)', 1, 'early-mid April, before Gok-u (~April 20)', 4, 4,
        'premium (culinary-tier)', TRUE, 34.7714, 127.0800,
        'Produced primarily as loose-leaf green tea (nokcha); matcha-style powder is a smaller, culinary-tier niche rather than ceremonial-grade tencha.',
        'https://teajourney.pub/article/harvest-review-south-korea-ujeon-sejak-early-season/', '2026-07-03');
