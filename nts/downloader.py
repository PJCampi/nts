import datetime
import os
import re
import sys
import urllib
from pathlib import Path
from tempfile import gettempdir

import mutagen
import requests
import youtube_dl
from bs4 import BeautifulSoup

from nts.file_builder import build_metadata

__version__ = '1.1.7'


def download(url, quiet, save_dir, save=True):
    nts_url = url
    page = requests.get(url).content
    bs = BeautifulSoup(page, 'html.parser')

    # guessing there is one
    metadata = parse_nts_data(bs)

    # add extra metadata
    metadata['album'] = 'NTS'
    metadata['url'] = nts_url
    metadata['compilation'] = True
    join_artists = metadata['artists'] + metadata['parsed_artists']
    all_artists, presence_set = [], set()
    for aa in join_artists:
        al = aa.lower()
        if al not in presence_set:
            presence_set.add(al)
            all_artists.append(aa)
    metadata['all_artists'] = all_artists
    metadata['name'] = f'{metadata["title"]} - {metadata["date"].day:02d}.{metadata["date"].month:02d}.{metadata["date"].year:02d}'
    file_name = f'{metadata["safe_title"]} - {metadata["date"].year}-{metadata["date"].month}-{metadata["date"].day}'

    button = bs.select('.episode__btn.mixcloud-btn')[0]
    link = button.get('data-src')

    # get album art. If the one on mixcloud is available, use it. Otherwise fall back to the nts website.
    page = requests.get(link).content
    bs = BeautifulSoup(page, 'html.parser')
    if len(bs.select('div.album-art')) != 0:
        img = bs.select('div.album-art')[0].img
        srcset = img.get('srcset').split()
        img = srcset[-2].split(',')[1]
        image = urllib.request.urlopen(img)
    elif metadata['image_url']:
        try:
            image = urllib.request.urlopen(metadata['image_url'])
        except Exception as e:
            print(f"failed to get image at: {metadata['image_url']} due to: {repr(e)}")
            image = None
    else:
        image = None
    metadata['image'] = image

    # download
    tempdir = gettempdir()
    if save:
        if not quiet:
            print(f'\ndownloading into: {tempdir}\n')
        ydl_opts = {
            'outtmpl': os.path.join(tempdir, f'{file_name}.%(ext)s'),
            'quiet': quiet
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])

        # get the downloaded file
        for file in Path(tempdir).glob(f"{file_name}*"):
            mp_file = mutagen.File(file)
            build_metadata(mp_file, metadata, quiet=quiet)
            file.rename(f"{save_dir}/{file.name}")
            if not quiet:
                print(f'\nsaved file as: {file}\n')
    return metadata


def parse_nts_data(bs):
    # guessing there is one
    title_box = bs.select('div.bio__title')[0]

    # title data
    title, safe_title = parse_title(title_box)

    # parse artists in the title
    artists, parsed_artists = parse_artists(title, bs)

    station = title_box.div.div.h2.find(text=True, recursive=False)
    if not station:
        station = 'London'
    else:
        station = station.strip()

    bg_tag = bs.select('section#bg[style]')
    background_image_regex = r'background-image:url\((.*)\)'
    if bg_tag:
        image_url = re.match(background_image_regex, bg_tag[0]['style']).groups()[0]
    else:
        image_url = None

    # sometimes it's just the date
    date = title_box.div.div.h2.span.text
    if ',' in date:
        date = date.split(',')[1].strip()
    else:
        date = date.strip()
    date = datetime.datetime.strptime(date, '%d.%m.%y')

    # genres
    genres = parse_genres(bs)

    # tracklist
    tracks = parse_tracklist(bs)
    return {
        'safe_title': safe_title,
        'date': date,
        'title': title,
        'artists': artists,
        'parsed_artists': parsed_artists,
        'genres': genres,
        'station': station,
        'tracks': tracks,
        'image_url': image_url,
    }


def parse_tracklist(bs):
    # tracklist
    tracks = []
    tracks_box = bs.select('.tracklist')[0]
    if tracks_box:
        tracks_box = tracks_box.ul
        if tracks_box:
            tracks_list = tracks_box.select('li.track')
            for track in tracks_list:
                artist = track.select('.track__artist')[0].text.strip()
                name = track.select('.track__title')[0].text.strip()
                tracks.append({
                    'artist': artist,
                    'name': name
                })
    return tracks


def parse_genres(bs):
    # genres
    genres = []
    genres_box = bs.select('.episode-genres')[0]
    for anchor in genres_box.find_all('a'):
        genres.append(anchor.text.strip())
    return genres


def parse_artists(title, bs):
    # parse artists in the title
    parsed_artists = re.findall(
        r'(?:w\/|with)(.+?)(?=and|,|&|\s-\s)', title, re.IGNORECASE)
    if not parsed_artists:
        parsed_artists = re.findall(
            r'(?:w\/|with)(.+)', title, re.IGNORECASE)
    # strip all
    parsed_artists = [x.strip() for x in parsed_artists]
    # get other artists after the w/
    if parsed_artists:
        more_people = re.sub(
            r'^.+?(?:w\/|with)(.+?)(?=and|,|&|\s-\s)', '', title, re.IGNORECASE)
        if more_people == title:
            # no more people
            more_people = ''
        if not re.match(r'^\s*-\s', more_people):
            # split if separators are encountered
            more_people = re.split(r',|and|&', more_people, re.IGNORECASE)
            # append to array
            if more_people:
                for mp in more_people:
                    mp.strip()
                    parsed_artists.append(mp)
    parsed_artists = list(filter(None, parsed_artists))
    # artists
    artists = []
    artist_box = bs.select('.bio-artists')
    if artist_box:
        artist_box = artist_box[0]
        for anchor in artist_box.find_all('a'):
            artists.append(anchor.text.strip())
    return artists, parsed_artists


def parse_title(title_box):
    title = title_box.div.h1.text
    title = title.strip()

    # remove unsafe characters for the FS
    safe_title = re.sub(r'\/|\:', '-', title)
    return title, safe_title


def get_episodes_of_show(show_name):
    offset = 0
    count = 0
    output = []
    while True:
        api_url = f'https://www.nts.live/api/v2/shows/{show_name}/episodes?offset={offset}'
        res = requests.get(api_url)
        try:
            res = res.json()
        except:
            print('error parsing api response json')
            exit(1)
        if count == 0:
            count = int(res['metadata']['resultset']['count'])
        offset += int(res['metadata']['resultset']['limit'])
        if res['results']:
            res = res['results']
            for ep in res:
                if ep['status'] == 'published':
                    alias = ep['episode_alias']
                    output.append(
                        f'https://www.nts.live/shows/{show_name}/episodes/{alias}')
        if len(output) == count:
            break

    return output
