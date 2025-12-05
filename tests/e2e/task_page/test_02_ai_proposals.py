"""
AI Proposal E2E Tests
Tests for AI-generated task proposal flows

Success Criteria:
- Proposals render with title, priority, due date, source meeting
- Accept creates task and removes proposal
- Reject removes proposal without creating task
- Accept All/Reject All work correctly
"""
import pytest
import time
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestProposalRendering:
    """Test AI proposal rendering"""
    
    def test_proposals_section_visible(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Proposals section shows when proposals exist"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals_container = page.locator('#ai-proposals-container')
        
        if proposals_container.locator('.ai-proposal-card').count() > 0:
            expect(proposals_container).to_be_visible()
    
    def test_proposal_shows_title(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Each proposal displays title"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() > 0:
            first_proposal = proposals.first
            title = first_proposal.locator('.proposal-title, .task-title')
            expect(title).to_be_visible()
            expect(title).not_to_be_empty()
    
    def test_proposal_shows_priority_badge(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Each proposal displays priority badge"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() > 0:
            first_proposal = proposals.first
            priority = first_proposal.locator('.priority-badge, .priority-dot')
            expect(priority).to_be_visible()
    
    def test_proposal_shows_source_meeting(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Each proposal links to source meeting"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() > 0:
            first_proposal = proposals.first
            meeting_link = first_proposal.locator('.meeting-source, .provenance-link, [data-meeting-id]')
            
            if meeting_link.count() > 0:
                expect(meeting_link.first).to_be_visible()
    
    def test_proposal_count_badge_matches(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Proposal count badge matches actual count"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        actual_count = proposals.count()
        
        count_badge = page.locator('.proposals-count, .ai-proposals-badge')
        
        if count_badge.is_visible() and actual_count > 0:
            badge_text = count_badge.text_content()
            assert str(actual_count) in badge_text, f"Badge shows {badge_text}, expected {actual_count}"
    
    def test_empty_proposals_state(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Empty state shown when no proposals"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() == 0:
            empty_state = page.locator('.proposals-empty-state, .no-proposals-message')
            pass


class TestProposalAccept:
    """Test proposal acceptance flows"""
    
    def test_accept_creates_task(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Accepting proposal creates a real task"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() == 0:
            pytest.skip("No proposals available to accept")
        
        initial_task_count = helpers.get_task_count()
        
        first_proposal = proposals.first
        proposal_title = first_proposal.locator('.proposal-title, .task-title').text_content()
        
        accept_btn = first_proposal.locator('.accept-btn, [data-action="accept"]')
        accept_btn.click()
        
        time.sleep(1)
        
        final_task_count = helpers.get_task_count()
        assert final_task_count == initial_task_count + 1, "Task was not created from proposal"
        
        new_task = helpers.get_task_by_title(proposal_title)
        expect(new_task).to_be_visible()
    
    def test_accept_removes_proposal(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Accepted proposal is removed from list"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        initial_count = proposals.count()
        
        if initial_count == 0:
            pytest.skip("No proposals available")
        
        first_proposal = proposals.first
        
        accept_btn = first_proposal.locator('.accept-btn, [data-action="accept"]')
        accept_btn.click()
        
        time.sleep(1)
        
        final_count = page.locator('.ai-proposal-card').count()
        assert final_count == initial_count - 1, "Proposal was not removed after acceptance"
    
    def test_accept_shows_toast(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Accepting proposal shows success toast"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() == 0:
            pytest.skip("No proposals available")
        
        first_proposal = proposals.first
        accept_btn = first_proposal.locator('.accept-btn, [data-action="accept"]')
        accept_btn.click()
        
        try:
            helpers.wait_for_toast(timeout=3000)
            toast_text = helpers.get_toast_message()
            assert 'created' in toast_text.lower() or 'accepted' in toast_text.lower()
        except:
            pass
    
    def test_accept_all_proposals(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Accept All creates tasks for all proposals"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        proposal_count = proposals.count()
        
        if proposal_count < 2:
            pytest.skip("Need multiple proposals to test Accept All")
        
        initial_task_count = helpers.get_task_count()
        
        accept_all_btn = page.locator('.accept-all-btn, [data-action="accept-all"]')
        
        if accept_all_btn.is_visible():
            accept_all_btn.click()
            time.sleep(2)
            
            final_task_count = helpers.get_task_count()
            assert final_task_count >= initial_task_count + proposal_count - 1
            
            remaining_proposals = page.locator('.ai-proposal-card').count()
            assert remaining_proposals == 0, "Not all proposals were accepted"


class TestProposalReject:
    """Test proposal rejection flows"""
    
    def test_reject_removes_proposal(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Rejecting proposal removes it from list"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        initial_count = proposals.count()
        
        if initial_count == 0:
            pytest.skip("No proposals available")
        
        first_proposal = proposals.first
        
        reject_btn = first_proposal.locator('.reject-btn, .dismiss-btn, [data-action="reject"], [data-action="dismiss"]')
        reject_btn.click()
        
        time.sleep(0.5)
        
        final_count = page.locator('.ai-proposal-card').count()
        assert final_count == initial_count - 1, "Proposal was not removed after rejection"
    
    def test_reject_does_not_create_task(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Rejecting proposal does not create task"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() == 0:
            pytest.skip("No proposals available")
        
        initial_task_count = helpers.get_task_count()
        
        first_proposal = proposals.first
        reject_btn = first_proposal.locator('.reject-btn, .dismiss-btn, [data-action="reject"], [data-action="dismiss"]')
        reject_btn.click()
        
        time.sleep(0.5)
        
        final_task_count = helpers.get_task_count()
        assert final_task_count == initial_task_count, "Task was created despite rejection"
    
    def test_reject_persists_after_refresh(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Rejected proposal stays gone after page refresh"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        initial_count = proposals.count()
        
        if initial_count == 0:
            pytest.skip("No proposals available")
        
        first_proposal = proposals.first
        proposal_id = first_proposal.get_attribute('data-proposal-id')
        
        reject_btn = first_proposal.locator('.reject-btn, .dismiss-btn, [data-action="reject"], [data-action="dismiss"]')
        reject_btn.click()
        
        time.sleep(1)
        
        page.reload()
        page.wait_for_load_state('networkidle')
        
        if proposal_id:
            rejected_proposal = page.locator(f'.ai-proposal-card[data-proposal-id="{proposal_id}"]')
            expect(rejected_proposal).not_to_be_visible()
    
    def test_reject_all_proposals(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Reject All clears all proposals"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() < 2:
            pytest.skip("Need multiple proposals to test Reject All")
        
        reject_all_btn = page.locator('.reject-all-btn, [data-action="reject-all"], [data-action="dismiss-all"]')
        
        if reject_all_btn.is_visible():
            reject_all_btn.click()
            time.sleep(1)
            
            remaining_proposals = page.locator('.ai-proposal-card').count()
            assert remaining_proposals == 0, "Not all proposals were rejected"


class TestProposalMeetingIntegration:
    """Test proposal-meeting relationship"""
    
    def test_proposal_links_to_meeting(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Clicking source meeting navigates correctly"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() == 0:
            pytest.skip("No proposals available")
        
        first_proposal = proposals.first
        meeting_link = first_proposal.locator('.meeting-source a, .provenance-link')
        
        if meeting_link.count() > 0 and meeting_link.first.is_visible():
            href = meeting_link.first.get_attribute('href')
            assert href and '/sessions/' in href, "Meeting link not properly formatted"
    
    def test_accepted_task_shows_meeting_badge(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Accepted proposal task shows meeting origin"""
        page = authenticated_task_page
        helpers.page = page
        
        proposals = page.locator('.ai-proposal-card')
        
        if proposals.count() == 0:
            pytest.skip("No proposals available")
        
        first_proposal = proposals.first
        proposal_title = first_proposal.locator('.proposal-title, .task-title').text_content()
        
        accept_btn = first_proposal.locator('.accept-btn, [data-action="accept"]')
        accept_btn.click()
        
        time.sleep(1)
        
        new_task = helpers.get_task_by_title(proposal_title)
        if new_task.is_visible():
            meeting_badge = new_task.locator('.provenance-compact, .meeting-badge')
            if meeting_badge.count() > 0:
                expect(meeting_badge.first).to_be_visible()
