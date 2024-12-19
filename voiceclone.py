import os
import sys
import argparse
import subprocess
from pathlib import Path
from elevenlabs import Voice, VoiceSettings
from elevenlabs.client import ElevenLabs
from typing import List, Optional
import requests
from utils import upload_to_fileio
import time


def generate_and_download_avatar(image_url: str, audio_url: str, output_path: str, 
                               token: str = "sk-78dec05e-dbe0-436f-beca-268dcb54968b",
                               resolution: str = "320",
                               expressiveness: float = 0.5,
                               max_retries: int = 30,
                               retry_delay: int = 5) -> Optional[str]:
    """
    Generate an avatar video and download it to the specified path.
    
    Args:
        image_url: URL of the source image
        audio_url: URL of the audio file
        output_path: Local path where the video should be saved
        token: API authentication token
        resolution: Video resolution
        expressiveness: Avatar expressiveness (0.0 to 1.0)
        max_retries: Maximum number of times to check job status
        retry_delay: Seconds to wait between status checks
    
    Returns:
        str: Path to downloaded file if successful, None if failed
    """
    # Initialize the generation
    generate_url = "https://infinity.ai/api/v2/generate"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
        "content-type": "application/json"
    }
    
    data = {
        "resolution": resolution,
        "crop_head": False,
        "expressiveness": expressiveness,
        "img_url": image_url,
        "audio_url": audio_url
    }
    
    try:
        # Start the generation job
        response = requests.post(generate_url, headers=headers, json=data)
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data.get('job_id')
        
        if not job_id:
            print("Error: No job ID received")
            return None
        
        # Poll for job completion
        job_url = f"https://infinity.ai/api/v2/generations/{job_id}"
        poll_headers = {"authorization": f"Bearer {token}"}
        
        for attempt in range(max_retries):
            response = requests.get(job_url, headers=poll_headers)
            response.raise_for_status()
            status_data = response.json()
            print(f"Attempt {attempt + 1}: {status_data}")
            if status_data.get('status') == 'completed':
                video_url = status_data.get('video_url')
                if video_url:
                    # Download the video
                    video_response = requests.get(video_url)
                    video_response.raise_for_status()
                    
                    with open(output_path, 'wb') as f:
                        f.write(video_response.content)
                    
                    print(f"Video successfully downloaded to {output_path}")
                    return output_path
                else:
                    print("Error: No video URL in completed job")
                    return None
            
            elif status_data.get('status') == 'failed':
                print("Job failed")
                return None
            
            print(f"Job in progress, checking again in {retry_delay} seconds...")
            time.sleep(retry_delay)
        
        print(f"Timeout after {max_retries} attempts")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None

def generate_avatar_from_files(image_path: str, audio_path: str, output_path: str):
    t_last = time.time()
    audio_url = upload_to_fileio(audio_path)
    print(f"Audio upload took {time.time() - t_last:.2f} seconds")
    t_last = time.time()
    image_url = upload_to_fileio(image_path)
    print(f"Image upload took {time.time() - t_last:.2f} seconds")
    t_last = time.time()
    generate_and_download_avatar(image_url, audio_url, output_path)
    print(f"Avatar generation took {time.time() - t_last:.2f} seconds")


def text_to_audio(client, text: str, voice_id: str, output_path: str) -> None:
    """
    Convert text to speech using ElevenLabs and create an MP4 video file.
    
    Args:
        text: The text to convert to speech
        voice_name: The ElevenLabs voice identifier to use
        output_path: Path where the final .mp4 file should be saved
    """
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Generate temporary paths
    # temp_audio = f"/tmp/{Path(output_path).stem}_temp.mp3"
    
    try:
        # Generate speech using ElevenLabs
        audio_generator = client.generate(
            text=text,
            voice=Voice(
                voice_id=voice_id, 
                settings=VoiceSettings(stability=1.0, similarity_boost=1.0, style=0.8, use_speaker_boost=True)),
            model="eleven_multilingual_v2"
        )
        
        # Convert generator to bytes
        audio_bytes = b"".join(chunk for chunk in audio_generator)
        
        # Save the audio file
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        
        # # Convert to video using ffmpeg with MP4 settings
        # cmd = [
        #     'ffmpeg',
        #     '-y',  # Overwrite output file if it exists
        #     '-f', 'lavfi',  # Input is a filter
        #     '-i', 'color=c=black:s=1920x1080',  # Create black background
        #     '-i', temp_audio,  # Input audio file
        #     '-shortest',  # Duration determined by shortest input
        #     '-c:v', 'libx264',  # Video codec
        #     '-tune', 'stillimage',  # Optimize for still image
        #     '-c:a', 'aac',  # Audio codec
        #     '-b:a', '192k',  # Audio bitrate
        #     '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
        #     '-movflags', '+faststart',  # Optimize for web playback
        #     '-profile:v', 'baseline',  # Most compatible H.264 profile
        #     '-level', '3.0',  # Compatible H.264 level
        #     output_path
        # ]
        
        # # Run ffmpeg command
        # subprocess.run(cmd, check=True)
        
    except Exception as e:
        print(f"Error processing {output_path}: {e}")
        raise
    
    # finally:
        # Clean up temporary file
        # if os.path.exists(temp_audio):
        #     os.remove(temp_audio)

def text_to_video(client, text: str, image_path: str, voice_id: str, output_path: str) -> None:
    tmp_path = "/tmp/temp.mp3"
    try:
        text_to_audio(client, text, voice_id, tmp_path)
        generate_avatar_from_files(image_path, tmp_path, output_path)
        os.remove(tmp_path)
    except Exception as e:
        print(f"Error processing {output_path}, text='{text}', voiceId={voice_id}: {e}")
        raise

def process_input_file(file_path: str) -> List[str]:
    """
    Read and parse the input file.
    Returns a list containing [voice_name, text] or [voice_name, new_joke_text, prompt_joke_text, caption_text]
    depending on the file format
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        parts = content.split('====')
        if len(parts) == 2:  # Simple format: just voice_id and text
            return [part.strip() for part in parts]
        elif len(parts) == 5:  # Original format with multiple sections
            return [part.strip() for part in parts]
        else:
            raise ValueError("Input file must contain either 2 or 4 sections separated by '===='")
        
    except Exception as e:
        print(f"Error reading input file: {e}")
        raise

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert text to speech and create videos')
    parser.add_argument('input_file', nargs='?', default='HUMAN_NOW.txt', 
                       help='Path to input file (default: HUMAN_NOW.txt)')
    args = parser.parse_args()
    
    # Check for API key in environment
    api_key = os.environ.get('ELEVENLABS_API_KEY')
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY environment variable must be set")
    
    # Set API key
    client = ElevenLabs(api_key=api_key)
    print("API key set")
    
    try:
        # Read and parse input file
        parts = process_input_file(args.input_file)
        
        # Create output directory if it doesn't exist
        output_dir = 'output'
        Path(output_dir).mkdir(exist_ok=True)
        
        if len(parts) == 2:  # Simple format
            voice_name, text = parts
            output_path = 'output/HUMAN_NOW.mp4' if args.input_file == 'HUMAN_NOW.txt' else f"{output_dir}/{voice_name}_output.mp4"
            print(f"Processing {output_path}...")
            text_to_audio(client, text, voice_name, output_path)
            print(f"Completed {output_path}")
        else:  # Original format with multiple sections
            voice_id, voice_name, new_joke_text, prompt_joke_text, caption_text = parts
            # Process each text section with .mp4 extension
            tasks = [
                (new_joke_text, f"{output_dir}/{voice_name}_new_joke.mp4"),
                (prompt_joke_text, f"{output_dir}/{voice_name}_prompt_joke.mp4"),
                (caption_text, f"{output_dir}/{voice_name}_caption.mp4")
            ]
            
            # Generate videos for each section
            for text, output_path in tasks:
                print(f"Processing {output_path}...")
                text_to_audio(client, text, voice_id, output_path)
                print(f"Completed {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    image_path = "blake.jpeg"
    output_path = "avatar_output.mp4"
    api_key = os.environ.get('ELEVENLABS_API_KEY')
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY environment variable must be set")
    
    # Set API key
    client = ElevenLabs(api_key=api_key)
    
    text_to_video(client,
    "I'm telling you, I popped into the glory hole for a second, and the clown was gone! Now, if you want me to figure out where the dame went... that's gonna cost cash. Real cash. Can you handle that? Or should I slice your thumbs off with the rest of them? Pervert.",
    image_path,
    "iztIefAzHtwkAtGcs9fA",
    output_path)