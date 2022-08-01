#!/usr/bin/env python
"""
A script for creating music videos for use in YouTube. It takes in one or more songs/
images and uses FFMPEG to encode videos out of them. It also contains installer
functions for FFMPEG (for Windows) to install it if need be.
"""
import argparse
import logging
import multiprocessing
import os
import platform
import random
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Sequence

import utility_functions as util

VALID_AUD_FORMATS = (".mp3", ".wav", ".flac", ".wma", ".opus", ".ogg")
VALID_IMG_FORMATS = (".jpg", ".jpeg", ".png", ".bmp")
VALID_VID_FORMATS = ("mp4", "avi", "flv", "webm", "wmv", "mov")
# The widths and heights that YouTube understands under each resolution type
RESOLUTIONS = {
    "360p": ("640", "360"),
    "480p": ("854", "480"),
    "720p": ("1280", "720"),
    "1080p": ("1920", "1080"),
}
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"  # pylint:disable=line-too-long
FFMPEG_ROOT_FOLDER = "ffmpeg-master-latest-win64-gpl"


# ! INSTALLER FUNCTIONS ---------------------------------------------------------------
def install_scoop(*, as_admin: bool):
    """Installs the Scoop command-line installer on the local system using Powershell.

    :param as_admin: True if we want to install it for the admin, and False otherwise.

    :raises CalledProcessErr: If the Scoop installation fails.
    """
    # Needed for Powershell to run .ps1 scripts
    subprocess.run(
        [
            "pwsh",
            "-c",
            "Set-ExecutionPolicy",
            "RemoteSigned",
            "-Scope",
            "CurrentUser",
        ],
        check=True,
        shell=True,
    )

    cmd = ["pwsh", "-c", "irm get.scoop.sh | iex"]
    if as_admin:
        cmd = ["pwsh", "-c", "iex", '"&', "{$(irm get.scoop.sh)}", '-RunAsAdmin"']

    subprocess.run(cmd, check=True, shell=True)


def download_ffmpeg_git_build(ffmpeg_path: Path | str):
    """Downloads and extracts the latest FFMPEG build to the the given path.

    :param ffmpeg_path: The path to extract FFMPEG to.
    """
    logging.info(f"Downloading latest FFMPEG win64 build from {FFMPEG_URL}...")
    urllib.request.urlretrieve(FFMPEG_URL, "ffmpeg.zip")

    logging.info(f"Download done. Unzipping at {ffmpeg_path}...")
    with zipfile.ZipFile("./ffmpeg.zip", "r") as zip_ref:
        zip_ref.extractall(ffmpeg_path)

    logging.info("Unzipped FFMPEG archive. Removing archive file...")
    os.remove("./ffmpeg.zip")


def install_ffmpeg_windows():
    """Installs FFMPEG on the local Windows system if it is not present"""
    if util.is_app_installed(["scoop"]):
        logging.warning("FFMPEG dependency missing. Using Scoop to install FFMPEG...")
        subprocess.run(["scoop", "install", "ffmpeg"], check=True, shell=True)
        return

    ffmpeg_path = ""
    try:
        ffmpeg_path = Path.home()
    except RuntimeError:
        ffmpeg_path = os.getcwd()
    ffmpeg_binaries_path = os.path.join(ffmpeg_path, FFMPEG_ROOT_FOLDER, "bin")
    ffmpeg_exists = os.path.isfile(os.path.join(ffmpeg_binaries_path, "ffmpeg.exe"))

    if util.is_app_installed(["pwsh", "-c", "$PSVersionTable"]) and not ffmpeg_exists:
        while True:
            logging.warning(
                "FFMPEG dependency is missing. Do you wish to install it via: \n"
                "[1] (Recommended) The Scoop command-line installer. This will "
                "install Scoop for the current non-admin user and subsequently "
                "FFMPEG. NOTE: Requires that this script is NOT run as admin. \n"
                "[2] The above, but Scoop will be installed as an admin instead.\n"
                "[3] Downloading the latest release from Github. Subsequent "
                "updates to FFMPEG will have to be handled manually.\n"
                "Enter 1, 2 or 3 to continue: "
            )
            choice = input()
            if choice in ("1", "2"):
                install_scoop(as_admin=choice == "2")
                subprocess.run(["scoop", "install", "ffmpeg"], check=True, shell=True)
                return
            if choice == "3":
                break

    # This block is run when the system has no Powershell support, or when the user
    # opts for a Github release installation in the prompt above
    if not ffmpeg_exists:
        download_ffmpeg_git_build(ffmpeg_path)

    logging.warning(
        "Adding FFMPEG to PATH for this session...\n"
        "WARNING: FFMPEG is only present in PATH for the current session.\n"
        "It is recommended that you manually add the directory containing the "
        f"FFMPEG binaries (currently {ffmpeg_binaries_path}) to your PATH environment "
        "variable."
    )
    os.environ["PATH"] += os.pathsep + ffmpeg_binaries_path


# ! MAIN FUNCTIONS --------------------------------------------------------------------
def parse_args(
    args: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    """Parses CLI arguments into a Namespace object. Defaults to sys.argv[1:], but
    allows a list of strings to be manually passed, mainly for unit testing.

    :param args: The strings to parse as arguments, defaults to sys.argv[1:]

    :return: A Namespace object containing the parsed arguments.
    """

    def convert_relative_path_to_absolute(path: str):
        """Convert relative paths to absolute for better console log clarity"""
        if not os.path.abspath(path) or path == "":
            return os.path.join(os.getcwd(), path)
        return path

    parser = argparse.ArgumentParser(
        description=(
            "Create one or more videos using one or more audio files and image(s)."
        ),
    )

    parser.add_argument(
        "-a",
        "--audio",
        dest="audio_path",
        type=convert_relative_path_to_absolute,
        help=(
            "The path containing the audio file(s). "
            "Can point to a single file or a directory."
        ),
    )
    parser.add_argument(
        "-i",
        "--image",
        dest="image_path",
        type=convert_relative_path_to_absolute,
        help=(
            "The path containing the image file(s). "
            "Can point to a single file or a directory."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        type=convert_relative_path_to_absolute,
        default=os.getcwd(),
        required=False,
        help="The output path for the videos. Defaults to the current folder.",
    )
    # For music videos with a static image, WebMs are generally the best fit given that
    # they have a small file size and therefore fast uploading/YT processing times
    # while still providing passable quality (for YouTube).
    parser.add_argument(
        "-vf",
        "--vid_format",
        type=str,
        choices=VALID_VID_FORMATS,
        required=False,
        default="webm",
        help="The format of the output videos. Defaults to WebM.",
    )
    parser.add_argument(
        "-x",
        "--use-x265",
        action="store_true",
        help=(
            "Whether to use x265 for video encoding. Defaults to False. "
            "NOTE: WebMs will always be encoded with VP9."
        ),
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help=(
            "Whether to make videos for all audio files in all "
            "subdirectories of the given input folder."
        ),
    )
    parser.add_argument(
        "-rng",
        "--random-image-order",
        dest="random_image_order",
        action="store_true",
        help=(
            "Shuffles the image order in the output videos for when a folder of "
            "images is passed. Is ignored when a single image file is input."
        ),
    )
    parser.add_argument(
        "-res",
        "--resolution",
        dest="resolution",
        choices=RESOLUTIONS.keys(),
        required=False,
        type=str,
        help=(
            "The resolution scale for the output videos. Uses the original "
            "resolution of the provided image(s) if no option is provided."
        ),
    )
    parser.add_argument(
        "-f",
        "--formats",
        action="store_true",
        help="Print the supported video/image/audio formats for this script.",
    )

    # Print the help message if script is called without arguments
    if (args is None and len(sys.argv) < 2) or (args is not None and len(args) < 1):
        parser.print_help(sys.stderr)
        raise SystemExit()

    return parser.parse_args(args)


def run_ffmpeg_command(cmd: list[str]):
    """Runs FFMPEG using the given command"""
    subprocess.run(cmd, check=True, capture_output=True)
    logging.info(f"Created video at {cmd[-1]}")


@util.track_elapsed_time(ndigits=4)
def create_videos(
    *,
    audio_paths: Sequence[str],
    img_paths: Sequence[str],
    vid_format="webm",
    resolution: Optional[tuple[str, str]] = None,
    out_path="",
    use_x265=False,
    random_image_order=False,
):
    """
    Outputs video files of a static image for one or more audio files.

    :param audio_paths: The paths to the audio file(s) to make videos for.
    :param img_paths: The path to the image file(s) to use in every video.
    :param vid_format: The video format of the output videos, defaults to WebM.
    :param resolution: The width and height to scale the output videos to.
    :param out_path: The path to output all the videos to, defaults to "" (current dir).
    :param use_x265: Whether to use x265 video encoding, defaults to False.
    :param random_image_order: Whether to randomize the image order for the output
    videos instead of assigning them sequentially, defaults to False.

    :x264 vs. x265:

    Currently YouTube seems to have a better and faster time processing videos that
    have been encoded with x264, and as such this has been set as the default video
    codec for making non-WebM videos. Should this change, or should you want to make
    videos for other purposes, then you can toggle the -x or --use-x265 switch to
    encode videos with x265 instead.

    :WebM exceptions:

    Since WebM's only support AAC and Vorbis audio, the chosen
    audio codec for WebM's will always be Vorbis (given its better quality at higher
    bitrates.) Similarly, WebM videos will always use VP9 for video encoding because of
    its superior file quality/size over VP8 and other available codecs.

    :Framerate setting:

    For the framerate of the output videos, we use 2fps instead of a more suitable 1.
    The reason being is that FFMPEG has a weird tendency to add ~30 seconds of silence
    at the end of created videos otherwise. See [1] for a more detailed explanation.
    Even with the current settings, created videos may have an extra 1 or 2 seconds
    of silence at the end.

    [1]: https://stackoverflow.com/questions/55800185/my-ffmpeg-output-always-add-extra-30s-of-silence-at-the-end  # pylint:disable=line-too-long
    """
    aud_codec = "copy"  # Use the same audio codec as the source audio
    vid_codec = "libx264"

    if vid_format == "webm":
        vid_codec = "libvpx-vp9"
        aud_codec = "libvorbis"
    elif use_x265:
        vid_codec = "libx265"

    # The PyCLI library would be a great fit for building more complicated commands
    # like these below without the code looking like spaghetti, though we're trying to
    # use the standard library where possible to prevent the user from having to worry
    # about dependencies. I'll consider it if this becomes too unmaintainable, however.
    new_command = [
        "ffmpeg",
        "-y",  # Overwrite existing files with the same name without asking
        "-loop",
        "1",
        "-framerate",
        "2",  # See "Framerate setting" in docstring above
        "-i",
        "image_path",  # Index 7 for editing the image path
        "-i",
        "audio_path",  # Index 9 for editing the audio path
        "-c:v",
        vid_codec,
        "-c:a",
        aud_codec,
        "-pix_fmt",
        "yuv420p",  # Use YUV420p color space for best compatibility
        "-shortest",  # Match video length with audio length
        "-fflags",
        "+shortest",
        "-max_interleave_delta",
        "100M",
        "output_filename",  # Last index for editing the output path
    ]

    if resolution is not None:
        # This tells FFMPEG to scale the source image to the target resolution and
        # aspect ratio, while padding the remaining space with black bars.
        new_command[14:14] = [
            "-vf",
            f"scale={resolution[0]}:{resolution[1]}:force_original_aspect_ratio="
            f"decrease,pad={resolution[0]}:{resolution[1]}:(ow-iw)/2:(oh-ih)/2",
        ]
    elif vid_codec == "libx264":
        # x264 encoding requires that the width and height be divisible by 2, so pad the
        # video where necessary (without downscaling anything) if we use x264.
        new_command[14:14] = ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]

    # Build a list of FFMPEG commands to execute in bulk
    commands = []
    img_list_index = 0
    for audio in audio_paths:
        image_path = img_paths[img_list_index]

        if random_image_order:
            image_path = random.choice(img_paths)
        else:
            img_list_index += 1
            if img_list_index >= len(img_paths):
                img_list_index = 0

        new_command[7] = image_path
        new_command[9] = audio
        new_command[-1] = os.path.join(out_path, Path(audio).stem + "." + vid_format)
        commands.append(new_command.copy())

    logging.info(f"Processing {len(audio_paths)} song(s)... (Press CTRL+C to abort)")
    if multiprocessing.cpu_count() > 2 and len(audio_paths) > 1:
        util.run_multiprocessed(run_ffmpeg_command, list(zip(commands)))
    else:
        for cmd in commands:
            run_ffmpeg_command(cmd)


def main(*, cli_args: Optional[Sequence[str]] = None) -> int:
    """The main entrypoint of this script.

    :param cli_args: The custom CLI args to pass to parse_args(), defaults to None

    :raises RuntimeError: If FFMPEG is not installed on this system.
    :raises FileNotFoundError: If given path points to no files of a supported format
    or directory.
    :raises TimeoutError: If the process takes too long to complete. Timeout is set to
    4096 seconds.
    :raises CalledProcessError: If something went wrong inside one of the subprocesses,
    such as within FFMPEG, scoop, powershell, etc.
    :raises SystemExit: If the user has chosen to abort this script during a prompt.

    :return: 0 if program was successfully completed.
    """
    try:
        args = parse_args(cli_args)

        if args.formats:
            raise SystemExit(
                f"Valid image formats: {VALID_IMG_FORMATS}\n"
                f"Valid audio formats: {VALID_AUD_FORMATS}\n"
                f"Valid video formats: {VALID_VID_FORMATS}\n"
            )

        if not util.is_app_installed(["ffmpeg", "-version"]):
            match platform.system():
                case "Windows":
                    install_ffmpeg_windows()
                case "Linux":
                    raise SystemExit(
                        "This script requires FFMPEG. Please install FFMPEG with "
                        "your local package manager (f.e. 'sudo apt install ffmpeg' if "
                        "you're using Ubuntu or Debian) before running this script."
                    )
                case _:
                    raise SystemExit(
                        "This script requires FFMPEG. Please first install FFMPEG on "
                        "your system first."
                    )

        audio_files = util.glob_files(
            args.audio_path, VALID_AUD_FORMATS, args.recursive
        )
        image_files = util.glob_files(
            args.image_path, VALID_IMG_FORMATS, args.recursive
        )

        if not os.path.isdir(args.output_path):
            util.create_missing_folder(args.output_path)

        create_videos(
            audio_paths=audio_files,
            img_paths=image_files,
            vid_format=args.vid_format,
            resolution=RESOLUTIONS.get(args.resolution),
            out_path=args.output_path,
            use_x265=args.use_x265,
            random_image_order=args.random_image_order,
        )
    except (
        KeyboardInterrupt,
        subprocess.CalledProcessError,
        FileNotFoundError,
        SystemExit,
        RuntimeError,
        TimeoutError,
    ) as err:
        raise err
    else:
        return 0  # Success!
    finally:
        # Workaround for bash not showing inputs anymore after running this script
        if platform.system() == "Linux":
            os.system("stty sane")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    sys.exit(main())
