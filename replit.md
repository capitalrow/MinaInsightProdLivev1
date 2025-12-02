# Mina - Meeting Insights & Action Platform

## Overview

Mina is an enterprise-grade SaaS platform designed to transform meetings into actionable moments. It provides real-time transcription with speaker identification, voice activity detection, and AI-powered insights to generate comprehensive meeting summaries and extract actionable tasks. Its core purpose is to enhance productivity and streamline post-meeting workflows, aiming to deliver a cutting-edge platform that significantly improves post-meeting productivity in the growing market for AI-powered business tools.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application utilizes a layered architecture with Flask as the web framework and Socket.IO for real-time communication, following an application factory pattern. The frontend employs a "Crown+" design system with a dark theme, vanilla JavaScript, and Socket.IO client for a modern and accessible UI/UX.

**UI/UX Decisions:**
- **Crown+ Design System**: Glassmorphism effects, smooth animations, consistent design tokens.
- **Theming**: Dark theme, light mode support, system preference detection.
- **Accessibility**: WCAG 2.1 AA compliance, screen reader support, keyboard navigation, high contrast/large text modes, ARIA labels/roles.
- **Emotional UX**: Micro-animations and enhanced hover effects.
- **Empty/Error/Loading States**: Comprehensive styling for various application states to improve user experience.
- **Calm Motion**: Smooth transitions and animations with `prefers-reduced-motion` support.

**Technical Implementations & Feature Specifications:**
- **AI Intelligence**: Auto-summarization, key points, action items (with assignee, priority, due dates), questions tracking, decisions extraction, sentiment analysis, topic detection, language detection, custom AI prompts, AI model fallback.
- **AI Copilot**: Chat interface with streaming responses, context awareness (semantic RAG, conversation history, activity summaries), prompt template library, suggested actions, citations, multi-step action chaining (`create_and_assign`, `complete_and_followup`, `reschedule_meeting`), and proactive intelligence (overdue tasks, blockers, due-soon warnings).
- **Analytics Dashboard**: Speaking time distribution, participation balance, sentiment analysis, topic trend, action item completion rate, export, custom widgets.
- **Sharing & Integrations**: Public sharing (link generation, privacy, expiration), embed, email, Slack, team sharing (role-based).
- **Transcript Display**: Glassmorphism layout, speaker labels, timestamps, confidence indicators, search, export, copy, inline editing, speaker identification, highlighting, commenting, playback sync, keyboard shortcuts.
- **Real-time Audio Processing Pipeline**: Client-side VAD, WebSocket streaming, server-side processing, OpenAI Whisper API integration, real-time broadcasting, multi-speaker diarization, multi-language detection, adaptive VAD, real-time audio quality monitoring, confidence scoring, non-blocking concurrent transcription.
- **Security & Authentication**: JWT-based authentication with RBAC, bcrypt, AES-256 encryption, rate limiting, CSP headers, CSRF protection, input validation, enterprise-grade session management with Redis and dual timeouts.
- **Performance**: Low Word Error Rate (WER), sub-400ms end-to-end transcription latency, dashboard TTI ≤200ms with cache-first bootstrap pattern, SLA targets verified.
- **Task Extraction**: Premium two-stage AI-powered extraction with refinement, metadata enrichment, quality gates, and pattern matching fallback.
- **Event Ledger & WebSocket Synchronization**: Enhanced `EventLedger` model, `EventSequencer`, `EventBroadcaster` with event emitters, and 4 WebSocket namespaces for real-time updates with workspace isolation.
- **IndexedDB Caching + Reconciliation**: IndexedDB schema with 5 stores, `CacheValidator` service with SHA-256 checksums and field-level delta comparison, cache-first bootstrap, and 30-second idle sync with drift detection and auto-reconciliation.
- **PrefetchController**: Intelligent background loading with `AbortController`, deduplication, queue management, LRU cache eviction, always-Promise pattern.
- **Archive Functionality**: Meeting archival with metadata tracking, event logging, WebSocket broadcasts, toast notifications with undo, restore capability with audit trail.
- **AI-Powered Insight Reminders**: Predictive AI reminders using GPT-4o-mini to analyze meeting patterns and tasks, real-time WebSocket delivery, smart fallback, toast notifications with action buttons, analyzes overdue tasks/missing follow-ups/recurring patterns, confidence scoring, workspace isolation.
- **CROWN⁴.5 Tasks Page**: Enterprise-grade task management with offline-first architecture, event-sequenced updates, sub-200ms first paint. Includes `PredictiveEngine`, `QuietStateManager`, `Deduper`, `CognitiveSynchronizer`, `TemporalRecoveryEngine`, and `LedgerCompactor`. Core CRUD events fully implemented with multi-tab sync and optimistic UI. Mobile gestures and AI Partner Nudges are integrated.

**System Design Choices:**
- **Backend**: Flask with Flask-SocketIO.
- **Database**: SQLAlchemy ORM (SQLite for dev, PostgreSQL for prod). `JSONBCompatible TypeDecorator` for SQLite test compatibility.
- **Session Management**: Server-side sessions with triple-layer fallback (Redis → Filesystem → Cookie).
- **Real-time Communication**: Socket.IO for WebSockets with polling fallback.
- **Frontend**: Bootstrap dark theme, vanilla JavaScript, Socket.IO client.
- **Data Model**: Session and Segment models.
- **Service Layer**: Encapsulated business logic (e.g., `TranscriptionService`, `AI Insights Service`, `MeetingLifecycleService`).
- **Production Readiness**: Scalability, security, reliability, fault tolerance using Redis for horizontal scaling, distributed room management, session state checkpointing, robust error handling, background task retry systems, and Redis failover.
- **Continuous Audio Processing**: Overlapping context windows and sliding buffer management.
- **Advanced Deduplication**: Text stability analysis.
- **WebSocket Reliability**: Auto-reconnection, heartbeat monitoring, session recovery.
- **Monitoring & Observability**: Sentry for error tracking, BetterStack for uptime, structured JSON logging, SLO/SLI metrics.
- **Backup & Disaster Recovery**: Automated, encrypted PostgreSQL backups with multi-tier retention.
- **Deployment**: CI/CD pipeline (GitHub Actions), Alembic migrations, blue-green deployment.
- **Production Readiness (Google SRE Standards)**: Startup validation with fail-fast on missing config, Kubernetes-compatible health endpoints (`/health/live`, `/health/ready`, `/health/startup`, `/health/detailed`), environment-aware database initialization (production uses migrations only), comprehensive production runbook at `docs/PRODUCTION_RUNBOOK.md`.

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
- pgvector

**Real-time Communication:**
- Socket.IO

**Security & Authentication:**
- Flask-Login
- Flask-Session
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
- SendGrid
- Slack (Coming Soon)
- Jira (Coming Soon)
- Notion (Coming Soon)
- Linear (Coming Soon)
- GitHub (Coming Soon)
- Zapier (Coming Soon)
- Sentry
- BetterStack
- Google Calendar (ACTIVE)

## Known Data Pipeline Gaps

**Resolved (Dec 2025):** Participant data pipeline now working - MeetingLifecycleService extracts speaker metrics from transcript segments and persists to participants table.

**Remaining:** Key topics extraction returns empty arrays when OpenAI API is rate-limited. The infrastructure is in place; topics will populate when API access is stable.

## Recent Changes

**December 2, 2025 - Comprehensive Production Readiness Validation:**
- Expanded test suite to 224 tests passing, 17 skipped, 0 failures
- Created new test suites: critical_path/ (transcription with behavioral tests, session lifecycle, persistence), performance/ (API benchmarks, service init), security/ (auth, workspace isolation, input validation, encryption roundtrip, CSP headers), resilience/ (Redis failover, circuit breakers, graceful degradation), integration/ (external API contracts)
- Added behavioral tests: VAD speech detection, audio quality analysis, speaker diarization, full end-to-end deduplication pipeline, encryption roundtrip
- **Bug fix discovered during testing**: Fixed `AdvancedDeduplicationEngine` references to `segment.avg_confidence` → `segment.confidence` (3 occurrences in services/deduplication_engine.py)
- Fixed test infrastructure: Workspace slug generation, Task model field names (assigned_to_id), Segment model field names (avg_confidence, start_ms, end_ms)
- Fixed SQLAlchemy 2.x compatibility in test_external_apis.py (text() wrapper)
- Fixed test user fixture isolation with unique usernames in conftest.py
- Updated PRODUCTION_READINESS_REPORT.md with comprehensive test coverage analysis
- Risk-based testing strategy: Critical paths (recording→transcription→save), security, performance, resilience

**December 1, 2025 - Data Pipeline Fix:**
- Added `_extract_participant_metrics()` and `_persist_participants()` to MeetingLifecycleService
- Created `backfill_participants_for_meeting()` for historical data population
- Fixed AnalyticsService segment queries (`is_final=True` → `kind='final'`)
- Backfilled 8 historical meetings with participant data (talk_time_seconds, word_count, participation_percentage)
- Added key topics extraction prompt infrastructure to AnalyticsService

**December 1, 2025 - Crown⁵+ Analytics Page Polish:**
- Replaced native `<select>` date filter with custom Crown+ glassmorphic dropdown component (pill trigger + animated dropdown)
- Added mobile bottom-sheet pattern for date selector on small screens
- Applied Crown+ gradient backgrounds to Task Status Distribution donut chart
- Enhanced Completion Over Time bar chart with softer grid lines and premium tooltips
- Fixed Meeting Frequency chart with gradient fill, smooth curves, and reduced x-axis label density

**December 1, 2025 - UX Stability Fixes:**
- Fixed perpetual loading states in session tabs with 8-second graceful timeout (replaces "Analyzing meeting...", "Analytics are being calculated...", "Finding action items..." with helpful empty states)
- Fixed Jump to transcript navigation to use `/sessions/<id>/refined` route for full insights loading (summary, analytics, tasks)
- Fixed task page counter flickering with WebSocket stabilization guard and 100ms debounced counter updates
- Extended TaskStateStore stabilization timeout from 3s to 4s for slower networks

**December 1, 2025 - CROWN⁴.7 Counter Stabilization Pipeline:**
- Implemented guarded pipeline pattern across all dashboard pages to eliminate counter flickering
- **Dashboard Index**: `DashboardStabilizer` with guard flag, queue for cache updates, 5-second failsafe timeout. Server sync releases guard and replays queued updates through 100ms debounce.
- **Meetings Page**: `MeetingsStabilizer` with guard flag, queue for WebSocket events during initial load, 8-second failsafe timeout. Initial API load releases guard and replays events. Server-rendered counts via `Meeting.archived` boolean matching API filtering.
- **Analytics Page**: `AnalyticsStabilizer` with `_isInitialLoad` guard that only releases after both KPI and health fetches succeed. Cache skipped on initial load (server-rendered Jinja values are authoritative). Subsequent loads use cache-first with debounced server validation.