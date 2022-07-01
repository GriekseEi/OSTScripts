#!/usr/bin/env python
import argparse
import copy
import os
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


def parse_args(
    valid_vid_formats: tuple[str, ...] = VALID_VID_FORMATS,
    args: Optional[list[str]] = None,
) -> argparse.Namespace:
    """Parses CLI arguments into a Namespace object. Defaults to sys.argv[1:], but
    allows a list of strings to be manually passed, mainly for unit testing.

    :param valid_vid_formats: Tuple of supported video file formats.
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
            "Create one or more videos using one or more audio files and one image."
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
        help="The path containing the image.",
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
        choices=valid_vid_formats,
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
            "subdirectories of the given input folder"
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
    except subprocess.CalledProcessError:
        return False
    else:
        return True


def run_ffmpeg_command(cmd: list[str]):
    """Runs FFMPEG using the given command"""
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Created video at {cmd[-1]}")


def create_videos(
    *,
    song_paths: list[str],
    img_path: str,
    vid_format: str,
    out_path: str = "",
    use_x265=False,
):
    """
    Outputs video files of a static image for one or more audio files.

    :param song_paths: The paths to the song(s) to make videos for.
    :param img_path: The path to the image to use in every video.
    :param vid_format: The video format of the output videos.
    :param out_path: The path to output all the videos to, defaults to "" (current dir).
    :param use_x265: Whether to use x265 video encoding, defaults to False

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
    base_command = [
                "ffmpeg",
                "-y",  # Overwrite existing files with the same name without asking
                "-loop",
                "1",
                "-framerate",
                "2",  # See "Framerate setting" in docstring above
                "-i",
                img_path,
                "-i",
                "default_audio_path",  # Index 9, should be edited by for loop below
                "-c:v",
                vid_codec,
                "-c:a",
                aud_codec,
                "-pix_fmt",
                "yuv420p",  # Use YUV color space for best compatibility
                "-shortest",  # Match video length with audio length
                "-fflags",
                "+shortest",
                "-max_interleave_delta",
                "100M",
                "default_output_path",
            ]
    for item in song_paths:
        new_command = copy.deepcopy(base_command)
        # Change audio path
        new_command[9] = item
        # x264 encoding requires that the width and height of the image are
        # divisible by 2, when applicable this pads the image to facilitate that
        if vid_codec == "libx264":
            new_command[14:14] = ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
        # Add final filename of video to end of command
        full_video_filename = os.path.join(out_path, Path(item).stem + "." + vid_format)
        new_command.append(full_video_filename)
        
        commands.append(new_command)

    core_count = multiprocessing.cpu_count()
    # Create videos in parallel only if the CPU has enough cores and we're processing
    # more than one song, otherwise the process pool only creates unnecessary overhead
    if core_count > 2 and len(song_paths) > 1:
        print(f"Processing {len(song_paths)} songs...")

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

    print(f"Created {len(song_paths)} videos in {elapsed_time}s!")


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


def main(
    *,
    valid_img_formats: tuple[str, ...] = VALID_IMG_FORMATS,
    valid_vid_formats: tuple[str, ...] = VALID_VID_FORMATS,
    valid_aud_formats: tuple[str, ...] = VALID_AUD_FORMATS,
    cli_args: Optional[list[str]] = None,
) -> int:
    """The main entrypoint of this script. Handles error-handling and filetype checking.

    :param valid_img_formats: Supported image formats, defaults to VALID_IMG_FORMATS
    :param valid_vid_formats: Supported video formats, defaults to VALID_VID_FORMATS
    :param valid_aud_formats: Supported audio formats, defaults to VALID_AUD_FORMATS
    :param cli_args: The CLI args to pass to parse_args(), defaults to None

    :raises RuntimeError: If FFMPEG is not installed on this system.
    :raises FileNotFoundError: If given path points to no file or directory.
    :raises TypeError: If the extension of the given file isn't supported.
    :raises TimeoutError: If the process takes too long to complete. Timeout is set to
    4096 seconds.

    :return: 0 if program was successfully completed, 1 if program was aborted by the
    user, and 2 if an error was caught.
    """
    try:
        multiple_audio_files = False

        args = parse_args(valid_vid_formats, cli_args)

        if args.formats:
            print(
                f"Valid image formats: {valid_img_formats}\n"
                f"Valid audio formats: {valid_aud_formats}\n"
                f"Valid video formats: {valid_vid_formats}\n"
            )
            return 1

        if not check_if_ffmpeg_is_installed():
            raise RuntimeError("FFMPEG needs to be installed for this script to work.")

        if os.path.isdir(args.audio_path):
            multiple_audio_files = True
        elif not os.path.isfile(args.audio_path):
            raise FileNotFoundError(f"Couldn't find file/folder at {args.audio_path}")

        if not os.path.isfile(args.image_path):
            raise FileNotFoundError(f"Couldn't find image at {args.image_path}")

        if not os.path.isdir(args.output_path):
            create_missing_folder(args.output_path)

        if not args.image_path.endswith(valid_img_formats):
            raise TypeError(
                f"Filetype of given image is not supported.\n"
                f"Supported image filetypes: {valid_img_formats}"
            )

        audio_files = []
        if multiple_audio_files:
            for ext in valid_aud_formats:
                audio_files.extend(
                    glob(
                        os.path.join(args.audio_path, "*" + ext),
                        recursive=args.recursive,
                    )
                )

            if len(audio_files) == 0:
                raise TypeError(
                    f"Found no audio with the supported filetypes.\n"
                    f"Supported filetypes: {valid_aud_formats}"
                )
        else:
            audio_files.append(args.audio_path)

        create_videos(
            song_paths=audio_files,
            img_path=args.image_path,
            vid_format=args.vid_format,
            out_path=args.output_path,
            use_x265=args.use_x265,
        )
    except (KeyboardInterrupt, SystemExit):
        return 1
    except subprocess.CalledProcessError as err:
        print(f"Video conversion failed.\nError message: {err.stderr}")
        return 2
    except (
        FileNotFoundError,
        RuntimeError,
        TypeError,
        TimeoutError
    ) as err:
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
