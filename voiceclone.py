import os
import sys
import argparse
import subprocess
from pathlib import Path
from elevenlabs import Voice, VoiceSettings
from elevenlabs.client import ElevenLabs
from typing import List, Optional




def text_to_video(client, text: str, voice_id: str, output_path: str) -> None:
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
    temp_audio = f"/tmp/{Path(output_path).stem}_temp.mp3"
    
    try:
        # Generate speech using ElevenLabs
        audio_generator = client.generate(
            text=text,
            voice=Voice(
                voice_id=voice_id, 
                settings=VoiceSettings(stability=1.0, similarity_boost=1.0, style=0.5, use_speaker_boost=True)),
            model="eleven_multilingual_v2"
        )
        
        # Convert generator to bytes
        audio_bytes = b"".join(chunk for chunk in audio_generator)
        
        # Save the audio file
        with open(temp_audio, 'wb') as f:
            f.write(audio_bytes)
        
        # Convert to video using ffmpeg with MP4 settings
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-f', 'lavfi',  # Input is a filter
            '-i', 'color=c=black:s=1920x1080',  # Create black background
            '-i', temp_audio,  # Input audio file
            '-shortest',  # Duration determined by shortest input
            '-c:v', 'libx264',  # Video codec
            '-tune', 'stillimage',  # Optimize for still image
            '-c:a', 'aac',  # Audio codec
            '-b:a', '192k',  # Audio bitrate
            '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
            '-movflags', '+faststart',  # Optimize for web playback
            '-profile:v', 'baseline',  # Most compatible H.264 profile
            '-level', '3.0',  # Compatible H.264 level
            output_path
        ]
        
        # Run ffmpeg command
        subprocess.run(cmd, check=True)
        
    except Exception as e:
        print(f"Error processing {output_path}: {e}")
        raise
    
    finally:
        # Clean up temporary file
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

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
        elif len(parts) == 4:  # Original format with multiple sections
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
            text_to_video(client, text, voice_name, output_path)
            print(f"Completed {output_path}")
        else:  # Original format with multiple sections
            voice_name, new_joke_text, prompt_joke_text, caption_text = parts
            # Process each text section with .mp4 extension
            tasks = [
                (new_joke_text, f"{output_dir}/{voice_name}_new_joke.mp4"),
                (prompt_joke_text, f"{output_dir}/{voice_name}_prompt_joke.mp4"),
                (caption_text, f"{output_dir}/{voice_name}_caption.mp4")
            ]
            
            # Generate videos for each section
            for text, output_path in tasks:
                print(f"Processing {output_path}...")
                text_to_video(client, text, voice_name, output_path)
                print(f"Completed {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()