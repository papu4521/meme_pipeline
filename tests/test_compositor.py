import pytest
from unittest.mock import patch, MagicMock
from nodes.compositor import MemeCompositor
import nodes.compositor as compositor_module
from PIL import Image
import tempfile
import os
import importlib

@pytest.fixture(autouse=True)
def reload_compositor():
    """Reload the compositor module before each test to prevent stale imports and patching issues."""
    importlib.reload(compositor_module)
    yield

def test_add_text_to_image():
    """Test that MemeCompositor adds text to an image without crashing and returns a PIL Image."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        # Create a real PIL Image instead of a mock so ImageDraw works
        real_img = Image.new('RGB', (800, 600), color='black')
        mock_open.return_value = real_img
        
        result = compositor.add_text_to_image("dummy.png", "Meme text")
        assert result is not None
        assert result.size == (800, 600)

def test_add_text_to_image_wrap_exact_division():
    """Test text that divides exactly evenly into max_width chunks."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        real_img = Image.new('RGB', (800, 600), color='black')
        mock_open.return_value = real_img
        # Assuming avg char width is ~20, chars_per_line = max(10, 800/20 - 2) = 38
        text = "a" * 38 + " " + "b" * 38
        result = compositor.add_text_to_image("dummy.png", text)
        assert result is not None

def test_add_text_to_image_empty_string():
    """Test text with empty string input."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        real_img = Image.new('RGB', (800, 600), color='black')
        mock_open.return_value = real_img
        result = compositor.add_text_to_image("dummy.png", "")
        assert result is not None

def test_add_text_to_image_real_file():
    """Test when the image file EXISTS with a real temp PIL image saved to disk."""
    compositor = MemeCompositor()
    tmp_name = ""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_name = tmp.name
    
    try:
        real_img = Image.new('RGB', (100, 100), color='black')
        real_img.save(tmp_name)
        result = compositor.add_text_to_image(tmp_name, "Test")
        assert result.size == (100, 100)
    finally:
        os.remove(tmp_name)

def test_add_text_to_image_truetype_success():
    """Test when truetype font loads successfully."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        real_img = Image.new('RGB', (800, 600), color='black')
        mock_open.return_value = real_img
        with patch('nodes.compositor.ImageFont.truetype') as mock_truetype, patch('nodes.compositor.ImageDraw.Draw') as mock_draw:
            mock_font = MagicMock()
            mock_font.getlength.return_value = 10
            mock_font.getbbox.return_value = (0, 0, 10, 10)
            mock_truetype.return_value = mock_font
            
            # Since we mock ImageDraw.Draw completely here, it won't crash on draw.text()
            # but we can also just let it patch and ensure no unpacked values crash occurs.
            result = compositor.add_text_to_image("dummy.png", "Meme text")
            assert result is not None
            mock_truetype.assert_called_once()

def test_add_text_to_image_verifies_content():
    """Test verifies the returned image has content (size is not 0x0, mode is RGB)."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        real_img = Image.new('RGB', (800, 600), color='black')
        mock_open.return_value = real_img
        result = compositor.add_text_to_image("dummy.png", "Meme text")
        assert result.size[0] > 0
        assert result.size[1] > 0
        assert result.mode == 'RGB'

def test_add_text_to_image_font_fallbacks():
    """Test font fallbacks (size default, and no-size default)."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        mock_open.return_value = Image.new('RGB', (800, 600), color='black')
        
        with patch('nodes.compositor.ImageFont.truetype', side_effect=Exception("No TTF")), \
             patch('nodes.compositor.ImageFont.load_default') as mock_default, \
             patch('nodes.compositor.ImageDraw.Draw'):
             
             # Test fallback to load_default(size)
             compositor.add_text_to_image("dummy.png", "Text")
             mock_default.assert_called_with(size=40)
             
             # Test fallback to load_default() when size fails
             mock_default.side_effect = [Exception("No size arg"), MagicMock()]
             compositor.add_text_to_image("dummy.png", "Text")
             assert mock_default.call_count == 3 # 1 for first test, 2 for second test

def test_add_text_to_image_getlength_fallback():
    """Test fallback when getlength fails on character width."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        mock_open.return_value = Image.new('RGB', (800, 600), color='black')
        with patch('nodes.compositor.ImageFont.truetype') as mock_truetype, patch('nodes.compositor.ImageDraw.Draw'):
            mock_font = MagicMock()
            mock_font.getlength.side_effect = Exception("No getlength")
            mock_font.getbbox.return_value = (0, 0, 10, 10)
            mock_truetype.return_value = mock_font
            
            result = compositor.add_text_to_image("dummy.png", "Long text that wraps")
            assert result is not None

def test_compositor_white_text():
    """Verify the function doesn't crash when draw.text is called with white fill."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        mock_open.return_value = Image.new('RGB', (800, 600), color='black')
        with patch('nodes.compositor.ImageFont.truetype') as mock_truetype, patch('nodes.compositor.ImageDraw.Draw') as mock_draw:
            mock_font = MagicMock()
            mock_font.getlength.return_value = 10
            mock_font.getbbox.return_value = (0, 0, 10, 10)
            mock_truetype.return_value = mock_font
            
            mock_draw_instance = MagicMock()
            mock_draw.return_value = mock_draw_instance
            
            result = compositor.add_text_to_image("dummy.png", "Text")
            assert result is not None
            
            # Find the text call and verify it uses fill="white"
            called_with_white = False
            for call in mock_draw_instance.text.call_args_list:
                if call.kwargs.get("fill") == "white":
                    called_with_white = True
                    break
            assert called_with_white

def test_compositor_adds_black_bar():
    """Verify the bottom portion of the returned image has dark pixels."""
    compositor = MemeCompositor()
    tmp_name = ""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_name = tmp.name
    
    try:
        # Create a pure white image
        real_img = Image.new('RGB', (400, 400), color='white')
        real_img.save(tmp_name)
        
        # Add text
        result = compositor.add_text_to_image(tmp_name, "Test text")
        
        # Check a pixel near the bottom (where the black bar should be)
        # The bar is semi-transparent black (0,0,0,160) blended with white (255,255,255)
        # So it should be dark gray, not pure white
        bottom_pixel = result.getpixel((200, 390))
        assert bottom_pixel[0] < 255 # Should be darkened
        assert bottom_pixel[1] < 255
        assert bottom_pixel[2] < 255
    finally:
        os.remove(tmp_name)

def test_compositor_getbbox_and_getlength_fallbacks():
    """Verify that font size is used for height when getbbox fails (lines 35-36), 
    and character estimation is used for width when both getbbox and getlength fail (lines 62-66)."""
    compositor = MemeCompositor()
    with patch('nodes.compositor.Image.open') as mock_open:
        mock_open.return_value = Image.new('RGB', (800, 600), color='black')
        with patch('nodes.compositor.ImageFont.truetype') as mock_truetype, patch('nodes.compositor.ImageDraw.Draw'):
            mock_font = MagicMock()
            
            # Make getbbox fail to hit lines 35-36 and line 62
            mock_font.getbbox.side_effect = Exception("No bbox")
            
            # Make getlength fail to hit lines 64-66
            mock_font.getlength.side_effect = Exception("No getlength")
            
            mock_truetype.return_value = mock_font
            
            # Since the fallbacks return estimated heights and widths, it shouldn't crash
            result = compositor.add_text_to_image("dummy.png", "Text")
            assert result is not None
