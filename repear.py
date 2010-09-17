#!/usr/bin/env python
#
# rePear, the iPod database management tool
# Copyright (C) 2006-2008 Martin J. Fiedler <martin.fiedler@gmx.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

__title__   = "rePear"
__version__ = "0.4.1"
__author__  = "Martin J. Fiedler"
__email__   = "martin.fiedler@gmx.net"
banner = "Welcome to %s, version %s" % (__title__, __version__)

"""
TODO: preserve .m3u playlists on update

0.4.1:
 - added artwork formats for nano 4G
 - added support for the 'mhii link' field, required for artwork on nano 4G

0.4.0:
 - added command-line options to override master playlist and scrobble config
   file names (either relative to the root directory or relative to the
   working directory from which rePear is being run)
 - fixed crash bug for rare broken ID3v2 tags
 - added 'help' action

0.4.0-rc2:
 - fixed crash after scrobbling

0.4.0-rc1:
 - added configuration actions
 - root directory auto-detection now checks current working directory, too
 - fixed time calculations (required for proper scrobbling)
 - fixed artwork processing if an artwork file is broken
 - fixed broken sort function

0.4.0-beta1:
 - added support for 2007 models (nano 3G, classic)
 - added support for MPEG-4 audio files
 - added experimental support for MPEG-4 video files
 - added Play Counts import to update play and skip counts and ratings
 - added last.fm scrobble support
 - added 'update' action
 - added playlist sort functionality
 - added global playlist option "skip album playlists = no" to disable
   pruning of album playlists
 - added global playlist option "directory playlists = yes" to turn every
   directory into a playlist
 - fixed iTunesDB parser so it reads post-iTunes 7.1 files
 - sped up MP3 parser by using Xing/LAME or FhG info tags, where available
 - ^C menu asks whether to skip a single track or completely cancel freezing
 - added --nowait option to bypass Win32 keypress waiting on quit
 - made the freeze process much more error robust -- I/O errors in single
   files won't stop the whole process any longer
 - added crash handler
 - fixed crash in the directory playlist construction code for Ogg->MP3
   transcoded files
 - fixed ID3v2.3.0 parser (thanks to Ian Camaclang for the patch!)
 - added msvcr71.dll to Win32 distribution
 - model list in help screen is now sorted
 - unfreezing empty databases now works
 - improved mtime comparison
 - not importing dot-files and directories any longer

0.3.0:
 - added playlist support -- two methods are availabe:
   - the "master playlist file" in /repear_playlists.ini
   - every *.m3u is collected and converted to a playlist, unless it exactly
     covers an album (in which case it would be pointless)
 - added Balanced Shuffle feature
 - MP3 detection code is now more error-tolerant (doesn't clip the file at the
   first broken frame any longer)
 - added automatic inference of the compilation flag: if the album tag of all
   files in a directory is the same, but the artists differ, the whole
   directory will be marked as a compilation
 - fixed crash when OggDec was not present
 - added a filename allocator; should improve big (>10GB) iPod compatibility
 - now guessing the track number from the file name even if there is an ID3v1.0
   tag available
 - when freezing, the cache file is now saved as early as possible to minimize
   data loss if rePear crashes at a later point (e.g. playlist processing)

0.2.2:
 - fixed endianness issue
 - filename-based metadata guessing now includes track numbers

0.2.1:
 - fixed album sort order

0.2.0:
 - Artwork support
 - limited automatic pathfinding on Windows systems: rePear needs to be
   installed somewhere on the iPod volume, but not necessarily in the root
   directory

0.1.1:
 - make dissect less destructive (keep filenames)
 - accept all full-hour time differences
 - auto-create an iTunesDB backup
 - create iTunesSD et al. -> iPod shuffle support
 - automatic transcoding of Ogg Vorbis tracks
 - some bugfixes
"""



DISSECT_BASE_DIR = "Dissected Tracks/"
DIRECTORY_COUNT = 10
DEFAULT_LAME_OPTS = "--quiet -h -V 5"
MASTER_PLAYLIST_FILE = "repear_playlists.ini"
SCROBBLE_CONFIG_FILE = "repear_scrobble.ini"
SUPPORTED_FILE_FORMATS = (".mp3", ".ogg", ".m4a", ".m4b", ".mp4")
MUSIC_DIR = "iPod_Control/Music/"
CONTROL_DIR = "iPod_Control/iTunes/"
ARTWORK_DIR = "iPod_Control/Artwork/"
DB_FILE = CONTROL_DIR + "iTunesDB"
CACHE_FILE = CONTROL_DIR + "repear.cache"
MODEL_FILE = CONTROL_DIR + "repear.model"
FWID_FILE = CONTROL_DIR + "fwid"
SCROBBLE_QUEUE_FILE = CONTROL_DIR + "repear.scrobble_queue"
ARTWORK_CACHE_FILE = ARTWORK_DIR + "repear.artwork_cache"
ARTWORK_DB_FILE = ARTWORK_DIR + "ArtworkDB"
def OLDNAME(x): return x.replace("repear", "retune")

import sys, optparse, os, fnmatch, stat, string, time, types, cPickle, random
import re, warnings, traceback, getpass, md5
warnings.filterwarnings('ignore', category=RuntimeWarning)  # for os.tempnam()
import iTunesDB, mp3info, hash58, scrobble
Options = {}


################################################################################
## Some internal management functions                                         ##
################################################################################

broken_log = False
homedir = ""

def open_log():
    global logfile
    Options['log'] = os.path.abspath(Options['log'])
    try:
        logfile = open(Options['log'], "w")
    except IOError:
        logfile = None

def log(line, flush=True):
    global logfile
    sys.stdout.write(line)
    if flush: sys.stdout.flush()
    if logfile:
        try:
            logfile.write(line)
            if flush: logfile.flush()
        except IOError:
            broken_log = True
iTunesDB.log = log

def quit(code=1):
    global logfile, broken_log
    if logfile:
        try:
            logfile.close()
        except IOError:
            broken_log = True
        logfile = None
    log("\nLog written to `%s'\n" % Options['log'])
    if broken_log:
        log("WARNING: there were errors while writing the log file\n")
    if not Options.get('nowait', True):  # Windows: wait for keypress
        log("Press ENTER to close this window. ", True)
        try:
            raw_input()
        except (IOError, EOFError, KeyboardInterrupt):
            pass  # I don't care at this point, we're going to leave anyway
    sys.exit(code)

def fatal(line):
    log("FATAL: %s\n" % line)
    quit()

def confirm(prompt):
    sys.stdout.write("%sDo you really want to continue? (y/N) " % prompt)
    sys.stdout.flush()
    try:
        answer = raw_input()
    except (IOError, EOFError, KeyboardInterrupt):
        answer = ""
    if answer.strip().lower() in ("y", "yes"):
        return
    log("Action aborted by user.\n")
    quit()



def goto_root_dir():
    global homedir
    homedir = os.path.abspath(os.path.split(sys.argv[0])[0]).replace("\\", "/")
    if homedir[-1] != '/': homedir += '/'
    if Options['root']:
        rootdir = Options['root'].replace("\\", "/")
        if rootdir[-1] != '/': rootdir += '/'
    else:
        # no root directory specified -- try the current directory
        rootdir = os.getcwd().replace("\\", "/")
        if rootdir[-1] != '/': rootdir += '/'
        if not os.path.isfile(rootdir + "iPod_Control/iTunes/iTunesDB"):
            # not found? then try the executable's directory
            rootdir = homedir
            # special case on Windows: if the current directory doesn't contain
            # a valid iPod directory structure, reduce the pathname to the first
            # three characters, as in 'X:/', which is usually the root directory
            if (os.name == 'nt') and not(os.path.isfile(rootdir + DB_FILE)):
                rootdir = rootdir[:3]

    if os.path.isfile(rootdir + DB_FILE):
        log("iPod root directory is `%s'\n" % rootdir)
    else:
        fatal("root directory `%s' contains no iPod database" % rootdir)

    try:
        os.chdir(rootdir)
    except OSError, e:
        fatal("can't change to the iPod root directory: %s" % e.strerror)



def load_cache(return_on_error=None):
    try:
        f = open(CACHE_FILE, "rb")
    except IOError:
        try:
            f = open(OLDNAME(CACHE_FILE), "rb")
        except IOError:
            return return_on_error
    try:
        content = cPickle.load(f)
        f.close()
    except (IOError, EOFError, cPickle.PickleError):
        return return_on_error
    return content

def save_cache(content=None):
    try:
        f = open(CACHE_FILE, "wb")
        cPickle.dump(content, f)
        f.close()
        delete(OLDNAME(CACHE_FILE), True)
    except (IOError, EOFError, cPickle.PickleError):
        log("ERROR: can't save the rePear cache\n")


def execute(program, args):
    global homedir
    if os.name == "nt":
        spawn = os.spawnv
        path = homedir + program + ".exe"
        args = ["\"%s\"" % arg for arg in args]
    else:
        spawn = os.spawnvp
        path = program
    try:
        return spawn(os.P_WAIT, path, [program] + args)
    except OSError, e:
        log("ERROR: can't execute %s: %s\n" % (program, e.strerror))
    except KeyboardInterrupt:
        return -2





################################################################################
## Some generic tool functions                                                ##
################################################################################

def printable(x, kill_chars=""):
    if type(x)==types.UnicodeType:
        x = x.encode(sys.getfilesystemencoding(), 'replace')
    x = str(x)
    for c in kill_chars:
        x = x.replace(c, "_")
    return x


def move_file(src, dest):
    # check if source file exists
    if not os.path.isfile(src):
        log("[FAILED]\nERROR: source file `%s' doesn't exist\n" %
            printable(src), True)
        return 'missing'

    # don't clobber files (wouldn't work on Windows anyway)
    if os.path.isfile(dest):
        log("[FAILED]\nERROR: destination file `%s' already exists\n" %
            printable(dest), True)
        return 'exists'

    # create parent directories if necessary
    dest_dir = os.path.split(dest)[0]
    if dest_dir and not(os.path.isdir(dest_dir)):
        try:
            os.makedirs(dest_dir)
        except OSError, e:
            log("[FAILED]\nERROR: can't create destination directory `%s': %s\n" %
                (printable(dest_dir), e.strerror), True)
            return 'mkdir'

    # finally rename it
    try:
        os.rename(src, dest)
    except OSError, e:
        log(" [FAILED]\nERROR: can't move `%s' to `%s': %s\n" %
            (printable(src), printable(dest), e.strerror), True)
        return 'move'
    log("[OK]\n", True)
    return None


def backup(filename):
    dest = "%s.repear_backup" % filename
    if os.path.exists(dest): return
    try:
        os.rename(filename, dest)
        return True
    except OSError, e:
        log("WARNING: Cannot backup `%s': %s\n" % (filename, e.strerror))
        return False


def delete(filename, may_fail=False):
    if not os.path.exists(filename): return
    try:
        os.remove(filename)
        return True
    except OSError, e:
        if not may_fail:
            log("ERROR: Cannot delete `%s': %s\n" % (filename, e.strerror))
        return False


class ExceptionLogHelper:
    def write(self, s):
        log(s)
Logger = ExceptionLogHelper()


# path and file name sorting routines
re_digit = re.compile(r'(\d+)')
def tryint(s):
    try: return int(s)
    except ValueError: return s.lower()
def fnrep(fn):
    return tuple(map(tryint, re_digit.split(fn)))
def fncmp(a, b):
    return cmp(fnrep(a), fnrep(b))
def pathcmp(a, b):
    a = a.split(u'/')
    b = b.split(u'/')
    # compare base directories
    for i in xrange(min(len(a), len(b)) - 1):
        r = fncmp(a[i], b[i])
        if r: return r
    # subdirectories first
    r = len(b) - len(a)
    if r: return r
    # finally, compare leaf file name
    return fncmp(a[-1], b[-1])
def trackcmp(a, b):
    return pathcmp(a.get('original path', None) or a.get('path', '???'), \
                   b.get('original path', None) or b.get('path', '???'))


################################################################################
## Filename Allocator                                                         ##
################################################################################

class Allocator:
    def __init__(self, root, files_per_dir=100, max_dirs=100):
        self.root = root
        self.files_per_dir = files_per_dir
        self.max_dirs = max_dirs
        self.names = {}
        self.files = {}
        digits = []
        digits = []
        try:
            dirs = os.listdir(root)
        except OSError:
            os.mkdir(root)
            dirs = []
        for elem in dirs:
            try:
                index = self.getindex(elem)
            except ValueError:
                continue
            self.names[index] = elem
            self.files[index] = self.scandir(os.path.join(root, elem))
            digits.append(len(elem) - 1)
        if digits:
            digits.sort()
            self.fmt = "F%%0%dd" % (digits[len(digits) / 2])
        else:
            self.fmt = "F%02d"
        if not self.files:
            self.mkdir(0)
        self.current_dir = min(self.files.iterkeys())

    def getindex(self, name):
        if not name: raise ValueError
        if name[0].upper() != 'F': raise ValueError
        return int(name[1:], 10)

    def scandir(self, root):
        try:
            dir_contents = os.listdir(root)
        except OSError:
            return []
        dir_contents = [os.path.splitext(x)[0].upper() for x in dir_contents if x[0] != '.']
        return dict(zip(dir_contents, [None] * len(dir_contents)))

    def __len__(self):
        return sum(map(len, self.files.itervalues()))

    def __repr__(self):
        return "<Allocator: %d files in %d directories>" % (len(self), len(self.files))

    def allocate_ex(self, index):
        while True:
            name = "".join([random.choice(string.ascii_uppercase) for x in range(4)])
            if not(name in self.files[index]):
                break
        self.files[index][name] = None
        return self.names[index] + '/' + name

    def mkdir(self, index):
        if index in self.files:
            return
        name = self.fmt % index
        try:
            os.mkdir(os.path.join(self.root, name))
        except OSError:
            pass
        self.names[index] = name
        self.files[index] = {}

    def allocate(self):
        count, index = min([(len(d[1]), d[0]) for d in self.files.iteritems()])
        # need to allocate a new directory
        if (count >= self.files_per_dir) and (len(self.files) < self.max_dirs):
            available = [i for i in range(self.max_dirs) if not i in self.files]
            index = available[0]
            self.mkdir(index)
        # generate a file name
        while True:
            name = "".join([random.choice(string.ascii_uppercase) for x in range(4)])
            if not(name in self.files[index]):
                break
        self.files[index][name] = None
        return self.root + '/' + self.names[index] + '/' + name

    def add(self, fullname):
        try:
            dirname, filename = fullname.split('/')[-2:]
            index = self.getindex(dirname)
        except ValueError:
            return
        filename = os.path.splitext(filename)[0]
        if not index in self.files:
            self.names[index] = dirname
            self.files[index] = {}
        self.files[index][filename] = None


################################################################################
## Balanced Shuffle                                                           ##
################################################################################

class BalancedShuffle:
    def __init__(self):
        self.root = { None: [] }

    def add(self, path, data):
        if type(path) == types.UnicodeType:
            path = path.encode('ascii', 'replace')
        path = path.replace("\\", "/").lower().split("/")
        if path and not(path[0]):
            path.pop(0)
        if not path:
            return  # broken path
        root = self.root
        while True:
            if len(path) == 1:
                # tail reached
                root[None].append(data)
                break
            component = path.pop(0)
            if not component in root:
                root[component] = { None: [] }
            root = root[component]

    def shuffle(self, root=None):
        if not root:
            root = self.root

        # shuffle the files of the root node
        random.shuffle(root[None])

        # build a list of directories to shuffle
        subdirs = filter(None, [root[None]] + \
                  [self.shuffle(root[key]) for key in root if key])

        # check for "tail" cases
        if not subdirs:
            return []
        if len(subdirs) == 1:
            return subdirs[0]

        # pad subdirectory list to a common length
        dircount = len(subdirs)
        maxlen = max(map(len, subdirs))
        subdirs = [self.fill(sd, maxlen) for sd in subdirs]

        # collect all items
        res = []
        last = -1
        for i in xrange(maxlen):
            # determine the directory order for this "column"
            order = range(dircount)
            random.shuffle(order)
            if (len(order) > 1) and (order[0] == last):
                order.append(order.pop(0))
            while len(order) > 1:  # = if len(order) > 1: while True:
                random.shuffle(order)
                if last != order[0]: break
            last = order[-1]

            # produce a result
            res.extend(filter(lambda x: x is not None, \
                       [subdirs[j][i] for j in order]))
        return res

    def fill(self, data, total):
        ones = len(data)
        invert = (ones > (total / 2))
        if invert:
            ones = total - ones
        bitmap = [0] * total
        remain = total
        for fraction in xrange(ones, 0, -1):
            bitmap[total - remain] = 1
            skip = float(remain) / fraction
            skip = random.randrange(int(0.9 * skip), int(1.1 * skip) + 2)
            remain -= min(max(1, skip), remain - fraction + 1)
        if invert:
            bitmap = [1-x for x in bitmap]
        offset = random.randrange(0, total)
        bitmap = bitmap[offset:] + bitmap[:offset]
        def decide(x):
            if x: return data.pop(0)
            return None
        return map(decide, bitmap)


################################################################################
## Play Counts import and Scrobbling                                          ##
################################################################################

def ImportPlayCounts(cache, index, scrobbler=None):
    log("Updating play counts and ratings ... ", True)

    # open Play Counts file
    try:
        pc = iTunesDB.PlayCountsReader()
    except IOError:
        log("\n0 track(s) updated.\n")
        return False
    except iTunesDB.InvalidFormat:
        log("\n-- Error in Play Counts file, import failed.\n")
        return False

    # parse old iTunesDB
    try:
        db = iTunesDB.DatabaseReader()
        files = [printable(item.get('path', u'??')[1:].replace(u':', u'/')).lower() for item in db]
        db.f.close()
        del db
    except (IOError, iTunesDB.InvalidFormat):
        log("\n-- Error in iTunesDB, import failed.\n")
        return False

    # plausability check
    if len(files) != pc.entry_count:
        log("\n-- Mismatch between iTunesDB and Play Counts file, import failed.\n")
        return False

    # walk through Play Counts file
    update_count = 0
    try:
        for item in pc:
            path = files[item.index]
            try:
                track = cache[index[path]]
            except (KeyError, IndexError):
                continue
            updated = False
            if item.play_count:
                track['play count'] = track.get('play count', 0) + item.play_count
                updated = True
            if item.last_played:
                track['last played time'] = item.last_played
                updated = True
            if item.skip_count:
                track['skip count'] = track.get('skip count', 0) + item.skip_count
                updated = True
            if item.last_skipped:
                track['last skipped time'] = item.last_skipped
                updated = True
            if item.bookmark:
                track['bookmark time'] = item.bookmark * 0.001
                updated = True
            if item.rating:
                track['rating'] = item.rating
                updated = True
            if updated:
                update_count += 1
            if item.play_count and scrobbler:
                scrobbler += track
        pc.f.close()
        del pc
    except (IOError, iTunesDB.InvalidFormat):
        log("\n-- Error in Play Counts file, import failed.\n")
        return False
    log("%d track(s) updated.\n" % update_count)
    return update_count


################################################################################
## DISSECT action                                                             ##
################################################################################

def Dissect():
    state, cache = load_cache((None, None))

    if (state is not None) and not(Options['force']):
        if state=="frozen": confirm("""
WARNING: This action will put all the music files on your iPod into a completely
new directory structure. All previous file and directory names will be lost.
This also means that any iTunesDB backups you have will NOT work any longer!
""")
        if state=="unfrozen": confirm("""
WARNING: The database is currently unfrozen, so the following operations will
almost completely fail.
""")

    cache = []
    try:
        db = iTunesDB.DatabaseReader()

        for info in db:
            if not info.get('path', None):
                log("ERROR: track lacks path attribute\n")
                continue
            src = printable(info['path'])[1:].replace(":", "/")
            if not os.path.isfile(src):
                log("ERROR: file `%s' is found in database, but doesn't exist\n" % src)
                continue
            if not info.get('title', None):
                info.update(iTunesDB.GuessTitleAndArtist(info['path']))
            ext = os.path.splitext(src)[1]
            base = DISSECT_BASE_DIR
            if info.get('artist', None):
                base += printable(info['artist'], "<>/\\:|?*\"") + '/'
                if info.get('album', None):
                    base += printable(info['album'], "<>/\\:|?*\"") + '/'
                    if info.get('track number', None):
                        base += "%02d - " % info['track number']
            base += printable(info['title'], "<>/\\:|?*\"")

            # move the file, but avoid filename collisions
            serial = 1
            dest = base + ext
            while os.path.exists(dest):
                serial += 1
                dest = base + " (%d)"%serial + ext
            log("%s => %s " % (src, dest), True)
            if move_file(src, dest):
                continue   # move failed

            # create a placeholder cache entry
            cache.append({
                'path': src,
                'original path': unicode(dest, sys.getfilesystemencoding(), 'replace')
            })
    except IOError:
        fatal("can't read iTunes database file")
    except iTunesDB.InvalidFormat:
        raise
        fatal("invalid iTunes database format")

    # clear the cache
    save_cache(("unfrozen", cache))



################################################################################
## FREEZE utilities                                                           ##
################################################################################

g_freeze_error_count = 0

def check_file(base, fn):
    if fn.startswith('.'):
        return None   # skip dot-files and -directories
    key, ext = [component.lower() for component in os.path.splitext(fn)]
    fullname = base + fn
    try:
        s = os.stat(fullname)
    except OSError:
        log("ERROR: directory entry `%s' is inaccessible\n" % fn)
        return None
    isfile = int(not(stat.S_ISDIR(s[stat.ST_MODE])))
    if isfile and not(stat.S_ISREG(s[stat.ST_MODE])):
        return None   # no directory and no normal file -> skip this crap
    if not(isfile) and (fullname=="iPod_Control" or fullname=="iPod_Control/Music"):
        isfile = -1   # trick the sort algorithm to move iPC/Music to front
    return (isfile, fnrep(fn), fullname, s, ext, key)


def make_cache_index(cache):
    index = {}
    for i in xrange(len(cache)):
        for path in [cache[i][f] for f in ('path', 'original path') if f in cache[i]]:
            key = printable(path).lower()
            if key in index:
                log("ERROR: `%s' is cached multiple times\n" % printable(path))
            else:
                index[key] = i
    return index


def find_in_cache(cache, index, path, s):
    i = index.get(printable(path).lower(), None)
    if i is None:
        return (False, None)  # not found
    info = cache[i]

    # check size and modification time
    if info.get('size', None) != s[stat.ST_SIZE]:
        return (False, info)  # mismatch
    if not iTunesDB.compare_mtime(info.get('mtime', 0), s[stat.ST_MTIME]):
        return (False, info)  # mismatch

    # all checks passed => correct file
    return (True, info)


def move_music(src, dest, info):
    global g_freeze_error_count
    format = info.get('format', "mp3-cbr")
    if format == "ogg":
        src = printable(src)
        dest = os.path.splitext(printable(dest))[0] + ".mp3"
        tmp = os.tempnam(None, "repear") + ".wav"

        # generate new source filename (replace .ogg by .mp3)
        newsrc = info.get('original path', src)
        if type(newsrc) != types.UnicodeType:
            newsrc = unicode(newsrc, sys.getfilesystemencoding(), 'replace')
        newsrc = u'.'.join(newsrc.split(u'.')[:-1]) + u'.mp3'

        # decode the Ogg file
        res = execute("oggdec", ["-Q", "-o", tmp, src])
        if res != 0:
            g_freeze_error_count += 1
            log("[FAILED]\nERROR: cannot execute OggDec ... result '%s'\n" % res)
            delete(tmp, may_fail=True)
            return None
        else:
            log("[decoded] ", True)

        # build LAME option list
        lameopts = Options['lameopts'].split(' ')
        for key, optn in (('title','tt'), ('artist','ta'), ('album','tl'), ('year','ty'), ('comment','tc'), ('track number','tn')):
            if key in info:
                lameopts.extend(["--"+optn, printable(info[key])])
        if 'genre' in info:
            ref_genre = printable(info['genre']).lower().replace(" ","")
            for number, genre in mp3info.ID3v1Genres.iteritems():
                if genre.lower().replace(" ","") == ref_genre:
                    lameopts.extend(["--tg", str(number)])
                    break

        # encode to MP3
        res = execute("lame", lameopts + [tmp, dest])
        delete(tmp)
        if res != 0:
            g_freeze_error_count += 1
            log("[FAILED]\nERROR: cannot execute LAME ... result code %d\n" % res)
            return None
        else:
            log("[encoded] ", True)

        # check the resulting file
        info = mp3info.GetAudioFileInfo(dest)
        if not info:
            g_freeze_error_count += 1
            log("[FAILED]\nERROR: generated MP3 file is invalid\n")
            delete(dest)
            return None
        delete(src)
        info['original path'] = newsrc
        info['changed'] = 2
        log("[OK]\n", True)
        return info

    else:  # no Ogg file  ->  move directly
        if move_file(src, dest):
            g_freeze_error_count += 1
            return None  # failed
        else:
            return info


def freeze_dir(cache, index, allocator, playlists=[], base="", artwork=None):
    global g_freeze_error_count
    try:
        flist = filter(None, [check_file(base, fn) for fn in os.listdir(base or ".")])
    except KeyboardInterrupt:
        raise
    except:
        g_freeze_error_count += 1
        log(base + "/\n" + " runtime error, traceback follows ".center(79, '-') + "\n")
        traceback.print_exc(file=Logger)
        log(79*'-' + "\n")
        return []

    # generate directory list
    directories = filter(lambda x: x[0] < 1, flist)
    directories.sort()

    # add playlist files
    playlists.extend([x[2] for x in flist if (x[0] > 0) and (x[4] == ".m3u")])

    # generate music file list
    music = filter(lambda x: (x[0] > 0) and (x[4] in SUPPORTED_FILE_FORMATS), flist)
    music.sort()

    # if there are no subdirs and no music files here, prune this directory
    if not(directories) and not(music):
        return []

    # generate name -> artwork file associations
    image_assoc = dict([(x[5], x[2]) for x in flist if (x[0] > 0) and (x[4] in (".jpg", ".png"))])

    # find artwork files that are not associated to a file or directory
    unassoc_images = image_assoc.copy()
    for d0,d1,d2,d3,d4,key in directories:
        if key in unassoc_images:
            del unassoc_images[key]
    for d0,d1,d2,d3,d4,key in music:
        if key in unassoc_images:
            del unassoc_images[key]
    unassoc_images = unassoc_images.values()
    unassoc_images.sort()

    # use one of the unassociated artwork files as this directory's artwork,
    # unless the inherited artwork file name is already a perfect match (i.e.
    # the directory name and the artwork name are identical)
    if unassoc_images:
        if not(artwork) or not(artwork.lower().startswith(base[:-1].lower())):
            artwork = find_good_artwork(unassoc_images, base)

    # now that the artwork problem is solved, we start processing:
    # recurse into subdirectories first
    res = []
    for isfile, dummy, fullname, s, ext, key in directories:
        res.extend(freeze_dir(cache, index, allocator, playlists, fullname + '/', artwork))

    # now process the local files
    locals = []
    unique_artist = None
    unique_album = None
    for isfile, dummy, fullname, s, ext, key in music:
        try:
            # we don't need to move this file if it's already in the Music directory
            already_there = fullname.startswith(MUSIC_DIR)

            # is this track cached?
            log(fullname + ' ', True)
            valid, info = find_in_cache(cache, index, fullname, s)
            if valid:
                info['changed'] = 0
                log("[cached] ", True)
            else:
                if info:
                    # cache entry present, but invalid => save iPod_Control location
                    path = info['path']
                    changed = 1
                else:
                    path = fullname
                    changed = 2
                info = mp3info.GetAudioFileInfo(fullname)
                iTunesDB.FillMissingTitleAndArtist(info)
                info['changed'] = changed
                if not already_there:
                    if type(info['path']) == types.UnicodeType:
                        info['original path'] = info['path']
                    else:
                        info['original path'] = unicode(info['path'], sys.getfilesystemencoding(), 'replace')
                    info['path'] = path

            # move the track to where it belongs
            if not already_there:
                path = info.get('path', None)
                if not(path) or os.path.exists(path) or not(os.path.isdir(os.path.split(path)[0])):
                    # if anything is wrong with the path, generate a new one
                    path = allocator.allocate() + ext
                else:
                    allocator.add(path)
                info['path'] = path
                info = move_music(fullname, path, info)
                if not info: continue  # something failed
            else:
                allocator.add(fullname)
                log("[OK]\n", True)

            # associate artwork to the track
            info['artwork'] = image_assoc.get(key, artwork)

            # check for unique artist and album
            check = info.get('artist', None)
            if not locals:
                unique_artist = check
            elif check != unique_artist:
                unique_artist = False
            check = info.get('album', None)
            if not locals:
                unique_album = check
            elif check != unique_album:
                unique_album = False

            # finally, append the track to the track list
            locals.append(info)

        except KeyboardInterrupt:
            log("\nInterrupted by user.\nContinue with next file or abort? [c/A] ")
            try:
                answer = raw_input()
            except (IOError, EOFError, KeyboardInterrupt):
                answer = ""
            if not answer.lower().startswith("c"):
                raise

        except:
            g_freeze_error_count += 1
            log("\n" + " runtime error, traceback follows ".center(79, '-') + "\n")
            traceback.print_exc(file=Logger)
            log(79*'-' + "\n")

    # if all files in this directory share the same album title, but differ
    # in the artist name, we assume it's a compilation
    if unique_album and not(unique_artist):
        for info in locals:
            info['compilation'] = 1

    # combine the lists and return them
    res.extend(locals)
    return res


################################################################################
## playlist sorting                                                           ##
################################################################################

def cmp_lst(a, b, order, empty_pos):
    a = max(a.get('last played time', 0), a.get('last skipped time', 0))
    b = max(b.get('last played time', 0), b.get('last skipped time', 0))
    if not a:
        if not b: return 0
        return empty_pos
    else:
        if not b: return -empty_pos
    return order * cmp(a, b)

def cmp_path(a, b, order, empty_pos):
    return order * trackcmp(a, b)

class cmp_key:
    def __init__(self, key):
        self.key = key
    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.key))
    def __call__(self, a, b, order, empty_pos):
        if self.key in a:
            if self.key in b:
                a = a[self.key]
                if type(a) in (types.StringType, types.UnicodeType): a = a.lower()
                b = b[self.key]
                if type(b) in (types.StringType, types.UnicodeType): b = b.lower()
                return order * cmp(a, b)
            else:
                return -empty_pos
        else:
            if self.key in b:
                return empty_pos
            else:
                return 0

sort_criteria = {
    'playcount': lambda a,b,o,e: o*cmp(a.get('play count', 0), b.get('play count', 0)),
    'skipcount': lambda a,b,o,e: o*cmp(a.get('skip count', 0), b.get('skip count', 0)),
    'startcount': lambda a,b,o,e: o*cmp(a.get('play count', 0) + a.get('skip count', 0), b.get('play count', 0) + b.get('skip count', 0)),
    'artworkcount': lambda a,b,o,e: o*cmp(a.get('artwork count', 0), b.get('artwork count', 0)),
    'laststartedtime': cmp_lst,
    'laststarttime': cmp_lst,
    'lastplaytime': 'last played time',
    'lastskiptime': 'last skipped time',
    'movie': 'movie flag',
    'filesize': 'size',
    'path': cmp_path,
}
for nc in ('title', 'artist', 'album', 'compilation', 'rating', 'path', \
'length', 'size', 'track number', 'year', 'bitrate', 'sample rate', 'volume', \
'last played time', 'last skipped time', 'mtime', 'disc number', 'total discs', \
'BPM', 'movie flag'):
    sort_criteria[nc.replace(' ', '').lower()] = nc


re_sortspec = re.compile(r'^([<>+-]*)(.*?)([<>+-]*)$')
class SSParseError: pass

class SortSpec:
    def __init__(self, pattern=None):
        if pattern:
            self.parse(pattern)
        else:
            self.criteria = []

    def parse(self, pattern):
        self.criteria = filter(None, map(self._parse_criterion, pattern.split(',')))

    def _parse_criterion(self, text):
        text = text.strip()
        if not text: return None
        m = re_sortspec.match(text)
        if not m:
            raise SSParseError, "invalid sort criterion `%s'" % text
        text = m.group(2).strip()
        key = text.lower().replace('_', '').replace(' ', '')
        try:
            criterion = sort_criteria[key]
        except KeyError:
            raise SSParseError, "unknown sort criterion `%s'" % text
        if type(criterion) == types.StringType:
            criterion = cmp_key(criterion)
        modifiers = m.group(1) + m.group(3)
        order = 1
        if '-' in modifiers: order = -1
        empty_pos = -1
        if '<' in modifiers: empty_pos = 1
        return (criterion, order, empty_pos)

    def _cmp(self, a, b):
        for cmp_func, order, empty_pos in self.criteria:
            res = cmp_func(self.tracks[a], self.tracks[b], order, empty_pos)
            if res: return res
        return cmp(a, b)

    def sort(self, tracks):
        self.tracks = tracks
        index = list(range(len(self.tracks)))
        index.sort(self._cmp)
        del self.tracks
        return [tracks[i] for i in index]

    def __add__(self, other):
        self.criteria += other.criteria
        return self

    def __len__(self):
        return len(self.criteria)


################################################################################
## playlist processing                                                        ##
################################################################################

def add_scripted_playlist(db, tracklist, list_name, include, exclude, shuffle=False, changemask=0, sort=None):
    if not(list_name) or not(include or changemask) or not(tracklist):
        return
    tracks = []
    log("Processing playlist `%s': " % iTunesDB.kill_unicode(list_name), True)
    for track in tracklist:
        if not 'original path' in track:
            continue  # we don't know the real name of this file, so skip it
        name = track['original path'].encode(sys.getfilesystemencoding(), 'replace').lower()
        ok = changemask & track.get('changed', 0)
        for pattern in include:
            if fnmatch.fnmatch(name, pattern):
                ok = True
                break
        for pattern in exclude:
            if fnmatch.fnmatch(name, pattern):
                ok = False
                break
        if ok:
            tracks.append(track)
    log("%d tracks\n" % len(tracks))
    if not tracks:
        return
    if shuffle == 1:
        shuffle = BalancedShuffle()
        for info in tracks:
            shuffle.add(info.get('original path', None) or info.get('path', "???"), info)
        tracks = shuffle.shuffle()
    if shuffle == 2:
        random.shuffle(tracks)
    if sort:
        tracks = sort.sort(tracks)
    db.add_playlist(tracks, list_name)


def process_m3u(db, tracklist, index, filename, skip_album_playlists):
    if not(filename) or not(tracklist):
        return
    basedir, list_name = os.path.split(filename)
    list_name = unicode(os.path.splitext(list_name)[0], sys.getfilesystemencoding(), 'replace')
    log("Processing playlist `%s': " % iTunesDB.kill_unicode(list_name), True)
    try:
        f = open(filename, "r")
    except IOError, e:
        log("ERROR: cannot open `%s': %s\n" % (filename, e.strerror))
    tracks = []

    # collect all tracks
    for line in f:
        line = line.strip()
        if line.startswith('#'):
            continue  # comment or EXTM3U line
        line = os.path.normpath(os.path.join(basedir, line)).replace("\\", "/").lower()
        try:
            tracks.append(tracklist[index[line]])
        except KeyError:
            continue  # file not found -> sad, but not fatal
    f.close()

    # check if it's an album playlist
    if skip_album_playlists:
        ref_album = None
        ok = True  # "we don't know enough about this playlist, so be optimistic"
        for info in tracks:
            if not 'album' in info: continue
            if not ref_album:
                ref_album = info['album']
            elif info['album'] != ref_album:
                ok = True  # "this playlist is mixed-album, so it's clean"
                break
            else:
                ok = False  # "all known tracks are from the same album, how sad"
        if not ok:
            # now check if this playlist really covers the _whole_ album
            ok = len(tracks)
            for info in tracklist:
                try:
                    if info.get('album', None) == ref_album:
                        ok -= 1
                        if ok < 0: break
                except (TypeError, UnicodeDecodeError):
                    # old (<0.3.0) cache files contain non-unicode information
                    # for ID3v1 tags which can cause trouble here, so ...
                    continue
        if not(ok) :
            log("album playlist, discarding.\n")
            return

    # finish everything
    log("%d tracks\n" % len(tracks))
    if not tracks:
        return
    db.add_playlist(tracks, list_name)


def make_directory_playlists(db, tracklist):
    log("Processing directory playlists ...\n")
    dirs = {}
    for track in tracklist:
        path = track.get('original path', None)
        if not path: continue
        for dir in path.split('/')[:-1]:
            if not dir: continue
            if dir in dirs:
                dirs[dir].append(track)
            else:
                dirs[dir] = [track]
    dirlist = dirs.keys()
    dirlist.sort(fncmp)

    for dir in dirlist:
        log("Processing playlist `%s': " % iTunesDB.kill_unicode(dir), True)
        tracks = dirs[dir]
        tracks.sort(trackcmp)
        log("%d tracks\n" % len(tracks))
        db.add_playlist(tracks, dir)


shuffle_options = {
    "0": 0,   "no": 0,  "off": 0,  "false": 0,  "disabled": 0    ,  "none": 0,
    "1": 1,  "yes": 1,   "on": 1,   "true": 0,   "enabled": 1,  "balanced": 1,
    "2": 2,                                       "random": 2,  "standard": 2,
}

def parse_master_playlist_file():
    # helper function
    def yesno(s):
        if s.lower() in ('true', 'enable', 'enabled', 'yes', 'y'):
            return 1
        try:
            return (int(s) != 0)
        except ValueError:
            return 0
    # default values
    skip_album_playlists = True
    directory_playlists = False
    lists = []
    # now we're parsing
    try:
        f = open(MASTER_PLAYLIST_FILE, "r")
    except IOError:
        return (skip_album_playlists, directory_playlists, lists)
    include = []
    exclude = []
    list_name = None
    shuffle = 0
    changemask = 0
    sort = SortSpec()
    lineno = 0
    for line in f:
        lineno += 1
        line = line.split(';', 1)[0].strip()
        if not line: continue
        if (line[0] == '[') and (line[-1] == ']'):
            if list_name and (include or changemask):
                lists.append((list_name, include, exclude, shuffle, changemask, sort))
            include = []
            exclude = []
            list_name = line[1:-1]
            shuffle = False
            changemask = 0
            sort = SortSpec()
            continue
        try:
            key, value = [x.strip().replace("\\", "/") for x in line.split('=')]
        except ValueError:
            continue
        key = key.lower().replace(' ', '_')
        if not value:
            log("WARNING: In %s:%d: key `%s' without a value\n" % (MASTER_PLAYLIST_FILE, lineno, key))
            continue
        if key == "skip_album_playlists":
            if list_name: log("WARNING: In %s:%d: global option `%s' inside a playlist\n" % (MASTER_PLAYLIST_FILE, lineno, key))
            skip_album_playlists = yesno(value)
        elif key == "directory_playlists":
            if list_name: log("WARNING: In %s:%d: global option `%s' inside a playlist\n" % (MASTER_PLAYLIST_FILE, lineno, key))
            directory_playlists = yesno(value)
        elif key == "shuffle":
            try:
                shuffle = shuffle_options[value.lower()]
            except KeyError:
                log("WARNING: In %s:%d: invalid value `%s' for shuffle option\n" % (MASTER_PLAYLIST_FILE, lineno, value))
        elif key == "new":
            changemask = (changemask & (~2)) | (yesno(value) << 1)
        elif key == "changed":
            changemask = (changemask & (~1)) | yesno(value)
        elif key == "sort":
            try:
                sort = SortSpec(value) + sort
            except SSParseError, e:
                log("WARNING: In %s:%d: %s\n" % (MASTER_PLAYLIST_FILE, lineno, e))
        elif key in ("include", "exclude"):
            if value[0] == "/":
                value = value[1:]
            if os.path.isdir(value):
                if value[-1] != "/":
                    value += "/"
                value += "*"
            if key == "include":
                include.append(value.lower())
            else:
                exclude.append(value.lower())
        else:
            log("WARNING: In %s:%d: unknown key `%s'\n" % (MASTER_PLAYLIST_FILE, lineno, key))
    f.close()
    if list_name and (include or changemask):
        lists.append((list_name, include, exclude, shuffle, changemask, sort))
    return (skip_album_playlists, directory_playlists, lists)


################################################################################
## artwork                                                                    ##
################################################################################

re_cover = re.compile(r'[^a-z]cover[^a-z]')
re_front = re.compile(r'[^a-z]front[^a-z]')
def find_good_artwork(files, base):
    if not files:
        return None   # sorry, no files here
    dirname, basename = os.path.split(base)
    if not basename:
        dirname, basename = os.path.split(base)
    basename = basename.strip().lower()
    candidates = []
    for name in files:
        ref = os.path.splitext(name)[0].strip().lower()
        # if the file has the same name as the directory, we'll use that directly
        if ref == basename:
            return name
        ref = "|%s|" % ref
        score = 0
        if re_cover.search(ref):
            # if the name contains the word "cover", it's a good candidate
            score = -1
        if re_front.search(ref):
            # if the name contains the word "front", that's even better
            score = -2
        candidates.append((score, name.lower(), name))
    candidates.sort()
    return candidates[0][2]  # return the candidate with the best score


def GenerateArtwork(model, tracklist):
    # step 0: check PIL availability
    if not iTunesDB.PILAvailable:
        log("ERROR: Python Imaging Library (PIL) isn't installed, Artwork is disabled.\n")
        log("       Visit http://www.pythonware.com/products/pil/ to get PIL.\n")
        return

    # step 1: generate an artwork list
    artwork_list = {}
    for track in tracklist:
        artwork = track.get('artwork', None)
        if not artwork:
            continue    # no artwork file
        dbid = track.get('dbid', None)
        if not dbid:
            continue    # artwork doesn't make sense without a dbid
        if artwork in artwork_list:
            artwork_list[artwork].append(dbid)
        else:
            artwork_list[artwork] = [dbid]

    # step 2: generate the artwork directory (if it doesn't exist already)
    try:
        os.mkdir(ARTWORK_DIR[:-1])
    except OSError:
        pass   # not critical (yet)

    # step 3: try to load the artwork cache
    try:
        try:
            f = open(ARTWORK_CACHE_FILE, "rb")
        except IOError:
            f = open(OLDNAME(ARTWORK_CACHE_FILE), "rb")
        old_cache = cPickle.load(f)
        f.close()
    except (IOError, EOFError, cPickle.PickleError):
        old_cache = ({}, {})

    # step 4: generate and save the ArtworkDB
    artwork_db, new_cache, dbid2mhii = iTunesDB.ArtworkDB(model, artwork_list, cache_data=old_cache)
    backup(ARTWORK_DB_FILE)
    try:
        f = open(ARTWORK_DB_FILE, "wb")
        f.write(artwork_db)
        f.close()
    except IOError, e:
        log("FAILED: %s\n" % e.strerror +
            "ERROR: The ArtworkDB file could not be written. This means that the iPod will\n" +
            "not show any artwork items.\n")

    # step 5: save the artwork cache
    try:
        f = open(ARTWORK_CACHE_FILE, "wb")
        cPickle.dump(new_cache, f)
        f.close()
        delete(OLDNAME(ARTWORK_CACHE_FILE), True)
    except (IOError, EOFError, cPickle.PickleError):
        log("ERROR: can't save the artwork cache\n")

    # step 6: update the 'mhii link' field
    for track in tracklist:
        dbid = track.get('dbid', None)
        mhii = dbid2mhii.get(dbid, None)
        if mhii:
            track['mhii link'] = mhii
        elif 'mhii link' in track:
            del track['mhii link']


################################################################################
## FREEZE and UPDATE action                                                   ##
################################################################################

def Freeze(CacheInfo=None, UpdateOnly=False):
    global g_freeze_error_count
    if not CacheInfo: CacheInfo = load_cache((None, []))
    state, cache = CacheInfo

    if UpdateOnly:
        if (state != "frozen") and not(Options['force']):
            confirm("""
NOTE: The database is not frozen, the update will not work as expected!
""")
    else:
        if (state == "frozen") and not(Options['force']):
            confirm("""
NOTE: The database is already frozen.
""")
        state = "frozen"

    # allocate the filename allocator
    if not UpdateOnly:
        log("Scanning for present files ...\n", True)
        try:
            allocator = Allocator(MUSIC_DIR[:-1])
        except (IOError, OSError):
            log("FATAL: can't read or write the music directory!\n")
            return

    # parse the master playlist setup file
    skip_album_playlists, directory_playlists, master_playlists = parse_master_playlist_file()

    # index the track cache
    log("Indexing track cache ...\n", True)
    index = make_cache_index(cache)

    # allocate scrobbler
    scrobbler = scrobble.Scrobbler()
    if scrobbler.config(SCROBBLE_CONFIG_FILE):
        if not scrobbler.load(SCROBBLE_QUEUE_FILE):
            scrobbler.load(OLDNAME(SCROBBLE_QUEUE_FILE))
    else:
        scrobbler = None

    # import Play Counts information
    if ImportPlayCounts(cache, index, scrobbler):
        # save cache and delete the play counts file afterwards
        save_cache((state, cache))
        delete(CONTROL_DIR + "Play Counts", may_fail=True)

    # scrobble
    if scrobbler and scrobbler.queue:
        old_count = len(scrobbler.queue)
        log("Scrobbling %d track(s) ... " % old_count, True)
        try:
            scrobbler.scrobble()
            log("OK.\n")
        except scrobble.ScrobbleError, e:
            log("%s\n" % e)
        except KeyboardInterrupt:
            log("interrupted by user.\n")
        new_count = len(scrobbler.queue)
        log("%s track(s) scrobbled, %d track(s) still in queue.\n" % (old_count - new_count, new_count))
        if scrobbler.save(SCROBBLE_QUEUE_FILE):
            delete(OLDNAME(SCROBBLE_QUEUE_FILE), True)
        else:
            log("Error writing scrobbler state file.\n")

    # now go for the real thing
    playlists = []
    if not UpdateOnly:
        log("Searching for playable files ...\n", True)
        tracklist = freeze_dir(cache, index, allocator, playlists)
        log("Scan complete: %d tracks found, %d error(s).\n" % (len(tracklist), g_freeze_error_count))

        # cache save checkpoint
        save_cache((state, tracklist))
    else:
        # in update mode, use the cached track list directly
        tracklist = cache

    # artwork processing
    if not UpdateOnly:
        model = Options['model']
        if not model:
            try:
                try:
                    f = open(MODEL_FILE, "r")
                except IOError:
                    f = open(OLDNAME(MODEL_FILE), "r")
                model = f.read().strip()[:10].lower()
                f.close()
                log("\nLoaded model name `%s' from the cache.\n" % model)
            except IOError:
                pass
        if model:
            model = model.strip().lower()
            if not(model in iTunesDB.ImageFormats):
                log("\nWARNING: model `%s' unrecognized, skipping Artwork generation.\n" % model)
            else:
                try:
                    f = open(MODEL_FILE, "w")
                    f.write(model)
                    f.close()
                    delete(OLDNAME(MODEL_FILE), True)
                except IOError:
                    pass
        else:
            log("\nNo model specified, skipping Artwork generation.\n")
    else:
        model = None

    # generate track IDs
    if not UpdateOnly:
        iTunesDB.GenerateIDs(tracklist)

    # generate the artwork list
    if model and not(UpdateOnly):
        log("\nProcessing Artwork ...\n", True)
        GenerateArtwork(model, tracklist)

    # build the database
    log("\nCreating iTunesDB ...\n", True)
    db = iTunesDB.iTunesDB(tracklist, name="%s %s"%(__title__, __version__))

    # save the tracklist as the cache for the next run
    save_cache((state, tracklist))

    # add playlists according to the master playlist file
    for listspec in master_playlists:
        add_scripted_playlist(db, tracklist, *listspec)

    # process all m3u playlists
    if playlists:
        log("Updating track index ...\n", True)
        index = make_cache_index(tracklist)
    for plist in playlists:
        process_m3u(db, tracklist, index, plist, skip_album_playlists)

    # create directory playlists
    if directory_playlists:
        make_directory_playlists(db, tracklist)

    # finish iTunesDB and apply hash stuff
    log("Finalizing iTunesDB ...\n")
    db = db.finish()
    fwids = hash58.GetFWIDs()
    try:
        f = open(FWID_FILE, "r")
        fwid = f.read().strip().upper()
        f.close()
        if len(fwid) != 16:
            fwid = None
    except IOError:
        fwid = None
    store_fwid = False
    if fwid:
        # preferred FWID stored on iPod
        if fwids and not(fwid in fwids):
            log("WARNING: Stored serial number doesn't match any connected iPod!\n")
    else:
        # auto-detect FWID
        if fwids:
            fwid = fwids[0]
            store_fwid = (len(fwids) == 1)
            if not store_fwid:
                log("WARNING: Multiple iPods are connected. If the iPod you are trying to freeze is\n" +
                    "         a recent model, it might not play anything. Please try again with the\n" +
                    "         other iPod unplugged.\n")
        else:
            log("WARNING: Could not determine your iPod's serial number. If it's a recent model,\n" +
                "         it will likely not play anything!\n")
    if fwid:
        db = hash58.UpdateHash(db, fwid)
    if store_fwid:
        try:
            f = open(FWID_FILE, "w")
            f.write(fwid)
            f.close()
        except IOError:
            pass

    # write iTunesDB
    write_ok = True
    backup(DB_FILE)
    try:
        f = open(DB_FILE, "wb")
        f.write(db)
        f.close()
    except IOError, e:
        write_ok = False
        log("FAILED: %s\n" % e.strerror +
            "ERROR: The iTunesDB file could not be written. This means that the iPod will\n" +
            "not play anything.\n")

    # write iPod shuffle stuff (if necessary)
    if os.path.exists(CONTROL_DIR + "iTunesSD"):
        backup(CONTROL_DIR + "iTunesSD")
        log("Creating iTunesSD ... ", True)
        db = iTunesDB.iTunesSD(tracklist)
        try:
            f = open(CONTROL_DIR + "iTunesSD", "wb")
            f.write(db)
            f.close()
            log("\n")
        except IOError, e:
            write_ok = False
            log("FAILED: %s\n" % e.strerror +
                "ERROR: The iTunesSD file could not be written. This means that the iPod will\n" +
                "not play anything.\n")
        delete(CONTROL_DIR + "iTunesShuffle")
        delete(CONTROL_DIR + "iTunesPState")

    # generate statistics
    if write_ok:
        log("\nYou can now unmount the iPod and listen to your music.\n")
        sec = int(sum([track.get('length', 0.0) for track in tracklist]) + 0.5)
        log("There are %d tracks (%d:%02d:%02d" % (len(tracklist), sec/3600, (sec/60)%60, sec%60))
        if sec > 86400: log(" = %.1f days" % (sec / 86400.0))
        log(") waiting for you to be heard.\n")

    # finally, save the tracklist as the cache for the next run
    save_cache((state, tracklist))



################################################################################
## UNFREEZE action                                                            ##
################################################################################

def Unfreeze(CacheInfo=None):
    if not CacheInfo: CacheInfo = load_cache((None, None))
    state, cache = CacheInfo

    try:
        cache_len = len(cache)
    except:
        cache_len = None

    if not(state) or (cache_len is None):
        fatal("can't unfreeze: rePear cache is missing or broken")
    if state!="frozen" and not(Options['force']):
        confirm("""
NOTE: The database is already unfrozen.
""")

    log("Moving tracks back to their original locations ...\n")
    success = 0
    failed = 0
    for info in cache:
        src = printable(info.get('path', ""))
        dest = printable(info.get('original path', ""))
        if not src:
            log("ERROR: track lacks path attribute\n")
            continue
        if not dest:
            continue  # no original path
        log("%s " % dest)
        if move_file(src, dest):
            failed += 1
        else:
            success += 1
    log("Operation complete: %d tracks total, %d moved back, %d failed.\n" % \
        (len(cache), success, failed))
    log("\nYou can now manage the music files on your iPod.\n")
    save_cache(("unfrozen", cache))


################################################################################
## the configuration actions                                                  ##
################################################################################

def ConfigFWID():
    log("Determining serial number (FWID) of attached iPods ...\n")
    fwids = hash58.GetFWIDs()
    try:
        f = open(FWID_FILE, "r")
        fwid = f.read().strip().upper()
        f.close()
        if len(fwid) != 16:
            fwid = None
    except IOError:
        fwid = None
    if not fwids:
        # no FWIDs detected
        if fwid:
            return log("No iPod detected, but FWID is already set up (%s).\n\n" % fwid)
        else:
            return log("No iPod detected, can't determine FWID.\n\n")
    if len(fwids) > 1:
        # multiple FWIDs detected
        if fwid and (fwid in fwids):
            return log("Multiple iPods detected, but FWID is already set up (%s).\n\n" % fwid)
        else:
            return log("Multiple iPods detected, can't determine FWID.\n" + \
                       "Please unplug all iPods except the one you're configuring\n\n")
    # exactly one FWID detected
    log("Serial number detected: %s\n" % fwids[0])
    if fwid and (fwid != fwids[0]):
        log("Warning: This serial number is different from the one that has been stored on\n" + \
            "         the iPod (%s). Storing the new FWID anyway.\n" % fwid)
    fwid = fwids[0]
    if not fwid:
        return log("\n")
    try:
        f = open(FWID_FILE, "w")
        f.write(fwid)
        f.close()
        log("FWID saved.\n\n")
    except IOError:
        log("Error saving the FWID.\n\n")


models = (
    (None, "other/unspecified (no cover artwork)"),
    ('photo', '4g', "iPod photo (4G)"),
    ('video', '5g', "iPod video (5G)"),
    ('classic', '6g', "iPod classic (6G)"),
    ('nano', 'nano1g', 'nano2g', "iPod nano (1G/2G)"),
    ('nano3g', "iPod nano (3G, \"fat nano\")"),
    ('nano4g', "iPod nano (4G)"),
)
def is_model_ok(mod_id):
    for m in models[1:]:
        if mod_id in m[:-1]:
            return True
    return False

def ConfigModel():
    try:
        try:
            f = open(MODEL_FILE, "r")
        except IOError:
            f = open(OLDNAME(MODEL_FILE), "r")
        model = f.read().strip().lower()
        f.close()
        if not is_model_ok(model):
            model = None
    except IOError:
        model = None
    print "Select iPod model:"
    default = 0
    for i in xrange(len(models)):
        if model in models[i][:-1]:
            default = i
            c = "*"
        else:
            c = " "
        print c, "%d." % i, models[i][-1]
    try:
        answer = int(raw_input("Which model is this iPod? [0-%d, default %d] => " % (len(models) - 1, default)))
    except (IOError, EOFError, KeyboardInterrupt, ValueError):
        answer = default
    if (answer < 0) or (answer >= len(models)):
        answer = default
    if answer:
        try:
            f = open(MODEL_FILE, "w")
            f.write(models[answer][0])
            f.close()
            log("Model set to `%s'.\n\n" % models[answer][-1])
        except IOError:
            log("Error: cannot set model.\n\n")
    else:
        delete(MODEL_FILE, True)
        log("Model set to `other'.\n\n")
    delete(OLDNAME(MODEL_FILE), True)


re_ini_key = re.compile(r'^[ \t]*(;)?[ \t]*(\w+)[ \t]*=[ \t]*(.*?)[ \t]*$', re.M)
class INIKey:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.present = False
        self.valid = False
    def check(self, m):
        if not m: return
        if m.group(2).lower() != self.key: return
        self.present = True
        valid = not(not(m.group(1)))
        if not(valid) and self.valid: return
        self.start = m.start(3)
        self.end = m.end(3)
        self.comment = m.start(1)
    def apply(self, s):
        if not self.present:
            if not s.endswith("\n"): s += "\n"
            return s + "%s = %s\n" % (self.key, self.value)
        s = s[:self.start] + self.value + s[self.end:]
        if not(self.valid) and (self.comment >= 0):
            s = s[:self.comment] + s[self.comment+1:]
        return s

def ConfigScrobble():
    print "Please enter your last.fm username, or just press ENTER if you don't want to"
    try:
        username = raw_input("use scrobbling => ").strip()
    except (IOError, EOFError, KeyboardInterrupt):
        username = ""
    if username:
        try:
            password = getpass.getpass("password => ")
        except (IOError, EOFError, KeyboardInterrupt):
            password = ""
        if password:
            password = md5.md5(password).hexdigest()
        else:
            username = ""
    else:
        password = ""

    # import config file
    try:
        f = open(SCROBBLE_CONFIG_FILE, "rb")
        config = f.read()
        f.close()
    except IOError:
        config = ""
    crlf = (config.find("\r\n") >= 0)
    config = config.replace("\r\n", "\n")

    kuser = INIKey("username", username)
    kpass = INIKey("password", password)
    for m in re_ini_key.finditer(config):
        kuser.check(m)
        kpass.check(m)
    if kuser.present and kpass.present and (kuser.start < kpass.start):
        config = kpass.apply(config)
        config = kuser.apply(config)
    else:
        config = kuser.apply(config)
        config = kpass.apply(config)

    # export config file
    if crlf:
        config = config.replace("\n", "\r\n")
    try:
        f = open(SCROBBLE_CONFIG_FILE, "wb")
        f.write(config)
        f.close()
        if username:
            log("Scrobbling enabled for user `%s'.\n\n" % username)
        else:
            log("Scrobbling disabled.\n\n")
    except IOError:
        log("Error updating the scrobble config file.\n\n")


def ConfigAll():
    ConfigFWID()
    ConfigModel()
    ConfigScrobble()


################################################################################
## the two minor ("also-ran") actions                                         ##
################################################################################

def Auto():
    state, cache = load_cache((None, []))
    if state == 'frozen':
        Unfreeze((state, cache))
    else:
        Freeze((state, cache))

def Reset():
    state, cache = load_cache((None, []))
    if (state == 'frozen') and not(Options['force']):
        confirm("""
WARNING: The database is currently frozen. If you reset the cache now, you will
         lose all file name information. This cannot be undone!
""")
        return
    try:
        os.remove(CACHE_FILE)
    except OSError:
        try:
            save_cache((None, []))
        except IOError:
            pass
    delete(OLDNAME(CACHE_FILE), True)
    delete(ARTWORK_CACHE_FILE, True)
    delete(OLDNAME(ARTWORK_CACHE_FILE), True)
    log("\nCache reset.\n")




################################################################################
## the main function                                                          ##
################################################################################

class MyOptionParser(optparse.OptionParser):
    def format_help(self, formatter=None):
        models = iTunesDB.ImageFormats.keys()
        models.sort()
        return optparse.OptionParser.format_help(self, formatter) + """
Artwork is supported on the following models:
  """ + ", ".join(models) + """

actions:
  help         show this help message and exit
  freeze       move all music files into the iPod's library
  unfreeze     move music files back to their original location
  update       update the frozen database without scanning for new files
  dissect      generate an Artist/Album/Title directory structure
  reset        clear rePear's metadata cache
  cfg-fwid     determine the iPod's serial number and save it
  cfg-model    interactively configure the iPod model
  cfg-scrobble configure last.fm scrobbling
  config       run all of the configuration steps
If no action is specified, rePear automatically determines which of the
`freeze' or `unfreeze' actions should be taken.

"""

if __name__ == "__main__":
    parser = MyOptionParser(version=__version__,
             usage="%prog [options] [<action>]")
    parser.add_option("-r", "--root", action="store", default=None, metavar="PATH",
                      help="set the iPod's root directory path")
    parser.add_option("-l", "--log", action="store", default="repear.log", metavar="FILE",
                      help="set the output log file path")
    parser.add_option("-m", "--model", action="store", default=None, metavar="MODEL",
                      help="specify the iPod model (REQUIRED for artwork support)")
    parser.add_option("-L", "--lameopts", action="store", default=DEFAULT_LAME_OPTS, metavar="CMDLINE",
                      help="set the LAME encoder options (default: %s)" % DEFAULT_LAME_OPTS)
    parser.add_option("-f", "--force", action="store_true", default=False,
                      help="skip confirmation prompts for dangerous actions")
    parser.add_option("-p", "--playlist", action="store", default=None, metavar="FILE",
                      help="specify playlist config file")
    parser.add_option("-s", "--scrobble", action="store", default=None, metavar="FILE",
                      help="specify scrobble config file")
    if os.name == 'nt':
        parser.add_option("--nowait", action="store_true", default=False,
                          help="don't wait for keypress when finished")
    (opts, args) = parser.parse_args()
    Options = opts.__dict__

    if len(args)>1: parser.error("too many arguments")
    if args:
        action = args[0].strip().lower()
    else:
        action = "auto"
    if action == "help":
        parser.print_help()
        sys.exit(0)
    if not action in (
        'auto', 'freeze', 'unfreeze', 'update', 'dissect', 'reset', \
        'config', 'cfg-fwid', 'cfg-scrobble', 'cfg-model'
    ):
        parser.error("invalid action `%s'" % action)

    oldcwd = os.getcwd()
    open_log()
    log("%s\n%s\n\n" % (banner, len(banner) * '-'))
    if not logfile:
        log("WARNING: can't open log file `%s', logging disabled\n\n" % Options['log'])
    goto_root_dir()

    if Options['playlist']:
        first = Options['playlist'].replace("\\", "/").split('/', 1)[0]
        if first in (".", ".."):
            MASTER_PLAYLIST_FILE = os.path.normpath(os.path.join(oldcwd, Options['playlist']))
        else:
            MASTER_PLAYLIST_FILE = Options['playlist']
        log("master playlist file is `%s'\n" % MASTER_PLAYLIST_FILE)
    if Options['scrobble']:
        first = Options['scrobble'].replace("\\", "/").split('/', 1)[0]
        if first in (".", ".."):
            SCROBBLE_CONFIG_FILE = os.path.normpath(os.path.join(oldcwd, Options['scrobble']))
        else:
            SCROBBLE_CONFIG_FILE = Options['scrobble']
        log("scrobble configuration file is `%s'\n" % SCROBBLE_CONFIG_FILE)

    log("\n")
    try:
        if   action=="auto":         Auto()
        elif action=="freeze":       Freeze()
        elif action=="unfreeze":     Unfreeze()
        elif action=="update":       Freeze(UpdateOnly=True)
        elif action=="dissect":      Dissect()
        elif action=="reset":        Reset()
        elif action=="config":       ConfigAll()
        elif action=="cfg-fwid":     ConfigFWID()
        elif action=="cfg-model":    ConfigModel()
        elif action=="cfg-scrobble": ConfigScrobble()
        else:
            log("Unknown action, don't know what to do.\n")
        code = 0
    except SystemExit, e:
        sys.exit(e.code)
    except KeyboardInterrupt:
        log("\n" + 79*'-' + "\n\nAction aborted by user.\n")
        code = 2
    except:
        log("\n" + 79*'-' + "\n\nOOPS -- rePear crashed!\n\n")
        traceback.print_exc(file=Logger)
        log("\nPlease inform the author of rePear about this crash by sending the\nrepear.log file.\n")
        code = 1
    quit(code)
