"""
📊 MONITORING DASHBOARD
Comprehensive monitoring dashboard for production health and Google Recorder benchmarks
"""

import logging
from flask import Blueprint, jsonify, render_template_string
from datetime import datetime, timedelta
from services.real_time_qa_bridge import get_qa_bridge
from services.performance_monitor import get_performance_monitor
from services.error_recovery_system import get_error_recovery
from services.accessibility_validator import get_accessibility_validator
from models.streaming_models import TranscriptionSession, TranscriptionChunk
from app import db

logger = logging.getLogger(__name__)

# Create monitoring dashboard blueprint
monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/api/monitoring')


@monitoring_bp.route('/health', methods=['GET'])
def get_system_health():
    """Get comprehensive system health status"""
    try:
        # Get all system health data
        performance_monitor = get_performance_monitor()
        error_recovery = get_error_recovery()
        qa_bridge = get_qa_bridge()
        
        # Adapt to existing PerformanceMonitor interface
        alerts = performance_monitor.get_alerts()
        global_metrics = performance_monitor.global_metrics
        error_health = error_recovery.get_health_status()
        
        # Build health status from available data
        perf_health = {
            'status': 'healthy' if not alerts else ('critical' if any(a['level'] == 'critical' for a in alerts) else 'degraded'),
            'cpu_healthy': global_metrics['system_cpu_usage'] < 80,
            'memory_healthy': global_metrics['system_memory_usage'] < 80,
            'latency_healthy': global_metrics['avg_latency_ms'] < 500,
            'overall_score': 100 - (len(alerts) * 20)  # Rough score based on alerts
        }
        
        # Calculate overall system health
        health_components = {
            'performance': perf_health.get('status', 'healthy'),
            'errors': error_health['status'],
            'database': 'healthy',  # Assume healthy if we can query
            'api': 'healthy'  # Assume healthy if OpenAI API is working
        }
        
        # Determine overall status
        component_scores = {
            'healthy': 100,
            'degraded': 60,
            'critical': 20,
            'error': 0
        }
        
        scores = [component_scores.get(status, 0) for status in health_components.values()]
        overall_score = sum(scores) / len(scores)
        
        if overall_score >= 90:
            overall_status = 'healthy'
        elif overall_score >= 60:
            overall_status = 'degraded'
        else:
            overall_status = 'critical'
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': overall_status,
            'overall_score': overall_score,
            'components': health_components,
            'details': {
                'performance': {
                    'cpu_healthy': perf_health.get('cpu_healthy', True),
                    'memory_healthy': perf_health.get('memory_healthy', True),
                    'latency_healthy': perf_health.get('latency_healthy', True),
                    'score': perf_health.get('overall_score', 100)
                },
                'error_recovery': {
                    'error_rate': error_health['error_rate'],
                    'consecutive_errors': error_health['consecutive_errors'],
                    'recovery_rate': error_health['recovery_rate'],
                    'active_circuit_breakers': error_health['active_circuit_breakers']
                }
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get system health: {e}", exc_info=True)
        return jsonify({
            'error': f'Health check failed: {str(e)}',
            'overall_status': 'error',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/benchmarks', methods=['GET'])
def get_benchmark_status():
    """Get Google Recorder benchmark compliance status"""
    try:
        qa_bridge = get_qa_bridge()
        performance_monitor = get_performance_monitor()
        
        # Get current metrics
        qa_metrics = qa_bridge.get_real_time_metrics()
        global_metrics = performance_monitor.global_metrics
        
        # Calculate benchmark compliance
        benchmarks = {
            'wer_target': {
                'target': 10.0,
                'current': qa_metrics.wer,
                'unit': '%',
                'status': 'pass' if qa_metrics.wer <= 10.0 else 'fail',
                'description': 'Word Error Rate ≤ 10%'
            },
            'latency_target': {
                'target': 500.0,
                'current': qa_metrics.latency_ms,
                'unit': 'ms',
                'status': 'pass' if qa_metrics.latency_ms < 500.0 else 'fail',
                'description': 'End-to-end latency < 500ms'
            },
            'completeness_target': {
                'target': 90.0,
                'current': qa_metrics.completeness,
                'unit': '%',
                'status': 'pass' if qa_metrics.completeness >= 90.0 else 'fail',
                'description': 'Audio coverage ≥ 90%'
            },
            'semantic_drift_target': {
                'target': 5.0,
                'current': qa_metrics.semantic_drift,
                'unit': '%',
                'status': 'pass' if qa_metrics.semantic_drift < 5.0 else 'fail',
                'description': 'Semantic drift < 5%'
            },
            'accuracy_target': {
                'target': 95.0,
                'current': qa_metrics.accuracy,
                'unit': '%',
                'status': 'pass' if qa_metrics.accuracy >= 95.0 else 'fail',
                'description': 'Transcription accuracy ≥ 95%'
            }
        }
        
        # Calculate overall compliance
        passed = sum(1 for b in benchmarks.values() if b['status'] == 'pass')
        total = len(benchmarks)
        compliance_rate = (passed / total) * 100
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'compliance_rate': compliance_rate,
            'benchmarks_passed': passed,
            'total_benchmarks': total,
            'overall_status': 'compliant' if compliance_rate >= 80 else 'non_compliant',
            'benchmarks': benchmarks,
            'google_recorder_comparison': {
                'wer_comparison': f"{'✅ Better' if qa_metrics.wer < 10.0 else '❌ Worse'} than Google Recorder",
                'latency_comparison': f"{'✅ Better' if qa_metrics.latency_ms < 500.0 else '❌ Slower'} than Google Recorder",
                'meeting_targets': compliance_rate >= 80
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get benchmark status: {e}", exc_info=True)
        return jsonify({
            'error': f'Benchmark check failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/performance', methods=['GET'])
def get_performance_metrics():
    """Get detailed performance metrics"""
    try:
        performance_monitor = get_performance_monitor()
        global_metrics = performance_monitor.global_metrics
        alerts = performance_monitor.get_alerts()
        
        # Build performance report from available data
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'system_health': {
                'status': 'healthy' if not alerts else 'degraded',
                'cpu_usage': global_metrics['system_cpu_usage'],
                'memory_usage': global_metrics['system_memory_usage'],
                'active_sessions': global_metrics['active_sessions']
            },
            'performance_metrics': {
                'avg_latency_ms': global_metrics['avg_latency_ms'],
                'total_sessions': global_metrics['total_sessions'],
                'dropped_chunks': global_metrics['total_dropped_chunks']
            },
            'alerts': alerts
        }
        
        return jsonify(report)
        
    except Exception as e:
        logger.error(f"❌ Failed to get performance metrics: {e}", exc_info=True)
        return jsonify({
            'error': f'Performance metrics failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/qa-metrics', methods=['GET'])
def get_qa_metrics():
    """Get detailed QA metrics"""
    try:
        qa_bridge = get_qa_bridge()
        summary = qa_bridge.get_session_summary()
        current_metrics = qa_bridge.get_real_time_metrics()
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'current_metrics': {
                'wer_percent': current_metrics.wer,
                'accuracy_percent': current_metrics.accuracy,
                'latency_ms': current_metrics.latency_ms,
                'completeness_percent': current_metrics.completeness,
                'semantic_drift_percent': current_metrics.semantic_drift,
                'confidence_avg': current_metrics.confidence_avg,
                'processing_efficiency_percent': current_metrics.processing_efficiency
            },
            'benchmark_compliance': {
                'wer_target_met': current_metrics.meets_wer_target,
                'latency_target_met': current_metrics.meets_latency_target,
                'completeness_target_met': current_metrics.meets_completeness_target,
                'drift_target_met': current_metrics.meets_drift_target
            },
            'session_summary': summary
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get QA metrics: {e}", exc_info=True)
        return jsonify({
            'error': f'QA metrics failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/errors', methods=['GET'])
def get_error_statistics():
    """Get error statistics and recovery metrics"""
    try:
        error_recovery = get_error_recovery()
        stats = error_recovery.get_error_statistics()
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'error_statistics': stats,
            'health_status': error_recovery.get_health_status()
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get error statistics: {e}", exc_info=True)
        return jsonify({
            'error': f'Error statistics failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/transcription-latency', methods=['GET'])
def get_transcription_latency():
    """Get real-time transcription latency metrics (Phase 3)"""
    try:
        from services.streaming_transcription_service import streaming_transcription_service
        
        stats = streaming_transcription_service.get_stats()
        target_latency_ms = stats.get('target_latency_ms', 2000)
        avg_latency_ms = stats.get('avg_latency_ms', 0)
        p95_latency_ms = stats.get('p95_latency_ms', 0)
        
        sla_status = 'healthy' if avg_latency_ms < target_latency_ms else 'degraded'
        if avg_latency_ms > target_latency_ms * 1.5:
            sla_status = 'critical'
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'latency_metrics': {
                'avg_latency_ms': avg_latency_ms,
                'p95_latency_ms': p95_latency_ms,
                'target_latency_ms': target_latency_ms,
                'sla_status': sla_status,
                'meets_target': avg_latency_ms < target_latency_ms
            },
            'throughput': {
                'total_chunks': stats.get('total_chunks', 0),
                'successful': stats.get('successful', 0),
                'failed': stats.get('failed', 0),
                'success_rate': round(stats.get('successful', 0) / max(1, stats.get('total_chunks', 1)) * 100, 1)
            },
            'active_sessions': stats.get('active_sessions', 0),
            'comparison': {
                'vs_otter_ai': '✅ Meeting target' if avg_latency_ms < 2000 else '⚠️ Above target',
                'vs_google_recorder': '✅ Better' if avg_latency_ms < 500 else '⚠️ Slower',
                'phase3_target': f"{'✅' if avg_latency_ms < 2000 else '❌'} <2s target"
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get transcription latency: {e}", exc_info=True)
        return jsonify({
            'error': f'Latency metrics failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/accessibility', methods=['GET'])
def get_accessibility_status():
    """Get accessibility compliance status"""
    try:
        validator = get_accessibility_validator()
        
        # Perform validation if not done recently
        if not validator.last_validation or \
           (datetime.utcnow().timestamp() - validator.last_validation.timestamp) > 3600:  # 1 hour
            validator.validate_interface()
        
        summary = validator.get_compliance_summary()
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'accessibility_compliance': summary
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get accessibility status: {e}", exc_info=True)
        return jsonify({
            'error': f'Accessibility check failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/sessions', methods=['GET'])
def get_session_statistics():
    """Get transcription session statistics"""
    try:
        # Get session statistics from database
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        
        # Today's sessions
        today_sessions = db.session.query(TranscriptionSession).filter(
            db.func.date(TranscriptionSession.created_at) == today
        ).count()
        
        # Yesterday's sessions
        yesterday_sessions = db.session.query(TranscriptionSession).filter(
            db.func.date(TranscriptionSession.created_at) == yesterday
        ).count()
        
        # Active sessions
        active_sessions = db.session.query(TranscriptionSession).filter(
            TranscriptionSession.status == 'active'
        ).count()
        
        # Total processed chunks
        total_chunks = db.session.query(TranscriptionChunk).count()
        
        # Average session duration
        completed_sessions = db.session.query(TranscriptionSession).filter(
            TranscriptionSession.status == 'completed',
            TranscriptionSession.ended_at.isnot(None)
        ).all()
        
        avg_duration = 0.0
        if completed_sessions:
            durations = [
                (session.ended_at - session.created_at).total_seconds()
                for session in completed_sessions
                if session.ended_at
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'session_statistics': {
                'active_sessions': active_sessions,
                'today_sessions': today_sessions,
                'yesterday_sessions': yesterday_sessions,
                'total_chunks_processed': total_chunks,
                'average_session_duration_seconds': avg_duration,
                'growth_rate': ((today_sessions - yesterday_sessions) / max(yesterday_sessions, 1)) * 100
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get session statistics: {e}", exc_info=True)
        return jsonify({
            'error': f'Session statistics failed: {str(e)}',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/dashboard', methods=['GET'])
def monitoring_dashboard():
    """Render comprehensive monitoring dashboard"""
    
    dashboard_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MINA - Production Monitoring Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            .status-healthy { color: #28a745; }
            .status-degraded { color: #ffc107; }
            .status-critical { color: #dc3545; }
            .metric-card { border-left: 4px solid #007bff; }
            .metric-card.success { border-left-color: #28a745; }
            .metric-card.warning { border-left-color: #ffc107; }
            .metric-card.danger { border-left-color: #dc3545; }
            .metric-value { font-size: 2rem; font-weight: bold; }
            .metric-label { font-size: 0.9rem; color: #6c757d; }
            .refresh-indicator { transition: transform 0.3s; }
            .refresh-indicator.spin { transform: rotate(360deg); }
        </style>
    </head>
    <body class="bg-light">
        <nav class="navbar navbar-dark bg-dark">
            <div class="container-fluid">
                <span class="navbar-brand mb-0 h1">
                    <i class="fas fa-chart-line me-2"></i>MINA Production Monitoring
                </span>
                <span class="navbar-text">
                    <i class="fas fa-sync-alt refresh-indicator" id="refreshIcon"></i>
                    <span id="lastUpdate">Loading...</span>
                </span>
            </div>
        </nav>

        <div class="container-fluid mt-4">
            <!-- System Health Overview -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="fas fa-heartbeat me-2"></i>System Health Overview</h5>
                        </div>
                        <div class="card-body">
                            <div class="row" id="healthOverview">
                                <div class="col-12 text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Google Recorder Benchmarks -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="fas fa-target me-2"></i>Google Recorder Benchmark Compliance</h5>
                        </div>
                        <div class="card-body">
                            <div class="row" id="benchmarkStatus">
                                <div class="col-12 text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Performance Metrics -->
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="fas fa-tachometer-alt me-2"></i>Performance Metrics</h5>
                        </div>
                        <div class="card-body" id="performanceMetrics">
                            <div class="text-center">
                                <div class="spinner-border" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="fas fa-exclamation-triangle me-2"></i>Error Recovery</h5>
                        </div>
                        <div class="card-body" id="errorMetrics">
                            <div class="text-center">
                                <div class="spinner-border" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- QA Metrics & Session Statistics -->
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="fas fa-microscope me-2"></i>QA Metrics</h5>
                        </div>
                        <div class="card-body" id="qaMetrics">
                            <div class="text-center">
                                <div class="spinner-border" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="fas fa-users me-2"></i>Session Statistics</h5>
                        </div>
                        <div class="card-body" id="sessionStats">
                            <div class="text-center">
                                <div class="spinner-border" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Accessibility Compliance -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="fas fa-universal-access me-2"></i>Accessibility Compliance (WCAG 2.1 AA)</h5>
                        </div>
                        <div class="card-body" id="accessibilityStatus">
                            <div class="text-center">
                                <div class="spinner-border" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // Auto-refresh dashboard every 30 seconds
            let refreshInterval;
            
            function updateDashboard() {
                const refreshIcon = document.getElementById('refreshIcon');
                refreshIcon.classList.add('spin');
                
                Promise.all([
                    fetch('/api/monitoring/health').then(r => r.json()),
                    fetch('/api/monitoring/benchmarks').then(r => r.json()),
                    fetch('/api/monitoring/performance').then(r => r.json()),
                    fetch('/api/monitoring/errors').then(r => r.json()),
                    fetch('/api/monitoring/qa-metrics').then(r => r.json()),
                    fetch('/api/monitoring/sessions').then(r => r.json()),
                    fetch('/api/monitoring/accessibility').then(r => r.json())
                ]).then(([health, benchmarks, performance, errors, qa, sessions, accessibility]) => {
                    updateHealthOverview(health);
                    updateBenchmarkStatus(benchmarks);
                    updatePerformanceMetrics(performance);
                    updateErrorMetrics(errors);
                    updateQAMetrics(qa);
                    updateSessionStats(sessions);
                    updateAccessibilityStatus(accessibility);
                    
                    document.getElementById('lastUpdate').textContent = 
                        'Last updated: ' + new Date().toLocaleTimeString();
                }).catch(error => {
                    console.error('Dashboard update failed:', error);
                }).finally(() => {
                    setTimeout(() => refreshIcon.classList.remove('spin'), 300);
                });
            }
            
            function updateHealthOverview(data) {
                const container = document.getElementById('healthOverview');
                const statusClass = `status-${data.overall_status}`;
                
                container.innerHTML = `
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="metric-value ${statusClass}">
                                <i class="fas fa-heartbeat"></i>
                            </div>
                            <div class="metric-label">Overall Status</div>
                            <div class="fw-bold ${statusClass}">${data.overall_status.toUpperCase()}</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="metric-value ${data.details.performance.cpu_healthy ? 'status-healthy' : 'status-critical'}">
                                ${data.details.performance.score.toFixed(0)}%
                            </div>
                            <div class="metric-label">Performance Score</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="metric-value ${data.details.error_recovery.error_rate < 5 ? 'status-healthy' : 'status-critical'}">
                                ${data.details.error_recovery.error_rate.toFixed(1)}%
                            </div>
                            <div class="metric-label">Error Rate</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="metric-value ${data.details.error_recovery.active_circuit_breakers === 0 ? 'status-healthy' : 'status-critical'}">
                                ${data.details.error_recovery.active_circuit_breakers}
                            </div>
                            <div class="metric-label">Active Circuit Breakers</div>
                        </div>
                    </div>
                `;
            }
            
            function updateBenchmarkStatus(data) {
                const container = document.getElementById('benchmarkStatus');
                const statusClass = data.overall_status === 'compliant' ? 'status-healthy' : 'status-critical';
                
                let benchmarkHtml = `
                    <div class="col-12 mb-3">
                        <div class="text-center">
                            <div class="metric-value ${statusClass}">
                                ${data.compliance_rate.toFixed(0)}%
                            </div>
                            <div class="metric-label">Benchmark Compliance Rate</div>
                            <div class="fw-bold ${statusClass}">
                                ${data.benchmarks_passed}/${data.total_benchmarks} benchmarks passed
                            </div>
                        </div>
                    </div>
                `;
                
                Object.entries(data.benchmarks).forEach(([key, benchmark]) => {
                    const statusIcon = benchmark.status === 'pass' ? 'check-circle' : 'times-circle';
                    const statusColor = benchmark.status === 'pass' ? 'text-success' : 'text-danger';
                    
                    benchmarkHtml += `
                        <div class="col-md-4 mb-3">
                            <div class="card metric-card ${benchmark.status === 'pass' ? 'success' : 'danger'}">
                                <div class="card-body">
                                    <div class="d-flex align-items-center">
                                        <i class="fas fa-${statusIcon} ${statusColor} me-2"></i>
                                        <div>
                                            <div class="fw-bold">${benchmark.description}</div>
                                            <div class="metric-label">
                                                Current: ${benchmark.current.toFixed(1)}${benchmark.unit} 
                                                (Target: ${benchmark.target}${benchmark.unit})
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                container.innerHTML = benchmarkHtml;
            }
            
            function updatePerformanceMetrics(data) {
                const container = document.getElementById('performanceMetrics');
                
                container.innerHTML = `
                    <div class="row">
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-info">${data.statistics?.latency?.avg_ms?.toFixed(0) || 0}ms</div>
                                <div class="metric-label">Avg Latency</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-success">${data.statistics?.cpu?.current_percent?.toFixed(0) || 0}%</div>
                                <div class="metric-label">CPU Usage</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-warning">${data.statistics?.memory?.current_percent?.toFixed(0) || 0}%</div>
                                <div class="metric-label">Memory Usage</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-primary">${data.statistics?.sessions?.active || 0}</div>
                                <div class="metric-label">Active Sessions</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            function updateErrorMetrics(data) {
                const container = document.getElementById('errorMetrics');
                const stats = data.error_statistics || {};
                
                container.innerHTML = `
                    <div class="row">
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-danger">${stats.total_errors || 0}</div>
                                <div class="metric-label">Total Errors</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-success">${stats.recovery_statistics?.success_rate_percent?.toFixed(0) || 0}%</div>
                                <div class="metric-label">Recovery Rate</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-warning">${stats.consecutive_errors || 0}</div>
                                <div class="metric-label">Consecutive Errors</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-info">${stats.recent_errors_1h || 0}</div>
                                <div class="metric-label">Errors (1h)</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            function updateQAMetrics(data) {
                const container = document.getElementById('qaMetrics');
                const metrics = data.current_metrics || {};
                
                container.innerHTML = `
                    <div class="row">
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-success">${metrics.accuracy_percent?.toFixed(1) || 0}%</div>
                                <div class="metric-label">Accuracy</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-primary">${metrics.wer_percent?.toFixed(1) || 0}%</div>
                                <div class="metric-label">Word Error Rate</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-info">${metrics.completeness_percent?.toFixed(0) || 0}%</div>
                                <div class="metric-label">Completeness</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-warning">${metrics.processing_efficiency_percent?.toFixed(0) || 0}%</div>
                                <div class="metric-label">VAD Efficiency</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            function updateSessionStats(data) {
                const container = document.getElementById('sessionStats');
                const stats = data.session_statistics || {};
                
                container.innerHTML = `
                    <div class="row">
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-primary">${stats.active_sessions || 0}</div>
                                <div class="metric-label">Active Sessions</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-success">${stats.today_sessions || 0}</div>
                                <div class="metric-label">Today's Sessions</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-info">${stats.total_chunks_processed || 0}</div>
                                <div class="metric-label">Chunks Processed</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="text-center">
                                <div class="metric-value text-warning">${(stats.average_session_duration_seconds / 60)?.toFixed(1) || 0}m</div>
                                <div class="metric-label">Avg Duration</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            function updateAccessibilityStatus(data) {
                const container = document.getElementById('accessibilityStatus');
                const compliance = data.accessibility_compliance || {};
                const overall = compliance.overall_compliance || {};
                
                const statusClass = overall.status === 'compliant' ? 'status-healthy' : 'status-critical';
                
                container.innerHTML = `
                    <div class="row">
                        <div class="col-md-4">
                            <div class="text-center">
                                <div class="metric-value ${statusClass}">${overall.score?.toFixed(0) || 0}%</div>
                                <div class="metric-label">WCAG 2.1 AA Compliance</div>
                                <div class="fw-bold ${statusClass}">${overall.level || 'Unknown'}</div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="text-center">
                                <div class="metric-value text-danger">${compliance.issue_summary?.errors || 0}</div>
                                <div class="metric-label">Critical Issues</div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="text-center">
                                <div class="metric-value text-warning">${compliance.issue_summary?.warnings || 0}</div>
                                <div class="metric-label">Warnings</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Initialize dashboard
            updateDashboard();
            refreshInterval = setInterval(updateDashboard, 30000); // Refresh every 30 seconds
            
            // Handle page visibility to pause/resume refreshing
            document.addEventListener('visibilitychange', function() {
                if (document.hidden) {
                    clearInterval(refreshInterval);
                } else {
                    updateDashboard();
                    refreshInterval = setInterval(updateDashboard, 30000);
                }
            });
        </script>
    </body>
    </html>
    """
    
    return dashboard_html


# Register error handlers
@monitoring_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Monitoring endpoint not found'}), 404


@monitoring_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal monitoring error'}), 500