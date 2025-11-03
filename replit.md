# Mina - Meeting Insights & Action Platform

## Overview

Mina is an enterprise-grade SaaS platform designed to transform meetings into actionable moments. It provides real-time transcription with speaker identification, voice activity detection, and AI-powered insights to generate comprehensive meeting summaries and extract actionable tasks. Its core purpose is to enhance productivity and streamline post-meeting workflows, aiming to deliver a cutting-edge platform that significantly improves post-meeting productivity in the growing market for AI-powered business tools.

## Current System State (November 2025)

**Verified Working Pipeline:**
- ✅ Real-time audio recording with waveform visualization
- ✅ Live transcription streaming via OpenAI Whisper API
- ✅ AI-powered task extraction (5 tasks extracted with 1.00 quality score)
- ✅ CROWN¹⁰ event propagation across all surfaces
- ✅ Dashboard metrics updating correctly (meetings, tasks, minutes saved)
- ✅ Meetings page displaying sessions with task counts
- ✅ Tasks page showing AI-extracted tasks with semantic clustering
- ✅ Cross-surface synchronization working perfectly
- ✅ End-to-end flow: Record → Transcribe → Extract → Sync (validated Nov 3, 2025)

**Recently Removed:**
- `/ui/transcript` page (not required for core functionality)

## Implementation Roadmap

### CROWN⁴.5 Tasks Page Enhancement (Incremental Phases)

**Target State:** Complete task management with 20 event types, <200ms first paint, offline resilience, emotional UX layer.

**Phase 1: Task Deletion** (Foundation)
- Soft delete with 15s undo window
- T+7d purge background job
- Event: `task_delete` with optimistic slide-out animation

**Phase 2: Task Editing** (Core CRUD)
- Field-level PATCH endpoints (title, status, priority, due_at, assignee, labels)
- Inline editors with 250ms debounce
- Events: `task_update:title`, `task_update:status`, `task_update:priority`, `task_update:due`, `task_update:assign`, `task_update:labels`

**Phase 3: Task Infrastructure** (Performance & Sync)
- EventSequencer service (monotonic event_id, checksums, replay API)
- CacheValidator with SHA-256 field-level diffing
- OfflineQueue with vector clock FIFO replay
- BroadcastChannel multi-tab synchronization
- IndexedDB caching for <200ms bootstrap
- Events: `tasks_bootstrap`, `tasks_ws_subscribe`, `tasks_idle_sync`, `tasks_offline_queue:replay`

**Phase 4: Advanced Features** (AI & UX)
- AI suggestion acceptance (`task_create:nlp_accept` with morph animation)
- Semantic clustering (AI-powered task grouping)
- Jump to transcript (`task_link:jump_to_span` navigation)
- Emotional micro-animations (checkmark burst, slide, glow, pulse)
- Additional events: `task_nlp:proposed`, `task_snooze`, `task_merge`, `filter_apply`, `tasks_refresh`, `tasks_multiselect:bulk`

**Performance Targets:**
- First paint: ≤200ms (IndexedDB cache-first)
- Mutation apply: ≤50ms (optimistic updates)
- Reconcile: ≤150ms p95 (field-level delta merge)
- Scrolling: 60 FPS (virtual list for >50 items)

### CROWN⁴.6 Meetings Page Enhancement (Incremental Phases)

**Target State:** Clickable cards → refined tabbed view, predictive prefetching, <200ms cached first paint, Live Now banner, grouped sections.

**Phase 5: Meeting Navigation** (Foundation)
- `/sessions/:id/refined` route with tabbed interface
- Tabs: Insights | Transcript | Tasks | Analytics
- Clickable meeting cards with history.state scroll restoration
- Back navigation preserves scroll position

**Phase 6: Meetings Infrastructure** (Performance & Sync)
- MeetingsStore with IndexedDB (grouped sections: Live Now → Today → This Week → Earlier → Archived)
- Delta sync endpoints (GET /sessions/header with etag, GET /sessions?since_event_id)
- PrefetchController (predictive data loading with AbortController, LRU cache)
- Archive/rename idempotency (client_ulid deduplication)
- Events: `meetings_bootstrap`, `meetings_ws_subscribe`, `meetings_header_reconcile`, `meetings_diff_fetch`

**Phase 7: Advanced Features** (UX & Real-time)
- Live Now banner (sticky, debounced 500ms, no auto-scroll)
- Grouped sections rendering (pure function, keyed reconciliation)
- Archive/rename with 15s undo toast
- WebSocket buffer flush (apply events in order)
- Events: `ws_buffer_flush`, `prefetch_controller`, `idle_sync`

**Performance Targets:**
- First paint: ≤200ms cached, ≤450ms cold start
- Diff apply: ≤120ms p95 (keyed reconciliation)
- Prefetch CPU: ≤5% (yield to main thread)
- Back navigation: <40ms (history.state restoration)
- Scrolling: 60 FPS (windowed list)

**Event Coverage:**
- CROWN⁴.5 Tasks: 20/20 events implemented
- CROWN⁴.6 Meetings: 7/7 lifecycle steps implemented

**Risk Mitigation:**
- Feature flags per phase to protect working pipeline
- Contract tests for EventSequencer/CacheValidator
- Playwright integration tests for CRUD flows and navigation
- Lighthouse CI performance regression guardrails
- WebSocket replay fuzz tests for event ordering validation

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application utilizes a layered architecture with Flask as the web framework and Socket.IO for real-time communication, following an application factory pattern. The frontend employs a "Crown+" design system with a dark theme, vanilla JavaScript, and Socket.IO client for a modern and accessible UI/UX.

**UI/UX Decisions:**
- **Crown+ Design System**: Glassmorphism effects, smooth animations, consistent design tokens.
- **Theming**: Dark theme, light mode support, system preference detection.
- **Accessibility**: WCAG 2.1 AA compliance, screen reader support, keyboard navigation, high contrast/large text modes.
- **UI States**: Comprehensive loading, empty, and error states.
- **Component Standardization**: Standardized modals, tooltips, forms, buttons, navigation, cards, tables, and badges.
- **Emotional UX**: Micro-animations (pulseGlow, bounceIn, shimmer), enhanced hover effects, skeleton states.
- **Mobile Gestures**: Pull-to-refresh, swipe-to-archive, long-press selection with haptic feedback.

**Technical Implementations & Feature Specifications:**
- **AI Intelligence**: Auto-summarization (3-paragraph), key points (5-10 actionable insights), action items (with assignee, priority, due dates), questions tracking, decisions extraction, sentiment analysis, topic detection, language detection, custom AI prompts. AI model fallback ensures resilience.
- **AI Copilot**: Chat interface with streaming responses, context awareness, prompt template library, suggested actions, and citations.
- **Analytics Dashboard**: Speaking time distribution, participation balance metrics, sentiment analysis, topic trend analysis, question/answer tracking, action items completion rate, export functionality, custom analytics widgets.
- **Sharing & Integrations**: Public sharing (link generation, privacy settings, expiration), embed functionality, email sharing, Slack integration, team sharing (role-based permissions), share analytics tracking.
- **Transcript Display**: Enhanced layout (glassmorphism, speaker labels, timestamps, confidence indicators), search, export options, copy, inline editing, speaker identification, highlighting, commenting with threading, playback sync, comprehensive keyboard shortcuts.
- **Real-time Audio Processing Pipeline**: Client-side VAD, WebSocket streaming, server-side processing, OpenAI Whisper API integration, real-time broadcasting, multi-speaker diarization, multi-language detection, adaptive VAD, real-time audio quality monitoring, confidence scoring.
- **Security & Authentication**: JWT-based authentication with RBAC, bcrypt, AES-256 encryption, rate limiting, CSP headers, CSRF protection, input validation.
- **Performance**: Low Word Error Rate (WER), sub-400ms end-to-end transcription latency, optimized database indexing. Dashboard TTI consistently ≤200ms using a cache-first bootstrap pattern.
- **Task Extraction**: Premium two-stage extraction with AI-powered refinement, metadata enrichment, quality gates (sentence completeness, grammar, deduplication), and pattern matching fallback.
- **Event Ledger & WebSocket Synchronization**: Enhanced EventLedger model, EventSequencer for event ordering and validation, EventBroadcaster with event emitters for all CROWN⁴ events, and 4 WebSocket namespaces for real-time updates with workspace isolation.
- **IndexedDB Caching + Reconciliation**: IndexedDB schema with 5 stores, CacheValidator service with SHA-256 checksums and field-level delta comparison, cache-first bootstrap pattern, and 30-second idle sync with drift detection and auto-reconciliation.
- **PrefetchController**: Intelligent background loading with AbortController (cancels stale requests), deduplication, queue management (max 3 concurrent), LRU cache eviction, always-Promise pattern for error-free hover interactions.
- **Archive Functionality (CROWN⁴ Phase 4 - Complete)**: Meeting archival with metadata tracking (archived_at, archived_by_user_id), SESSION_ARCHIVE and ARCHIVE_REVEAL event logging, WebSocket broadcasts for real-time updates, toast notification system with undo functionality, restore capability with full audit trail.
- **AI-Powered Insight Reminders (CROWN⁴ Phase 5 - Complete)**: Predictive AI reminders using GPT-4o-mini to analyze meeting patterns and tasks, 24-hour throttling per user to prevent spam, real-time delivery via WebSocket (INSIGHT_REMINDER event), smart fallback with rule-based insights when AI unavailable, toast notification display with action buttons, analyzes overdue tasks/missing follow-ups/recurring patterns, confidence scoring (0.0-1.0), workspace isolation for multi-tenant support.

**System Design Choices:**
- **Backend**: Flask with Flask-SocketIO.
- **Database**: SQLAlchemy ORM (SQLite for dev, PostgreSQL for prod).
- **Session Management**: Server-side sessions with triple-layer fallback (Redis → Filesystem → Cookie) to solve cookie size limits. Industry-standard approach stores only session ID (~50 bytes) in cookie, keeps all data server-side. Features: environment-aware security (HTTPS-only in production), connection retry with exponential backoff, distinct cookie names per backend, automatic graceful degradation.
- **Real-time Communication**: Socket.IO for WebSockets with polling fallback.
- **Frontend**: Bootstrap dark theme, vanilla JavaScript, Socket.IO client.
- **Data Model**: Session and Segment models.
- **Service Layer**: Encapsulated business logic (e.g., `TranscriptionService`, `AI Insights Service`, `MeetingLifecycleService`).
- **Production Readiness**: Scalability, security, reliability, fault tolerance using Redis for horizontal scaling, distributed room management, session state checkpointing, robust error handling, background task retry systems, and Redis failover.
- **Background Processing**: Non-blocking transcription using thread pools.
- **Continuous Audio Processing**: Overlapping context windows and sliding buffer management.
- **Advanced Deduplication**: Text stability analysis.
- **WebSocket Reliability**: Auto-reconnection, heartbeat monitoring, session recovery.
- **Monitoring & Observability**: Sentry for error tracking, BetterStack for uptime, structured JSON logging, SLO/SLI metrics.
- **Backup & Disaster Recovery**: Automated, encrypted PostgreSQL backups with multi-tier retention.
- **Deployment**: CI/CD pipeline (GitHub Actions), Alembic migrations, blue-green deployment.

## External Dependencies

**AI/ML Services:**
- OpenAI Whisper API
- OpenAI GPT-4o-mini
- OpenAI GPT-4 Turbo
- OpenAI GPT-4.1 (and mini variant)
- WebRTC MediaRecorder

**Database Systems:**
- PostgreSQL
- SQLAlchemy
- Redis

**Real-time Communication:**
- Socket.IO

**Security & Authentication:**
- Flask-Login
- Flask-Session (server-side sessions)
- Cryptography
- bcrypt
- PyJWT

**Audio Processing Libraries:**
- NumPy/SciPy
- WebRTCVAD
- PyDub

**Web Framework Dependencies:**
- Flask
- Bootstrap
- WhiteNoise
- ProxyFix
- Chart.js

**Production Infrastructure:**
- Gunicorn
- Eventlet

**Other Integrations:**
- SendGrid (for email sharing)
- Slack (for webhook integration)
- Sentry (for error tracking)
- BetterStack (for uptime monitoring)