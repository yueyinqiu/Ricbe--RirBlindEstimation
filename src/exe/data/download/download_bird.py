from pathlib import Path

import csdir


def main():
    from exe.data.download import download_bird_config as config

    directory_compressed: Path = config.destination.joinpath("compressed")
    csdir.create_directory(directory_compressed)

    i: int
    for i in range(config.start_index, 10 + 1):
        source: str = config.url_pattern.format(i)
        destination: Path = directory_compressed.joinpath(f"fold{i:02d}.zip")
        
        print(f"Downloading {source}...")
        import urllib.request
        urllib.request.urlretrieve(source, destination)

        print(f"Extracting {source}...")
        import zipfile
        zip: zipfile.ZipFile
        with zipfile.ZipFile(destination) as zip:
            zip.extractall(config.destination)

    print("Completed.")


if __name__ == "__main__":
    main()
