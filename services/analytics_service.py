"""
Analytics Service
Comprehensive meeting analytics, insights, and performance metrics calculation.
"""

import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from statistics import mean, median
from collections import defaultdict
from models import db, Analytics, Meeting, Participant, Task, Session, Segment
from services.openai_client_manager import get_openai_client
from services.event_broadcaster import EventBroadcaster


class AnalyticsService:
    """Service for calculating comprehensive meeting analytics and insights."""
    
    def __init__(self):
        self.client = get_openai_client()
        self.event_broadcaster = EventBroadcaster()
        
        # Keywords for different analysis
        self.decision_keywords = [
            "decide", "decision", "agreed", "consensus", "vote", "choose",
            "final", "settled", "resolved", "conclusion"
        ]
        
        self.idea_keywords = [
            "idea", "suggestion", "propose", "think", "concept", "approach",
            "solution", "way", "method", "strategy"
        ]
        
        self.disagreement_keywords = [
            "disagree", "no", "wrong", "incorrect", "but", "however",
            "against", "oppose", "different", "alternative"
        ]

    async def analyze_meeting(self, meeting_id: int) -> Dict:
        """Perform comprehensive analysis of a meeting."""
        meeting = db.session.get(Meeting, meeting_id)
        if not meeting:
            return {"success": False, "message": "Meeting not found"}
        
        try:
            # Create or get analytics record
            analytics = db.session.query(Analytics).filter_by(meeting_id=meeting_id).first()
            if not analytics:
                analytics = Analytics(meeting_id=meeting_id)
                db.session.add(analytics)
            
            analytics.start_analysis()
            db.session.commit()
            
            # Perform various analyses
            await self._analyze_basic_metrics(analytics, meeting)
            await self._analyze_engagement(analytics, meeting)
            await self._analyze_sentiment(analytics, meeting)
            await self._analyze_productivity(analytics, meeting)
            await self._analyze_content(analytics, meeting)
            await self._analyze_communication_patterns(analytics, meeting)
            await self._analyze_efficiency(analytics, meeting)
            await self._generate_insights(analytics, meeting)
            
            # Calculate overall effectiveness score
            analytics.calculate_effectiveness_score()
            
            analytics.complete_analysis()
            db.session.commit()
            
            # Broadcast analytics_refresh event with workspace-wide statistics
            analytics_data = analytics.to_dict(include_detailed_data=True)
            if meeting.workspace_id:
                # Get workspace-wide statistics for accurate KPIs
                try:
                    from services.meeting_lifecycle_service import MeetingLifecycleService
                    workspace_stats = MeetingLifecycleService.get_meeting_statistics(
                        meeting.workspace_id, 
                        days=365
                    )
                    
                    self.event_broadcaster.broadcast_analytics_refresh(
                        meeting_id=meeting.id,
                        analytics_data={
                            'kpis': {
                                'total_meetings': workspace_stats['total_meetings'],
                                'total_hours': round(workspace_stats['total_duration_hours'], 1),
                                'action_items': workspace_stats['total_tasks'],
                                'avg_duration': f"{int(workspace_stats.get('avg_duration_minutes', 0))} min"
                            },
                            'charts': {
                                'engagement': analytics_data.get('overall_engagement_score', 0),
                                'sentiment': analytics_data.get('sentiment_analysis', {}),
                                'productivity': analytics_data.get('productivity_score', 0)
                            },
                            'meeting_specific': {
                                'participant_count': analytics_data.get('participant_count', 0),
                                'word_count': analytics_data.get('word_count', 0),
                                'duration_minutes': analytics_data.get('total_duration_minutes', 0)
                            }
                        },
                        workspace_id=meeting.workspace_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to get workspace stats for analytics_refresh: {e}")
                    # Fallback to basic broadcast without KPIs
                    self.event_broadcaster.broadcast_analytics_refresh(
                        meeting_id=meeting.id,
                        analytics_data={'charts': {}},
                        workspace_id=meeting.workspace_id
                    )
            
            return {
                "success": True,
                "message": "Meeting analysis completed",
                "analytics": analytics_data
            }
            
        except Exception as e:
            if analytics:
                analytics.fail_analysis(str(e))
                db.session.commit()
            return {"success": False, "message": f"Analysis failed: {str(e)}"}

    async def _analyze_basic_metrics(self, analytics: Analytics, meeting: Meeting):
        """Analyze basic meeting metrics."""
        # Duration analysis
        if meeting.actual_start and meeting.actual_end:
            duration = meeting.actual_end - meeting.actual_start
            analytics.total_duration_minutes = duration.total_seconds() / 60
        
        if meeting.scheduled_start and meeting.scheduled_end and analytics.total_duration_minutes:
            scheduled_duration = (meeting.scheduled_end - meeting.scheduled_start).total_seconds() / 60
            analytics.actual_vs_scheduled_ratio = analytics.total_duration_minutes / scheduled_duration
        
        # Participant count
        participants = db.session.query(Participant).filter_by(meeting_id=meeting.id).all()
        analytics.participant_count = len(participants)
        analytics.unique_speakers = len([p for p in participants if p.talk_time_seconds and p.talk_time_seconds > 0])
        
        # Word count from transcript
        if meeting.session:
            segments = db.session.query(Segment).filter_by(session_id=meeting.session.id, is_final=True).all()
            analytics.word_count = sum(len(segment.text.split()) for segment in segments)

    async def _analyze_engagement(self, analytics: Analytics, meeting: Meeting):
        """Analyze participant engagement metrics."""
        participants = db.session.query(Participant).filter_by(meeting_id=meeting.id).all()
        
        if not participants:
            return
        
        # Calculate engagement metrics
        talk_times = [p.talk_time_seconds or 0 for p in participants]
        engagement_scores = [p.engagement_score or 0 for p in participants]
        
        if talk_times:
            analytics.average_talk_time_per_person = sum(talk_times) / len(talk_times) / 60  # Convert to minutes
            
            # Talk time distribution
            total_talk_time = sum(talk_times)
            if total_talk_time > 0:
                distribution = {
                    p.name: (p.talk_time_seconds or 0) / total_talk_time 
                    for p in participants
                }
                analytics.talk_time_distribution = distribution
                
                # Check if participation is balanced (no single speaker dominates)
                max_percentage = max(distribution.values()) if distribution else 0
                analytics.dominant_speaker_percentage = max_percentage
                analytics.balanced_participation = max_percentage < 0.6  # No one speaks more than 60%
        
        if engagement_scores:
            analytics.overall_engagement_score = sum(engagement_scores) / len(engagement_scores)
        
        # Find most active and quietest participants
        if participants:
            most_active = max(participants, key=lambda p: p.talk_time_seconds or 0)
            quietest = min(participants, key=lambda p: p.talk_time_seconds or 0)
            analytics.most_active_participant = most_active.name
            analytics.quietest_participant = quietest.name
        
        # Interruption analysis
        interruptions = sum(p.interruption_count or 0 for p in participants)
        if analytics.total_duration_minutes:
            analytics.interruption_frequency = interruptions / analytics.total_duration_minutes

    async def _analyze_sentiment(self, analytics: Analytics, meeting: Meeting):
        """Analyze sentiment patterns throughout the meeting."""
        participants = db.session.query(Participant).filter_by(meeting_id=meeting.id).all()
        
        sentiment_scores = []
        for participant in participants:
            if participant.sentiment_score is not None:
                sentiment_scores.append(participant.sentiment_score)
        
        if sentiment_scores:
            analytics.overall_sentiment_score = sum(sentiment_scores) / len(sentiment_scores)
        
        # Analyze sentiment trend over time (would need more detailed timestamp data)
        if meeting.session:
            sentiment_trend = await self._analyze_sentiment_trend(meeting.session)
            analytics.sentiment_trend = sentiment_trend
            
            # Identify positive and negative moments
            positive_moments = [i for i, score in enumerate(sentiment_trend) if score > 0.5]
            negative_moments = [i for i, score in enumerate(sentiment_trend) if score < -0.2]
            analytics.positive_moments = positive_moments
            analytics.negative_moments = negative_moments

    async def _analyze_sentiment_trend(self, session: Session) -> List[float]:
        """Analyze sentiment trend over time during the meeting."""
        if not self.client:
            return [0.0]
        
        segments = db.session.query(Segment).filter_by(
            session_id=session.id, 
            is_final=True
        ).order_by(Segment.timestamp).all()
        
        if not segments:
            return [0.0]
        
        # Group segments into time windows (e.g., 5-minute intervals)
        window_size = 5 * 60  # 5 minutes in seconds
        time_windows = defaultdict(list)
        
        start_time = segments[0].timestamp
        for segment in segments:
            time_diff = (segment.timestamp - start_time).total_seconds()
            window_index = int(time_diff // window_size)
            time_windows[window_index].append(segment.text)
        
        # Analyze sentiment for each window
        sentiment_trend = []
        for window_index in sorted(time_windows.keys()):
            window_text = " ".join(time_windows[window_index])
            sentiment = await self._get_text_sentiment(window_text)
            sentiment_trend.append(sentiment)
        
        return sentiment_trend

    async def _get_text_sentiment(self, text: str) -> float:
        """Get sentiment score for a piece of text."""
        if not self.client or not text.strip():
            return 0.0
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze the sentiment of the following text. Return only a number between -1 (very negative) and 1 (very positive)."
                    },
                    {"role": "user", "content": text[:500]}  # Limit text length
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            sentiment_text = response.choices[0].message.content.strip()
            return float(sentiment_text)
        except Exception:
            return 0.0

    async def _analyze_productivity(self, analytics: Analytics, meeting: Meeting):
        """Analyze meeting productivity metrics."""
        # Task analysis
        tasks = db.session.query(Task).filter_by(meeting_id=meeting.id).all()
        analytics.action_items_created = len(tasks)
        
        # Decision analysis
        if meeting.session:
            segments = db.session.query(Segment).filter_by(session_id=meeting.session.id, is_final=True).all()
            full_text = " ".join(segment.text.lower() for segment in segments)
            
            # Count decisions made
            decision_count = sum(1 for keyword in self.decision_keywords if keyword in full_text)
            analytics.decisions_made_count = decision_count
            
            # Analyze agenda completion (if agenda exists)
            if meeting.agenda:
                agenda_completion = await self._analyze_agenda_completion(meeting.agenda, full_text)
                analytics.agenda_completion_rate = agenda_completion
        
        # Follow-up analysis
        unresolved_count = len([task for task in tasks if task.status in ['todo', 'in_progress']])
        analytics.unresolved_issues_count = unresolved_count
        analytics.follow_up_required = unresolved_count > 0

    async def _analyze_agenda_completion(self, agenda: Dict, transcript: str) -> float:
        """Analyze how well the meeting covered the planned agenda."""
        if not agenda or not isinstance(agenda, dict):
            return 0.0
        
        agenda_items = agenda.get('items', [])
        if not agenda_items:
            return 0.0
        
        covered_items = 0
        for item in agenda_items:
            item_text = item.get('title', '') + ' ' + item.get('description', '')
            # Simple keyword matching - could be enhanced with semantic analysis
            keywords = item_text.lower().split()
            if any(keyword in transcript for keyword in keywords[:3]):  # Check first 3 keywords
                covered_items += 1
        
        return covered_items / len(agenda_items)

    async def _analyze_content(self, analytics: Analytics, meeting: Meeting):
        """Analyze meeting content patterns."""
        if not meeting.session:
            return
        
        segments = db.session.query(Segment).filter_by(session_id=meeting.session.id, is_final=True).all()
        full_text = " ".join(segment.text.lower() for segment in segments)
        
        # Count different types of content
        analytics.question_count = full_text.count('?')
        analytics.idea_count = sum(1 for keyword in self.idea_keywords if keyword in full_text)
        analytics.disagreement_count = sum(1 for keyword in self.disagreement_keywords if keyword in full_text)
        
        # Extract key topics and keywords
        if self.client:
            topics = await self._extract_key_topics(full_text)
            analytics.key_topics = topics
            
            keywords = await self._extract_keywords(full_text)
            analytics.topic_keywords = keywords

    async def _extract_key_topics(self, text: str) -> List[str]:
        """Extract main topics discussed in the meeting."""
        if not self.client:
            return []
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract the 5 main topics discussed in this meeting. Return as a JSON array of strings."
                    },
                    {"role": "user", "content": text[:2000]}
                ],
                temperature=0.2,
                max_tokens=200
            )
            
            topics = json.loads(response.choices[0].message.content)
            return topics if isinstance(topics, list) else []
        except Exception:
            return []

    async def _extract_keywords(self, text: str) -> List[str]:
        """Extract key terms and phrases from the meeting."""
        # Simple keyword extraction - could be enhanced with NLP libraries
        words = text.split()
        word_freq = defaultdict(int)
        
        for word in words:
            word = word.strip('.,!?').lower()
            if len(word) > 3:  # Skip very short words
                word_freq[word] += 1
        
        # Return top 10 most frequent words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:10]]

    async def _analyze_communication_patterns(self, analytics: Analytics, meeting: Meeting):
        """Analyze communication patterns and dynamics."""
        if not meeting.session:
            return
        
        segments = db.session.query(Segment).filter_by(session_id=meeting.session.id, is_final=True).all()
        
        # Analyze consensus moments (simplified)
        consensus_indicators = ["everyone agrees", "we all think", "consensus", "unanimous"]
        consensus_moments = []
        
        for i, segment in enumerate(segments):
            if any(indicator in segment.text.lower() for indicator in consensus_indicators):
                consensus_moments.append(i)
        
        analytics.consensus_moments = consensus_moments

    async def _analyze_efficiency(self, analytics: Analytics, meeting: Meeting):
        """
        Analyze meeting efficiency using comprehensive 6-dimensional weighted algorithm.
        Produces both a raw composite score (0-1) and a display score (1-10).
        
        Dimensions (with weights):
        1. Productivity Output (25%) - Action items & decisions per hour
        2. Time Efficiency (15%) - On-time performance
        3. Participation Balance (15%) - Equitable speaking distribution
        4. Engagement Quality (15%) - Active participation metrics
        5. Preparation & Follow-through (15%) - Agenda completion & task resolution
        6. Decision Effectiveness (15%) - Decision quality and consensus
        """
        sub_scores = {}
        weights = {
            'productivity': 0.25,
            'time_efficiency': 0.15,
            'participation_balance': 0.15,
            'engagement_quality': 0.15,
            'preparation': 0.15,
            'decision_effectiveness': 0.15
        }
        
        # 1. Productivity Output (0-1)
        sub_scores['productivity'] = self._calculate_productivity_score(analytics, meeting)
        
        # 2. Time Efficiency (0-1)
        sub_scores['time_efficiency'] = self._calculate_time_efficiency_score(analytics, meeting)
        
        # 3. Participation Balance (0-1)
        sub_scores['participation_balance'] = self._calculate_participation_balance_score(analytics, meeting)
        
        # 4. Engagement Quality (0-1)
        sub_scores['engagement_quality'] = self._calculate_engagement_quality_score(analytics, meeting)
        
        # 5. Preparation & Follow-through (0-1)
        sub_scores['preparation'] = self._calculate_preparation_score(analytics, meeting)
        
        # 6. Decision Effectiveness (0-1)
        sub_scores['decision_effectiveness'] = self._calculate_decision_effectiveness_score(analytics, meeting)
        
        # Calculate weighted composite score (0-1)
        composite_score = sum(
            sub_scores[dimension] * weights[dimension]
            for dimension in sub_scores
        )
        
        # Calculate confidence (based on how many metrics were available)
        available_metrics = sum(1 for score in sub_scores.values() if score > 0)
        confidence = available_metrics / len(sub_scores)
        
        # Store both raw composite (0-1) and display score (1-10)
        analytics.meeting_efficiency_score = min(1.0, max(0.0, composite_score))
        analytics.efficiency_score_display = round(1 + 9 * analytics.meeting_efficiency_score, 1)
        analytics.efficiency_confidence = round(confidence, 2)
        
        # Store sub-scores for transparency
        analytics.efficiency_breakdown = {
            'productivity': round(sub_scores['productivity'], 2),
            'time_efficiency': round(sub_scores['time_efficiency'], 2),
            'participation_balance': round(sub_scores['participation_balance'], 2),
            'engagement_quality': round(sub_scores['engagement_quality'], 2),
            'preparation': round(sub_scores['preparation'], 2),
            'decision_effectiveness': round(sub_scores['decision_effectiveness'], 2),
            'confidence': round(confidence, 2)
        }
        
        # Estimate time spent on agenda vs off-topic
        if analytics.agenda_completion_rate:
            analytics.time_spent_on_agenda = analytics.agenda_completion_rate * 100
            analytics.off_topic_time_percentage = max(0, 100 - analytics.time_spent_on_agenda)

    def _calculate_productivity_score(self, analytics: Analytics, meeting: Meeting) -> float:
        """Calculate productivity output score (0-1) based on deliverables per hour."""
        if not analytics.total_duration_minutes or analytics.total_duration_minutes < 5:
            return 0.5  # Neutral for very short meetings
        
        duration_hours = analytics.total_duration_minutes / 60
        
        # Calculate output rate
        action_items_per_hour = (analytics.action_items_created or 0) / duration_hours
        decisions_per_hour = (analytics.decisions_made_count or 0) / duration_hours
        
        # Benchmarks (based on typical productive meetings)
        # Good meeting: 5-10 action items/hour, 2-4 decisions/hour
        action_score = min(1.0, action_items_per_hour / 10)
        decision_score = min(1.0, decisions_per_hour / 4)
        
        # Weighted combination (60% actions, 40% decisions)
        return 0.6 * action_score + 0.4 * decision_score

    def _calculate_time_efficiency_score(self, analytics: Analytics, meeting: Meeting) -> float:
        """Calculate time efficiency score (0-1) based on schedule adherence."""
        if not analytics.actual_vs_scheduled_ratio:
            return 0.7  # Neutral default
        
        ratio = analytics.actual_vs_scheduled_ratio
        
        # Ideal: exactly on time (ratio = 1.0)
        # Acceptable: ±10% (0.9-1.1)
        # Poor: >20% over or under
        if 0.95 <= ratio <= 1.05:
            return 1.0  # Perfect timing
        elif 0.9 <= ratio <= 1.1:
            return 0.9  # Slightly off
        elif 0.8 <= ratio <= 1.2:
            return 0.7  # Moderately off
        elif ratio < 0.8:
            return 0.5  # Meeting ended too early (might indicate lack of engagement)
        else:  # ratio > 1.2
            return max(0.3, 1.0 - (ratio - 1.0) * 0.5)  # Penalty for going over

    def _calculate_participation_balance_score(self, analytics: Analytics, meeting: Meeting) -> float:
        """Calculate participation balance using Gini coefficient or dominant speaker analysis."""
        if not analytics.talk_time_distribution:
            return 0.7  # Neutral default
        
        # Calculate Gini coefficient for talk time distribution
        values = sorted(analytics.talk_time_distribution.values())
        n = len(values)
        
        if n < 2:
            return 1.0  # Perfect balance (only one speaker)
        
        # Gini coefficient calculation
        index_sum = sum((i + 1) * val for i, val in enumerate(values))
        total = sum(values)
        
        if total == 0:
            return 0.5
        
        gini = (2 * index_sum) / (n * total) - (n + 1) / n
        
        # Convert Gini (0 = perfect equality, 1 = perfect inequality) to score
        # Lower Gini = better balance = higher score
        balance_score = 1.0 - gini
        
        # Check for dominant speaker (>60% of time)
        if max(values) / total > 0.6:
            balance_score *= 0.7  # Penalty for domination
        
        return max(0.0, min(1.0, balance_score))

    def _calculate_engagement_quality_score(self, analytics: Analytics, meeting: Meeting) -> float:
        """Calculate engagement quality based on active participation metrics."""
        if not analytics.overall_engagement_score:
            return 0.6  # Neutral default
        
        base_engagement = analytics.overall_engagement_score
        
        # Boost for high unique speaker ratio
        if analytics.participant_count and analytics.unique_speakers:
            speaker_ratio = analytics.unique_speakers / analytics.participant_count
            engagement_boost = speaker_ratio * 0.2  # Up to +0.2 bonus
        else:
            engagement_boost = 0
        
        # Boost for interaction (questions, ideas)
        if analytics.questions_asked_count and analytics.questions_asked_count > 0:
            question_boost = min(0.1, analytics.questions_asked_count / 20)
        else:
            question_boost = 0
        
        total_score = base_engagement + engagement_boost + question_boost
        return min(1.0, max(0.0, total_score))

    def _calculate_preparation_score(self, analytics: Analytics, meeting: Meeting) -> float:
        """Calculate preparation & follow-through score."""
        score = 0.5  # Base neutral score
        
        # Agenda completion (if available)
        if analytics.agenda_completion_rate:
            score = analytics.agenda_completion_rate
        
        # Penalty if there are many unresolved action items
        if analytics.action_items_created and analytics.action_items_created > 0:
            # Assume we'd track completion in real-time
            # For now, give small boost for having actionable outcomes
            score += 0.1
        
        return min(1.0, max(0.0, score))

    def _calculate_decision_effectiveness_score(self, analytics: Analytics, meeting: Meeting) -> float:
        """Calculate decision-making effectiveness."""
        if not analytics.total_duration_minutes or analytics.total_duration_minutes < 5:
            return 0.6  # Neutral for very short meetings
        
        decisions = analytics.decisions_made_count or 0
        duration_hours = analytics.total_duration_minutes / 60
        
        # Decision density (decisions per hour)
        decision_density = decisions / duration_hours
        
        # Good meetings: 2-5 decisions per hour
        if 2 <= decision_density <= 5:
            score = 1.0
        elif 1 <= decision_density < 2:
            score = 0.8
        elif 5 < decision_density <= 8:
            score = 0.9  # Many decisions, still good
        elif decision_density > 8:
            score = 0.7  # Too many decisions might indicate lack of focus
        else:  # < 1 decision per hour
            score = 0.5
        
        # Boost if sentiment is positive (indicates consensus)
        if analytics.overall_sentiment_score and analytics.overall_sentiment_score > 0.6:
            score += 0.1
        
        return min(1.0, max(0.0, score))

    async def _generate_insights(self, analytics: Analytics, meeting: Meeting):
        """Generate AI-powered insights and recommendations."""
        if not self.client:
            return
        
        # Prepare meeting summary for AI analysis
        meeting_summary = {
            "duration": analytics.total_duration_minutes,
            "participants": analytics.participant_count,
            "engagement": analytics.overall_engagement_score,
            "sentiment": analytics.overall_sentiment_score,
            "tasks_created": analytics.action_items_created,
            "decisions_made": analytics.decisions_made_count
        }
        
        try:
            # Use unified AI model manager with GPT-4.1 fallback (async version)
            from services.ai_model_manager import AIModelManager
            
            async def make_api_call(model: str):
                return await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": """Analyze this meeting data and provide insights and recommendations.
                            Return a JSON object with:
                            {
                              "insights": ["insight 1", "insight 2", ...],
                              "recommendations": ["recommendation 1", "recommendation 2", ...]
                            }"""
                        },
                        {"role": "user", "content": json.dumps(meeting_summary)}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
            
            # Use async version of AI model manager
            result_obj = await AIModelManager.call_with_fallback_async(
                make_api_call,
                operation_name="analytics insights generation"
            )
            
            if not result_obj.success:
                raise Exception(f"All AI models failed")
            
            response = result_obj.response
            
            result = json.loads(response.choices[0].message.content)
            analytics.insights_generated = result.get("insights", [])
            analytics.recommendations = result.get("recommendations", [])
            
        except Exception as e:
            print(f"Insight generation failed: {e}")

    async def get_topic_trends(self, meeting: Meeting) -> Dict:
        """
        Analyze topic evolution throughout the meeting for timeline visualization.
        Returns topics with timestamps showing when they were discussed.
        """
        if not meeting.session:
            return {"topics": [], "timeline": []}
        
        segments = db.session.query(Segment).filter_by(
            session_id=meeting.session.id,
            is_final=True
        ).order_by(Segment.created_at).all()
        
        if not segments:
            return {"topics": [], "timeline": []}
        
        # Group segments into 5-minute windows for topic analysis
        window_size = 5 * 60  # 5 minutes in seconds
        time_windows = {}
        
        start_time = segments[0].created_at
        for segment in segments:
            time_diff = (segment.created_at - start_time).total_seconds()
            window_index = int(time_diff // window_size)
            
            if window_index not in time_windows:
                time_windows[window_index] = {
                    'start_offset': window_index * window_size,
                    'text': [],
                    'segments': []
                }
            
            time_windows[window_index]['text'].append(segment.text)
            time_windows[window_index]['segments'].append(segment.id)
        
        # Extract topics for each time window
        timeline = []
        all_topics_set = set()
        
        for window_index in sorted(time_windows.keys()):
            window_data = time_windows[window_index]
            window_text = " ".join(window_data['text'])
            
            # Extract topics using AI or keyword analysis
            if self.client and len(window_text) > 50:
                topics = await self._extract_topics_for_window(window_text)
            else:
                topics = self._extract_keywords_simple(window_text)[:3]
            
            for topic in topics:
                all_topics_set.add(topic)
            
            timeline.append({
                'time_offset_minutes': window_data['start_offset'] / 60,
                'topics': topics,
                'segment_count': len(window_data['segments']),
                'text_preview': window_text[:100] + '...' if len(window_text) > 100 else window_text
            })
        
        # Create topic frequency summary
        topic_summary = []
        for topic in all_topics_set:
            appearances = sum(1 for window in timeline if topic in window['topics'])
            first_mention = next((w['time_offset_minutes'] for w in timeline if topic in w['topics']), 0)
            
            topic_summary.append({
                'name': topic,
                'frequency': appearances,
                'first_mentioned_at': first_mention,
                'coverage_percentage': round((appearances / len(timeline)) * 100, 1) if timeline else 0
            })
        
        topic_summary.sort(key=lambda x: x['frequency'], reverse=True)
        
        return {
            'topics': topic_summary,
            'timeline': timeline,
            'total_windows': len(timeline),
            'window_size_minutes': window_size / 60
        }

    async def _extract_topics_for_window(self, text: str) -> List[str]:
        """Extract 2-3 main topics for a specific time window."""
        if not self.client or not text.strip():
            return []
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract 2-3 main topics or themes from this meeting segment. Return as a JSON array of short topic names (2-4 words each)."
                    },
                    {"role": "user", "content": text[:1000]}
                ],
                temperature=0.2,
                max_tokens=100
            )
            
            topics = json.loads(response.choices[0].message.content)
            return topics[:3] if isinstance(topics, list) else []
        except Exception:
            return self._extract_keywords_simple(text)[:3]

    def _extract_keywords_simple(self, text: str) -> List[str]:
        """Simple keyword extraction as fallback."""
        words = text.lower().split()
        word_freq = defaultdict(int)
        
        # Common stop words to ignore
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'was', 'that', 'this'}
        
        for word in words:
            word = word.strip('.,!?').lower()
            if len(word) > 4 and word not in stop_words:
                word_freq[word] += 1
        
        return sorted(word_freq.keys(), key=lambda x: word_freq[x], reverse=True)[:5]

    async def get_question_answer_analytics(self, meeting: Meeting) -> Dict:
        """
        Track questions asked during the meeting and whether they were answered.
        Returns Q&A analytics for visualization.
        """
        if not meeting.session:
            return {"questions": [], "summary": {"total": 0, "answered": 0, "unanswered": 0}}
        
        segments = db.session.query(Segment).filter_by(
            session_id=meeting.session.id,
            is_final=True
        ).order_by(Segment.created_at).all()
        
        if not segments:
            return {"questions": [], "summary": {"total": 0, "answered": 0, "unanswered": 0}}
        
        # Extract questions (segments with '?')
        questions = []
        for i, segment in enumerate(segments):
            if '?' in segment.text:
                # Check if answered in next 3-5 segments
                context_segments = segments[i+1:i+6]
                answered = self._check_if_answered(segment.text, context_segments)
                
                questions.append({
                    'question': segment.text,
                    'asked_by': segment.speaker_label or 'Unknown',
                    'timestamp_minutes': ((segment.created_at - segments[0].created_at).total_seconds() / 60),
                    'answered': answered,
                    'segment_id': segment.id
                })
        
        answered_count = sum(1 for q in questions if q['answered'])
        
        return {
            'questions': questions,
            'summary': {
                'total': len(questions),
                'answered': answered_count,
                'unanswered': len(questions) - answered_count,
                'answer_rate': round((answered_count / len(questions)) * 100, 1) if questions else 0
            }
        }

    def _check_if_answered(self, question: str, context_segments: List[Segment]) -> bool:
        """Simple heuristic to check if a question was answered."""
        if not context_segments:
            return False
        
        # Look for affirmative words, explanations, or extended responses
        answer_indicators = ['yes', 'no', 'because', 'think', 'would', 'should', 'the answer']
        context_text = " ".join(seg.text.lower() for seg in context_segments)
        
        # If any indicator is present and response is substantial, likely answered
        has_indicator = any(ind in context_text for ind in answer_indicators)
        substantial_response = len(context_text.split()) > 10
        
        return has_indicator and substantial_response

    def get_workspace_analytics_summary(self, workspace_id: int, days: int = 30) -> Dict:
        """Get analytics summary for a workspace over specified days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).all()
        
        if not meetings:
            return {"meetings": [], "summary": {}}
        
        analytics_records = []
        for meeting in meetings:
            analytics = db.session.query(Analytics).filter_by(meeting_id=meeting.id).first()
            if analytics and analytics.is_analysis_complete:
                analytics_records.append(analytics)
        
        if not analytics_records:
            return {"meetings": [m.to_dict() for m in meetings], "summary": {}}
        
        # Calculate workspace averages
        avg_effectiveness = mean([a.meeting_effectiveness_score for a in analytics_records if a.meeting_effectiveness_score])
        avg_engagement = mean([a.overall_engagement_score for a in analytics_records if a.overall_engagement_score])
        avg_sentiment = mean([a.overall_sentiment_score for a in analytics_records if a.overall_sentiment_score])
        total_tasks = sum(a.action_items_created or 0 for a in analytics_records)
        total_decisions = sum(a.decisions_made_count or 0 for a in analytics_records)
        
        return {
            "meetings": [m.to_dict() for m in meetings],
            "analytics": [a.to_dict() for a in analytics_records],
            "summary": {
                "total_meetings": len(meetings),
                "analyzed_meetings": len(analytics_records),
                "avg_effectiveness": round(avg_effectiveness, 2) if avg_effectiveness else 0,
                "avg_engagement": round(avg_engagement, 2) if avg_engagement else 0,
                "avg_sentiment": round(avg_sentiment, 2) if avg_sentiment else 0,
                "total_tasks_created": total_tasks,
                "total_decisions_made": total_decisions,
                "productivity_score": round((total_tasks + total_decisions) / len(meetings), 2) if meetings else 0
            }
        }


# Singleton instance
analytics_service = AnalyticsService()