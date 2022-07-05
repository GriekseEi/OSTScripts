#!/usr/bin/env python
import argparse
import os
import random
import signal
import subprocess
import sys
import time
import traceback
from glob import glob
from pathlib import Path
from typing import Optional
import multiprocessing


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


def parse_args(
    args: Optional[list[str]] = None,
) -> argparse.Namespace:
    """Parses CLI arguments into a Namespace object. Defaults to sys.argv[1:], but
    allows a list of strings to be manually passed, mainly for unit testing.

    :param args: The strings to parse as arguments, defaults to sys.argv[1:]

    :return: A Namespace object containing the parsed arguments.
    """

    def convert_relative_path_to_absolute(path: str):
        """Convert relative paths to absolute for better console log clarity"""
        if not os.path.abspath(path):
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


def check_if_ffmpeg_is_installed():
    """Checks if FFMPEG is installed locally."""
    try:
        _ = subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
    except subprocess.CalledProcessError as _:
        raise RuntimeError(
            "FFMPEG needs to be installed for this script to work."
        ) from _


def run_ffmpeg_command(cmd: list[str]):
    """Runs FFMPEG using the given command"""
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Created video at {cmd[-1]}")


def create_videos(
    *,
    audio_paths: list[str],
    img_paths: list[str],
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
    :param out_path: The path to output all the videos to, defaults to "" (current dir).
    :param use_x265: Whether to use x265 video encoding, defaults to False.
    :param random_image_order: Whether to randomize the image order for the output
    videos instead of assigning them sequentially, defaults to False.

    #### x264 vs. x265

    Currently YouTube seems to have a better and faster time processing videos that
    have been encoded with x264, and as such this has been set as the default video
    codec for making non-WebM videos. Should this change, or should you want to make
    videos for other purposes, then you can toggle the -x or --use-x265 switch to
    encode videos with x265 instead.

    #### WebM exceptions

    Since WebM's only support AAC and Vorbis audio, the chosen
    audio codec for WebM's will always be Vorbis (given its better quality at higher
    bitrates.) Similarly, WebM videos will always use VP9 for video encoding because of
    its superior file quality/size over VP8 and other available codecs.

    #### Framerate setting

    For the framerate of the output videos, we use 2fps instead of a more suitable 1.
    The reason being is that FFMPEG has a weird tendency to add ~30 seconds of silence
    at the end of created videos otherwise. See [this Stack Overflow answer][1] for a
    more detailed explanation. Even with the current settings, created videos may have
    an extra 1 or 2 seconds of silence at the end.

    [1]: https://stackoverflow.com/questions/55800185/my-ffmpeg-output-always-add-extra-30s-of-silence-at-the-end  # pylint:disable=line-too-long
    """
    start_time = time.perf_counter()

    aud_codec = "copy"  # Use the same audio codec as the source audio
    vid_codec = "libx264"

    if vid_format == "webm":
        vid_codec = "libvpx-vp9"
        aud_codec = "libvorbis"
    elif use_x265:
        vid_codec = "libx265"

    commands = []
    img_list_index = 0

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
        # video where necessary if we use x264.
        new_command[14:14] = ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]

    for audio in audio_paths:
        output_filename = os.path.join(out_path, Path(audio).stem + "." + vid_format)
        image_path = img_paths[img_list_index]

        if random_image_order:
            image_path = random.choice(img_paths)
        else:
            img_list_index += 1
            if img_list_index >= len(img_paths):
                img_list_index = 0

        new_command[7] = image_path
        new_command[9] = audio
        new_command[-1] = output_filename
        commands.append(new_command.copy())

    core_count = multiprocessing.cpu_count()
    # Create videos in parallel only if the CPU has enough cores and we're processing
    # more than one song, otherwise the process pool only creates unnecessary overhead
    if core_count > 2 and len(audio_paths) > 1:
        print(f"Processing {len(audio_paths)} songs... (Press CTRL+C to abort)")

        # Ignore SIGINT in the main process, so that the child processes created by
        # instantiating the pool will inherit the SIGINT handler
        original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        pool = multiprocessing.Pool(core_count - 1)
        # Restore the original SIGINT handler in the main process so that we can
        # actually catch KeyboardInterrupts from here
        signal.signal(signal.SIGINT, original_sigint_handler)

        try:
            result = pool.map_async(run_ffmpeg_command, commands)
            # Wait on the result with a timeout because otherwise the default blocking
            # wait ignores all signals, including KeyboardInterrupt. This is set to
            # something unreasonably high to prevent most timeouts
            result.get(0xFFF)
        except (TimeoutError, KeyboardInterrupt) as err:
            pool.terminate()
            pool.join()
            raise err
        else:
            pool.close()
        pool.join()
    else:
        for cmd in commands:
            run_ffmpeg_command(cmd)

    end_time = time.perf_counter()
    elapsed_time = round((end_time - start_time), 4)

    print(f"Created {len(audio_paths)} videos in {elapsed_time}s!")


def create_missing_folder(path: str):
    """Creates the output folders for when the given output path does not exist.

    :param path: The name of the folders to create.
    :raises SystemExit: If the user decides not to create a new folder.
    """
    while True:
        print(
            f"Could not find output folder '{os.path.join(os.getcwd(), path)}'.\n"
            f"Do you want to create this folder? [Y/n]"
        )
        valid = {"yes": True, "y": True, "ye": True, "": True, "no": False, "n": False}
        choice = input().lower()

        if choice in valid and valid[choice]:
            os.makedirs(path)
            print("Created new folder at given path.")
            break
        elif choice in valid and not valid[choice]:
            raise SystemExit()


def glob_files(
    path: str,
    valid_formats: tuple[str, ...],
    recursive: bool = False,
) -> list[str]:
    """Returns a list of all filenames in the given directory that support the given
    formats if the given path is a directory, or returns a list of only one path if
    the given path points to a single file. The paths in the list are sorted
    alphabetically.

    :param path: The path to the target file or directory.
    :param valid_formats: The formats of the files we want to glob.
    :param recursive: Whether, defaults to False

    :raises FileNotFoundError: If there are no files/folders at the given path with the
    given extensions.
    """
    has_multiple = False
    if os.path.isdir(path):
        has_multiple = True
    elif not os.path.isfile(path):
        raise FileNotFoundError(f"Couldn't find image/folder at {path}")

    output = []
    if has_multiple:
        for ext in valid_formats:
            output.extend(glob(os.path.join(path, "*" + ext), recursive=recursive))

        if len(output) < 1:
            raise FileNotFoundError(
                "Couldn't find files of supported type in the ",
                f"given folder. Supported types: {valid_formats}",
            )
        output = sorted(output)
    else:
        output.append(path)

    return output


def main(*, cli_args: Optional[list[str]] = None) -> int:
    """The main entrypoint of this script.

    :param cli_args: The CLI args to pass to parse_args(), defaults to None

    :raises RuntimeError: If FFMPEG is not installed on this system.
    :raises FileNotFoundError: If given path points to no files of a supported format
    or directory.
    :raises TimeoutError: If the process takes too long to complete. Timeout is set to
    4096 seconds.

    :return: 0 if program was successfully completed, 1 if program was aborted by the
    user, and 2 if an error was caught.
    """
    try:
        args = parse_args(cli_args)

        if args.formats:
            raise SystemExit(
                f"Valid image formats: {VALID_IMG_FORMATS}\n"
                f"Valid audio formats: {VALID_AUD_FORMATS}\n"
                f"Valid video formats: {VALID_VID_FORMATS}\n"
            )

        check_if_ffmpeg_is_installed()

        audio_files = glob_files(args.audio_path, VALID_AUD_FORMATS, args.recursive)
        image_files = glob_files(args.image_path, VALID_IMG_FORMATS, args.recursive)

        if not os.path.isdir(args.output_path):
            create_missing_folder(args.output_path)

        create_videos(
            audio_paths=audio_files,
            img_paths=image_files,
            vid_format=args.vid_format,
            resolution=RESOLUTIONS.get(args.resolution),
            out_path=args.output_path,
            use_x265=args.use_x265,
            random_image_order=args.random_image_order,
        )
    except (KeyboardInterrupt, SystemExit) as err:
        print(err)
        return 1
    except subprocess.CalledProcessError as err:
        print(f"Video conversion failed.\nError message: {err.stderr}")
        return 2
    except (FileNotFoundError, RuntimeError, TimeoutError) as err:
        print(f"Caught error:\n{err}")
        return 2
    except BaseException as err:  # pylint:disable=broad-except
        print("Unhandled exception occurred")
        traceback.print_exception(err)
        return 2
    else:
        return 0  # Success!


if __name__ == "__main__":
    sys.exit(main())
