import requests

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