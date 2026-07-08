import sys
from config import settings
from nodes.node7_instagram import InstagramPublisher

def main():
    ig = InstagramPublisher()
    test_url = "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg"
    
    print("Testing Instagram Publisher with account ID:", settings.INSTAGRAM_ACCOUNT_ID)
    print("Token starts with:", settings.META_ACCESS_TOKEN[:10] if settings.META_ACCESS_TOKEN else "None")
    print(f"Testing with image URL: {test_url}")
    
    try:
        res = ig.publish_image(image_url=test_url, caption="Testing Meta Graph API Integration")
        print("SUCCESS! Response:", res)
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    main()
