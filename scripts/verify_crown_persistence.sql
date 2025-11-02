-- ==========================================
-- CROWN¹⁰ Database Persistence Verification
-- ==========================================
-- Run these queries to verify Session→Meeting→Task linkage

-- 1. CHECK ALL SESSIONS WITH LINKAGE STATUS
SELECT 
    s.id,
    s.external_id,
    s.title,
    s.user_id,
    s.workspace_id,
    s.meeting_id,
    s.status,
    s.post_transcription_status,
    CASE 
        WHEN s.user_id IS NULL THEN '❌ Missing user_id'
        WHEN s.workspace_id IS NULL THEN '❌ Missing workspace_id'
        WHEN s.meeting_id IS NULL THEN '⚠️  No meeting created'
        ELSE '✅ Fully linked'
    END as linkage_status,
    s.started_at,
    s.completed_at
FROM sessions s
ORDER BY s.started_at DESC
LIMIT 10;

-- 2. CHECK SESSION→MEETING→TASK PIPELINE FOR LATEST SESSIONS
SELECT 
    s.id as session_id,
    s.external_id,
    s.user_id,
    s.workspace_id,
    s.meeting_id,
    m.id as meeting_actual_id,
    m.title as meeting_title,
    m.workspace_id as meeting_workspace,
    (SELECT COUNT(*) FROM tasks t WHERE t.meeting_id = m.id) as meeting_tasks,
    (SELECT COUNT(*) FROM tasks t WHERE t.session_id = s.id AND t.meeting_id IS NULL) as orphaned_tasks,
    s.post_transcription_status
FROM sessions s
LEFT JOIN meetings m ON m.id = s.meeting_id
ORDER BY s.started_at DESC
LIMIT 10;

-- 3. FIND ORPHANED TASKS (tasks without meeting linkage)
SELECT 
    t.id,
    t.title,
    t.session_id,
    t.meeting_id,
    t.created_by_id,
    t.extracted_by_ai,
    t.status,
    t.due_date,
    s.external_id as session_external_id,
    s.user_id as session_user_id,
    s.workspace_id as session_workspace_id
FROM tasks t
LEFT JOIN sessions s ON s.id = t.session_id
WHERE t.meeting_id IS NULL 
  AND t.session_id IS NOT NULL
ORDER BY t.created_at DESC;

-- 4. VERIFY CURRENT USER'S MEETINGS (replace user_id with your current user)
SELECT 
    m.id,
    m.title,
    m.workspace_id,
    m.organizer_id,
    m.status,
    m.actual_start,
    m.actual_end,
    (SELECT COUNT(*) FROM tasks t WHERE t.meeting_id = m.id) as task_count,
    m.created_at
FROM meetings m
WHERE m.organizer_id = (SELECT id FROM users WHERE username = 'Alex Chohan' LIMIT 1)
  AND m.archived = false
ORDER BY m.created_at DESC
LIMIT 20;

-- 5. CHECK USER AND WORKSPACE CONFIGURATION
SELECT 
    u.id as user_id,
    u.username,
    u.workspace_id,
    w.name as workspace_name,
    w.is_active,
    (SELECT COUNT(*) FROM meetings m WHERE m.organizer_id = u.id) as total_meetings,
    (SELECT COUNT(*) FROM tasks t WHERE t.created_by_id = u.id) as total_tasks
FROM users u
LEFT JOIN workspaces w ON w.id = u.workspace_id
WHERE u.active = true
ORDER BY u.last_login DESC NULLS LAST
LIMIT 10;

-- 6. DASHBOARD KPI VERIFICATION (counts should match Dashboard display)
SELECT 
    'Total Meetings' as metric,
    COUNT(*) as count
FROM meetings
WHERE archived = false
UNION ALL
SELECT 
    'Total Tasks' as metric,
    COUNT(*) as count
FROM tasks
WHERE status != 'archived'
UNION ALL
SELECT 
    'Completed Meetings' as metric,
    COUNT(*) as count
FROM meetings
WHERE status = 'completed' AND archived = false
UNION ALL
SELECT 
    'Active Tasks' as metric,
    COUNT(*) as count
FROM tasks
WHERE status IN ('todo', 'in_progress');

-- 7. RECENT SESSION ACTIVITY (last 24 hours)
SELECT 
    DATE_TRUNC('hour', s.started_at) as hour,
    COUNT(*) as sessions_started,
    COUNT(s.meeting_id) as meetings_created,
    AVG(s.total_segments) as avg_segments,
    AVG(s.average_confidence) as avg_confidence
FROM sessions s
WHERE s.started_at > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', s.started_at)
ORDER BY hour DESC;
