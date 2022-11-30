# OSTScripts <!-- omit in toc -->

![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg) ![Linter: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen) ![Python version](https://img.shields.io/github/pipenv/locked/python-version/GriekseEi/OSTScripts?style=plastic) ![License: MIT](https://img.shields.io/github/license/GriekseEi/OSTScripts?style=plastic)

A repository of assorted scripts to automate the creation and uploading of music videos on YouTube.

## Table of Contents <!-- omit in toc -->

- [Scripts](#scripts)
  - [create_music_video_python](#create_music_video_python)
    - [Requirements](#requirements)
    - [Usage](#usage)
    - [Options](#options)
    - [Known Issues](#known-issues)
- [Development](#development)

## Scripts

### create_music_video.py

A cross-platform Python script using [FFMPEG](https://ffmpeg.org/) and Python standard libraries only that takes in one or more images and one or more audio files to create a video for every audio file displaying the given static image(s). Has multiple options that allow you to encode the music videos in different resolutions and video codecs.

#### Requirements

- Python 3.10+ (download and install it from [here](https://www.python.org/downloads/))
- [FFMPEG](https://ffmpeg.org/) (on Windows the script can install it for you via [Scoop](https://scoop.sh/) or a manual download of the [latest release](https://ffmpeg.org/download.html#build-windows), but for Linux you should install it via your local package manager)

#### Usage

You can run the script from the terminal as follows in the same folder containing the script. The paths to the input files can be both relative to where you're running the script from (i.e `./input_files`) or absolute (`C:/Documents/input_files`).

```bash
python create_music_video.py --audio [path to audio file or directory of audio files] --image [path to image file or directory of image files] --output [path to where to output the files]
```

You can run this script from any folder in your system by adding it to your PATH. To do so, follow the following instructions for [Windows](https://correlated.kayako.com/article/40-running-python-scripts-from-anywhere-under-windows) or [Linux](https://stackoverflow.com/a/6967931).

#### Options

The scripts allows for a range of options, which can also be printed in your terminal by entering `python create_music_video.py -h`. These options are as follows:

- `-a AUDIO_PATH` / `--audio AUDIO_PATH`: (**Required**) The path to the audio file/directory containing all audio files. If pointed to a single file, then the script will make a single music video using that audio file. If pointed to a directory, then all audio files inside (if their audio filetype is supported) will have a video made of.

    *Example usage*:

    ```bash
    python create_music_video.py ... -a ./audio_files
    python create_music_video.py ... -a ./audio_files/song.mp3
    ```

- `-i IMAGE_PATH` / `--image IMAGE_PATH`: (**Required**) The path to the image file/directory containing all image files we wish to include. If pointed to a single image file, then that image will be used for all created music videos. If pointed to a directory of image files, then for every music video the script will use a different image by iterating through the list of images *in alphabetical order*, and loops back to the start if the list of given images is smaller than the list of given audio files. For example, if we provide 3 audio files (`test1.mp3`, `test2.mp3`, `test3.mp3`) and 2 image files (`img1.jpg`, `img2.jpg`), then the script will output three videos (`test1.webm`, `test2.webm`, `test3.webm`), where `test1.webm` has `img1.jpg` for its video, `test2.webm` has `img2.jpg`, and `test3.webm` has `img1.jpg`.

    *Example usage*:

    ```bash
    python create_music_video.py ... -i ./image_files
    python create_music_video.py ... --image ./image_files/img.jpg
    ```

- `-o OUTPUT_PATH` / `--output OUTPUT_PATH`: (*Optional*) The output path for the created videos. Defaults to the current working directory. If the given output folder does not exist, the script will prompt you whether to create one.

    *Example usage*:

    ```bash
    python create_music_video.py ... -o ./output
    ```

- `-vf FORMAT` / `--vid-format FORMAT`: (*Optional*) The desired output format for the videos. Defaults to WebM for better size/quality ratio, given that music videos usually feature only a static image. The currently supported video formats are: `mp4`, `avi`, `flv`, `wmv`, and `mov`.

    *Example usage*:

    ```bash
    python create_music_video.py ... -vf mp4
    python create_music_video.py ... --vid-format avi
    ```

- `-x` / `--use-x265`: (*Optional*) Toggles whether to use [x265](https://en.wikipedia.org/wiki/X265) encoding for the output videos. By default x264 is used for all output videos (except for WebMs, which don't support it and will and are set by the script to always use [VP9](https://en.wikipedia.org/wiki/VP9) encoding) because YouTube tends to process those faster.
- `-r` / `--recursive`: (*Optional*) Whether to also include all the image/audio files in the subdirectories of the given audio/image paths.
- `-rng` / `--random-image-order`: (*Optional*) If given a list of images, then the script will choose a random one for each video.
- `-res RESOLUTION` / `--resolution RESOLUTION`: (*Optional*) The resolution type to use for the output videos, or at least what [YouTube understands under each resolution type](https://influencermarketinghub.com/youtube-video-size). By default uses the resolution of the input images. Currently supported resolution types are `360p` (640x360), `480p` (854x480), `720p` (1280x720), and `1080p` (1920x1080). The script will downscale the image to the target resolution while maintaining the original aspect ratio, and pad the sides of the image with black bars if necessary.

    *Example usage*:

    ```bash
    python create_music_video.py ... -res 360p
    python create_music_video.py ... --resolution 720p
    ```

- `-f` / `--formats`: (*Optional*) Prints all supported image/audio/video formats by the script and ends it prematurely.

#### Known Issues

- On Windows, the script refuses to terminate itself and its subprocesses properly when inputting CTRL+C.

### utility_functions.py

A Python module containing a bunch of utility functions meant for general reuse in other scripts. They include the following:

- `track_elapsed_time()`: A decorator function for tracking the execution time of a given function and printing it.
- `is_app_installed()`: Checks if a command-line application is available on the local system.
- `prompt_yes_no()`: Prompts the user repeatedly with a message to input Y(es)/N(o) in response to a prompt.
- `run_multiprocessed()`: Runs a given function with the given commands in parallel across different subprocesses, if the host system supports parallel operations.
- `creates_missing_folder()`: Creates a missing folder if it doesn't exist yet.
- `glob_files()`: Globs a given path for files of the given supported filetypes.

## Development

For the Python scripts, [pipenv](https://pipenv.pypa.io/en/latest/) is used for dependency management and virtual environment creation. To contribute to these scripts, you can enter the following to set up an appropriate development environment:

```bash
git clone https://github.com/GriekseEi/OSTScripts.git
pip install --user pipenv
python -m pipenv install --dev
```
