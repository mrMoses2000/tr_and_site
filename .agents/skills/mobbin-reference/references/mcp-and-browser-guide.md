# Mobbin MCP & Browser Reference Guide

---

## 1. Connecting Mobbin MCP
Mobbin provides an official MCP server at:
`https://api.mobbin.com/mcp`

Configuration in `mcp_config.json`:
```json
{
  "mcpServers": {
    "mobbin": {
      "serverUrl": "https://api.mobbin.com/mcp"
    }
  }
}
```

### Authentication Details:
- Mobbin uses Supabase Auth (`https://ujasntkfphywizsdaapi.supabase.co/auth/v1`).
- An active Mobbin Pro or Team account is required for API access.
- When authorizing via browser or bearer token, pass:
  `Authorization: Bearer <MOBBIN_ACCESS_TOKEN>`

## 2. Available Mobbin Tools
- `mobbin_search_screens`: Searches over 600,000+ app screens by keyword, category, platform (iOS, Web), and UI pattern.
- `mobbin_search_flows`: Traces multi-screen user journeys (e.g. signup, onboarding, checkout, upgrade).
- `mobbin_search_sections`: Fetches specific component sections (headers, pricing tables, hero sections).

## 3. Browser-Assisted Research Fallback
If direct MCP credentials are not yet authorized:
1. Use `chrome-devtools` MCP or browser navigation to open Mobbin or target product sites.
2. Capture screenshots using `take_screenshot`.
3. Inspect DOM trees and CSS using `take_snapshot` and `evaluate_script`.
4. Extract color tokens, layout classes, and typographic hierarchy directly from the inspected page.
