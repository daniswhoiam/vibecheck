// Lightweight mock API server for Phase 9 Playwright testing
// Serves realistic data matching the backend API format
import http from "node:http";

const ENTITIES = [
  { id: 1, name: "Claude", category: "model", created_at: "2024-01-01T00:00:00Z", latest_sentiment: 0.65 },
  { id: 2, name: "GPT-4", category: "model", created_at: "2024-01-01T00:00:00Z", latest_sentiment: 0.45 },
  { id: 3, name: "Cursor", category: "tool", created_at: "2024-01-01T00:00:00Z", latest_sentiment: 0.55 },
];

const TIMESERIES = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.now() - (29 - i) * 86400000).toISOString().split("T")[0],
  sentiment_mean: 0.3 + Math.sin(i / 5) * 0.3,
  post_count: Math.floor(Math.random() * 20) + 5,
  source: ["hn", "reddit", "discourse", "devto"][i % 4],
}));

const RECENT_MENTIONS = [
  { id: 101, title: "Claude is great for coding", source: "Hacker News", url: "https://example.com/1", date: "2024-03-01", sentiment: 0.8 },
  { id: 102, title: "Tried Claude for data analysis", source: "Reddit", url: "https://example.com/2", date: "2024-03-02", sentiment: 0.6 },
  { id: 103, title: "Claude vs GPT comparison", source: "Discourse", url: "https://example.com/3", date: "2024-03-03", sentiment: 0.4 },
  { id: 104, title: "Building apps with Claude API", source: "Dev.to", url: "https://example.com/4", date: "2024-03-04", sentiment: 0.7 },
  { id: 105, title: "Claude performance benchmarks", source: "Hacker News", url: "https://example.com/5", date: "2024-03-05", sentiment: 0.5 },
];

function makeAspects(source) {
  if (source === "discourse") {
    return {
      performance: { mean: null, count: 0 },
      cost: { mean: null, count: 0 },
      reliability: { mean: null, count: 0 },
      ux: { mean: null, count: 0 },
      speed: { mean: null, count: 0 },
      code_quality: { mean: null, count: 0 },
      context_window: { mean: null, count: 0 },
    };
  }
  return {
    performance: { mean: 0.65, count: 12 },
    cost: { mean: -0.30, count: 8 },
    reliability: { mean: 0.40, count: 9 },
    ux: { mean: 0.10, count: 5 },
    speed: { mean: 0.55, count: 11 },
    code_quality: { mean: 0.20, count: 7 },
    context_window: { mean: null, count: 0 },
  };
}

const server = http.createServer((req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Access-Control-Allow-Origin", "*");

  const url = new URL(req.url, "http://localhost:8000");
  const path = url.pathname;

  // GET /entities
  if (path === "/entities" && req.method === "GET") {
    res.end(JSON.stringify(ENTITIES));
    return;
  }

  // GET /entities/:id
  const entityMatch = path.match(/^\/entities\/(\d+)$/);
  if (entityMatch && req.method === "GET") {
    const id = parseInt(entityMatch[1]);
    const entity = ENTITIES.find(e => e.id === id);
    if (!entity) {
      res.writeHead(404);
      res.end(JSON.stringify({ detail: "Not found" }));
      return;
    }
    res.end(JSON.stringify(entity));
    return;
  }

  // GET /entities/:id/timeseries
  const tsMatch = path.match(/^\/entities\/(\d+)\/timeseries$/);
  if (tsMatch && req.method === "GET") {
    res.end(JSON.stringify(TIMESERIES));
    return;
  }

  // GET /entities/:id/mentions
  const mentionsMatch = path.match(/^\/entities\/(\d+)\/mentions$/);
  if (mentionsMatch && req.method === "GET") {
    res.end(JSON.stringify(RECENT_MENTIONS));
    return;
  }

  // GET /entities/:id/aspects
  const aspectsMatch = path.match(/^\/entities\/(\d+)\/aspects$/);
  if (aspectsMatch && req.method === "GET") {
    const id = parseInt(aspectsMatch[1]);
    const source = url.searchParams.get("source");
    const window = url.searchParams.get("window") || "7d";
    res.end(JSON.stringify({
      entity_id: id,
      window,
      source: source || null,
      aspects: makeAspects(source),
    }));
    return;
  }

  // GET /health
  if (path === "/health") {
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ detail: "Not found" }));
});

server.listen(8000, () => {
  console.log("Mock API server running on http://localhost:8000");
});
