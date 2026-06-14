// Load Destinations nodes dari CSV
LOAD CSV WITH HEADERS FROM "file:///destinations.csv" AS row
CREATE (d:Destination {
  destination_id: row.destination_id,
  wikidata_id: row.wikidata_id,
  google_place_id: row.google_place_id,
  osm_node_id: row.osm_node_id,
  name: row.name,
  description: row.description,
  category: row.category,
  subcategory: row.subcategory,
  latitude: toFloat(row.latitude),
  longitude: toFloat(row.longitude),
  opening_hours: row.opening_hours,
  estimated_duration_minutes: toInteger(row.estimated_visit_duration_minutes),
  ticket_price_min: toInteger(row.ticket_price_min_idr),
  ticket_price_max: toInteger(row.ticket_price_max_idr),
  currency: row.ticket_currency,
  rating: toFloat(row.rating),
  rating_count: toInteger(row.rating_count),
  rating_source: row.rating_source,
  popularity_score: toFloat(row.popularity_score),
  source: row.source
})
RETURN count(d) AS destinations_created;

// Create Cities dan Provinces dari Destinations
LOAD CSV WITH HEADERS FROM "file:///destinations.csv" AS row
WITH DISTINCT row.city AS city, row.province AS province, row.country AS country
MERGE (c:City {name: city, province: province, country: country})
WITH c, province, country
MERGE (p:Province {name: province, country: country})
MERGE (c)-[:PART_OF]->(p)
RETURN count(DISTINCT c) AS cities_created;

// Link Destinations ke Cities
LOAD CSV WITH HEADERS FROM "file:///destinations.csv" AS row
MATCH (d:Destination {destination_id: row.destination_id})
MATCH (c:City {name: row.city})
MERGE (d)-[:LOCATED_IN]->(c)
RETURN count(*) AS location_links;

// Create Categories
LOAD CSV WITH HEADERS FROM "file:///destinations.csv" AS row
WITH DISTINCT row.category AS cat
MERGE (c:Category {name: cat})
RETURN count(c) AS categories_created;

// Link Destinations to Categories
LOAD CSV WITH HEADERS FROM "file:///destinations.csv" AS row
MATCH (d:Destination {destination_id: row.destination_id})
MATCH (c:Category {name: row.category})
MERGE (d)-[:HAS_CATEGORY]->(c)
RETURN count(*) AS category_links;

// Load Restaurants
LOAD CSV WITH HEADERS FROM "file:///restaurants.csv" AS row
MERGE (r:Restaurant {
  restaurant_id: row.restaurant_id,
  name: row.name,
  cuisine_type: row.cuisine_type,
  halal_status: row.halal_status,
  latitude: toFloat(row.latitude),
  longitude: toFloat(row.longitude),
  opening_hours: row.opening_hours,
  price_level: toInteger(row.price_level),
  rating: toFloat(row.rating),
  rating_count: toInteger(row.rating_count),
  source: row.source
})
RETURN count(r) AS restaurants_created;

// Link Restaurants to Nearby Destinations (hardcoded untuk MVP)
MATCH (r:Restaurant), (d:Destination)
WHERE toFloat(r.latitude) IS NOT NULL 
  AND toFloat(r.longitude) IS NOT NULL
  AND toFloat(d.latitude) IS NOT NULL 
  AND toFloat(d.longitude) IS NOT NULL
WITH r, d, 
  sqrt(
    (toFloat(r.latitude) - toFloat(d.latitude))^2 + 
    (toFloat(r.longitude) - toFloat(d.longitude))^2
  ) AS distance
WHERE distance < 0.05  // approx 5 km
MERGE (r)-[:NEAR {distance_km: distance * 111}]->(d)
RETURN count(*) AS restaurant_links;
