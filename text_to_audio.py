import os
import requests
import urllib.parse
from config import VOICERSS_API_KEY  # Update your config.py to include this

# VoiceRSS API endpoint
VOICERSS_URL = "http://api.voicerss.org/"

def text_to_speech_file(text: str, folder: str) -> str:
    """
    Convert text to speech using VoiceRSS API and save as MP3 file
    """
    try:
        # VoiceRSS API parameters
        params = {
            'key': VOICERSS_API_KEY,
            'src': text,
            'hl': 'en-us',  # Language (English US)
            'v': 'Linda',   # Voice name (options: Linda, Amy, Mary, John, Mike, etc.)
            'r': '0',       # Speech rate (-10 to 10, 0 is normal)
            'c': 'mp3',     # Audio codec (mp3, wav, aac, ogg, caf)
            'f': '22khz_16bit_mono',  # Audio format
            'ssml': 'false',  # SSML support
            'b64': 'false'    # Base64 encoding
        }
        
        print(f"Generating audio for folder: {folder}")
        print(f"Text length: {len(text)} characters")
        
        # Make request to VoiceRSS API
        response = requests.get(VOICERSS_URL, params=params, timeout=30)
        
        # Check if request was successful
        if response.status_code == 200:
            # Check if response contains audio data (not error message)
            content_type = response.headers.get('content-type', '')
            if 'audio' in content_type or content_type == 'application/octet-stream':
                # Save audio file
                save_file_path = os.path.join(f"user_uploads/{folder}", "audio.mp3")
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
                
                with open(save_file_path, "wb") as f:
                    f.write(response.content)
                
                # Verify file was created and has content
                if os.path.exists(save_file_path) and os.path.getsize(save_file_path) > 0:
                    file_size = os.path.getsize(save_file_path)
                    print(f"{save_file_path}: Audio file saved successfully! ({file_size} bytes)")
                    return save_file_path
                else:
                    print(f"Error: Audio file was not created or is empty")
                    return None
            else:
                # Response contains error message
                error_message = response.text
                print(f"VoiceRSS API Error: {error_message}")
                return None
        else:
            print(f"HTTP Error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in text_to_speech_file: {e}")
        return None

# Alternative function with more voice options
def text_to_speech_file_advanced(text: str, folder: str, voice: str = 'Linda', language: str = 'en-us', rate: int = 0) -> str:
    """
    Advanced version with more customization options
    
    Available voices for English:
    - Linda (female, US)
    - Amy (female, UK) 
    - Mary (female, US)
    - John (male, US)
    - Mike (male, US)
    
    Available languages:
    - en-us (English US)
    - en-gb (English UK)
    - en-au (English Australia)
    - en-ca (English Canada)
    - en-in (English India)
    """
    try:
        params = {
            'key': VOICERSS_API_KEY,
            'src': text,
            'hl': language,
            'v': voice,
            'r': str(rate),  # Speech rate (-10 to 10)
            'c': 'mp3',
            'f': '22khz_16bit_mono',
            'ssml': 'false',
            'b64': 'false'
        }
        
        print(f"Generating audio for folder: {folder} (Voice: {voice}, Language: {language}, Rate: {rate})")
        
        response = requests.get(VOICERSS_URL, params=params, timeout=30)
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'audio' in content_type or content_type == 'application/octet-stream':
                save_file_path = os.path.join(f"user_uploads/{folder}", "audio.mp3")
                os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
                
                with open(save_file_path, "wb") as f:
                    f.write(response.content)
                
                if os.path.exists(save_file_path) and os.path.getsize(save_file_path) > 0:
                    file_size = os.path.getsize(save_file_path)
                    print(f"{save_file_path}: Audio file saved successfully! ({file_size} bytes)")
                    return save_file_path
                else:
                    print(f"Error: Audio file was not created or is empty")
                    return None
            else:
                error_message = response.text
                print(f"VoiceRSS API Error: {error_message}")
                return None
        else:
            print(f"HTTP Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error in text_to_speech_file_advanced: {e}")
        return None

# Test function (uncomment to test)
# if __name__ == "__main__":
#     test_text = "Hello, this is a test of VoiceRSS text to speech conversion."
#     test_folder = "test_folder"
#     os.makedirs(f"user_uploads/{test_folder}", exist_ok=True)
#     result = text_to_speech_file(test_text, test_folder)
#     print(f"Test result: {result}")