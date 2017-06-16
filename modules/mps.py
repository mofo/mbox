
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

class Config(object):

    """ Holds various configuration values. """

    ORDER = ConfigItem("order", "relevance")
    ORDER.allowed_values = "relevance date views rating".split()
    MAX_RESULTS = ConfigItem("max_results", 19, maxval=50, minval=1)
    CONSOLE_WIDTH = ConfigItem("console_width", 80, minval=70, maxval=880,
                               check_fn=check_console_width)
    MAX_RES = ConfigItem("max_res", 2160, minval=192, maxval=2160)
    PLAYER = ConfigItem("player", "mplayer" + (".exe" if mswin else ""),
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
        duration = sum(s.length for s in self.songs)
        duration = time.strftime('%H:%M:%S', time.gmtime(int(duration)))
        return duration


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
    last_search_query = {}
    current_pagetoken = ''
    page_tokens = ['']
    active = Playlist(name="active")
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
        if splash:
            g.content = logo(c.b) + "\n\n"
            screen_update()

        # perform fetch
        try:

            wdata = utf8_decode(urlopen(url).read())
            wdata = json.loads(wdata)
            songs = get_tracks_from_json(wdata)

        except (URLError, HTTPError) as e:
            g.message = F('no data') % e
            g.content = logo(c.r)
            return

    if songs and pre_load:
        # preload first result url
        kwa = {"song": songs[0], "delay": 0}
        t = threading.Thread(target=preload, kwargs=kwa)
        t.start()

    if songs:
        # cache results
        add_to_url_memo(url, songs[::])
        g.model.songs = songs
        return True

    return False

def generate_search_qs(term, page=None, result_count=None, match='term'):
    """ Return query string. """
    if not result_count:
        result_count = 100

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

def search(term, page=None, splash=True):
    """ Perform search. """
    if not term or len(term) < 2:
        return

    print("search for %s", term)
    url = "https://www.googleapis.com/youtube/v3/search"
    query = generate_search_qs(term, page)
    have_results = _search(url, term, query)

    if have_results:
        g.message = "Search results for %s%s%s" % (c.y, term, c.w)
        g.last_opened = ""
        g.last_search_query = {"term": term}
        g.browse_mode = "normal"
        g.current_pagetoken = page or ''
        g.content = generate_songlist_display(frmat="search")

    else:
        g.message = "Found nothing for %s%s%s" % (c.y, term, c.w)
        g.content = logo(c.r)
        g.current_pagetoken = ''
        g.last_search_query = {}

# def matchfunction(func, regex, userinput):
#     """ Match userinput against regex.

#     Call func, return True if matches.

#     """
#     if regex.match(userinput):
#         matches = regex.match(userinput).groups()
#         print("input: %s", userinput)
#         print("function call: %s", func.__name__)
#         print("regx matches: %s", matches)

#         if g.debug_mode:
#             func(*matches)

#         else:

#             try:
#                 func(*matches)

#             except IndexError:
#                 g.message = F('invalid range')
#                 g.content = g.content or generate_songlist_display()

#             except (ValueError, IOError) as e:
#                 g.message = F('cant get track') % uni(e)
#                 g.content = g.content or\
#                     generate_songlist_display(zeromsg=g.message)

#         return True


def searchstring (searchstring):
    search(searchstring)
    return

# def execute ():

#     regx = {
#         ls: r'ls$',
#         vp: r'vp$',
#         dump: r'(un)?dump',
#         play: r'(%s{0,3})([-,\d\s]{1,250})\s*(%s{0,3})$' % (rs, rs),
#         info: r'i\s*(\d{1,4})$',
#         quits: r'(?:q|quit|exit)$',
#         plist: r'pl\s+%s' % pl,
#         yt_url: r'url\s(.*[-_a-zA-Z0-9]{11}.*$)',
#         search: r'(?:search|\.|/)\s*([^./].{1,500})',
#         dl_url: r'dlurl\s(.*[-_a-zA-Z0-9]{11}.*$)',
#         play_pl: r'play\s+(%s|\d+)$' % word,
#         related: r'r\s?(\d{1,4})$',
#         download: r'(dv|da|d|dl|download)\s*(\d{1,4})$',
#         play_url: r'playurl\s(.*[-_a-zA-Z0-9]{11}[^\s]*)(\s-(?:f|a|w))?$',
#         comments: r'c\s?(\d{1,4})$',
#         nextprev: r'(n|p)$',
#         play_all: r'(%s{0,3})(?:\*|all)\s*(%s{0,3})$' % (rs, rs),
#         user_pls: r'u(?:ser)?pl\s(.*)$',
#         save_last: r'save\s*$',
#         pl_search: r'(?:\.\.|\/\/|pls(?:earch)?\s)\s*(.*)$',
#         # setconfig: r'set\s+([-\w]+)\s*"?([^"]*)"?\s*$',
#         setconfig: r'set\s+([-\w]+)\s*(.*?)\s*$',
#         clip_copy: r'x\s*(\d+)$',
#         down_many: r'(da|dv)\s+((?:\d+\s\d+|-\d|\d+-|\d,)(?:[\d\s,-]*))\s*$',
#         show_help: r'(?:help|h)(?:\s+([-_a-zA-Z]+)\s*)?$',
#         show_encs: r'encoders?\s*$',
#         user_more: r'u\s?([\d]{1,4})$',
#         down_plist: r'(da|dv)pl\s+%s' % pl,
#         clearcache: r'clearcache$',
#         usersearch: r'user\s+([^\s].{1,})$',
#         shuffle_fn: r'\s*(shuffle)\s*$',
#         add_rm_all: r'(rm|add)\s(?:\*|all)$',
#         showconfig: r'(set|showconfig)\s*$',
#         search_album: r'album\s*(.{0,500})',
#         playlist_add: r'add\s*(-?\d[-,\d\s]{1,250})(%s)$' % word,
#         down_user_pls: r'(da|dv)upl\s+(.*)$',
#         open_save_view: r'(open|save|view)\s*(%s)$' % word,
#         songlist_mv_sw: r'(mv|sw)\s*(\d{1,4})\s*[\s,]\s*(\d{1,4})$',
#         songlist_rm_add: r'(rm|add)\s*(-?\d[-,\d\s]{,250})$',
#         playlist_rename: r'mv\s*(%s\s+%s)$' % (word, word),
#         playlist_remove: r'rmp\s*(\d+|%s)$' % word,
#         open_view_bynum: r'(open|view)\s*(\d{1,4})$',
#         playlist_rename_idx: r'mv\s*(\d{1,3})\s*(%s)\s*$' % word}

#     for k, v in regx.items():
#         if matchfunction(k, v, userinput):
#             break
#     return
