#!/usr/bin/env python

"""
mps-youtube.

https://github.com/np1/mps-youtube

Copyright (C) 2014, 2015 np1 and contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

from __future__ import print_function

__version__ = "0.2.4"
__notes__ = "released 13 May 2015"
__author__ = "np1"
__license__ = "GPLv3"
__url__ = "http://github.com/np1/mps-youtube"

from xml.etree import ElementTree as ET
import terminalsize
import multiprocessing
import unicodedata
import collections
import subprocess
import threading
import platform
import tempfile
import difflib
import logging
import random
import locale
import socket
import shlex
import time
import math
import pafy
import json
import sys
import re
import os


try:
    # pylint: disable=F0401
    from colorama import init as init_colorama, Fore, Style
    has_colorama = True

except ImportError:
    has_colorama = False

try:
    import readline
    readline.set_history_length(2000)
    has_readline = True

except ImportError:
    has_readline = False

try:
    # pylint: disable=F0401
    import xerox
    has_xerox = True

except ImportError:
    has_xerox = False

# Python 3 compatibility hack

if sys.version_info[:2] >= (3, 0):
    # pylint: disable=E0611,F0401
    import pickle
    from urllib.request import urlopen, build_opener
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    uni, byt, xinput = str, bytes, input

else:
    from urllib2 import urlopen, HTTPError, URLError, build_opener
    import cPickle as pickle
    from urllib import urlencode
    uni, byt, xinput = unicode, str, raw_input


def utf8_encode(x):
    """ Encode Unicode. """
    return x.encode("utf8") if isinstance(x, uni) else x


def utf8_decode(x):
    """ Decode Unicode. """
    return x.decode("utf8") if isinstance(x, byt) else x

mswin = os.name == "nt"
not_utf8_environment = mswin or "UTF-8" not in os.environ.get("LANG", "")


def member_var(x):
    """ Return True if x is a member variable. """
    return not(x.startswith("__") or callable(x))


locale.setlocale(locale.LC_ALL, "")  # for date formatting
XYTuple = collections.namedtuple('XYTuple', 'width height max_results')

iso8601timedurationex = re.compile(r'PT((\d{1,3})H)?((\d{1,3})M)?(\d{1,2})S')


def getxy():
    """ Get terminal size, terminal width and max-results. """
    if g.detectable_size:
        x, y = terminalsize.get_terminal_size()
        max_results = y - 4 if y < 54 else 50
        max_results = 1 if y <= 5 else max_results

    else:
        x, max_results = Config.CONSOLE_WIDTH.get, Config.MAX_RESULTS.get
        y = max_results + 4

    return XYTuple(x, y, max_results)


def utf8_replace(txt):
    """ Replace unsupported characters in unicode string, returns unicode. """
    sse = sys.stdout.encoding
    txt = txt.encode(sse, "replace").decode("utf8", "ignore")
    return txt


def xenc(stuff):
    """ Replace unsupported characters. """
    if g.isatty:
        return utf8_replace(stuff) if not_utf8_environment else stuff

    else:
        return stuff.encode("utf8", errors="replace")


def xprint(stuff, end=None):
    """ Compatible print. """
    print(xenc(stuff), end=end)


def get_default_ddir():
    """ Get system default Download directory, append mps dir. """
    user_home = os.path.expanduser("~")
    join, exists = os.path.join, os.path.exists

    if mswin:
        return join(user_home, "Downloads", "mps")

    USER_DIRS = join(user_home, ".config", "user-dirs.dirs")
    DOWNLOAD_HOME = join(user_home, "Downloads")

    # define ddir by (1) env var, (2) user-dirs.dirs file,
    #                (3) existing ~/Downloads dir (4) ~

    if 'XDG_DOWNLOAD_DIR' in os.environ:
        ddir = os.environ['XDG_DOWNLOAD_DIR']

    elif exists(USER_DIRS):
        lines = open(USER_DIRS).readlines()
        defn = [x for x in lines if x.startswith("XDG_DOWNLOAD_DIR")]

        if len(defn) == 1:
            ddir = defn[0].split("=")[1].replace('"', '')
            ddir = ddir.replace("$HOME", user_home).strip()

        else:
            ddir = DOWNLOAD_HOME if exists(DOWNLOAD_HOME) else user_home

    else:
        ddir = DOWNLOAD_HOME if exists(DOWNLOAD_HOME) else user_home

    ddir = utf8_decode(ddir)
    return os.path.join(ddir, "mps")


def get_config_dir():
    """ Get user's configuration directory. Migrate to new mps name if old."""
    if mswin:
        confdir = os.environ["APPDATA"]

    elif 'XDG_CONFIG_HOME' in os.environ:
        confdir = os.environ['XDG_CONFIG_HOME']

    else:
        confdir = os.path.join(os.path.expanduser("~"), '.config')

    mps_confdir = os.path.join(confdir, "mps-youtube")

    if not os.path.exists(mps_confdir):
        os.makedirs(mps_confdir)

    return mps_confdir


def get_mpv_version(exename):
    """ Get version of mpv as 3-tuple. """
    o = utf8_decode(subprocess.check_output([exename, "--version"]))
    re_ver = re.compile(r"%s (\d+)\.(\d+)\.(\d+)" % exename)

    for line in o.split("\n"):
        m = re_ver.match(line)

        if m:
            v = tuple(map(int, m.groups()))
            dbg("%s version %s.%s.%s detected", exename, *v)
            return v

    dbg("%sFailed to detect mpv version%s", c.r, c.w)
    return -1, 0, 0


def has_exefile(filename):
    """ Check whether file exists in path and is executable.

    Return path to file or False if not found
    """
    paths = [os.getcwd()] + os.environ.get("PATH", '').split(os.pathsep)
    paths = [i for i in paths if i]
    dbg("searching path for %s", filename)

    for path in paths:
        exepath = os.path.join(path, filename)

        if os.path.isfile(exepath):
            if os.access(exepath, os.X_OK):
                dbg("found at %s", exepath)
                return exepath

    return False


def get_content_length(url, preloading=False):
    """ Return content length of a url. """
    prefix = "preload: " if preloading else ""
    dbg(c.y + prefix + "getting content-length header" + c.w)
    response = utf8_decode(urlopen(url))
    headers = response.headers
    cl = headers['content-length']
    return int(cl)


def prune_streams():
    """ Keep cache size in check. """
    while len(g.pafs) > g.max_cached_streams:
        g.pafs.popitem(last=False)

    while len(g.streams) > g.max_cached_streams:
        g.streams.popitem(last=False)

    # prune time expired items

    now = time.time()
    oldpafs = [k for k in g.pafs if g.pafs[k].expiry < now]

    if len(oldpafs):
        dbg(c.r + "%s old pafy items pruned%s", len(oldpafs), c.w)

    for oldpaf in oldpafs:
        g.pafs.pop(oldpaf, 0)

    oldstreams = [k for k in g.streams if g.streams[k]['expiry'] < now]

    if len(oldstreams):
        dbg(c.r + "%s old stream items pruned%s", len(oldstreams), c.w)

    for oldstream in oldstreams:
        g.streams.pop(oldstream, 0)

    dbg(c.b + "paf: %s, streams: %s%s", len(g.pafs), len(g.streams), c.w)


def get_pafy(item, force=False, callback=None):
    """ Get pafy object for an item. """
    def nullfunc(x):
        """ Function that returns None. """
        return None

    callback_fn = callback or nullfunc
    cached = g.pafs.get(item["ytid"])

    if not force and cached and cached.expiry > time.time():
        dbg("get pafy cache hit for %s", cached.title)
        cached.fresh = False
        return cached

    else:

        try:
            p = pafy.new(item["ytid"], callback=callback_fn)

        except IOError as e:

            if "pafy" in uni(e):
                dbg(c.p + "retrying failed pafy get: " + item["ytid "]+ c.w)
                p = pafy.new(item["ytid"], callback=callback)

            else:
                raise

        g.pafs[item["ytid"]] = p
        p.fresh = True
        thread = "preload: " if not callback else ""
        dbg("%s%sgot new pafy object: %s%s" % (c.y, thread, p.title[:26], c.w))
        dbg("%s%sgot new pafy object: %s%s" % (c.y, thread, p.videoid, c.w))
        return p


def get_streams(vid, force=False, callback=None, threeD=False):
    """ Get all streams as a dict.  callback function passed to get_pafy. """
    now = time.time()
    ytid = vid["ytid"]
    have_stream = g.streams.get(ytid) and g.streams[ytid]['expiry'] > now
    prfx = "preload: " if not callback else ""

    if not force and have_stream:
        ss = uni(int(g.streams[ytid]['expiry'] - now) // 60)
        dbg("%s%sGot streams from cache (%s mins left)%s", c.g, prfx, ss, c.w)
        return g.streams.get(ytid)['meta']

    p = get_pafy(vid, force=force, callback=callback)
    ps = p.allstreams if threeD else [x for x in p.allstreams if not x.threed]

    try:
        # test urls are valid
        [x.url for x in ps]

    except TypeError:
        # refetch if problem
        dbg("%s****Type Error in get_streams. Retrying%s", c.r, c.w)
        p = get_pafy(vid, force=True, callback=callback)
        ps = p.allstreams if threeD else [x for x in p.allstreams
                                          if not x.threed]

    streams = []

    for s in ps:
        x = dict(url=s.url,
                 ext=s.extension,
                 quality=s.quality,
                 mtype=s.mediatype,
                 size=-1)
        streams.append(x)

    g.streams[ytid] = dict(expiry=p.expiry, meta=streams)
    prune_streams()
    return streams


def select_stream(slist, q=0, audio=False, m4a_ok=True, maxres=None):
    """ Select a stream from stream list. """
    
    #xprint ("gian: this is select_stream")

    maxres = maxres or Config.MAX_RES.get
    slist = slist['meta'] if isinstance(slist, dict) else slist
    au_streams = [x for x in slist if x['mtype'] == "audio"]

    def okres(x):
        """ Return True if resolution is within user specified maxres. """
        return int(x['quality'].split("x")[1]) <= maxres

    def getq(x):
        """ Return height aspect of resolution, eg 640x480 => 480. """
        return int(x['quality'].split("x")[1])

    vo_streams = [x for x in slist if x['mtype'] == "normal" and okres(x)]
    vo_streams = sorted(vo_streams, key=getq, reverse=True)

    if not m4a_ok:
        au_streams = [x for x in au_streams if not x['ext'] == "m4a"]

    streams = au_streams if audio else vo_streams
    dbg("select stream, q: %s, audio: %s, len: %s", q, audio, len(streams))

    try:
        ret = streams[q]

    except IndexError:
        ret = streams[0] if q and len(streams) else None

    return ret


def get_size(ytid, url, preloading=False):
    """ Get size of stream, try stream cache first. """
    # try cached value
    stream = [x for x in g.streams[ytid]['meta'] if x['url'] == url][0]
    size = stream['size']
    prefix = "preload: " if preloading else ""

    if not size == -1:
        dbg("%s%susing cached size: %s%s", c.g, prefix, size, c.w)

    else:
        writestatus("Getting content length", mute=preloading)
        stream['size'] = get_content_length(url, preloading=preloading)
        dbg("%s%s - content-length: %s%s", c.y, prefix, stream['size'], c.w)

    return stream['size']


class ConfigItem(object):

    """ A configuration item. """

    def __init__(self, name, value, minval=None, maxval=None, check_fn=None):
        """ If specified, the check_fn should return a dict.

        {valid: bool, message: success/fail mesage, value: value to set}

        """
        self.default = self.value = value
        self.name = name
        self.type = type(value)
        self.maxval, self.minval = maxval, minval
        self.check_fn = check_fn
        self.require_known_player = False
        self.allowed_values = []

    @property
    def get(self):
        """ Return value. """
        return self.value

    @property
    def display(self):
        """ Return value in a format suitable for display. """
        retval = self.value

        if self.name == "max_res":
            retval = uni(retval) + "p"

        if self.name == "encoder":
            retval = str(retval) + " [%s]" % (uni(g.encoders[retval]['name']))

        return retval

    def set(self, value):
        """ Set value with checks. """
        # note: fail_msg should contain %s %s for self.name, value
        #       success_msg should not
        # pylint: disable=R0912
        # too many branches

        success_msg = fail_msg = ""
        value = value.strip()
        value_orig = value

        # handle known player not set

        if self.allowed_values and value not in self.allowed_values:
            fail_msg = "%s must be one of * - not %s"
            fail_msg = fail_msg.replace("*", ", ".join(self.allowed_values))

        if self.require_known_player and not known_player_set():
            fail_msg = "%s requires mpv or mplayer, can't set to %s"

        # handle true / false values

        elif self.type == bool:

            if value.upper() in "0 OFF NO DISABLED FALSE".split():
                value = False
                success_msg = "%s set to False" % c.c("g", self.name)

            elif value.upper() in "1 ON YES ENABLED TRUE".split():
                value = True
                success_msg = "%s set to True" % c.c("g", self.name)

            else:
                fail_msg = "%s requires True/False, got %s"

        # handle int values

        elif self.type == int:

            if not value.isdigit():
                fail_msg = "%s requires a number, got %s"

            else:
                value = int(value)

                if self.maxval and self.minval:

                    if not self.minval <= value <= self.maxval:
                        m = " must be between %s and %s, got "
                        m = m % (self.minval, self.maxval)
                        fail_msg = "%s" + m + "%s"

                if not fail_msg:
                    dispval = value or "None"
                    success_msg = "%s set to %s" % (c.c("g", self.name),
                                                    dispval)

        # handle space separated list

        elif self.type == list:
            success_msg = "%s set to %s" % (c.c("g", self.name), value)
            value = value.split()

        # handle string values

        elif self.type == str:
            dispval = value or "None"
            success_msg = "%s set to %s" % (c.c("g", self.name),
                                            c.c("g", dispval))

        # handle failure

        if fail_msg:
            failed_val = value_orig.strip() or "<nothing>"
            colvals = c.y + self.name + c.w, c.y + failed_val + c.w
            return fail_msg % colvals

        elif self.check_fn:
            checked = self.check_fn(value)
            value = checked.get("value") or value

            if checked['valid']:
                value = checked.get("value", value)
                self.value = value
                saveconfig()
                return checked.get("message", success_msg)

            else:
                return checked.get('message', fail_msg)

        elif success_msg:
            self.value = value
            saveconfig()
            return success_msg


def check_console_width(val):
    """ Show ruler to check console width. """
    valid = True
    message = "-" * val + "\n"
    message += "console_width set to %s, try a lower value if above line ove"\
        "rlaps" % val
    return dict(valid=valid, message=message)


def check_api_key(key):
    url = "https://www.googleapis.com/youtube/v3/i18nLanguages"
    query = {"part": "snippet", "fields": "items/id", "key": key}
    try:
        urlopen(url + "?" + urlencode(query)).read()
        message = "The key, '" + key + "' will now be used for API requests."
        return dict(valid=True, message=message)
    except HTTPError as e:
        message = "Invalid key or quota exceeded, '" + key + "'"
        return dict(valid=False, message=message)



def check_ddir(d):
    """ Check whether dir is a valid directory. """
    expanded = os.path.expanduser(d)
    if os.path.isdir(expanded):
        message = "Downloads will be saved to " + c.y + d + c.w
        return dict(valid=True, message=message, value=expanded)

    else:
        message = "Not a valid directory: " + c.r + d + c.w
        return dict(valid=False, message=message)


def check_win_pos(pos):
    """ Check window position input. """
    if not pos.strip():
        return dict(valid=True, message="Window position not set (default)")

    pos = pos.lower()
    reg = r"(TOP|BOTTOM).?(LEFT|RIGHT)"

    if not re.match(reg, pos, re.I):
        msg = "Try something like top-left or bottom-right (or default)"
        return dict(valid=False, message=msg)

    else:
        p = re.match(reg, pos, re.I).groups()
        p = "%s-%s" % p
        msg = "Window position set to %s" % p
        return dict(valid=True, message=msg, value=p)


def check_win_size(size):
    """ Check window size input. """
    if not size.strip():
        return dict(valid=True, message="Window size not set (default)")

    size = size.lower()
    reg = r"\d{1,4}x\d{1,4}"

    if not re.match(reg, size, re.I):
        msg = "Try something like 720x480"
        return dict(valid=False, message=msg)

    else:
        return dict(valid=True, value=size)


def check_colours(val):
    """ Check whether colour config value can be set. """
    if val and mswin and not has_colorama:
        message = "The colorama module needs to be installed for colour output"
        return dict(valid=False, message=message)

    else:
        return dict(valid=True)


def check_encoder(option):
    """ Check encoder value is acceptable. """
    encs = g.encoders

    if option >= len(encs):
        message = "%s%s%s is too high, type %sencoders%s to see valid values"
        message = message % (c.y, option, c.w, c.g, c.w)
        return dict(valid=False, message=message)

    else:
        message = "Encoder set to %s%s%s"
        message = message % (c.y, encs[option]['name'], c.w)
        return dict(valid=True, message=message)


def check_player(player):
    """ Check player exefile exists and get mpv version. """
    if has_exefile(player):

        if "mpv" in player:
            g.mpv_version = get_mpv_version(player)
            version = "%s.%s.%s" % g.mpv_version
            fmt = c.g, c.w, c.g, c.w, version
            msg = "%splayer%s set to %smpv%s (version %s)" % fmt
            return dict(valid=True, message=msg, value=player)

        else:
            msg = "%splayer%s set to %s%s%s" % (c.g, c.w, c.g, player, c.w)
            return dict(valid=True, message=msg, value=player)

    else:
        if mswin and not player.endswith(".exe"):
            return check_player(player + ".exe")

        else:
            msg = "Player application %s%s%s not found" % (c.r, player, c.w)
            return dict(valid=False, message=msg)


class Config(object):

    """ Holds various configuration values. """

    ORDER = ConfigItem("order", "relevance")
    ORDER.allowed_values = "relevance date views rating".split()
    MAX_RESULTS = ConfigItem("max_results", 19, maxval=50, minval=1)
    CONSOLE_WIDTH = ConfigItem("console_width", 80, minval=70, maxval=880,
                               check_fn=check_console_width)
    MAX_RES = ConfigItem("max_res", 2160, minval=192, maxval=2160)
    PLAYER = ConfigItem("player", "mpv" + (".exe" if mswin else ""),
                        check_fn=check_player)
    PLAYERARGS = ConfigItem("playerargs", "")
    ENCODER = ConfigItem("encoder", 0, minval=0, check_fn=check_encoder)
    NOTIFIER = ConfigItem("notifier", "")
    CHECKUPDATE = ConfigItem("checkupdate", True)
    SHOW_MPLAYER_KEYS = ConfigItem("show_mplayer_keys", True)
    SHOW_MPLAYER_KEYS.require_known_player = True
    FULLSCREEN = ConfigItem("fullscreen", False)
    FULLSCREEN.require_known_player = True
    SHOW_STATUS = ConfigItem("show_status", True)
    COLUMNS = ConfigItem("columns", "")
    DDIR = ConfigItem("ddir", get_default_ddir(), check_fn=check_ddir)
    OVERWRITE = ConfigItem("overwrite", True)
    SHOW_VIDEO = ConfigItem("show_video", False)
    SEARCH_MUSIC = ConfigItem("search_music", True)
    WINDOW_POS = ConfigItem("window_pos", "", check_fn=check_win_pos)
    WINDOW_POS.require_known_player = True
    WINDOW_SIZE = ConfigItem("window_size", "", check_fn=check_win_size)
    WINDOW_SIZE.require_known_player = True
    COLOURS = ConfigItem("colours",
                         False if mswin and not has_colorama else True,
                         check_fn=check_colours)
    DOWNLOAD_COMMAND = ConfigItem("download_command", '')
    API_KEY = ConfigItem("api_key", "AIzaSyCIM4EzNqi1in22f4Z3Ru3iYvLaY8tc3bo", check_fn=check_api_key)


class Playlist(object):

    """ Representation of a playist, has list of songs. """

    def __init__(self, name=None, songs=None):
        """ class members. """
        self.name = name
        self.creation = time.time()
        self.songs = songs or []

    @property
    def is_empty(self):
        """ Return True / False if songs are populated or not. """
        return not self.songs

    @property
    def size(self):
        """ Return number of tracks. """
        return len(self.songs)

    @property
    def duration(self):
        """ Sum duration of the playlist. """
        duration = sum(s["length"] for s in self.songs)
        duration = time.strftime('%H:%M:%S', time.gmtime(int(duration)))
        return duration

    def getSongs(self):
        return self.songs


class g(object):

    """ Class for holding globals that are needed throught the module. """

    transcoder_path = "auto"
    delete_orig = True
    encoders = []
    muxapp = False
    meta = {}
    detectable_size = True
    command_line = False
    debug_mode = False
    preload_disabled = False
    isatty = sys.stdout.isatty()
    ytpls = []
    mpv_version = 0, 0, 0
    mpv_usesock = False
    mprisctl = None
    browse_mode = "normal"
    preloading = []
    # expiry = 5 * 60 * 60  # 5 hours
    blank_text = "\n" * 200
    helptext = []
    max_retries = 3
    max_cached_streams = 1500
    url_memo = collections.OrderedDict()
    username_query_cache = collections.OrderedDict()
    model = Playlist(name="model")
    active = Playlist(name="active")
    playing = False
    paused = False
    skip = False
    volume = 20
    elapsedTime = 0;
    percentElapsed = 0
    pl_token = 0;
    last_search_query = {}
    current_pagetoken = ''
    page_tokens = ['']
    text = {}
    userpl = {}
    ytpl = {}
    pafs = collections.OrderedDict()
    streams = collections.OrderedDict()
    pafy_pls = {}  #
    last_opened = message = content = ""
    config = [x for x in sorted(dir(Config)) if member_var(x)]
    defaults = {setting: getattr(Config, setting) for setting in config}
    suffix = "3" if sys.version_info[:2] >= (3, 0) else ""
    CFFILE = os.path.join(get_config_dir(), "config")
    TCFILE = os.path.join(get_config_dir(), "transcode")
    OLD_PLFILE = os.path.join(get_config_dir(), "playlist" + suffix)
    PLFILE = os.path.join(get_config_dir(), "playlist_v2")
    CACHEFILE = os.path.join(get_config_dir(), "cache_py_" + sys.version[0:5])
    READLINE_FILE = None
    playerargs_defaults = {
        "mpv": {
            "msglevel": {"<0.4": "--msg-level=all=no:statusline=status",
                         ">=0.4": "--msg-level=all=no:statusline=status"},
            "title": "--title",
            "fs": "--fs",
            "novid": "--no-video",
            "ignidx": "--demuxer-lavf-o=fflags=+ignidx",
            "geo": "--geometry"},
        "mplayer": {
            "title": "-title",
            "fs": "-fs",
            "novid": "-novideo",
            # "ignidx": "-lavfdopts o=fflags=+ignidx".split()
            "ignidx": "",
            "geo": "-geometry"}
        }


def init():
    """ Initial setup. """
    # I believe these two lines once resolved a pickle error.
    # perhaps no longer needed, commenting out.
    # __main__.Playlist = Playlist
    # __main__.Video = Video

    # if "mpv" in Config.PLAYER.get and not mswin:
    #     options = utf8_decode(subprocess.check_output(
    #         [Config.PLAYER.get, "--list-options"]))
    #     # g.mpv_usesock = "--input-unix-socket" in options and not mswin

    #     if "--input-unix-socket" in options:
    #         g.mpv_usesock = True
    #         dbg(c.g + "mpv supports --input-unix-socket" + c.w)

    # try:
    #     import mpris
    #     g.mprisctl, conn = multiprocessing.Pipe()
    #     t = multiprocessing.Process(target=mpris.main, args=(conn,))
    #     t.daemon = True
    #     t.start()
    # except ImportError:
    #     pass
    #random.init
    #process_cl_args(sys.argv)
    g.pl_token = 0
    #random.randint(0, 99999)


def init_cache():
    """ Import cache file. """
    if os.path.isfile(g.CACHEFILE):

        try:

            with open(g.CACHEFILE, "rb") as cf:
                cached = pickle.load(cf)

            if 'streams' in cached:
                g.streams = cached['streams']
                g.username_query_cache = cached['userdata']
            else:
                g.streams = cached

            dbg(c.g + "%s cached streams imported%s", uni(len(g.streams)), c.w)

        except (EOFError, IOError):
            dbg(c.r + "Cache file failed to open" + c.w)

        prune_streams()


def init_readline():
    """ Enable readline for input history. """
    if g.command_line:
        return

    if has_readline:
        g.READLINE_FILE = os.path.join(get_config_dir(), "input_history")

        if os.path.exists(g.READLINE_FILE):
            readline.read_history_file(g.READLINE_FILE)
            dbg(c.g + "Read history file" + c.w)


def known_player_set():
    """ Return true if the set player is known. """
    for allowed_player in g.playerargs_defaults:
        regex = r'(?:\b%s($|\.[a-zA-Z0-9]+$))' % re.escape(allowed_player)
        match = re.search(regex, Config.PLAYER.get)

        if mswin:
            match = re.search(regex, Config.PLAYER.get, re.IGNORECASE)

        if match:
            return allowed_player

    return None


def showconfig(_):
    """ Dump config data. """
    width = getxy().width
    width -= 30
    s = "  %s%-17s%s : %s\n"
    out = "  %s%-17s   %s%s%s\n" % (c.ul, "Key", "Value", " " * width, c.w)

    for setting in g.config:
        val = getattr(Config, setting)

        # don't show player specific settings if unknown player
        if not known_player_set() and val.require_known_player:
            continue

        # don't show max_results if auto determined
        if g.detectable_size and setting == "MAX_RESULTS":
            continue

        if g.detectable_size and setting == "CONSOLE_WIDTH":
            continue

        out += s % (c.g, setting.lower(), c.w, val.display)

    g.content = out
    g.message = "Enter %sset <key> <value>%s to change\n" % (c.g, c.w)
    g.message += "Enter %sset all default%s to reset all" % (c.g, c.w)


def saveconfig():
    """ Save current config to file. """
    config = {setting: getattr(Config, setting).value for setting in g.config}

    with open(g.CFFILE, "wb") as cf:
        pickle.dump(config, cf, protocol=2)

    dbg(c.p + "Saved config: " + g.CFFILE + c.w)


def savecache():
    """ Save stream cache. """
    caches = dict(
        streams=g.streams,
        userdata=g.username_query_cache)

    with open(g.CACHEFILE, "wb") as cf:
        pickle.dump(caches, cf, protocol=2)

    dbg(c.p + "saved cache file: " + g.CACHEFILE + c.w)


def import_config():
    """ Override config if config file exists. """
    if os.path.exists(g.CFFILE):

        with open(g.CFFILE, "rb") as cf:
            saved_config = pickle.load(cf)

        for k, v in saved_config.items():

            try:
                getattr(Config, k).value = v

            except AttributeError:  # Ignore unrecognised data in config
                dbg("Unrecognised config item: %s", k)

        # Update config files from versions <= 0.01.41
        if isinstance(Config.PLAYERARGS.get, list):
            Config.WINDOW_POS.value = "top-right"
            redundant = ("-really-quiet --really-quiet -prefer-ipv4 -nolirc "
                         "-fs --fs".split())

            for r in redundant:
                dbg("removing redundant arg %s", r)
                list_update(r, Config.PLAYERARGS.value, remove=True)

            Config.PLAYERARGS.value = " ".join(Config.PLAYERARGS.get)
            saveconfig()


class c(object):

    """ Class for holding colour code values. """

    if mswin and has_colorama:
        white = Style.RESET_ALL
        ul = Style.DIM + Fore.YELLOW
        red, green, yellow = Fore.RED, Fore.GREEN, Fore.YELLOW
        blue, pink = Fore.CYAN, Fore.MAGENTA

    elif mswin:
        Config.COLOURS.value = False

    else:
        white = "\x1b[%sm" % 0
        ul = "\x1b[%sm" * 3 % (2, 4, 33)
        cols = ["\x1b[%sm" % n for n in range(91, 96)]
        red, green, yellow, blue, pink = cols

    if not Config.COLOURS.get:
        ul = red = green = yellow = blue = pink = white = ""
    r, g, y, b, p, w = red, green, yellow, blue, pink, white

    @classmethod
    def c(cls, colour, text):
        """ Return coloured text. """
        return getattr(cls, colour) + text + cls.w


def setconfig(key, val):
    """ Set configuration variable. """
    key = key.replace("-", "_")
    if key.upper() == "ALL" and val.upper() == "DEFAULT":

        for ci in g.config:
            getattr(Config, ci).value = getattr(Config, ci).default

        saveconfig()
        message = "Default configuration reinstated"

    elif not key.upper() in g.config:
        message = "Unknown config item: %s%s%s" % (c.r, key, c.w)

    elif val.upper() == "DEFAULT":
        att = getattr(Config, key.upper())
        att.value = att.default
        message = "%s%s%s set to %s%s%s (default)"
        dispval = att.display or "None"
        message = message % (c.y, key, c.w, c.y, dispval, c.w)
        saveconfig()

    else:
        # saveconfig() will be called by Config.set() method
        message = getattr(Config, key.upper()).set(val)

    showconfig(1)
    g.message = message


def fmt_time(seconds):
    """ Format number of seconds to %H:%M:%S. """
    hms = time.strftime('%H:%M:%S', time.gmtime(int(seconds)))
    H, M, S = hms.split(":")

    if H == "00":
        hms = M + ":" + S

    elif H == "01" and int(M) < 40:
        hms = uni(int(M) + 60) + ":" + S

    elif H.startswith("0"):
        hms = ":".join([H[1], M, S])

    return hms


def get_track_id_from_json(item):
    """ Try to extract video Id from various response types """
    fields = ['contentDetails/videoId',
             'snippet/resourceId/videoId',
             'id/videoId',
             'id']
    for field in fields:
        node = item
        for p in field.split('/'):
            if node and type(node) is dict:
                node = node.get(p)
        if node:
            return node
    return ''


def store_pagetokens_from_json(jsons):
    """Extract the page tokens from json result and store them."""
    # delete global page token list if apparently new search
    if not g.current_pagetoken:
        g.page_tokens = ['']

    # make page token list from api response
    page_tokens = [jsons.get(field) for field in
                   ['prevPageToken', 'nextPageToken']]
    page_tokens.insert(1, g.current_pagetoken)

    curidx = lambda: g.page_tokens.index(g.current_pagetoken)

    # update global page token list
    if page_tokens[2]:
        if page_tokens[0] and g.page_tokens[curidx()-1] is None:
            g.page_tokens[curidx()-1:curidx()+2] = page_tokens
        else:
            g.page_tokens[curidx():curidx()+2] = page_tokens[1:]
    else:
        if page_tokens[0] and g.page_tokens[curidx()-1] is None:
            g.page_tokens[curidx()-1:curidx()+1] = page_tokens[:2]
        else:
            g.page_tokens[curidx()] = page_tokens[1]


def get_tracks_from_json(jsons):
    """ Get search results from API response """

    store_pagetokens_from_json(jsons)

    items = jsons.get("items")
    if not items:
        dbg("got unexpected data or no search results")
        return False

    # fetch detailed information about items from videos API
    vurl = "https://www.googleapis.com/youtube/v3/videos"
    vurl += "?" + urlencode({'part':'contentDetails,statistics,snippet',
                             'key': Config.API_KEY.get,
                             'id': ','.join([get_track_id_from_json(i)
                                             for i in items])})
    try:
        wdata = utf8_decode(urlopen(vurl).read())
        wdata = json.loads(wdata)
        items_vidinfo = wdata.get('items', [])
        # enhance search results by adding information from videos API response
        for searchresult, vidinfoitem in zip(items, items_vidinfo):
            searchresult.update(vidinfoitem)

    except (URLError, HTTPError) as e:
        #g.message = F('no data') % e
        #g.content = logo(c.r)
        return

    # populate list of video objects
    songs = []
    for item in items:

        try:

            ytid = get_track_id_from_json(item)
            duration = item.get('contentDetails', {}).get('duration')

            if duration:
                duration = iso8601timedurationex.findall(duration)
                if len(duration) > 0:
                    _, hours, _, minutes, seconds = duration[0]
                    duration = [seconds, minutes, hours]
                    duration = [int(v) if len(v) > 0 else 0 for v in duration]
                    duration = sum([60**p*v for p, v in enumerate(duration)])
                else:
                    duration = 30
            else:
                duration = 30

            durationString = ''

            print (hours + "h" + minutes + "m" + seconds)

            if hours:
                durationString += hours + 'h '
            if minutes:
                durationString += minutes + 'm '
            if seconds:
                durationString += seconds + 's '

            #durationString = hours + ':' + minutes + ':' + seconds

            stats = item.get('statistics', {})
            snippet = item.get('snippet', {})
            title = snippet.get('title', '').strip()
            # instantiate video representation in local model
            likes = int(stats.get('likeCount', 0))
            dislikes = int(stats.get('dislikeCount', 0))
            rating = 5.*likes/(likes+dislikes) if (likes+dislikes) > 0 else 0
            thumb = snippet.get('thumbnails', {}).get('default', {}).get('url')
            #cursong = Video(ytid=ytid, title=title, length=duration, thumb=thumb)
            cursong = {'ytid' : ytid, 'title' : title, 'length' : duration, 'timestring' : durationString, 'thumb' : thumb }

            # cache video information in custom global variable store
            g.meta[ytid] = dict(
                # tries to get localized title first, fallback to normal title
                title=snippet.get('localized',
                                  {'title':snippet.get('title',
                                                       '[!!!]')}).get('title',
                                                                      '[!]'),
                length=uni(fmt_time(cursong.length)),
                #XXX this is a very poor attempt to calculate a rating value
                rating=uni('{}'.format(rating))[:4].ljust(4, "0"),
                uploader=snippet.get('channelId'),
                uploaderName=snippet.get('channelTitle'),
                category=snippet.get('categoryId'),
                aspect="custom", #XXX
                uploaded=yt_datetime(snippet.get('publishedAt', ''))[1],
                likes=uni(num_repr(likes)),
                dislikes=uni(num_repr(dislikes)),
                commentCount=uni(num_repr(int(stats.get('commentCount', 0)))),
                viewCount=uni(num_repr(int(stats.get('viewCount', 0)))))

        except Exception as e:

            dbg(json.dumps(item, indent=2))
            dbg('Error during metadata extraction/instantiation of search '
                +'result {}\n{}'.format(ytid, e))

        songs.append(cursong)

    # return video objects
    return songs


def num_repr(num):
    """ Return up to four digit string representation of a number, eg 2.6m. """
    if num <= 9999:
        return uni(num)

    def digit_count(x):
        """ Return number of digits. """
        return int(math.floor(math.log10(x)) + 1)

    digits = digit_count(num)
    sig = 3 if digits % 3 == 0 else 2
    rounded = int(round(num, int(sig - digits)))
    digits = digit_count(rounded)
    suffix = "_kmBTqXYX"[(digits - 1) // 3]
    front = 3 if digits % 3 == 0 else digits % 3

    if not front == 1:
        return uni(rounded)[0:front] + suffix

    return uni(rounded)[0] + "." + uni(rounded)[1] + suffix


def yt_datetime(yt_date_time):
    """ Return a time object and locale formated date string. """
    time_obj = time.strptime(yt_date_time, "%Y-%m-%dT%H:%M:%S.%fZ")
    locale_date = time.strftime("%x", time_obj)
    # strip first two digits of four digit year
    short_date = re.sub(r"(\d\d\D\d\d\D)20(\d\d)$", r"\1\2", locale_date)
    return time_obj, short_date


def writestatus(text, mute=False):
    """ Update status line. """
    # Gian Hack:
    mute = True
    if not mute and Config.SHOW_STATUS.get:
        writeline(text)


def writeline(text):
    """ Print text on same line. """
    width = getxy().width
    spaces = width - len(text) - 1
    text = text[:width - 3]
    sys.stdout.write(" " + text + (" " * spaces) + "\r")
    sys.stdout.flush()


def list_update(item, lst, remove=False):
    """ Add or remove item from list, checking first to avoid exceptions. """
    if not remove and item not in lst:
        lst.append(item)

    elif remove and item in lst:
        lst.remove(item)


def generate_real_playerargs(song, override, failcount):
    """ Generate args for player command.

    Return args and songdata status.

    """
    # pylint: disable=R0914
    # pylint: disable=R0912
    video = Config.SHOW_VIDEO.get
    video = True if override in ("fullscreen", "window") else video
    video = False if override == "audio" else video
    m4a = "mplayer" not in Config.PLAYER.get
    q, audio, cached = failcount, not video, g.streams[song["ytid"]]
    stream = select_stream(cached, q=q, audio=audio, m4a_ok=m4a)

    # handle no audio stream available, or m4a with mplayer
    # by switching to video stream and suppressing video output.
    if not stream and not video or failcount and not video:
        dbg(c.r + "no audio or mplayer m4a, using video stream" + c.w)
        override = "a-v"
        video = True
        stream = select_stream(cached, q=q, audio=False, maxres=1600)

    if not stream and video:
        raise IOError("No streams available")

    if "uiressl=yes" in stream['url'] and "mplayer" in Config.PLAYER.get:
        raise IOError("%s : Sorry mplayer doesn't support this stream. "
                      "Use mpv or download it" % song["title"])

    size = get_size(song["ytid"], stream['url'])
    songdata = (song["ytid"], stream['ext'] + " " + stream['quality'],
                int(size / (1024 ** 2)))

    # pylint: disable=E1103
    # pylint thinks PLAYERARGS.get might be bool
    argsstr = Config.PLAYERARGS.get.strip()
    args = argsstr.split() if argsstr else []

    known_player = known_player_set()
    if known_player:
        pd = g.playerargs_defaults[known_player]
        args.append(pd["title"])
        args.append(song["title"])
        novid_arg = pd["novid"]
        fs_arg = pd["fs"]
        list_update(fs_arg, args, remove=not Config.FULLSCREEN.get)

        geometry = ""

        if Config.WINDOW_SIZE.get and "-geometry" not in argsstr:
            geometry = Config.WINDOW_SIZE.get

        if Config.WINDOW_POS.get and "-geometry" not in argsstr:
            wp = Config.WINDOW_POS.get
            xx = "+1" if "top" in wp else "-1"
            yy = "+1" if "left" in wp else "-1"
            geometry += "%s%s" % (yy, xx)

        if geometry:
            list_update(pd['geo'], args)
            list_update(geometry, args)

        # handle no audio stream available
        if override == "a-v":
            list_update(novid_arg, args)

        elif override == "fullscreen":
            list_update(fs_arg, args)

        elif override == "window":
            list_update(fs_arg, args, remove=True)

        # prevent ffmpeg issue (https://github.com/mpv-player/mpv/issues/579)
        if not video and stream['ext'] == "m4a":
            dbg("%susing ignidx flag%s", c.y, c.w)
            list_update(pd["ignidx"], args)

        if "mplayer" in Config.PLAYER.get:
            list_update("-really-quiet", args, remove=True)
            list_update("-noquiet", args)
            list_update("-prefer-ipv4", args)

        elif "mpv" in Config.PLAYER.get:
            msglevel = pd["msglevel"]["<0.4"]

            #  undetected (negative) version number assumed up-to-date
            if g.mpv_version[0:2] < (0, 0) or g.mpv_version[0:2] >= (0, 4):
                msglevel = pd["msglevel"][">=0.4"]

            if g.mpv_usesock:
                list_update("--really-quiet", args)
            else:
                list_update("--really-quiet", args, remove=True)
                list_update(msglevel, args)

    return [Config.PLAYER.get] + args + [stream['url']], songdata


def playsong(song, failcount=0, override=False):
    """ Play song using config.PLAYER called with args config.PLAYERARGS."""
    # pylint: disable=R0911,R0912
    if not Config.PLAYER.get or not has_exefile(Config.PLAYER.get):
        g.message = "Player not configured! Enter %sset player <player_app> "\
            "%s to set a player" % (c.g, c.w)
        return

    if Config.NOTIFIER.get:
        subprocess.call(shlex.split(Config.NOTIFIER.get) + [song["title"]])

    # don't interrupt preloading:
    while song["ytid"] in g.preloading:
        writestatus("fetching item..")
        time.sleep(0.1)

    try:
        get_streams(song, force=failcount, callback=writestatus)

    except (IOError, URLError, HTTPError, socket.timeout) as e:
        dbg("--ioerror in playsong call to get_streams %s", uni(e))

        if "Youtube says" in uni(e):
            #g.message = F('cant get track') % (song["title"] + " " + uni(e))
            return

        elif failcount < g.max_retries:
            dbg("--ioerror - trying next stream")
            failcount += 1
            return playsong(song, failcount=failcount, override=override)

        elif "pafy" in uni(e):
            g.message = uni(e) + " - " + song["ytid"]
            return

    except ValueError:
        #g.message = F('track unresolved')
        dbg("----valueerror in playsong call to get_streams")
        return

    try:
        cmd, songdata = generate_real_playerargs(song, override, failcount)

    except (HTTPError) as e:

        # Fix for invalid streams (gh-65)
        dbg("----htterror in playsong call to gen_real_args %s", uni(e))
        if failcount < g.max_retries:
            failcount += 1
            return playsong(song, failcount=failcount, override=override)

    except IOError as e:
        # this may be cause by attempting to play a https stream with
        # mplayer
        # ====
        errmsg = e.message if hasattr(e, "message") else uni(e)
        g.message = c.r + uni(errmsg) + c.w
        return

    songdata = "%s; %s; %s Mb" % songdata
    print("gian: " + songdata)
    writestatus(songdata)
    dbg("%splaying %s (%s)%s", c.b, song["title"], failcount, c.w)
    dbg("calling %s", " ".join(cmd))
    returncode = launch_player(song, songdata, cmd)
    failed = returncode not in (0, 42, 43)

    if failed and failcount < g.max_retries:
        dbg(c.r + "stream failed to open" + c.w)
        dbg("%strying again (attempt %s)%s", c.r, (2 + failcount), c.w)
        writestatus("error: retrying")
        time.sleep(1.2)
        failcount += 1
        return playsong(song, failcount=failcount, override=override)

    return returncode


def get_input_file():
    """ Check for existence of custom input file.

    Return file name of temp input file with mpsyt mappings included
    """
    confpath = conf = ''

    if "mpv" in Config.PLAYER.get:
        confpath = os.path.join(get_config_dir(), "mpv-input.conf")

    elif "mplayer" in Config.PLAYER.get:
        confpath = os.path.join(get_config_dir(), "mplayer-input.conf")

    if os.path.isfile(confpath):
        dbg("using %s for input key file", confpath)

        with open(confpath) as conffile:
            conf = conffile.read() + '\n'

    conf = conf.replace("quit", "quit 43")
    conf = conf.replace("playlist_prev", "quit 42")
    conf = conf.replace("pt_step -1", "quit 42")
    conf = conf.replace("playlist_next", "quit")
    conf = conf.replace("pt_step 1", "quit")
    standard_cmds = ['q quit 43\n', '> quit\n', '< quit 42\n', 'NEXT quit\n',
                     'PREV quit 42\n', 'ENTER quit\n']
    bound_keys = [i.split()[0] for i in conf.splitlines() if i.split()]

    for i in standard_cmds:
        key = i.split()[0]

        if key not in bound_keys:
            conf += i

    with tempfile.NamedTemporaryFile('w', prefix='mpsyt-input',
                                     delete=False) as tmpfile:
        tmpfile.write(conf)
        return tmpfile.name


def launch_player(song, songdata, cmd):
    """ Launch player application. """
    # fix for github issue 59
    if known_player_set() and mswin and sys.version_info[:2] < (3, 0):
        cmd = [x.encode("utf8", errors="replace") for x in cmd]

    arturl = "http://i.ytimg.com/vi/%s/default.jpg" % song["ytid"]
    input_file = get_input_file()
    sockpath = None
    fifopath = None

    try:
        if "mplayer" in Config.PLAYER.get:
            cmd.append('-input')

            if mswin:
                # Mplayer does not recognize path starting with drive letter,
                # or with backslashes as a delimiter.
                input_file = input_file[2:].replace('\\', '/')

            cmd.append('conf=' + input_file)

            if g.mprisctl:
                fifopath = tempfile.mktemp('.fifo', 'mpsyt-mplayer')
                os.mkfifo(fifopath)
                cmd.extend(['-input', 'file=' + fifopath])
                g.mprisctl.send(('mplayer-fifo', fifopath))
                g.mprisctl.send(('metadata', (song["ytid"], song["title"],
                                              song["length"], arturl)))

            p = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, bufsize=1)
            player_status(p, songdata + "; ", song["length"])
            returncode = p.wait()

        elif "mpv" in Config.PLAYER.get:
            cmd.append('--input-conf=' + input_file)

            if g.mpv_usesock:
                sockpath = tempfile.mktemp('.sock', 'mpsyt-mpv')
                cmd.append('--input-unix-socket=' + sockpath)

                with open(os.devnull, "w") as devnull:
                    p = subprocess.Popen(cmd, shell=False, stderr=devnull)

                if g.mprisctl:
                    g.mprisctl.send(('socket', sockpath))
                    g.mprisctl.send(('metadata', (song["ytid"], song["title"],
                                                  song["length"], arturl)))

            else:
                if g.mprisctl:
                    fifopath = tempfile.mktemp('.fifo', 'mpsyt-mpv')
                    os.mkfifo(fifopath)
                    cmd.append('--input-file=' + fifopath)
                    g.mprisctl.send(('mpv-fifo', fifopath))
                    g.mprisctl.send(('metadata', (song["ytid"], song["title"],
                                                  song["length"], arturl)))
                print ("gian: this is before opening the pipes")
                p = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     bufsize=1)

            print("gian: here is before player_status")
            player_status(p, songdata + "; ", song["length"], mpv=True,
                          sockpath=sockpath)

            print ("this is when it exits")
            
            g.percentElapsed = 0

            if p.poll():
                p.terminate()

            returncode = 0 #p.kill()

        else:
            with open(os.devnull, "w") as devnull:
                returncode = subprocess.call(cmd, stderr=devnull)
            p = None

        return returncode

    except OSError:
        #g.message = F('no player') % Config.PLAYER.get
        return None

    finally:
        os.unlink(input_file)

        print("this is the real kill")
        # May not exist if mpv has not yet created the file
        if sockpath and os.path.exists(sockpath):
            os.unlink(sockpath)

        if fifopath:
            os.unlink(fifopath)

        if g.mprisctl:
            g.mprisctl.send(('stop', True))

        if p and p.poll() is None:
            p.terminate()  # make sure to kill mplayer if mpsyt crashes


def player_status(po_obj, prefix, songlength=0, mpv=False, sockpath=None):
    """ Capture time progress from player output. Write status line. """
    # pylint: disable=R0914, R0912
    re_mplayer = re.compile(r"A:\s*(?P<elapsed_s>\d+)\.\d\s*")
    re_mpv = re.compile(r".{,15}AV?:\s*(\d\d):(\d\d):(\d\d)")
    re_volume = re.compile(r"Volume:\s*(?P<volume>\d+)\s*%")
    re_player = re_mpv if mpv else re_mplayer
    last_displayed_line = None
    buff = ''
    volume_level = None
    last_pos = None

    print("in player_status")
    if sockpath:
        s = socket.socket(socket.AF_UNIX)

        print("gian: in player_status sockpath")

        tries = 0
        while tries < 10 and po_obj.poll() is None:
            time.sleep(.5)
            try:
                s.connect(sockpath)
                break
            except socket.error:
                pass
            tries += 1
        else:
            return

        try:
            observe_full = False
            cmd = {"command": ["observe_property", 1, "time-pos"]}
            s.send(json.dumps(cmd).encode() + b'\n')
            volume_level = elapsed_s = None

            for line in s.makefile():
                resp = json.loads(line)

                # deals with bug in mpv 0.7 - 0.7.3
                if resp.get('event') == 'property-change' and not observe_full:
                    cmd = {"command": ["observe_property", 2, "volume"]}
                    s.send(json.dumps(cmd).encode() + b'\n')
                    observe_full = True

                if resp.get('event') == 'property-change' and resp['id'] == 1:
                    elapsed_s = int(resp['data'])

                elif resp.get('event') == 'property-change' and resp['id'] == 2:
                    volume_level = int(resp['data'])

                if elapsed_s:
                    line = make_status_line(elapsed_s, prefix, songlength,
                                            volume=volume_level)

                    if line != last_displayed_line:
                        writestatus(line)
                        last_displayed_line = line

        except socket.error:
            pass

    else:
        elapsed_s = 0

        print("gian: in player_status elapsed_s")

        while po_obj.poll() is None:
            stdstream = po_obj.stderr if mpv else po_obj.stdout

            char = stdstream.read(1).decode("utf-8", errors="ignore")

            if char in '\r\n':

                mv = re_volume.search(buff)

                if mv:
                    volume_level = int(mv.group("volume"))

                match_object = re_player.match(buff)

                if match_object:

                    try:
                        h, m, s = map(int, match_object.groups())
                        elapsed_s = h * 3600 + m * 60 + s

                    except ValueError:

                        try:
                            elapsed_s = int(match_object.group('elapsed_s')
                                            or '0')

                        except ValueError:
                            continue

                    line = make_status_line(elapsed_s, prefix, songlength,
                                            volume=volume_level)

                    if line != last_displayed_line:
                        writestatus(line)
                        last_displayed_line = line

                if buff.startswith('ANS_volume='):
                    volume_level = round(float(buff.split('=')[1]))

                paused = ("PAUSE" in buff) or ("Paused" in buff)
                paused = g.paused
                volume_level = g.volume
                if (elapsed_s != last_pos or paused) and g.mprisctl:
                    last_pos = elapsed_s
                    g.mprisctl.send(('pause', paused))
                    g.mprisctl.send(('volume', volume_level))
                    g.mprisctl.send(('time-pos', elapsed_s))

                buff = ''

            else:

                if g.playing != True:
                    return
                if g.skip == True:
                    return

                buff += char


def make_status_line(elapsed_s, prefix, songlength=0, volume=None):
    """ Format progress line output.  """
    # pylint: disable=R0914

    display_s = elapsed_s
    display_h = display_m = 0

    if elapsed_s >= 60:
        display_m = display_s // 60
        display_s %= 60

        if display_m >= 100:
            display_h = display_m // 60
            display_m %= 60

    pct = (float(elapsed_s) / songlength * 100) if songlength else 0
    
    g.percentElapsed = pct
    g.elapsedTime = elapsed_s

    status_line = "%02i:%02i:%02i %s" % (
        display_h, display_m, display_s,
        ("[%.0f%%]" % pct).ljust(6)
    )

    if volume:
        vol_suffix = " vol: %d%%" % volume

    else:
        vol_suffix = ""

    cw = getxy().width
    prog_bar_size = cw - len(prefix) - len(status_line) - len(vol_suffix) - 7
    progress = int(math.ceil(pct / 100 * prog_bar_size))
    status_line += " [%s]" % ("=" * (progress - 1) +
                              ">").ljust(prog_bar_size, ' ')
    return prefix + status_line + vol_suffix


def _search(url, progtext, qs=None, splash=True, pre_load=True):
    """ Perform memoized url fetch, display progtext. """
    g.message = "Searching for '%s%s%s'" % (c.y, progtext, c.w)

    # attach query string if supplied
    url = url + "?" + urlencode(qs) if qs else url
    # use cached value if exists
    if url in g.url_memo:
        songs = g.url_memo[url]
        dbg('load {} songs from cache for key {}'.format(len(songs), url))

    # show splash screen during fetch
    else:
        dbg('url not in cache yet: {}'.format(url))

        try:
            wdata = utf8_decode(urlopen(url).read())
            wdata = json.loads(wdata)
            songs = get_tracks_from_json(wdata)
            #print(songs)

        except (URLError, HTTPError) as e:
            #g.message = F('no data') % e
            #g.content = logo(c.r)
            return False

    if songs:
        # cache results
        add_to_url_memo(url, songs[::])
        g.model.songs = songs
        return True

    return False



def generate_search_qs(term, page=None, result_count=None, match='term'):
    """ Return query string. """
    if not result_count:
        result_count = 15

    aliases = dict(views='viewCount')
    term = utf8_encode(term)
    qs = {
        'q': term,
        'maxResults': result_count,
        'safeSearch': "none",
        'order': aliases.get(Config.ORDER.get, Config.ORDER.get),
        'part': 'id,snippet',
        'type': 'video',
        'key': Config.API_KEY.get
    }

    if match == 'related':
        qs['relatedToVideoId'] = term
        del qs['q']

    if page:
        qs['pageToken'] = page
    else:
        g.current_pagetoken = ''

    if Config.SEARCH_MUSIC.get:
        qs['videoCategoryId'] = 10

    return qs


def related_search(vitem, page=None, splash=True):
    """ Fetch uploads by a YouTube user. """
    query = generate_search_qs(vitem.ytid, page, match='related')

    if query.get('category'):
        del query['category']

    url = "https://www.googleapis.com/youtube/v3/search"
    t = vitem.title
    ttitle = t[:48].strip() + ".." if len(t) > 49 else t

    have_results = _search(url, ttitle, query)

    if have_results:
        g.message = "Videos related to %s%s%s" % (c.y, ttitle, c.w)
        g.last_opened = ""
        g.last_search_query = {"related": vitem}
        g.current_pagetoken = page or ''
        #g.content = generate_songlist_display(frmat="search")

    else:
        g.message = "Related to %s%s%s not found" % (c.y, vitem.ytid, c.w)
        #g.content = logo(c.r)
        g.current_pagetoken = ''
        g.last_search_query = {}


def search(term, page=None, splash=True):
    """ Perform search. """
    if not term or len(term) < 2:
        g.message = c.r + "Not enough input" + c.w
        #g.content = generate_songlist_display()
        return

    logging.info("search for %s", term)
    url = "https://www.googleapis.com/youtube/v3/search"
    query = generate_search_qs(term, page)
    have_results = _search(url, term, query)

    if have_results:
        g.message = "Search results for %s%s%s" % (c.y, term, c.w)
        g.last_opened = ""
        g.last_search_query = {"term": term}
        g.browse_mode = "normal"
        g.current_pagetoken = page or ''
        #g.content = generate_songlist_display(frmat="search")

    else:
        g.message = "Found nothing for %s%s%s" % (c.y, term, c.w)
        #g.content = logo(c.r)
        g.current_pagetoken = ''
        g.last_search_query = {}


def add_to_url_memo(key, value):
    """ Add to url memo, ensure url memo doesn't get too big. """
    dbg('Cache data for query url {}:'.format(key))
    g.url_memo[key] = value

    while len(g.url_memo) > 300:
        g.url_memo.popitem(last=False)


def songlist_rm_add(action, songNum):
    """ Remove or add tracks. works directly on user input. """
    selection = songNum

    if action == "add":

        g.active.songs.append(g.model.songs[selection])
        d = g.active.duration
        g.pl_token = random.randint(0, 99999)

        if g.playing == False:
            start_automated_play()
        #g.message = F('added to pl') % (len(selection), g.active.size, d)

    elif action == "rm":

        g.active.songs.pop(selection)


def preload(song, delay=2, override=False):
    """  Get streams (runs in separate thread). """
    if g.preload_disabled:
        return

    ytid = song.ytid
    g.preloading.append(ytid)
    time.sleep(delay)
    video = Config.SHOW_VIDEO.get
    video = True if override in ("fullscreen", "window") else video
    video = False if override == "audio" else video

    try:
        stream = get_streams(song)
        m4a = "mplayer" not in Config.PLAYER.get
        stream = select_stream(stream, audio=not video, m4a_ok=m4a)

        if not stream and not video:
            # preload video stream, no audio available
            stream = select_stream(g.streams[ytid], audio=False)

        get_size(ytid, stream['url'], preloading=True)

    except (ValueError, AttributeError, IOError) as e:
        dbg(e)  # Fail silently on preload

    finally:
        g.preloading.remove(song.ytid)


def play_plist_thread():

    while len(g.active.songs):

        if g.playing:
            g.skip = False
            song = g.active.songs[0]

            try:
                returncode = playsong(song)

            except KeyboardInterrupt:
                logging.info("Keyboard Interrupt")
                xprint(c.w + "Stopping...                          ")
                reset_terminal()
                g.message = c.y + "Playback halted" + c.w
                break

        else:
            break

        g.active.songs.pop(0)
        g.pl_token = random.randint(0, 99999)

    g.playing = False


def start_automated_play():
        g.playing = True
        t = threading.Thread(target=play_plist_thread)
        t.start()


def playCtrl(cmd):
    global g
    print (cmd)

    if cmd == "stop":

        print("gian: " + cmd)
        g.playing = False

    elif cmd == "skip":

        print("gian: " + cmd)
        g.skip = True


def songlist_mv_sw(action, a, b):
    """ Move a song or swap two songs. """
    i, j = int(a) - 1, int(b) - 1

    if action == "mv":
        g.model.songs.insert(j, g.model.songs.pop(i))
        #g.message = F('song move') % (g.model.songs[j].title, b)

    elif action == "sw":
        g.model.songs[i], g.model.songs[j] = g.model.songs[j], g.model.songs[i]
        #g.message = F('song sw') % (min(a, b), max(a, b))

    #g.content = generate_songlist_display()


def get_adj_pagetoken(np):
    """ Get page token either previous (p) or next (n) to currently displayed one """
    delta = ['p', None, 'n'].index(np) - 1
    pt_index = g.page_tokens.index(g.current_pagetoken) + delta
    return g.page_tokens[pt_index]


def nextprev(np):
    """ Get next / previous search results. """
    glsq = g.last_search_query
    content = g.model.songs

    if "user" in g.last_search_query:
        function, query = usersearch_id, glsq['user']

    elif "related" in g.last_search_query:
        function, query = related_search, glsq['related']

    elif "term" in g.last_search_query:
        function, query = search, glsq['term']

    elif "playlists" in g.last_search_query:
        function, query = pl_search, glsq['playlists']
        content = g.ytpls

    elif "playlist" in g.last_search_query:
        function, query = plist, glsq['playlist']

    good = False

    #dbg('switching from current page {} to {}'.format(
      #g.current_pagetoken, {'n':'next','p':'prev'}[np]))

    if np == "n":
        max_results = 15
        if len(content) == max_results and glsq:
            g.current_pagetoken = get_adj_pagetoken(np)
            good = True

    elif np == "p":
        if glsq:
            if g.page_tokens.index(g.current_pagetoken) > 0:
                g.current_pagetoken = get_adj_pagetoken(np)
                good = True

    if good:
        function(query, g.current_pagetoken, splash=True)
        g.message += " : page {}".format(g.page_tokens.index(g.current_pagetoken)+1)

    else:
        norp = "next" if np == "n" else "previous"
        g.message = "No %s items to display" % norp

    #g.content = generate_songlist_display(frmat="search")


dbg = logging.debug

def searchstring (searchstring):
    search(searchstring)
    for song in g.model.songs:
        print (song.get('title'))

    #playsong(g.model.songs[0])
    #songlist_rm_add("add", 3)
    #time.sleep(10)
    #playlistCtrl("stop")

    #time.sleep(10)

    return

if __name__ == '__main__':
    init()
    searchstring("ac dc")
