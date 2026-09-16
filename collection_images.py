"""Keep imported product pictures in the same upload storage as manual pictures."""
import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from collection_tools import fetch_public, CollectionError
from runtime_paths import DATA_DIR


def store_images(urls):
    directory = Path(DATA_DIR, 'static', 'uploads')
    directory.mkdir(parents=True, exist_ok=True)

    def download(url):
        if url.startswith('/uploads/'):
            return url, False
        try:
            image = fetch_public(url, image=True)
            name = 'collected_' + hashlib.sha256(image['data']).hexdigest() + image['extension']
            destination = directory / name
            if not destination.exists():
                descriptor, temporary = tempfile.mkstemp(prefix='.collect-', dir=directory)
                try:
                    with os.fdopen(descriptor, 'wb') as output:
                        output.write(image['data'])
                    os.replace(temporary, destination)
                finally:
                    if os.path.exists(temporary): os.unlink(temporary)
            return '/uploads/' + name, False
        except (CollectionError, OSError):
            return url, True

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(download, urls))
    return [item[0] for item in results], sum(item[1] for item in results)
