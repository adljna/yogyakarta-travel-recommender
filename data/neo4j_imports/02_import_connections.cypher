// Load Destination Connections (routes between destinations)
LOAD CSV WITH HEADERS FROM "file:///destination_connections.csv" AS row
MATCH (d1:Destination {destination_id: row.from_destination_id})
MATCH (d2:Destination {destination_id: row.to_destination_id})
MERGE (d1)-[conn:CONNECTED_TO {
  distance_km: toFloat(row.distance_km),
  duration_minutes_car: toInteger(row.duration_minutes_car),
  duration_minutes_bike: row.duration_minutes_bike,
  transport_mode: row.transport_mode
}]->(d2)
RETURN count(*) AS connections_created;
