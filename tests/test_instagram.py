import pytest
from unittest.mock import patch, MagicMock, mock_open
from httpx import Response
from nodes.node7_instagram import InstagramPublisher, InstagramAuthError, InstagramRateLimitError, InstagramPublishError

@pytest.fixture
def mock_config():
    with patch('nodes.node7_instagram.settings') as mock_settings:
        mock_settings.INSTAGRAM_ACCOUNT_ID = "12345"
        mock_settings.META_ACCESS_TOKEN = "abcde"
        yield mock_settings

def test_publish_image_success(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get:
         
         # Mock Step A: Create container
         mock_post_create = MagicMock(spec=Response)
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "container_123"}
         
         # Mock Step C: Publish container
         mock_post_publish = MagicMock(spec=Response)
         mock_post_publish.status_code = 200
         mock_post_publish.json.return_value = {"id": "media_789"}
         
         mock_post.side_effect = [mock_post_create, mock_post_publish]
         
         # Mock Step B: Poll status
         mock_get_status = MagicMock(spec=Response)
         mock_get_status.status_code = 200
         mock_get_status.json.return_value = {"status_code": "FINISHED"}
         mock_get.return_value = mock_get_status
         
         result = instagram.publish_image("http://public.com/image.png", "A funny meme")
         
         assert result == {"instagram_media_id": "media_789"}
         assert mock_post.call_count == 2
         assert mock_get.call_count == 1

def test_publish_image_polls_until_ready(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get, \
         patch('nodes.node7_instagram.time.sleep'):
         
         mock_post_create = MagicMock(spec=Response)
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "container_123"}
         
         mock_post_publish = MagicMock(spec=Response)
         mock_post_publish.status_code = 200
         mock_post_publish.json.return_value = {"id": "media_789"}
         
         mock_post.side_effect = [mock_post_create, mock_post_publish]
         
         mock_get_status_1 = MagicMock(spec=Response)
         mock_get_status_1.status_code = 200
         mock_get_status_1.json.return_value = {"status_code": "IN_PROGRESS"}
         
         mock_get_status_2 = MagicMock(spec=Response)
         mock_get_status_2.status_code = 200
         mock_get_status_2.json.return_value = {"status_code": "IN_PROGRESS"}
         
         mock_get_status_3 = MagicMock(spec=Response)
         mock_get_status_3.status_code = 200
         mock_get_status_3.json.return_value = {"status_code": "FINISHED"}
         
         mock_get.side_effect = [mock_get_status_1, mock_get_status_2, mock_get_status_3]
         
         result = instagram.publish_image("http://public.com/img.png", "Caption")
         
         assert result == {"instagram_media_id": "media_789"}
         assert mock_get.call_count == 3

def test_publish_image_auth_error(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post:
         mock_err = MagicMock(spec=Response)
         mock_err.status_code = 401
         mock_err.json.return_value = {"error": {"message": "Invalid OAuth"}}
         mock_post.return_value = mock_err
         
         with pytest.raises(InstagramAuthError):
             instagram.publish_image("http://public.com/img.png", "Caption")

def test_publish_image_rate_limit(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post:
         mock_err = MagicMock(spec=Response)
         mock_err.status_code = 429
         mock_err.json.return_value = {"error": {"message": "Rate limit", "code": 4}}
         mock_post.return_value = mock_err
         
         with pytest.raises(InstagramRateLimitError):
             instagram.publish_image("http://public.com/img.png", "Caption")

def test_publish_image_timeout(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get, \
         patch('nodes.node7_instagram.time.sleep'):
         
         mock_post_create = MagicMock(spec=Response)
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "container_123"}
         mock_post.return_value = mock_post_create
         
         mock_get_status = MagicMock(spec=Response)
         mock_get_status.status_code = 200
         mock_get_status.json.return_value = {"status_code": "IN_PROGRESS"}
         mock_get.return_value = mock_get_status
         
         with pytest.raises(InstagramPublishError, match="did not reach FINISHED"):
             instagram.publish_image("http://public.com/img.png", "Caption")
             
         assert mock_get.call_count == 10

def test_publish_image_publish_step_fails(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get:
         
         mock_post_create = MagicMock(spec=Response)
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "container_123"}
         
         mock_post_publish = MagicMock(spec=Response)
         mock_post_publish.status_code = 500
         mock_post_publish.json.return_value = {"error": {"message": "Internal error"}}
         
         mock_post.side_effect = [mock_post_create, mock_post_publish]
         
         mock_get_status = MagicMock(spec=Response)
         mock_get_status.status_code = 200
         mock_get_status.json.return_value = {"status_code": "FINISHED"}
         mock_get.return_value = mock_get_status
         
         with pytest.raises(InstagramPublishError):
             instagram.publish_image("http://public.com/img.png", "Caption")

def test_localhost_url_rejected(mock_config):
    instagram = InstagramPublisher()
    with pytest.raises(ValueError, match="publicly accessible"):
        instagram.publish_image("http://localhost:8000/image.png", "Caption")
    with pytest.raises(ValueError, match="publicly accessible"):
        instagram.publish_image("data:image/png;base64,123", "Caption")

def test_missing_credentials(mock_config):
    mock_config.INSTAGRAM_ACCOUNT_ID = ""
    instagram = InstagramPublisher()
    with pytest.raises(InstagramAuthError, match="Missing INSTAGRAM_ACCOUNT_ID"):
        instagram.publish_image("http://public.com/img.png", "Caption")

def test_missing_creation_id(mock_config):
    instagram = InstagramPublisher()
    with patch('nodes.node7_instagram.httpx.post') as mock_post:
        mock_post_create = MagicMock(spec=Response)
        mock_post_create.status_code = 200
        mock_post_create.json.return_value = {} # missing id
        mock_post.return_value = mock_post_create
        
        with pytest.raises(InstagramPublishError, match="Failed to get creation_id"):
            instagram.publish_image("http://public.com/img.png", "Caption")

def test_container_status_error(mock_config):
    instagram = InstagramPublisher()
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get:
         
         mock_post_create = MagicMock(spec=Response)
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "container_123"}
         mock_post.return_value = mock_post_create
         
         mock_get_status = MagicMock(spec=Response)
         mock_get_status.status_code = 200
         mock_get_status.json.return_value = {"status_code": "ERROR"}
         mock_get.return_value = mock_get_status
         
         with pytest.raises(InstagramPublishError, match="failed processing"):
             instagram.publish_image("http://public.com/img.png", "Caption")

def test_missing_media_id(mock_config):
    instagram = InstagramPublisher()
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get:
         
         mock_post_create = MagicMock(spec=Response)
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "container_123"}
         
         mock_post_publish = MagicMock(spec=Response)
         mock_post_publish.status_code = 200
         mock_post_publish.json.return_value = {} # missing id
         
         mock_post.side_effect = [mock_post_create, mock_post_publish]
         
         mock_get_status = MagicMock(spec=Response)
         mock_get_status.status_code = 200
         mock_get_status.json.return_value = {"status_code": "FINISHED"}
         mock_get.return_value = mock_get_status
         
         with pytest.raises(InstagramPublishError, match="Failed to get published media ID"):
             instagram.publish_image("http://public.com/img.png", "Caption")

def test_handle_error_invalid_json(mock_config):
    instagram = InstagramPublisher()
    with patch('nodes.node7_instagram.httpx.post') as mock_post:
        mock_err = MagicMock(spec=Response)
        mock_err.status_code = 500
        mock_err.json.side_effect = ValueError("Invalid JSON")
        mock_err.text = "Bad Gateway"
        mock_post.return_value = mock_err
        
        with pytest.raises(InstagramPublishError, match="Publish error 500"):
            instagram.publish_image("http://public.com/img.png", "Caption")

def test_container_status_http_error(mock_config):
    instagram = InstagramPublisher()
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get:
         
         mock_post_create = MagicMock()
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "123"}
         mock_post.return_value = mock_post_create
         
         mock_get_status = MagicMock()
         mock_get_status.status_code = 500
         mock_get_status.text = "Server error"
         mock_get.return_value = mock_get_status
         
         with pytest.raises(InstagramPublishError):
             instagram.publish_image("http://public.com/img.png", "Caption")

def test_catbox_bypass_success(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get, \
         patch('builtins.open', mock_open(read_data=b'dummy')):
         
         # Mock catbox.moe response
         mock_catbox = MagicMock()
         mock_catbox.status_code = 200
         mock_catbox.text = "http://catbox.moe/image.jpg"
         
         # Mock Instagram Create
         mock_post_create = MagicMock()
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "123"}
         
         # Mock Instagram Publish
         mock_post_publish = MagicMock()
         mock_post_publish.status_code = 200
         mock_post_publish.json.return_value = {"id": "media_789"}
         
         mock_post.side_effect = [mock_catbox, mock_post_create, mock_post_publish]
         
         # Mock Instagram Status
         mock_get_status = MagicMock()
         mock_get_status.status_code = 200
         mock_get_status.json.return_value = {"status_code": "FINISHED"}
         mock_get.return_value = mock_get_status
         
         result = instagram.publish_image("http://trycloudflare.com/img.png", "Caption", local_path="/tmp/img.jpg")
         
         assert result == {"instagram_media_id": "media_789"}
         # catbox bypass should modify the url passed to Instagram Create
         create_call_args = mock_post.call_args_list[1]
         assert create_call_args[1]["data"]["image_url"] == "http://catbox.moe/image.jpg"

def test_catbox_bypass_failure(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('builtins.open', mock_open(read_data=b'dummy')):
         
         # Mock catbox.moe response failure (e.g. 500 or Exception)
         mock_post.side_effect = Exception("Catbox down!")
         
         with pytest.raises(InstagramPublishError, match="Local bypass upload failed:"):
             instagram.publish_image("http://trycloudflare.com/img.png", "Caption", local_path="/tmp/img.jpg")

def test_catbox_bypass_fallback_local_path(mock_config):
    instagram = InstagramPublisher()
    
    with patch('nodes.node7_instagram.httpx.post') as mock_post, \
         patch('nodes.node7_instagram.httpx.get') as mock_get, \
         patch('builtins.open', mock_open(read_data=b'dummy')), \
         patch('os.path.exists', return_value=True):
         
         mock_catbox = MagicMock()
         mock_catbox.status_code = 200
         mock_catbox.text = "http://catbox.moe/image.jpg"
         
         mock_post_create = MagicMock()
         mock_post_create.status_code = 200
         mock_post_create.json.return_value = {"id": "123"}
         
         mock_post_publish = MagicMock()
         mock_post_publish.status_code = 200
         mock_post_publish.json.return_value = {"id": "media_789"}
         
         mock_post.side_effect = [mock_catbox, mock_post_create, mock_post_publish]
         mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status_code": "FINISHED"})
         
         result = instagram.publish_image("http://trycloudflare.com/images/1234.jpg", "Caption")
         
         assert result == {"instagram_media_id": "media_789"}
         create_call_args = mock_post.call_args_list[1]
         assert create_call_args[1]["data"]["image_url"] == "http://catbox.moe/image.jpg"
