"""
Slack Integration Service for Mina - Phase 2 Group 4 (T2.28)
Handles posting meeting summaries to Slack channels using Incoming Webhooks.
"""

import os
import logging
import requests
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class SlackService:
    """Service for posting meeting transcripts to Slack channels."""
    
    def __init__(self):
        self.webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        self.is_configured = bool(self.webhook_url)
        
        if self.is_configured:
            logger.info("✅ Slack service initialized with webhook")
        else:
            logger.warning("⚠️ Slack service not configured - SLACK_WEBHOOK_URL not found")
    
    def is_available(self) -> bool:
        """Check if Slack service is available."""
        return self.is_configured
    
    def post_message(self, channel: str, text: str) -> bool:
        """
        Post a simple text message to Slack (for testing).
        
        Args:
            channel: Channel ID or name (e.g., #general)
            text: Message text to post
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured:
            logger.warning("⚠️ Slack not configured - cannot post message")
            return False
        
        try:
            payload = {
                "text": text,
                "channel": channel
            }
            
            webhook_url = self.webhook_url or ""
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            success = response.status_code == 200
            if success:
                logger.info(f"✅ Posted message to Slack channel: {channel}")
            else:
                logger.error(f"❌ Slack post failed: {response.status_code}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error posting to Slack: {str(e)}")
            return False
    
    def post_transcript_summary(
        self,
        session_title: str,
        session_date: datetime,
        summary: Optional[str] = None,
        share_link: Optional[str] = None,
        sender_name: Optional[str] = None,
        channel_override: Optional[str] = None
    ) -> Dict:
        """
        Post transcript summary to Slack channel.
        
        Args:
            session_title: Meeting/session title
            session_date: Date of the meeting
            summary: Optional meeting summary
            share_link: Link to full transcript
            sender_name: Name of the person sharing
            channel_override: Optional channel to post to (overrides webhook default)
            
        Returns:
            Dict with success status and message
        """
        if not self.is_configured:
            return {
                'success': False,
                'error': 'Slack not configured. Please set SLACK_WEBHOOK_URL.'
            }
        
        try:
            # Build Slack message using Block Kit
            blocks = self._build_slack_blocks(
                session_title=session_title,
                session_date=session_date,
                summary=summary,
                share_link=share_link,
                sender_name=sender_name
            )
            
            payload: Dict = {
                "blocks": blocks
            }
            
            # Add channel override if provided
            if channel_override:
                payload["channel"] = channel_override
            
            # Post to Slack (webhook_url is guaranteed to exist here)
            webhook_url = self.webhook_url or ""  # Type safety
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ Successfully posted to Slack")
                return {
                    'success': True,
                    'message': 'Posted to Slack successfully'
                }
            else:
                logger.error(f"❌ Slack API error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'Slack posting failed with status {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            logger.error("❌ Slack request timeout")
            return {
                'success': False,
                'error': 'Request to Slack timed out'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Slack request error: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to post to Slack: {str(e)}'
            }
        except Exception as e:
            logger.error(f"❌ Slack posting error: {str(e)}")
            return {
                'success': False,
                'error': f'Slack posting failed: {str(e)}'
            }
    
    def _build_slack_blocks(
        self,
        session_title: str,
        session_date: datetime,
        summary: Optional[str] = None,
        share_link: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> list:
        """Build Slack Block Kit message."""
        
        date_str = session_date.strftime('%B %d, %Y at %I:%M %p') if session_date else 'Unknown date'
        sender_text = f"{sender_name} shared" if sender_name else "New"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📝 {sender_text} a Meeting Transcript",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{session_title}*\n📅 {date_str}"
                }
            }
        ]
        
        # Add summary if available
        if summary:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary:*\n{summary[:500]}{'...' if len(summary) > 500 else ''}"
                }
            })
        
        # Add divider
        blocks.append({"type": "divider"})
        
        # Add action button if share link available
        if share_link:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Full Transcript",
                            "emoji": True
                        },
                        "url": share_link,
                        "style": "primary"
                    }
                ]
            })
        
        # Add footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Powered by *Mina* | Transform meetings into actionable moments"
                }
            ]
        })
        
        return blocks


slack_service = SlackService()
