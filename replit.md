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
- **States**: Comprehensive styling for empty, error, and loading states.
- **Calm Motion**: Smooth transitions and animations with `prefers-reduced-motion` support.

**Technical Implementations & Feature Specifications:**
- **AI Intelligence**: Auto-summarization, key points, action items (with assignee, priority, due dates), questions tracking, decisions extraction, sentiment analysis, topic detection, language detection, custom AI prompts, AI model fallback.
- **AI Copilot**: Chat interface with streaming responses, context awareness (semantic RAG, conversation history, activity summaries), prompt template library, suggested actions, citations, multi-step action chaining, and proactive intelligence (overdue tasks, blockers, due-soon warnings).
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
- **Phase 3: Low-Latency Transcription Pipeline** (December 2025): Optimized for <2s transcription delivery targeting Otter.ai parity. Features include:
  - `StreamingTranscriptionService` with 2.5s chunk duration, 300ms overlap, 3 parallel workers
  - Direct transcription integration bypassing internal HTTP for reduced latency
  - Tiered usage enforcement: Free (5 hrs/month), Pro (unlimited), Business (unlimited + streaming)
  - Server-side authentication binding for secure tier enforcement (prevents spoofing)
  - Real-time latency metrics via WebSocket (`latency_metrics` event) with P95 tracking
  - `/api/monitoring/transcription-latency` endpoint for SLA monitoring
  - Background AI service prewarm on startup (OpenAI client, local Whisper)
  - Buffer configuration: max_flush 2.5s, min_flush 1.5s for faster delivery

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
- **Production Readiness (Google SRE Standards)**: Startup validation with fail-fast on missing config, Kubernetes-compatible health endpoints, environment-aware database initialization, comprehensive production runbook.

## External Dependencies

**AI/ML Services:**
- OpenAI Whisper API
- OpenAI GPT-4o-mini
- OpenAI GPT-4 Turbo
- OpenAI GPT-4.1
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
- Sentry
- BetterStack
- Google Calendar