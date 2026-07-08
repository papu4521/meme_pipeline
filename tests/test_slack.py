import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from nodes.node6_slack import router, SlackHITL
from fastapi import FastAPI
import json

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_slack_actions_approve_post():
    """Test /slack/actions endpoint with a valid approve_post action."""
    with patch('nodes.node6_slack.signature_verifier') as mock_verifier, \
         patch('nodes.node6_slack.slack_client.chat_update') as mock_update, \
         patch('nodes.node6_slack.instagram.publish_image') as mock_post:
        
        mock_verifier.is_valid_request.return_value = True
        
        payload = {
            "type": "block_actions",
            "channel": {"id": "C123"},
            "message": {"ts": "123.456", "blocks": [{"type": "section", "text": {"text": "```My tweet```"}}]},
            "actions": [{"action_id": "approve_post", "value": "meme123"}]
        }
        
        response = client.post("/slack/actions", data={"payload": json.dumps(payload)})
        assert response.status_code == 200
        mock_post.assert_called_once()
        mock_update.assert_called_once()

def test_slack_actions_reject_post():
    """Test /slack/actions endpoint with a reject_post action."""
    with patch('nodes.node6_slack.signature_verifier') as mock_verifier, \
         patch('nodes.node6_slack.slack_client.chat_update') as mock_update:
        
        mock_verifier.is_valid_request.return_value = True
        
        payload = {
            "type": "block_actions",
            "channel": {"id": "C123"},
            "message": {"ts": "123.456", "blocks": [{"type": "section"}]},
            "actions": [{"action_id": "reject_post", "value": "meme123"}]
        }
        
        response = client.post("/slack/actions", data={"payload": json.dumps(payload)})
        assert response.status_code == 200
        mock_update.assert_called_once()

def test_slack_actions_invalid_signature():
    """Test Signature verification rejection (403) when sig is invalid."""
    with patch('nodes.node6_slack.signature_verifier') as mock_verifier:
        mock_verifier.is_valid_request.return_value = False
        response = client.post("/slack/actions", data={"payload": "{}"})
        assert response.status_code == 403

def test_send_for_approval_local_path():
    """Test send_for_approval() with a local image path (triggers files_upload_v2)."""
    slack = SlackHITL()
    with patch.object(slack.client, 'chat_postMessage') as mock_post, \
         patch.object(slack.client, 'files_upload_v2') as mock_upload:
        
        payload = {
            "tweet_text": "hello",
            "source_title": "News",
            "image_url": "http://localhost:8000/images/1.png",
            "local_path": "/tmp/1.png",
            "id": "123"
        }
        slack.send_for_approval(payload)
        mock_post.assert_called_once()
        mock_upload.assert_called_once_with(channel=slack.channel_id, file="/tmp/1.png", title="Generated Meme Image")

def test_send_for_approval_public_url():
    """Test send_for_approval() with a public image URL (uses image block, no file upload)."""
    slack = SlackHITL()
    with patch.object(slack.client, 'chat_postMessage') as mock_post, \
         patch.object(slack.client, 'files_upload_v2') as mock_upload:
        
        payload = {
            "tweet_text": "hello",
            "source_title": "News",
            "image_url": "https://example.com/1.png",
            "id": "123"
        }
        slack.send_for_approval(payload)
        mock_post.assert_called_once()
        mock_upload.assert_not_called()

def test_slack_actions_no_payload():
    """Test /slack/actions fails without payload."""
    with patch('nodes.node6_slack.signature_verifier') as mock_verifier:
        mock_verifier.is_valid_request.return_value = True
        response = client.post("/slack/actions", data={})
        assert response.status_code == 400

def test_slack_actions_chat_update_error():
    """Test /slack/actions handles SlackApiError on chat_update."""
    with patch('nodes.node6_slack.signature_verifier') as mock_verifier, \
         patch('nodes.node6_slack.slack_client.chat_update') as mock_update:
        mock_verifier.is_valid_request.return_value = True
        from slack_sdk.errors import SlackApiError
        mock_update.side_effect = SlackApiError("API Error", MagicMock())
        payload = {
            "type": "block_actions",
            "channel": {"id": "C123"},
            "message": {"ts": "123.456", "blocks": [{"type": "section"}]},
            "actions": [{"action_id": "reject_post", "value": "meme123"}]
        }
        response = client.post("/slack/actions", data={"payload": json.dumps(payload)})
        assert response.status_code == 200 # Still returns 200
        assert response.status_code == 400

def test_slack_actions_chat_update_error():
    """Test /slack/actions handles SlackApiError on chat_update."""
    with patch('nodes.node6_slack.signature_verifier') as mock_verifier, \
         patch('nodes.node6_slack.slack_client.chat_update') as mock_update:
        mock_verifier.is_valid_request.return_value = True
        from slack_sdk.errors import SlackApiError
        mock_update.side_effect = SlackApiError("API Error", MagicMock())
        payload = {
            "type": "block_actions",
            "channel": {"id": "C123"},
            "message": {"ts": "123.456", "blocks": [{"type": "section"}]},
            "actions": [{"action_id": "reject_post", "value": "meme123"}]
        }
        response = client.post("/slack/actions", data={"payload": json.dumps(payload)})
        assert response.status_code == 200 # Still returns 200

def test_send_for_approval_api_error():
    """Test send_for_approval handles SlackApiError."""
    slack = SlackHITL()
    with patch.object(slack.client, 'chat_postMessage') as mock_post:
        from slack_sdk.errors import SlackApiError
        mock_post.side_effect = SlackApiError("API Error", MagicMock())
        slack.send_for_approval({"tweet_text": "A", "source_title": "B", "id": "1"})

def test_process_approval_instagram_errors():
    from nodes.node6_slack import process_approval
    from nodes.node7_instagram import InstagramPublishError
    blocks = [{"type": "section"}]
    
    with patch('nodes.node6_slack.instagram.publish_image') as mock_pub, \
         patch('nodes.node6_slack.slack_client.chat_update') as mock_upd:
         
         # InstagramPublishError
         mock_pub.side_effect = InstagramPublishError("Failed")
         process_approval("approve_post", blocks.copy(), "C1", "123", "m1", "url", "text", "link", "title")
         
         # Generic Exception
         mock_pub.side_effect = Exception("Failed")
         process_approval("approve_post", blocks.copy(), "C1", "123", "m1", "url", "text", "link", "title")

def test_slack_actions_valid_json_value():
    payload = {
        "type": "block_actions",
        "channel": {"id": "C123"},
        "message": {"ts": "123", "blocks": [{"type": "section"}]},
        "actions": [{"action_id": "approve_post", "value": '{"id": "test", "url": "http://img", "link": "http://link", "title": "t"}'}]
    }
    with patch('nodes.node6_slack.signature_verifier.is_valid_request', return_value=True):
        response = client.post("/slack/actions", data={"payload": json.dumps(payload)})
        assert response.status_code == 200

def test_slack_actions_uncaught_exception():
    with patch('nodes.node6_slack.signature_verifier.is_valid_request', side_effect=Exception("Unexpected")):
        response = client.post("/slack/actions", data={"payload": "{}"})
        assert response.status_code == 500
