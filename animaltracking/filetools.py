from typing import Union, Optional
from pathlib import Path
import requests
import zipfile
import tqdm


def wget(url: str, fname: Union[Path, str], force: bool = False):
    fname = Path(fname)
    if fname.exists() and ~force:
        print(f"File already exists. Use force=True to owerwrite.")
        return
    fname.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, stream=True)
    total_size_in_bytes = int(response.headers.get("content-length", 0))
    block_size = 1024  # 1 Kibibyte
    progress_bar = tqdm.tqdm(total=total_size_in_bytes, unit="iB", unit_scale=True)
    with open(fname, "wb") as file:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            file.write(data)
    progress_bar.close()
    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
        raise Exception("ERROR, download failed, something went wrong")


def unzip(filename: Union[Path, str], output_path: Union[None, Path, str] = None):
    from zipfile import ZipFile

    # from tqdm import tqdm

    filename = Path(filename)
    if output_path is None:
        output_path = Path(".") / filename.name
    else:
        output_path = Path(output_path)

    output_path.mkdir(exist_ok=True, parents=True)
    # Open your .zip file
    with ZipFile(file=filename) as zip_file:
        # Loop over each file
        for file in tqdm.tqdm(
            iterable=zip_file.namelist(), total=len(zip_file.namelist())
        ):
            # Extract each file to another directory
            # If you want to extract to current working directory, don't specify path
            zip_file.extract(member=file, path=output_path)

    # zf = zipfile.ZipFile(filename)
    # zf.extractall()
    # zf.close()
