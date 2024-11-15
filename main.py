import os
import sys
import requests
import replicate
import json
from pathlib import Path

def check_environment_variables():
    """Check if required environment variables are set"""
    missing_vars = []
    for var in ['REPLICATE_API_TOKEN', 'HUGGINGFACE_TOKEN']:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            "Please set them before running the script."
        )

def transcript_to_plaintext(transcript):
    return "\n".join(map(lambda seg: seg['text'], transcript["segments"]))

def upload_to_fileio(file_path):
    """Upload a file to file.io and return the public URL"""
    print(f"Uploading {file_path} to file.io...")
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post('https://file.io', files=files)
        
    if response.status_code != 200:
        raise Exception(f"Upload failed with status code: {response.status_code}")
    
    response_data = response.json()
    if not response_data.get('success'):
        raise Exception("Upload failed: " + response_data.get('message', 'Unknown error'))
        
    url = response_data['link']
    print(f"File uploaded successfully. URL: {url}")
    return url

def transcribe_with_replicate(file_url):
    """Send the file URL to Replicate for transcription"""
    print("Starting transcription...")
    
    replicate.Client(api_token=os.getenv('REPLICATE_API_TOKEN'))

    output = replicate.run(
        "victor-upmeet/whisperx:84d2ad2d6194fe98a17d2b60bef1c7f910c46b2f6fd38996ca457afd9c8abfcb",
        input={
            "audio_file": file_url,
            "debug": False,
            "vad_onset": 0.5,
            "batch_size": 64,
            "vad_offset": 0.363,
            "diarization": False,
            "temperature": 0,
            "align_output": False,
            "huggingface_access_token": os.getenv('HUGGINGFACE_TOKEN'),
            "language_detection_min_prob": 0,
            "language_detection_max_tries": 5
        }
    )
    
    return output

def save_transcription(transcription, original_file_path):
    """Save the transcription to a file"""
    output_path = Path(original_file_path).with_suffix('.transcript.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(transcript_to_plaintext(transcription))
    return output_path

def main():
    if len(sys.argv) != 2:
        print("Usage: python transcribe.py <path_to_audio_file>")
        sys.exit(1)
    
    try:
        check_environment_variables()
        
        file_path = sys.argv[1]
        
        # Upload file
        public_url = upload_to_fileio(file_path)
        
        # Get transcription
        transcription = transcribe_with_replicate(public_url)
        
        # Save to file
        output_path = save_transcription(transcription, file_path)
        
        # Print results
        print("\nTranscription completed successfully!")
        print("\nTranscript:")
        print("-" * 40)
        print(transcription)
        print("-" * 40)
        print(f"\nTranscription saved to: {output_path}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()