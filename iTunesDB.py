#!/usr/bin/env python
#
# iTunesDB generator library for rePear, the iPod database management tool
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

import struct, random, types, array, sys, os, stat, time
try:
    import Image, JpegImagePlugin, PngImagePlugin
    PILAvailable = True
except ImportError:
    PILAvailable = False


def DefaultLoggingFunction(text, force_flush=True):
    sys.stdout.write(text)
    if force_flush:
        sys.stdout.flush()
log = DefaultLoggingFunction


################################################################################
## some helper classes to represent ITDB records, and some helper functions   ##
################################################################################

class Field:
    def __str__(self): raise Exception, "abstract function call"
    def __len__(self): raise Exception, "abstract function call"

class F_Tag(Field):
    def __init__(self, tag): self.tag = tag
    def __str__(self): return self.tag
    def __len__(self): return len(self.tag)

class F_Formatable(Field):
    def __init__(self, format, value):
        self.format = format
        self.value = value
    def __str__(self): return struct.pack("<"+self.format, self.value)
    def __len__(self): return struct.calcsize(self.format)

class F_Int64(F_Formatable):
    def __init__(self, value): F_Formatable.__init__(self, "Q", value)
class F_Int32(F_Formatable):
    def __init__(self, value): F_Formatable.__init__(self, "L", value)
class F_Int16(F_Formatable):
    def __init__(self, value): F_Formatable.__init__(self, "H", value)
class F_Int8(F_Formatable):
    def __init__(self, value): F_Formatable.__init__(self, "B", value)

class F_HeaderLength(F_Int32):
    def __init__(self): F_Int32.__init__(self, 0)
class F_TotalLength(F_Int32):
    def __init__(self): F_Int32.__init__(self, 0)
class F_ChildCount(F_Int32):
    def __init__(self): F_Int32.__init__(self, 0)

class F_Padding(Field):
    def __init__(self, length): self.length = length
    def __str__(self): return self.length * "\0"
    def __len__(self): return self.length


class Record:
    def __init__(self, header):
        self.header_length_at = None
        self.total_length_at = None
        self.child_count_at = None
        data = ""
        for field in header:
            if field.__class__ == F_HeaderLength: self.header_length_at = len(data)
            if field.__class__ == F_TotalLength:  self.total_length_at  = len(data)
            if field.__class__ == F_ChildCount:   self.child_count_at   = len(data)
            data += str(field)
        if self.header_length_at:
            data = data[:self.header_length_at] + struct.pack("<L", len(data)) + data[self.header_length_at+4:]
        self.data = data
        self.child_count = 0
    def add(self, obj, count=1):
        self.child_count += count
        self.data += str(obj)
    def __str__(self):
        data = self.data
        if self.total_length_at:
            data = data[:self.total_length_at] + struct.pack("<L", len(data)) + data[self.total_length_at+4:]
        if self.child_count_at:
            data = data[:self.child_count_at] + struct.pack("<L", self.child_count) + data[self.child_count_at+4:]
        return data


def kill_unicode(x):
    if type(x)!=types.UnicodeType: return x
    return x.encode(sys.getfilesystemencoding(), 'replace')


def make_compare_key(x):
    if type(x) == types.UnicodeType:
        return x.encode(sys.getfilesystemencoding(), 'replace').lower()
    elif type(x) == types.StringType:
        return x.lower()
    else:
        return x


def compare_dict(a, b, fields):
    for field in fields:
        res = cmp(make_compare_key(a.get(field,None)), \
                  make_compare_key(b.get(field,None)))
        if res: return res
    return 0


def ifelse(condition, then_val, else_val=None):
    if condition: return then_val
    else: return else_val


MAC_TIME_OFFSET = 2082844800
if time.daylight: tzoffset = time.altzone
else:             tzoffset = time.timezone
def unixtime2mactime(t):
    if not t: return t
    return t + MAC_TIME_OFFSET - tzoffset
def mactime2unixtime(t):
    if not t: return t
    return t - MAC_TIME_OFFSET + tzoffset


# "fuzzy" mtime comparison, allows for two types of slight deviations:
# 1. differences of exact multiples of one hour (usually time zome problems)
# 2. differences of less than 2 seconds (FAT timestamps are imprecise)
def compare_mtime(a, b):
    diff = abs(a - b)
    if diff > 86402: return False
    return ((diff % 3600) in (0, 1, 2, 3598, 3599))


################################################################################
## some higher-level ITDB record classes                                      ##
################################################################################

class StringDataObject(Record):
    def __init__(self, mhod_type, content):
        if type(content) != types.UnicodeType:
            content = unicode(content, sys.getfilesystemencoding(), 'replace')
        content = content.encode('utf_16_le', 'replace')
        Record.__init__(self, (
            F_Tag("mhod"),
            F_Int32(0x18),
            F_TotalLength(),
            F_Int32(mhod_type),
            F_Padding(8),
            F_Int32(1),
            F_Int32(len(content)),
            F_Int32(1),
            F_Padding(4)
        ))
        self.add(content)


class OrderDataObject(Record):
    def __init__(self, order):
        Record.__init__(self, (
            F_Tag("mhod"),
            F_Int32(0x18),
            F_Int32(0x2C),
            F_Int32(100),
            F_Padding(8),
            F_Int32(order),
            F_Padding(16)
        ))


class TrackItemRecord(Record):
    def __init__(self, info):
        if not 'id' in info:
            raise KeyError, "no track ID set"
        format = info.get('format', "mp3-cbr")
        if info.get('artwork', None):
            default_has_artwork = True
            default_artwork_size = 1
        else:
            default_has_artwork = False
            default_artwork_size = 0
        if 'video format' in info:
            media_type = 2
        else:
            media_type = 1
        Record.__init__(self, (
            F_Tag("mhit"),
            F_HeaderLength(),
            F_TotalLength(),
            F_ChildCount(),
            F_Int32(info.get('id', 0)),                                   # !!!
            F_Int32(info.get('visible', 1)), # visible
            F_Tag({"mp3": " 3PM", "aac": " CAA", "mp4a": "A4PM"}.get(format[:3], "\0\0\0\0")),
            F_Int16({"mp3-cbr": 0x100, "mp3-vbr": 0x101, "aac": 0, "mp4a": 0}.get(format, 0)),
            F_Int8(info.get('compilation', 0)),
            F_Int8(info.get('rating', 0)),
            F_Int32(unixtime2mactime(info.get('mtime', 0))),
            F_Int32(info.get('size', 0)),                                 # !!!
            F_Int32(int(info.get('length', 0) * 1000)),                   # !!!
            F_Int32(info.get('track number', 0)),
            F_Int32(info.get('total tracks', 0)),
            F_Int32(info.get('year', 0)),
            F_Int32(info.get('bitrate', 0)),                              # !!!
            F_Int16(0),
            F_Int16(info.get('sample rate', 0)),                          # !!!
            F_Int32(info.get('volume', 0)),
            F_Int32(info.get('start time', 0)),
            F_Int32(info.get('stop time', 0)),
            F_Int32(info.get('soundcheck', 0)),
            F_Int32(info.get('play count', 0)),
            F_Int32(0),
            F_Int32(unixtime2mactime(info.get('last played time', 0))),
            F_Int32(info.get('disc number', 0)),
            F_Int32(info.get('total discs', 0)),
            F_Int32(info.get('user id', 0)),
            F_Int32(info.get('date added', 0)),
            F_Int32(int(info.get('bookmark time', 0) * 1000)),
            F_Int64(info.get('dbid', 0)),                                 # !!!
            F_Int8(info.get('checked', 0)),
            F_Int8(info.get('application rating', 0)),
            F_Int16(info.get('BPM', 0)),
            F_Int16(info.get('artwork count', 1)),
            F_Int16({"wave": 0, "audible": 1}.get(format, 0xFFFF)),
            F_Int32(info.get('artwork size', default_artwork_size)),
            F_Int32(0),
            F_Formatable("f", info.get('sample rate', 0)),
            F_Int32(info.get('release date', 0)),
            F_Int16({"aac": 0x0033, "mp4a": 0x0033, "audible": 0x0029, "wave:": 0}.get(format, 0x0C)),
            F_Int16(info.get('explicit flag', 0)),
            F_Padding(8),
            F_Int32(info.get('skip count', 0)),
            F_Int32(unixtime2mactime(info.get('last skipped time', 0))),
            F_Int8(2 - int(info.get('has artwork', default_has_artwork))),
            F_Int8(not info.get('shuffle flag', 1)),
            F_Int8(info.get('bookmark flag', 0)),
            F_Int8(info.get('podcast flag', 0)),
            F_Int64(info.get('dbid', 0)),
            F_Int8(info.get('lyrics flag', 0)),
            F_Int8(info.get('movie flag', 0)),
            F_Int8(info.get('played mark', 1)),
            F_Padding(9),
            F_Int32(ifelse(format[:3]=="mp3", 0, info.get('sample count', 0))),
            F_Padding(16),
            F_Int32(media_type),
            F_Int32(0), # season number
            F_Int32(0), # episode number
            F_Padding(28),
            F_Int32(info.get('gapless data', 0)),
            F_Int32(0),
            F_Int16(info.get('gapless track flag', 0)),
            F_Int16(info.get('gapless album flag', 0)),
            F_Padding(20), # hash
            F_Padding(18), # misc unknowns
            F_Int16(info.get('album id', 0)),
            F_Padding(52), # padding before mhii link
            F_Int32(info.get('mhii link', 0))
        ))
        for mhod_type, key in ((1,'title'), (4,'artist'), (3,'album'), (5,'genre'), (6,'filetype'), (2,'path')):
            if key in info:
                value = info[key]
                if key=="path":
                    value = ":" + value.replace("/", ":").replace("\\", ":")
                self.add(StringDataObject(mhod_type, value))


class PlaylistItemRecord(Record):
    def __init__(self, order, trackid, timestamp=0):
        Record.__init__(self, (
            F_Tag("mhip"),
            F_HeaderLength(),
            F_TotalLength(),
            F_ChildCount(),
            F_Int32(0),
            F_Int32((trackid + 0x1337) & 0xFFFF),
            F_Int32(trackid),
            F_Int32(timestamp),
            F_Int32(0),
            F_Padding(40)
        ))
        self.add(OrderDataObject(order))


class PlaylistRecord(Record):
    def __init__(self, name, track_count, order=0, master=0, timestamp=0, plid=None, sort_order=1):
        if not plid: plid = random.randrange(0L, 18446744073709551615L)
        Record.__init__(self, (
            F_Tag("mhyp"),
            F_HeaderLength(),
            F_TotalLength(),
            F_ChildCount(),
            F_Int32(track_count),
            F_Int32(master),
            F_Int32(timestamp),
            F_Int64(plid),
            F_Int32(0),
            F_Int16(1),
            F_Int16(0),
            F_Int32(sort_order),
            F_Padding(60)
        ))
        self.add(StringDataObject(1, name))
        self.add(OrderDataObject(order))

    def add_index(self, tracklist, index_type, fields):
        order = range(len(tracklist))
        order.sort(lambda a,b: compare_dict(tracklist[a], tracklist[b], fields))
        mhod = Record((
            F_Tag("mhod"),
            F_Int32(24),
            F_TotalLength(),
            F_Int32(52),
            F_Padding(8),
            F_Int32(index_type),
            F_Int32(len(order)),
            F_Padding(40)
        ))
        arr = array.array('L', order)
        # the array module doesn't directly support endianness, so we detect
        # the machine's endianness and swap if it is big-endian
        if ord(array.array('L', [1]).tostring()[3]):
            arr.byteswap()
        data = arr.tostring()
        mhod.add(data)
        self.add(mhod)

    def set_playlist(self, track_ids):
        for i in xrange(len(track_ids)):
            self.add(PlaylistItemRecord(i+1, track_ids[i]), 0)



################################################################################
## the toplevel ITDB class                                                    ##
################################################################################

class iTunesDB:
    def __init__(self, tracklist, name="Unnamed", dbid=None, dbversion=0x19):
        if not dbid: dbid = random.randrange(0L, 18446744073709551615L)

        self.mhbd = Record((
            F_Tag("mhbd"),
            F_HeaderLength(),
            F_TotalLength(),
            F_Int32(0),
            F_Int32(dbversion),
            F_ChildCount(),
            F_Int64(dbid),
            F_Int16(2),
            F_Padding(14),
            F_Int16(0),  # hash indicator (set later by hash58)
            F_Padding(20),  # first hash
            F_Tag("en"),  # language = 'en'
            F_Tag("\0rePear!"),  # library persistent ID
            F_Padding(20),  # hash58
            F_Padding(80)
        ))

        self.mhsd = Record((
            F_Tag("mhsd"),
            F_HeaderLength(),
            F_TotalLength(),
            F_Int32(1),
            F_Padding(80)
        ))
        self.mhlt = Record((
            F_Tag("mhlt"),
            F_HeaderLength(),
            F_ChildCount(),
            F_Padding(80)
        ))

        for track in tracklist:
            self.mhlt.add(TrackItemRecord(track))

        self.mhsd.add(self.mhlt)
        del self.mhlt
        self.mhbd.add(self.mhsd)

        self.mhsd = Record((
            F_Tag("mhsd"),
            F_HeaderLength(),
            F_TotalLength(),
            F_Int32(2),
            F_Padding(80)
        ))
        self.mhlp = Record((
            F_Tag("mhlp"),
            F_HeaderLength(),
            F_ChildCount(),
            F_Padding(80)
        ))

        mhyp = PlaylistRecord(name, len(tracklist), master=1, sort_order=10)
        mhyp.add_index(tracklist, 0x03, ('title',))
        mhyp.add_index(tracklist, 0x04, ('album','disc number','track number','title'))
        mhyp.add_index(tracklist, 0x05, ('artist','album','disc number','track number','title'))
        mhyp.add_index(tracklist, 0x07, ('genre','artist','album','disc number','track number','title'))
        mhyp.add_index(tracklist, 0x12, ('composer','title'))
        mhyp.set_playlist([track['id'] for track in tracklist])
        self.mhlp.add(mhyp)

    def add_playlist(self, tracks, name="Unnamed"):
        mhyp = PlaylistRecord(name, len(tracks), sort_order=1)
        mhyp.set_playlist([track['id'] for track in tracks])
        self.mhlp.add(mhyp)

    def finish(self):
        self.mhsd.add(self.mhlp)
        del self.mhlp
        self.mhbd.add(self.mhsd)
        del self.mhsd
        result = str(self.mhbd)
        del self.mhbd
        return result



################################################################################
## ArtworkDB / PhotoDB record classes                                         ##
################################################################################

class RGB565_LE:
    bpp = 16
    def convert(data):
        res = array.array('B', [0 for x in xrange(len(data)/3*2)])
        io = 0
        for ii in xrange(0, len(data), 3):
            g = ord(data[ii+1]) >> 2
            res[io] = ((g & 7) << 5) | (ord(data[ii+2]) >> 3)
            res[io|1] = (ord(data[ii]) & 0xF8) | (g >> 3)
            io += 2
        return res.tostring()
    convert = staticmethod(convert)

ImageFormats = {
    'nano':   ((1027, 100, 100, RGB565_LE),
               (1031,  42,  42, RGB565_LE)),
    'photo':  ((1016, 140, 140, RGB565_LE),
               (1017,  56,  56, RGB565_LE)),
    'video':  ((1028, 100, 100, RGB565_LE),
               (1029, 200, 200, RGB565_LE)),
    'nano3g': ((1055, 128, 128, RGB565_LE),
               (1060, 320, 320, RGB565_LE),
               (1061,  55,  56, RGB565_LE)),
    'nano4g': ((1055, 128, 128, RGB565_LE),
               (1078,  80,  80, RGB565_LE),
               (1071, 240, 240, RGB565_LE),
               (1074,  50,  50, RGB565_LE)),
    '4g': 'photo',
    '5g': 'video',
    '6g': 'nano3g',
    'classic': 'nano3g',
    'nano1g': 'nano',
    'nano2g': 'nano',
}

class ImageInfo:
    pass

class ArtworkFormat:
    def __init__(self, descriptor, cache_info=(0,0)):
        self.fid, self.height, self.width, self.format = descriptor
        self.filename = "F%04d_1.ithmb" % self.fid
        self.size = self.width * self.height * self.format.bpp/8
        self.fullname = "iPod_Control/Artwork/" + self.filename

        # check if the cache file can be used
        try:
            s = os.stat(self.fullname)
            use_cache = stat.S_ISREG(s[stat.ST_MODE]) \
                        and compare_mtime(cache_info[0], s[stat.ST_MTIME]) \
                        and (s[stat.ST_SIZE] == cache_info[1])
        except OSError:
            use_cache = False

        # load the cache
        if use_cache:
            try:
                f = open(self.fullname, "rb")
                self.cache = f.read()
                f.close()
            except IOError:
                use_cache = False
        if not use_cache:
            self.cache = None

        # open the destination file
        try:
            self.f = open(self.fullname, "wb")
        except IOError, e:
            log("WARNING: Error opening the artwork data file `%s'\n", self.filename)
            self.f = None

    def close(self):
        if self.f:
            self.f.close()
        try:
            s = os.stat(self.fullname)
            cache_info = (s[stat.ST_MTIME], s[stat.ST_SIZE])
        except OSError:
            cache_info = (0, 0)
        return (self.fid, cache_info)

    def GenerateImage(self, image, index, cache_entry=None):
        if cache_entry and self.cache:
            offset = self.size * cache_entry['index']
            data = self.cache[offset : offset+self.size]
            sx = cache_entry['dim'][self.fid]['sx']
            sy = cache_entry['dim'][self.fid]['sy']
            mx = cache_entry['dim'][self.fid]['mx']
            my = cache_entry['dim'][self.fid]['my']
        else:
            log(" [%dx%d]" % (self.width, self.height), True)

            # sx/sy = resulting image size
            sx = self.width
            sy = image.size[1] * sx / image.size[0]
            if sy > self.height:
                sy = self.height
                sx = image.size[0] * sy / image.size[1]
            # mx/my = margin size
            mx = self.width  - sx
            my = self.height - sy

            # process the image
            temp = image.resize((sx, sy), Image.ANTIALIAS)
            thumb = Image.new('RGB', (self.width, self.height), (255, 255, 255))
            thumb.paste(temp, (mx/2, my/2))
            del temp
            data = self.format.convert(thumb.tostring())
            del thumb

        # save the image
        try:
            self.f.seek(self.size * index)
            self.f.write(data)
        except IOError:
            log(" [WRITE ERROR]", True)

        # return image metadata
        iinfo = ImageInfo()
        iinfo.format = self
        iinfo.index = index
        iinfo.sx = sx
        iinfo.sy = sy
        iinfo.mx = mx
        iinfo.my = my
        return iinfo



class ArtworkDBStringDataObject(Record):
    def __init__(self, mhod_type, content):
        if type(content) != types.UnicodeType:
            content = unicode(content, sys.getfilesystemencoding(), 'replace')
        content = content.encode('utf_16_le', 'replace')
        padding = len(content) % 4
        if padding: padding = 4 - padding
        Record.__init__(self, (
            F_Tag("mhod"),
            F_Int32(0x18),
            F_TotalLength(),
            F_Int16(mhod_type),
            F_Int16(padding),
            F_Padding(8),
            F_Int32(len(content)),
            F_Int32(2),
            F_Int32(0)
        ))
        self.add(content)
        if padding:
            self.add("\0" * padding)


class ImageDataObject(Record):
    def __init__(self, iinfo):
        Record.__init__(self, (
            F_Tag("mhod"),
            F_Int32(0x18),
            F_TotalLength(),
            F_Int32(2),
            F_Padding(8)
        ))

        mhni = Record((
            F_Tag("mhni"),
            F_Int32(0x4C),
            F_TotalLength(),
            F_ChildCount(),
            F_Int32(iinfo.format.fid),
            F_Int32(iinfo.format.size * iinfo.index),
            F_Int32(iinfo.format.size),
            F_Int16(iinfo.my),
            F_Int16(iinfo.mx),
            F_Int16(iinfo.sy),
            F_Int16(iinfo.sx),
            F_Padding(4),
            F_Int32(iinfo.format.size),
            F_Padding(32)
        ))

        mhod = ArtworkDBStringDataObject(3, ":" + iinfo.format.filename)
        mhni.add(mhod)
        self.add(mhni)


class ImageItemRecord(Record):
    def __init__(self, img_id, dbid, iinfo_list, orig_size=0):
        Record.__init__(self, (
            F_Tag("mhii"),
            F_Int32(0x98),
            F_TotalLength(),
            F_ChildCount(),
            F_Int32(img_id),
            F_Int64(dbid),
            F_Padding(20),
            F_Int32(orig_size),
            F_Padding(100)
        ))

        for iinfo in iinfo_list:
            self.add(ImageDataObject(iinfo))


def ArtworkDB(model, imagelist, base_id=0x40, cache_data=({}, {})):
    while type(ImageFormats.get(model, None)) == types.StringType:
        model = ImageFormats[model]
    if not model in ImageFormats:
        return None

    format_cache, image_cache = cache_data
    formats = []
    for descriptor in ImageFormats[model]:
        formats.append(ArtworkFormat(descriptor,
                       cache_info = format_cache.get(descriptor[0], (0,0))))
        # if there's at least one format whose image file isn't cache-clean,
        # invalidate the cache
        if not formats[-1].cache:
            image_cache = {}

    # Image List
    mhsd = Record((
        F_Tag("mhsd"),
        F_HeaderLength(),
        F_TotalLength(),
        F_Int32(1),
        F_Padding(80)
    ))
    mhli = Record((
        F_Tag("mhli"),
        F_HeaderLength(),
        F_ChildCount(),
        F_Padding(80)
    ))

    img_id = base_id
    index = 0
    output_image_cache = {}
    image_count = 0
    dbid2mhii = {}
    for source, dbid_list in imagelist.iteritems():
        log(source, False)

        # stat this image
        try:
            s = os.stat(source)
        except OSError, e:
            log(" [Error: %s]\n" % e.strerror, True)
            continue

        # check if the image is cacheworthy
        cache_entry = image_cache.get(source, None)
        if cache_entry:
            if (cache_entry['size'] != s[stat.ST_SIZE]) \
            or not(compare_mtime(cache_entry['mtime'], s[stat.ST_MTIME])):
                cache_entry = None

        # if it's not cached, open the image
        if not cache_entry:
            try:
                image = Image.open(source)
                image.tostring()
            except IOError, e:
                log(" [Error: %s]\n" % e, True)
                continue
        else:
            log(" [cached]", True)
            image = None

        # generate the image data and ArtworkDB records
        iinfo_list = [format.GenerateImage(image, index, cache_entry) for format in formats]
        for dbid in dbid_list:
            mhli.add(ImageItemRecord(img_id, dbid, iinfo_list, s[stat.ST_SIZE]))
            dbid2mhii[dbid] = img_id
            img_id += 1
        del image

        # add the image into the new cache
        dim = {}
        for iinfo in iinfo_list:
            dim[iinfo.format.fid] = {
                'sx': iinfo.sx,
                'sy': iinfo.sy,
                'mx': iinfo.mx,
                'my': iinfo.my
            }
        output_image_cache[source] = {
            'index': index,
            'size': s[stat.ST_SIZE],
            'mtime': s[stat.ST_MTIME],
            'dim': dim
        }

        # done with this image
        del iinfo_list
        index += 1
        image_count += len(dbid_list)
        log(" [OK]\n", True)

    # Date File Header
    mhfd = Record((
        F_Tag("mhfd"),
        F_HeaderLength(),
        F_TotalLength(),
        F_Int32(0),
        F_Int32(2),
        F_Int32(3),
        F_Int32(0),
        F_Int32(base_id + image_count),
        F_Padding(16),
        F_Int32(2),
        F_Padding(80)
    ))

    mhsd.add(mhli)
    mhfd.add(mhsd)

    # Album List (dummy)
    mhsd = Record((
        F_Tag("mhsd"),
        F_HeaderLength(),
        F_TotalLength(),
        F_Int32(2),
        F_Padding(80)
    ))
    mhsd.add(Record((
        F_Tag("mhla"),
        F_HeaderLength(),
        F_Int32(0),
        F_Padding(80)
    )))
    mhfd.add(mhsd)

    # File List
    mhsd = Record((
        F_Tag("mhsd"),
        F_HeaderLength(),
        F_TotalLength(),
        F_Int32(3),
        F_Padding(80)
    ))

    mhlf = Record((
        F_Tag("mhlf"),
        F_HeaderLength(),
        F_Int32(len(formats)),
        F_Padding(80)
    ))

    for format in formats:
        mhlf.add(Record((
            F_Tag("mhif"),
            F_HeaderLength(),
            F_TotalLength(),
            F_Int32(0),
            F_Int32(format.fid),
            F_Int32(format.size),
            F_Padding(100)
        )))

    # finalize ArtworkDB
    mhsd.add(mhlf)
    mhfd.add(mhsd)
    output_format_cache = dict([format.close() for format in formats])
    del formats
    output_cache_data = (output_format_cache, output_image_cache)
    return (str(mhfd), output_cache_data, dbid2mhii)


################################################################################
## a rudimentary ITDB reader (only reads titles, no playlists, and isn't very ##
## fault-tolerant) for the "dissect" action                                   ##
################################################################################

mhod_type_map = {
    1: 'title',
    2: 'path',
    3: 'album',
    4: 'artist',
    5: 'genre',
    6: 'filetype',
    8: 'comment',
   12: 'composer'
}

class InvalidFormat(Exception): pass

class DatabaseReader:
    def __init__(self, f="iPod_Control/iTunes/iTunesDB"):
        if type(f)==types.StringType:
            f = open(f, "rb")
        self.f = f
        self._skip_header("mhbd")
        while True:
            h = self._skip_header("mhsd")
            if len(h) < 16:
                raise InvalidFormat
            size, mhsd_type = struct.unpack('<LL', h[8:16])
            if mhsd_type == 1:
                break  # found the mhlt entry -> yeah!
            if size < len(h):
                raise InvalidFormat
            self.f.seek(size - len(h), 1)
        self._skip_header("mhlt")

    def _skip_header(self, tag):  # a little helper function
        hh = self.f.read(8)
        if (len(hh) != 8) or (hh[:4] != tag):
            raise InvalidFormat
        size = struct.unpack('<L', hh[4:])[0]
        if size < 8:
            raise InvalidFormat
        return hh + self.f.read(size - 8)

    def __iter__(self): return self
    def next(self):
        try:
            header = self._skip_header("mhit")
        except (IOError, InvalidFormat):
            raise StopIteration
        data_size = struct.unpack('<L', header[8:12])[0] - len(header)
        if data_size<0:
            raise InvalidFormat

        info = {}
        data = self.f.read(data_size)
        if len(data) < 48:
            raise InvalidFormat
        trk = struct.unpack('<L', header[44:48])[0]
        if trk: info['track number'] = trk

        # walk through mhods
        while (len(data) > 40) and (data[:4] == "mhod"):
            size, mhod_type = struct.unpack('<LL', data[8:16])
            value = unicode(data[40:size], "utf_16_le", 'replace')
            if mhod_type in mhod_type_map:
                info[mhod_type_map[mhod_type]] = value
            data = data[size:]
        return info


################################################################################
## Play Counts file reader                                                    ##
################################################################################

class PlayCountsItem:
    def __init__(self, data, index):
        self.index = index
        self.play_count, \
        t_last_played, \
        self.bookmark, \
        self.rating, \
        dummy, \
        self.skip_count, \
        t_last_skipped = \
            struct.unpack("<LLLLLLL", data + "\0" * (28 - len(data)))
        self.last_played = mactime2unixtime(t_last_played)
        self.last_skipped = mactime2unixtime(t_last_skipped)

class PlayCountsReader:
    def __init__(self, f="iPod_Control/iTunes/Play Counts"):
        if type(f)==types.StringType:
            f = open(f, "rb")
        self.f = f
        self.f.seek(0, 2)
        self.file_size = self.f.tell()
        self.f.seek(0)
        if self.file_size < 16:
            raise InvalidFormat
        if self.f.read(4) != "mhdp":
            raise InvalidFormat
        header_size, self.entry_size, self.entry_count = struct.unpack("<LLL", f.read(12))
        if self.file_size != (header_size + self.entry_size * self.entry_count):
            raise InvalidFormat
        self.f.seek(header_size)
        self.index = 0

    def __iter__(self): return self
    def next(self):
        data = self.f.read(self.entry_size)
        if not data: raise StopIteration
        self.index += 1
        return PlayCountsItem(data[:28], self.index-1)


################################################################################
## an iTunesSD generator (for iPod shuffle devices)                           ##
################################################################################

def be3(x):
    return "%c%c%c" % (x >> 16,  (x >> 8) & 0xFF,  x & 0xFF)

SD_type_map = { "aac": 2, "mp4a": 2, "wave": 4}

def MakeSDEntry(info):
    path = info['path']
    if type(path) != types.UnicodeType:
        path = unicode(path, sys.getfilesystemencoding(), 'replace')
    path = u'/' + path
    return "\0\x02\x2E\x5A\xA5\x01" + (20*"\0") + \
           "\x64\0\0%c\0\x02\0" % (SD_type_map.get(info.get('type', None), 1)) + \
           path.encode("utf_16_le", 'replace') + \
           ((261 - len(path)) * 2) * "\0" + \
           "%c%c\0" % (info.get('shuffle flag', 1), info.get('bookmark flag', 0))

def iTunesSD(tracklist):
    header = "\0\x02\x2E\x5A\xA5\x01" + (20*"\0") + "\x64\0\0\0x01\0\0x02\0"
    return be3(len(tracklist)) + "\x01\x06\0\0\0\x12" + (9*"\0") + \
           "".join(map(MakeSDEntry, tracklist))


################################################################################
## some useful helper functions for "fine tuning" of track lists              ##
################################################################################

def GenerateIDs(tracklist):
    trackid = random.randint(0, (0xFFFF-0x1337) - len(tracklist))
    dbid = random.randrange(0, 18446744073709551615L - len(tracklist))
    for track in tracklist:
        track['id'] = trackid
        track['dbid'] = dbid
        trackid += 1
        dbid += 1


def GuessTitleAndArtist(filename):
    info = {}
    filename = os.path.split(filename)[1]
    filename = os.path.splitext(filename)[0]
    filename = filename.replace('_', ' ')
    n = ""
    for i in xrange(len(filename)):
        c = filename[i]
        if c in "0123456789":
            n += c
            continue
        if c in " -":
            if n: info['track number'] = int(n)
            filename = filename[i+1:]
        break
    parts = filename.split('-', 1)
    if len(parts)==2:
        info['artist'] = parts[0].strip()
        info['title'] = parts[1].strip(" -\r\n\t\v")
    else:
        info['title'] = filename.strip()
    return info

def FillMissingTitleAndArtist(track_or_list):
    if type(track_or_list)==types.ListType:
        for track in track_or_list:
            FillMissingTitleAndArtist(track)
    else:
        if track_or_list.get('title',None) and track_or_list.get('artist',None):
            return  # no need to do something, it's fine already
        guess = GuessTitleAndArtist(track_or_list['path'])
        for key in ('title', 'artist', 'track number'):
            if not(track_or_list.get(key,None)) and guess.get(key,None):
                track_or_list[key] = guess[key]


################################################################################
## some additional general purpose helper functions                           ##
################################################################################

def ASCIIMap(c):
    if ord(c) < 32: return "."
    if ord(c) == 127: return "."
    return c

def HexDump(obj):
    s = str(obj)
    offset = 0
    while s:
        line = "%08X | " % offset
        for i in xrange(16):
            if i < len(s):
                line += "%02X " % ord(s[i])
            else:
                line += "   "
        line += "| " + "".join(map(ASCIIMap, s[:16]))
        print line
        offset += 16
        s = s[16:]


def DisplayTitle(info):
    s = kill_unicode(info.get('title', ""))
    if 'album' in info: s = "%s -> %s" % (kill_unicode(info['album']), s)
    if 'artist' in info: s = "%s: %s" % (kill_unicode(info['artist']), s)
    q = [str(kill_unicode(info[key])) for key in ('genre','year') if key in info]
    if q: s = "%s [%s]" % (s, ", ".join(q))
    return s


################################################################################

if __name__ == "__main__":
    print "Do not start this file directly, start repear.py instead."
