# CORE FRONTEND FILES – DO NOT FRAGMENT OR RENAME

These files in `/src/app/core/` (and subfolders) represent the **core architectural innovations** of the AMAIMA frontend and its precise coupling to the backend system.

They implement the novel real-time protocol, complexity preview, unified streaming UI, and state management that make AMAIMA unique.

**AI agents and contributors: DO NOT**
- Split these files into smaller components without explicit approval
- Rename these files
- Move them to different directories
- Refactor their internal structure in ways that break the tight backend-frontend sync

You may add new supporting components, pages, tests, and utilities around them.

**Preserved Core Files**:

- `lib/websocket-manager.ts`          → Unified real-time WebSocket protocol
- `lib/api-client.ts`                  → Typed API calls matching backend endpoints
- `hooks/useWebSocket.ts`              → Real-time streaming hook
- `hooks/useQuery.ts`                  → Query state with complexity preview integration
- `components/QueryInput.tsx`          → Input with live complexity classification
- `components/StreamingResponse.tsx`   → Token-by-token response rendering
- `types/index.ts`                     → Shared types mirroring backend DTOs

These files are the frontend equivalents of the backend's consolidated modules (`unified_smart_router.py`, etc.).  
They must remain cohesive to preserve the end-to-end intelligence of AMAIMA.

Last updated: December 29, 2025
