# Mina Production Runbook

## Overview

This runbook documents operational procedures for deploying, monitoring, and maintaining Mina in production. It follows Google SRE best practices for production readiness.

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Deployment Procedures](#deployment-procedures)
3. [Health Monitoring](#health-monitoring)
4. [Incident Response](#incident-response)
5. [Rollback Procedures](#rollback-procedures)
6. [Database Operations](#database-operations)
7. [Troubleshooting Guide](#troubleshooting-guide)

---

## Pre-Deployment Checklist

### Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SESSION_SECRET` | Session encryption key (min 32 chars) | **Yes** |
| `DATABASE_URL` | PostgreSQL connection string | **Yes** |
| `SENTRY_DSN` | Sentry error tracking DSN | Recommended |
| `REDIS_URL` | Redis URL for sessions/caching | Recommended |
| `OPENAI_API_KEY` | OpenAI API key for transcription | For AI features |

### Security Verification

- [ ] SESSION_SECRET is at least 32 characters
- [ ] No secrets are hardcoded in code
- [ ] HTTPS is enabled in production
- [ ] CSRF protection is active
- [ ] Rate limiting is configured

### Database Preparation

```bash
# Run migrations before deployment
flask db upgrade

# Verify migration status
flask db current
```

---

## Deployment Procedures

### Standard Deployment

1. **Pre-flight checks:**
   ```bash
   # Run smoke tests
   pytest tests/test_production_readiness.py -v
   
   # Check health endpoints
   curl https://your-app.replit.app/health/ready
   ```

2. **Deploy via Replit:**
   - Click "Publish" in Replit
   - Monitor deployment logs
   - Verify health check passes

3. **Post-deployment verification:**
   ```bash
   # Check liveness
   curl https://your-app.replit.app/health/live
   
   # Check readiness (includes dependencies)
   curl https://your-app.replit.app/health/ready
   
   # Check detailed health
   curl https://your-app.replit.app/health/detailed
   ```

### Database Migration Deployment

For deployments that include database schema changes:

1. **Backup current data** (if needed)
2. **Apply migrations:**
   ```bash
   flask db upgrade
   ```
3. **Verify migration:**
   ```bash
   flask db current
   ```
4. **Test database connectivity:**
   ```bash
   curl https://your-app.replit.app/health/ready
   ```

---

## Health Monitoring

### Health Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health/live` | Liveness probe | `200 {"status": "alive"}` |
| `/health/ready` | Readiness probe | `200 {"status": "ready"}` |
| `/health/startup` | Startup probe | `200 {"status": "started"}` |
| `/health/detailed` | Full diagnostics | `200 {dependencies, system...}` |
| `/healthz` | Legacy compatibility | `200 {"ok": true}` |

### Monitoring Dashboards

1. **Sentry:** Error tracking and performance monitoring
2. **Application logs:** Structured JSON logs with request context
3. **Health endpoint:** `/health/detailed` for system metrics

### Key Metrics to Monitor

- Response latency (P50, P95, P99)
- Error rate (4xx, 5xx)
- Database connection pool usage
- Memory and CPU utilization
- WebSocket connection count

---

## Incident Response

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| P1 - Critical | Complete outage, data loss | Immediate |
| P2 - High | Major feature broken | < 1 hour |
| P3 - Medium | Minor feature degraded | < 4 hours |
| P4 - Low | Cosmetic issue | Next business day |

### Incident Response Steps

1. **Acknowledge** - Acknowledge the incident
2. **Assess** - Determine severity and impact
3. **Mitigate** - Apply immediate fixes or rollback
4. **Communicate** - Update stakeholders
5. **Resolve** - Implement permanent fix
6. **Review** - Conduct post-mortem

### Quick Diagnostics

```bash
# Check application health
curl https://your-app.replit.app/health/detailed | jq

# Check recent errors in Sentry
# (Use Sentry dashboard)

# Check application logs
# (Use Replit logs panel)
```

---

## Rollback Procedures

### When to Rollback

- Health checks failing after deployment
- Significant increase in error rate
- Critical feature broken
- Data corruption detected

### Rollback Steps

1. **Use Replit Checkpoints:**
   - Go to Replit project
   - Open History/Checkpoints
   - Select last known good checkpoint
   - Rollback code and database

2. **Database-only Rollback:**
   ```bash
   # Downgrade to previous migration
   flask db downgrade -1
   
   # Or to specific revision
   flask db downgrade <revision_id>
   ```

3. **Verify rollback:**
   ```bash
   curl https://your-app.replit.app/health/ready
   ```

---

## Database Operations

### Safe Migration Process

```bash
# 1. Create new migration
flask db migrate -m "Description of changes"

# 2. Review generated migration
cat migrations/versions/<latest>.py

# 3. Test in development
flask db upgrade

# 4. Test rollback works
flask db downgrade -1
flask db upgrade
```

### Common Database Commands

```bash
# Check current migration
flask db current

# Show migration history
flask db history

# Apply all pending migrations
flask db upgrade

# Rollback one migration
flask db downgrade -1
```

### Database Backup

For critical operations, use Replit's database backup features:
1. Go to Database panel
2. Create checkpoint before changes
3. Proceed with operations

---

## Troubleshooting Guide

### Application Won't Start

1. Check environment variables:
   ```bash
   # Required variables
   echo $SESSION_SECRET
   echo $DATABASE_URL
   ```

2. Check startup validation logs for errors

3. Verify database connectivity:
   ```bash
   curl http://localhost:5000/health/ready
   ```

### High Error Rate

1. Check Sentry for error patterns
2. Review application logs for stack traces
3. Check database connection pool
4. Verify external service availability

### Database Connection Issues

1. Check DATABASE_URL is correct
2. Verify PostgreSQL is running
3. Check connection pool settings
4. Review connection count limits

### WebSocket Issues

1. Check Socket.IO connection status
2. Verify CORS settings
3. Check for connection limit issues
4. Review client-side console errors

### Memory Issues

1. Check `/health/detailed` for memory stats
2. Review for memory leaks
3. Check for large file uploads
4. Restart application if needed

---

## Contacts and Escalation

| Role | Contact | When to Contact |
|------|---------|-----------------|
| On-call Engineer | (TBD) | P1/P2 incidents |
| Database Admin | (TBD) | Database issues |
| Platform Support | Replit Support | Infrastructure issues |

---

## Appendix

### Environment Detection

The application automatically detects environment:
- `REPLIT_DEPLOYMENT=1` → Production
- `FLASK_ENV=production` → Production
- Otherwise → Development

### Log Format

Production logs use structured JSON format:
```json
{
  "timestamp": "2025-01-01T12:00:00Z",
  "level": "INFO",
  "message": "Request completed",
  "request_id": "abc-123",
  "http": {"method": "GET", "path": "/api/..."}
}
```

### Feature Flags

Check feature flag status at `/api/flags` (if enabled).

---

*Last Updated: November 2025*
*Version: 1.0*
