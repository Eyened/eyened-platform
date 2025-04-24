import os
import zipfile

import requests
from tqdm import tqdm


def download_and_extract_dataset(url, extract_dir=None):
    """
    Download a dataset from a URL and extract it to a local folder.
    
    Args:
        url: URL of the zip file to download
        download_dir: Directory to save the downloaded zip file
        extract_dir: Directory to extract the zip file (defaults to download_dir if None)
    
    Returns:
        Path to the extracted directory
    """
   
    
    # Get filename from URL
    filename = url.split('/')[-1]
    if extract_dir is None:
        extract_dir = filename.split('.')[0]

     # Create directories if they don't exist
    os.makedirs(extract_dir, exist_ok=True)
    
    # Download the file
    print(f"Downloading {url}...")
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    # Show progress bar while downloading
    with open(filename, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    
    # Extract the zip file
    print(f"Extracting to {extract_dir}...")
    with zipfile.ZipFile(filename, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    print("Download and extraction complete!")
    return extract_dir