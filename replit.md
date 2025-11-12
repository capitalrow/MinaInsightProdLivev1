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
- **Accessibility**: WCAG 2.1 AA compliance, screen reader support, keyboard navigation, high contrast/large text modes.
- **Emotional UX**: Micro-animations and enhanced hover effects.

**Technical Implementations & Feature Specifications:**
- **AI Intelligence**: Auto-summarization, key points, action items (with assignee, priority, due dates), questions tracking, decisions extraction, sentiment analysis, topic detection, language detection, custom AI prompts. AI model fallback ensures resilience.
- **AI Copilot**: Chat interface with streaming responses, context awareness, prompt template library, suggested actions, and citations.
- **Analytics Dashboard**: Speaking time distribution, participation balance metrics, sentiment analysis, topic trend analysis, action items completion rate, export functionality, custom analytics widgets.
- **Sharing & Integrations**: Public sharing (link generation, privacy settings, expiration), embed functionality, email sharing, Slack integration, team sharing (role-based permissions).
- **Transcript Display**: Enhanced layout (glassmorphism, speaker labels, timestamps, confidence indicators), search, export, copy, inline editing, speaker identification, highlighting, commenting, playback sync, and comprehensive keyboard shortcuts.
- **Real-time Audio Processing Pipeline**: Client-side VAD, WebSocket streaming, server-side processing, OpenAI Whisper API integration, real-time broadcasting, multi-speaker diarization, multi-language detection, adaptive VAD, real-time audio quality monitoring, confidence scoring.
- **Security & Authentication**: JWT-based authentication with RBAC, bcrypt, AES-256 encryption, rate limiting, CSP headers, CSRF protection, input validation.
- **Performance**: Low Word Error Rate (WER), sub-400ms end-to-end transcription latency. Dashboard TTI consistently ≤200ms using a cache-first bootstrap pattern.
- **Task Extraction**: Premium two-stage extraction with AI-powered refinement, metadata enrichment, quality gates, and pattern matching fallback.
- **Event Ledger & WebSocket Synchronization**: Enhanced EventLedger model, EventSequencer for event ordering and validation, EventBroadcaster with event emitters for all CROWN⁴ events, and 4 WebSocket namespaces for real-time updates with workspace isolation.
- **IndexedDB Caching + Reconciliation**: IndexedDB schema with 5 stores, CacheValidator service with SHA-256 checksums and field-level delta comparison, cache-first bootstrap pattern, and 30-second idle sync with drift detection and auto-reconciliation.
- **PrefetchController**: Intelligent background loading with AbortController, deduplication, queue management, LRU cache eviction, always-Promise pattern.
- **Archive Functionality**: Meeting archival with metadata tracking, event logging, WebSocket broadcasts for real-time updates, toast notification system with undo functionality, restore capability with full audit trail.
- **AI-Powered Insight Reminders**: Predictive AI reminders using GPT-4o-mini to analyze meeting patterns and tasks, 24-hour throttling per user, real-time delivery via WebSocket, smart fallback with rule-based insights, toast notification display with action buttons, analyzes overdue tasks/missing follow-ups/recurring patterns, confidence scoring, workspace isolation for multi-tenant support.
- **CROWN⁴.5 Tasks Page (Phase 1 Complete)**: Enterprise-grade task management with offline-first architecture, event-sequenced updates, and sub-200ms first paint performance. **Subsystem Infrastructure (Phase 1.1-1.7)**: PredictiveEngine (ML-based smart defaults, /api/tasks/predict endpoint), QuietStateManager (≤3 concurrent animation enforcement with priority queue, 35ms overhead target), Deduper (origin_hash matching, workspace-scoped duplicate detection, TaskMergeUI modal with collapse animations), CognitiveSynchronizer (event-driven learning infrastructure, task:updated listener, telemetry tracking via /api/tasks/predict/learn), TemporalRecoveryEngine (vector clock-based event reordering, gap detection with full resync, /api/tasks/events/recover and /api/tasks/events/validate endpoints, frontend buffering with drift metrics telemetry), LedgerCompactor (daily mutation compression with workspace-scoped admin-only endpoints /api/tasks/ledger/compact and /api/tasks/ledger/status, retention policies 30/90/7 days, CompactionSummary audit trail with workspace isolation, frontend monitoring module with auto-compaction scheduling), **PrefetchController** (adapter-based resource prefetching with task adapter, IntersectionObserver-based visible task warming, workspace-scoped cache keys, write-through to IndexedDB, requestIdleCallback for low-priority background loading, /api/tasks/{id}?detail=mini endpoint for optimized payloads, TaskDetailModal integration for instant modal opens with prefetched data). **UI Components**: TaskCard with Crown+ glassmorphism (36-40px height), inline title editing with optimistic UI + task:updated event emission, status toggle with WebSocket broadcast, priority selector with visual indicators, due date picker with smart parsing, multi-assignee support via junction table (assignee_ids array + TaskAssignee model), task actions menu with 15s undo window using soft delete pattern, bulk operations (select all, bulk complete/archive/delete), **drag-and-drop reordering** with native HTML5 API + GSAP animations + position-based persistence. Pending: Phase 2 event matrix implementation (20 events), Phase 3 emotional UX layer, Phase 4 performance optimization.

**System Design Choices:**
- **Backend**: Flask with Flask-SocketIO.
- **Database**: SQLAlchemy ORM (SQLite for dev, PostgreSQL for prod).
- **Session Management**: Server-side sessions with triple-layer fallback (Redis → Filesystem → Cookie).
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
- Slack
- Sentry
- BetterStack