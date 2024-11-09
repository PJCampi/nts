import re
from typing import Mapping, Any

import mutagen
from mutagen.id3 import TextFrame, TOAL, Encoding, TIT2, TOPE, TCMP, TALB, TPE1, TDRC, COMM, TCON
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3

__all__ = ["build_metadata"]


def build_metadata(audio: mutagen.File, metadata: Mapping[str, Any], *, quiet: bool = False) -> mutagen.File:
    if isinstance(audio, MP4):
        _build_metadata_mp4(audio, metadata)
    elif isinstance(audio, MP3):
        _build_metadata_mp3(audio, metadata)
    else:
        raise NotImplementedError(f"metadata building is not implemented for file type: {type(audio).__name__}")
    audio.save()


def _build_metadata_mp4(audio: MP4, metadata: Mapping[str, Any]) -> None:
    # title
    audio['\xa9nam'] = metadata['name']
    # part of a compilation
    audio['cpil'] = metadata['compilation']
    # album
    audio['\xa9alb'] = 'NTS'
    # artist
    audio['\xa9ART'] = "; ".join(metadata['all_artists'])
    # year
    audio['\xa9day'] = f'{metadata["date"].year}'
    # comment
    audio['\xa9cmt'] = metadata['url']
    # genre
    if len(metadata['genres']) != 0:
        audio['\xa9gen'] = metadata['genres'][0]
    # cover
    image = metadata['image']
    if image:
        image_type = image.info().get_content_type()
        image = image.read()
        match = re.match(r'jpe?g$', image_type)
        if match:
            img_format = mutagen.mp4.AtomDataType.JPEG
        else:
            img_format = mutagen.mp4.AtomDataType.PNG
        cover = mutagen.mp4.MP4Cover(image, img_format)
        audio["covr"] = [cover]


def _build_metadata_mp3(audio: MP3, metadata: Mapping[str, Any]) -> None:
    # title
    audio["TIT2"] = TIT2(Encoding.UTF8, metadata['name'])
    # part of a compilation
    audio["TCMP"] = TCMP(Encoding.UTF8, str(int(metadata['compilation'])))
    # album
    audio["TALB"] = TALB(Encoding.UTF8, 'NTS')
    # artist
    audio["TPE1"] = TPE1(Encoding.UTF8, "; ".join(metadata["all_artists"]))
    # year
    audio["TDRC"] = TDRC(Encoding.UTF8, f'{metadata["date"].year}')
    # comment
    #audio["COMM"] = COMM(Encoding.UTF8, str(metadata["url"]))
    # genre
    if len(metadata['genres']) != 0:
        audio["TCON"] = TCON(Encoding.UTF8, metadata['genres'][0])
    # cover
    image = metadata['image']
    if False:
        image_type = image.info().get_content_type()
        match = re.match(r'jpe?g$', image_type)
        if match:
            img_format = mutagen.mp4.AtomDataType.JPEG
        else:
            img_format = mutagen.mp4.AtomDataType.PNG
        cover = mutagen.mp4.MP4Cover(image, img_format)
        audio[COVER] = [cover]
