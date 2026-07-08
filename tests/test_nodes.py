import pytest
from unittest.mock import patch, MagicMock, mock_open
from PIL import Image
from nodes.node2_bouncer import BounceFilter
from nodes.node3_brain import BrainNode
from nodes.node4_image import ImageNode
from pydantic_models import BrainOutput, JudgeOutput
import base64

def test_bouncer_rejects_tragedy(fake_trend):
    bouncer = BounceFilter()
    with patch('llm_client.get_completion') as mock_llm:
        mock_llm.return_value = {"is_relevant": False}
        result = bouncer.check_relevance(fake_trend)
        assert result is False
        mock_llm.assert_called_once()

def test_brain_judge_selects_winner(fake_trend):
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        # Return proper Pydantic objects instead of dictionaries
        mock_brain_output = BrainOutput(
            image_prompt="test prompt",
            candidates=["Option A", "Option B", "Option C"]
        )
        mock_judge_output = JudgeOutput(
            winning_tweet="Option B",
            reasoning="Because it is funny."
        )
        
        mock_llm.side_effect = [mock_brain_output, mock_judge_output]
        
        result = brain.generate(fake_trend)
        assert result["tweet_text"] == "Option B"
        assert result["image_prompt"] == "test prompt"
        assert mock_llm.call_count == 2

def test_vision_gate_rejects_text_image():
    image_node = ImageNode()
    with patch('llm_client.get_vision_validation') as mock_vision:
        # First call returns false, second returns true
        mock_vision_fail = MagicMock()
        mock_vision_fail.is_clean = False
        
        mock_vision_pass = MagicMock()
        mock_vision_pass.is_clean = True
        
        mock_vision.side_effect = [mock_vision_fail, mock_vision_pass]
        
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            fake_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            fake_b64 = base64.b64encode(fake_png_bytes).decode('utf-8')
            
            mock_post_resp = MagicMock()
            mock_post_resp.json.return_value = {"b64_json": fake_b64}
            mock_post.return_value = mock_post_resp
            
            mock_get_resp = MagicMock()
            mock_get_resp.content = fake_png_bytes
            mock_get.return_value = mock_get_resp
            
            with patch('builtins.open', mock_open(read_data=fake_png_bytes)):
                with patch('os.remove') as mock_remove:
                    with patch.object(Image.Image, 'save'):
                        result = image_node.generate_image("test prompt")
                
            assert mock_vision.call_count == 2
            assert mock_remove.call_count == 1  # Should remove the bad image on first attempt

def test_vision_gate_allows_clean_image():
    image_node = ImageNode()
    with patch('llm_client.get_vision_validation') as mock_vision:
        mock_vision_pass = MagicMock()
        mock_vision_pass.is_clean = True
        mock_vision.return_value = mock_vision_pass
        
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            fake_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            fake_b64 = base64.b64encode(fake_png_bytes).decode('utf-8')
            
            mock_post_resp = MagicMock()
            mock_post_resp.json.return_value = {"b64_json": fake_b64}
            mock_post.return_value = mock_post_resp
            
            mock_get_resp = MagicMock()
            mock_get_resp.content = fake_png_bytes
            mock_get.return_value = mock_get_resp
            
            with patch('builtins.open', mock_open(read_data=fake_png_bytes)):
                with patch('os.remove') as mock_remove:
                    with patch.object(Image.Image, 'save'):
                        result = image_node.generate_image("test prompt")
                
            assert mock_vision.call_count == 1
            assert mock_remove.call_count == 0  # Should not remove a good image

def test_brain_judge_fallback(fake_trend):
    """Test BrainNode uses fallback prompt if validation fails."""
    from pydantic import ValidationError
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_fallback = BrainOutput(image_prompt="fallback", candidates=["fallback 1", "fallback 2", "fallback 3"])
        
        # We need a proper ValidationError. Just mocking it as an Exception might not work 
        # if the code explicitly catches ValidationError. Let's create a real ValidationError
        from pydantic_core import InitErrorDetails
        ve = ValidationError.from_exception_data("error", line_errors=[])
        
        mock_llm.side_effect = [ve, mock_fallback]
        result = brain.generate(fake_trend)
        assert result["tweet_text"] == "fallback 1"

def test_brain_judge_failure_uses_first_candidate(fake_trend):
    """Test BrainNode uses first candidate if judge fails."""
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_brain = BrainOutput(image_prompt="img", candidates=["cand 1", "cand 2", "cand 3"])
        mock_llm.side_effect = [mock_brain, Exception("Judge failed")]
        result = brain.generate(fake_trend)
        assert result["tweet_text"] == "cand 1"

def test_image_node_nvidia_branch():
    """Test ImageNode NVIDIA branch success."""
    import config
    # Temporarily patch NVIDIA_API_KEY
    with patch.object(config.settings, 'NVIDIA_API_KEY', 'fake_key'):
        image_node = ImageNode()
        with patch('requests.post') as mock_post:
            fake_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            fake_b64 = base64.b64encode(fake_png_bytes).decode('utf-8')
            
            mock_post_resp = MagicMock()
            mock_post_resp.json.return_value = {"b64_json": fake_b64}
            mock_post.return_value = mock_post_resp
            
            with patch('llm_client.get_vision_validation') as mock_vision:
                mock_vision.return_value.is_clean = True
                
                with patch('builtins.open', mock_open(read_data=fake_png_bytes)):
                    with patch('os.remove'):
                        with patch.object(Image.Image, 'save'):
                            result = image_node.generate_image("prompt")
                            
            assert mock_post.call_count == 1

def test_brain_judge_fallback(fake_trend):
    """Test BrainNode uses fallback prompt if validation fails."""
    from pydantic import ValidationError
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_fallback = BrainOutput(image_prompt="fallback", candidates=["fallback 1", "fallback 2", "fallback 3"])
        
        # We need a proper ValidationError. Just mocking it as an Exception might not work 
        # if the code explicitly catches ValidationError. Let's create a real ValidationError
        from pydantic_core import InitErrorDetails
        ve = ValidationError.from_exception_data("error", line_errors=[])
        
        mock_llm.side_effect = [ve, mock_fallback]
        result = brain.generate(fake_trend)
        assert result["tweet_text"] == "fallback 1"

def test_brain_judge_failure_uses_first_candidate(fake_trend):
    """Test BrainNode uses first candidate if judge fails."""
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_brain = BrainOutput(image_prompt="img", candidates=["cand 1", "cand 2", "cand 3"])
        mock_llm.side_effect = [mock_brain, Exception("Judge failed")]
        result = brain.generate(fake_trend)
        assert result["tweet_text"] == "cand 1"

def test_image_node_nvidia_branch():
    """Test ImageNode NVIDIA branch success."""
    import config
    # Temporarily patch NVIDIA_API_KEY
    with patch.object(config.settings, 'NVIDIA_API_KEY', 'fake_key'):
        image_node = ImageNode()
        with patch('requests.post') as mock_post:
            fake_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            fake_b64 = base64.b64encode(fake_png_bytes).decode('utf-8')
            
            mock_post_resp = MagicMock()
            mock_post_resp.json.return_value = {"b64_json": fake_b64}
            mock_post.return_value = mock_post_resp
            
            with patch('llm_client.get_vision_validation') as mock_vision:
                mock_vision.return_value.is_clean = True
                
                with patch('builtins.open', mock_open(read_data=fake_png_bytes)):
                    with patch('os.remove'):
                        with patch.object(Image.Image, 'save'):
                            result = image_node.generate_image("prompt")
                            
            assert mock_post.call_count == 1
            assert result is not None

def test_image_node_all_attempts_fail():
    """Test ImageNode raises ImageGenerationError after 3 failed attempts."""
    from nodes.node4_image import ImageGenerationError
    image_node = ImageNode()
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        mock_get.side_effect = Exception("Network error")
        mock_post.side_effect = Exception("Network error")
        with patch('time.sleep'): # mock sleep so test is fast
            with pytest.raises(ImageGenerationError, match="Failed to generate"):
                image_node.generate_image("prompt")
    from nodes.node2_bouncer import BounceFilter
    with patch('llm_client.get_completion') as mock_llm:
        mock_llm.side_effect = Exception("Crash")
        bouncer = BounceFilter()
        assert bouncer.check_relevance({"title": "A", "summary": "B"}) is False

def test_brain_fallback_also_fails(fake_trend):
    """Test BrainNode returns hardcoded defaults when fallback generation also fails."""
    from pydantic import ValidationError
    ve = ValidationError.from_exception_data("error", line_errors=[])
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_llm.side_effect = [ve, Exception("Fallback died")]
        result = brain.generate(fake_trend)
        assert "Tech is crazy right now" in result["tweet_text"]

def test_brain_one_candidate(fake_trend):
    """Test BrainNode uses the only candidate if just one is returned."""
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_brain = MagicMock()
        mock_brain.candidates = ["only one"]
        mock_llm.return_value = mock_brain
        result = brain.generate(fake_trend)
        assert result["tweet_text"] == "only one"

def test_brain_truncates_long_tweet(fake_trend):
    """Test BrainNode truncates tweet if > 240 chars."""
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        long_tweet = "A" * 250 + " " + "B" * 10
        mock_brain = MagicMock()
        mock_brain.candidates = [long_tweet, "c", "d"]
        mock_llm.return_value = mock_brain
        result = brain.generate(fake_trend)
        assert len(result["tweet_text"]) <= 240

def test_image_node_pollinations_branch():
    """Test ImageNode uses Pollinations when NVIDIA key is not set."""
    import config
    with patch.object(config.settings, 'NVIDIA_API_KEY', ''):
        image_node = ImageNode()
        with patch('requests.get') as mock_get, patch('llm_client.get_vision_validation') as mock_vision:
            mock_get_resp = MagicMock()
            mock_get_resp.content = b'imagebytes'
            mock_get.return_value = mock_get_resp
            mock_vision.return_value.is_clean = True
            with patch('builtins.open', mock_open()), patch('os.remove'), patch.object(Image.Image, 'save'):
                result = image_node.generate_image("prompt")
                assert mock_get.call_count == 1
                assert result is not None

def test_image_node_nvidia_data_uri_and_value_error():
    """Test ImageNode NVIDIA parsing of data URI and missing data."""
    from nodes.node4_image import ImageGenerationError
    import config
    with patch.object(config.settings, 'NVIDIA_API_KEY', 'fake_key'):
        image_node = ImageNode()
        with patch('requests.post') as mock_post, patch('llm_client.get_vision_validation') as mock_vision:
            # 1. Test data URI format
            mock_post_resp = MagicMock()
            mock_post_resp.json.return_value = {"data": [{"url": "data:image/png,cGF5bG9hZA=="}]}
            mock_post.side_effect = [mock_post_resp, mock_post_resp] # For two calls?
            mock_vision.return_value.is_clean = True
            
            with patch('builtins.open', mock_open()), patch('os.remove'):
                result = image_node.generate_image("prompt")
                assert result is not None
                
            # 2. Test ValueError when no image data
            mock_post_resp2 = MagicMock()
            mock_post_resp2.json.return_value = {"empty": "data"}
            mock_post.side_effect = [mock_post_resp2, mock_post_resp2, mock_post_resp2]
            with patch('time.sleep'):
                with pytest.raises(ImageGenerationError):
                    image_node.generate_image("prompt")

def test_image_node_returns_last_image_on_vision_api_failure():
    """Test ImageNode returns last_image_data if vision API fails 3 times."""
    import config
    with patch.object(config.settings, 'NVIDIA_API_KEY', 'fake_key'):
        image_node = ImageNode()
        with patch('requests.post') as mock_post, patch('llm_client.get_vision_validation') as mock_vision:
            mock_post_resp = MagicMock()
            mock_post_resp.json.return_value = {"b64_json": "cGF5bG9hZA=="}
            mock_post.return_value = mock_post_resp
            mock_vision.side_effect = Exception("Vision API down")
    from nodes.node2_bouncer import BounceFilter
    with patch('llm_client.get_completion') as mock_llm:
        mock_llm.side_effect = Exception("Crash")
        bouncer = BounceFilter()
        assert bouncer.check_relevance({"title": "A", "summary": "B"}) is False

def test_brain_fallback_also_fails(fake_trend):
    """Test BrainNode returns hardcoded defaults when fallback generation also fails."""
    from pydantic import ValidationError
    ve = ValidationError.from_exception_data("error", line_errors=[])
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_llm.side_effect = [ve, Exception("Fallback died")]
        result = brain.generate(fake_trend)
        assert "Tech is crazy right now" in result["tweet_text"]

def test_brain_one_candidate(fake_trend):
    """Test BrainNode uses the only candidate if just one is returned."""
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_brain = MagicMock()
        mock_brain.candidates = ["only one"]
        mock_llm.return_value = mock_brain
        result = brain.generate(fake_trend)
        assert result["tweet_text"] == "only one"

def test_brain_truncates_long_tweet(fake_trend):
    """Test BrainNode truncates tweet if > 240 chars."""
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        long_tweet = "A" * 250 + " " + "B" * 10
        mock_brain = MagicMock()
        mock_brain.candidates = [long_tweet]
        mock_llm.return_value = mock_brain
        result = brain.generate(fake_trend)
        assert len(result["tweet_text"]) <= 240

def test_brain_generation_exception(fake_trend):
    """Test BrainNode raises Exception on complete failure."""
    brain = BrainNode()
    with patch('llm_client.get_completion') as mock_llm:
        mock_llm.side_effect = Exception("Total fail")
        with pytest.raises(Exception):
            brain.generate(fake_trend)

def test_image_node_pollinations_branch():
    """Test ImageNode uses Pollinations when NVIDIA key is not set."""
    import config
    with patch.object(config.settings, 'NVIDIA_API_KEY', ''):
        image_node = ImageNode()
        with patch('requests.get') as mock_get, patch('llm_client.get_vision_validation') as mock_vision:
            mock_get_resp = MagicMock()
            mock_get_resp.content = b'imagebytes'
            mock_get.return_value = mock_get_resp
            mock_vision.return_value.is_clean = True
            with patch('builtins.open', mock_open()), patch('os.remove'), patch.object(Image.Image, 'save'):
                result = image_node.generate_image("prompt")
                assert mock_get.call_count == 1
                assert result is not None

def test_image_node_nvidia_data_uri_and_value_error():
    """Test ImageNode NVIDIA parsing of data URI and missing data."""
    from nodes.node4_image import ImageGenerationError
    import config
    with patch.object(config.settings, 'NVIDIA_API_KEY', 'fake_key'):
        image_node = ImageNode()
        with patch('requests.post') as mock_post, patch('llm_client.get_vision_validation') as mock_vision:
            # 1. Test data URI format
            mock_post_resp = MagicMock()
            mock_post_resp.json.return_value = {"data": [{"url": "data:image/png,cGF5bG9hZA=="}]}
            mock_post.side_effect = [mock_post_resp, mock_post_resp] # For two calls?
            mock_vision.return_value.is_clean = True
            
            with patch('builtins.open', mock_open()), patch('os.remove'):
                result = image_node.generate_image("prompt")
                assert result is not None
                
            # 2. Test ValueError when no image data
            mock_post_resp2 = MagicMock()
            mock_post_resp2.json.return_value = {"empty": "data"}
            mock_post.side_effect = [mock_post_resp2, mock_post_resp2, mock_post_resp2]
            with patch('time.sleep'), patch('requests.get', side_effect=Exception("Pollinations API down")):
                with pytest.raises(ImageGenerationError):
                    image_node.generate_image("prompt")

def test_image_node_returns_last_image_on_vision_api_failure():
    """Test ImageNode returns last_image_data if vision API fails 3 times."""
    import config
    with patch.object(config.settings, 'NVIDIA_API_KEY', 'fake_key'):
        image_node = ImageNode()
        with patch('requests.post') as mock_post, patch('llm_client.get_vision_validation') as mock_vision:
            mock_post_resp = MagicMock()
            mock_post_resp.json.return_value = {"b64_json": "cGF5bG9hZA=="}
            mock_post.return_value = mock_post_resp
            mock_vision.side_effect = Exception("Vision API down")
            with patch('builtins.open', mock_open()), patch('time.sleep'), patch('requests.get', side_effect=Exception("Pollinations API down")):
                result = image_node.generate_image("prompt")
                assert result is not None
                assert "cGF5bG9hZA==" in result["data_url"]

def test_image_node_503_wait_time():
    """Test ImageNode wait time is 20s for 503 errors."""
    from nodes.node4_image import ImageGenerationError
    import config
    with patch.object(config.settings, 'NVIDIA_API_KEY', ''):
        image_node = ImageNode()
        with patch('requests.get') as mock_get, patch('time.sleep') as mock_sleep:
            mock_get.side_effect = Exception("Error 503 Service Unavailable")
            with pytest.raises(ImageGenerationError):
                image_node.generate_image("prompt")
            mock_sleep.assert_called_with(20)

def test_run_pipeline_calls_compositor():
    """Mock compositor.add_text_to_image and verify it is called when local_path is present."""
    from main import run_pipeline, compositor
    fake_trend = {"title": "Test Trend", "summary": "Test Summary"}
    
    with patch('main.bouncer.check_relevance') as mock_bouncer, \
         patch('main.brain.generate') as mock_brain, \
         patch('main.image_gen.generate_image') as mock_image_gen, \
         patch('main.slack.send_for_approval') as mock_slack, \
         patch.object(compositor, 'add_text_to_image') as mock_compositor, \
         patch('builtins.open', mock_open(read_data=b'dummydata')):
         
        mock_bouncer.return_value = True
        mock_brain.return_value = {"tweet_text": "funny tweet", "image_prompt": "funny image"}
        mock_image_gen.return_value = {"image_url": "http://img", "local_path": "/tmp/img.png", "data_url": "data:image"}
        
        mock_composited_img = MagicMock()
        mock_compositor.return_value = mock_composited_img
        
        run_pipeline(fake_trend)
        
        # Verify compositor was called
        mock_compositor.assert_called_once_with("/tmp/img.png", "funny tweet")
        mock_composited_img.save.assert_called_once_with("/tmp/img.jpg", format="JPEG", quality=90)
        mock_slack.assert_called_once()

def test_run_pipeline_compositor_failure_does_not_abort():
    """When compositor raises Exception, pipeline should continue and call slack.send_for_approval."""
    from main import run_pipeline, compositor
    fake_trend = {"title": "Test Trend", "summary": "Test Summary"}
    
    with patch('main.bouncer.check_relevance') as mock_bouncer, \
         patch('main.brain.generate') as mock_brain, \
         patch('main.image_gen.generate_image') as mock_image_gen, \
         patch('main.slack.send_for_approval') as mock_slack, \
         patch.object(compositor, 'add_text_to_image') as mock_compositor:
         
        mock_bouncer.return_value = True
        mock_brain.return_value = {"tweet_text": "funny tweet", "image_prompt": "funny image"}
        mock_image_gen.return_value = {"image_url": "http://img", "local_path": "/tmp/img.png", "data_url": "data:image"}
        
        # Make compositor crash
        mock_compositor.side_effect = Exception("Compositor crash!")
        
        run_pipeline(fake_trend)
        
        # Pipeline should continue to slack
        mock_slack.assert_called_once()
        payload = mock_slack.call_args[0][0]
        assert payload["data_url"] == "data:image" # retains raw data_url

def test_image_node_nsfw_black_image():
    from nodes.node4_image import ImageNode, ImageGenerationError
    node = ImageNode()
    with patch('requests.post') as mock_post, \
         patch('builtins.open', mock_open()), \
         patch('nodes.node4_image.Image.open') as mock_image_open, \
         patch('os.remove'), \
         patch('time.sleep'), \
         patch('nodes.node4_image.settings.NVIDIA_API_KEY', "test_key"):
         
         mock_resp = MagicMock()
         mock_resp.json.return_value = {"b64_json": "YmFzZTY0"}
         mock_post.return_value = mock_resp
         
         mock_img = MagicMock()
         mock_img.convert.return_value.getextrema.return_value = (0, 0)
         mock_img.getbbox.return_value = None
         mock_image_open.return_value.__enter__.return_value = mock_img
         
         with pytest.raises(ImageGenerationError):
             node.generate_image("test")
