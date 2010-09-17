#!/usr/bin/env python
#
# QuickTime parser library for rePear, the iPod database management tool
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

import sys, struct, types

ID3v1Genres = { 0:"Blues", 1:"Classic Rock", 2:"Country", 3:"Dance", 4:"Disco",
5:"Funk", 6:"Grunge", 7:"Hip-Hop", 8:"Jazz", 9:"Metal", 10:"New Age",
11:"Oldies", 12:"Other", 13:"Pop", 14:"R&B", 15:"Rap", 16:"Reggae", 17:"Rock",
18:"Techno", 19:"Industrial", 20:"Alternative", 21:"Ska", 22:"Death Metal",
23:"Pranks", 24:"Soundtrack", 25:"Euro-Techno", 26:"Ambient", 27:"Trip-Hop",
28:"Vocal", 29:"Jazz&Funk", 30:"Fusion", 31:"Trance", 32:"Classical",
33:"Instrumental", 34:"Acid", 35:"House", 36:"Game", 37:"Sound Clip",
38:"Gospel", 39:"Noise", 40:"Alternative Rock", 41:"Bass", 42:"Soul",
43:"Punk", 44:"Space", 45:"Meditative", 46:"Instrumental Pop",
47:"Instrumental Rock", 48:"Ethnic", 49:"Gothic", 50:"Darkwave",
51:"Techno-Industrial", 52:"Electronic", 53:"Pop-Folk", 54:"Eurodance",
55:"Dream", 56:"Southern Rock", 57:"Comedy", 58:"Cult", 59:"Gangsta",
60:"Top 40", 61:"Christian Rap", 62:"Pop/Funk", 63:"Jungle", 64:"Native US",
65:"Cabaret", 66:"New Wave", 67:"Psychedelic", 68:"Rave", 69:"Showtunes",
70:"Trailer", 71:"Lo-Fi", 72:"Tribal", 73:"Acid Punk", 74:"Acid Jazz",
75:"Polka", 76:"Retro", 77:"Musical", 78:"Rock & Roll", 79:"Hard Rock",
80:"Folk", 81:"Folk-Rock", 82:"National Folk", 83:"Swing", 84:"Fast Fusion",
85:"Bebop", 86:"Latin", 87:"Revival", 88:"Celtic", 89:"Bluegrass",
90:"Avantgarde", 91:"Gothic Rock", 92:"Progressive Rock",
93:"Psychedelic Rock", 94:"Symphonic Rock", 95:"Slow Rock", 96:"Big Band",
97:"Chorus", 98:"Easy Listening", 99:"Acoustic", 100:"Humour", 101:"Speech",
102:"Chanson", 103:"Opera", 104:"Chamber Music", 105:"Sonata", 106:"Symphony",
107:"Booty Bass", 108:"Primus", 109:"Porn Groove", 110:"Satire",
111:"Slow Jam", 112:"Club", 113:"Tango", 114:"Samba", 115:"Folklore",
116:"Ballad", 117:"Power Ballad", 118:"Rhytmic Soul", 119:"Freestyle",
120:"Duet", 121:"Punk Rock", 122:"Drum Solo", 123:"Acapella", 124:"Euro-House",
125:"Dance Hall", 126:"Goa", 127:"Drum & Bass", 128:"Club-House",
129:"Hardcore", 130:"Terror", 131:"Indie", 132:"BritPop", 133:"Negerpunk",
134:"Polsk Punk", 135:"Beat", 136:"Christian Gangsta", 137:"Heavy Metal",
138:"Black Metal", 139:"Crossover", 140:"Contemporary Christian",
141:"Christian Rock", 142:"Merengue", 143:"Salsa", 144:"Thrash Metal",
145:"Anime", 146:"JPop", 147:"SynthPop" }



QTAtomTypeMap = {
    'moov': 'container',
    'udta': 'container',
    'trak': 'container',
    'mdia': 'container',
    'minf': 'container',
    'stbl': 'container',
    'pinf': 'container',
    'schi': 'container',
    'ilst': 'container',
}

QTTrackTypeMap = {
    'vide': 'video',
    'soun': 'audio',
}

QTMetaDataMap = {
    '$nam': ('text',    'title'),
    '$alb': ('text',    'album'),
    '$art': ('text',    'artist'),
    '$ART': ('text',    'artist'),  # FAAC writes this tag in captital letters
    'aART': ('text',    'album artist'),
    '$cmt': ('text',    'comment'),
    '$day': ('year',    'year'),
    '$gen': ('text',    'genre'),
    '$wrt': ('text',    'composer'),
    '$too': ('text',    'encoder'),
    'cprt': ('text',    'copyright'),
    'trkn': ('track',   None),
    'disk': ('disc',    None),
    'covr': ('artwork', None),
    'cpil': ('flag',    'compilation'),
    '$lyr': ('text',    'lyrics'),
    'desc': ('text',    'description'),
    'purl': ('text',    'podcast url'),
    'egid': ('text',    'episode id'),
    'catg': ('text',    'category'),
    'keyw': ('text',    'keyword'),
    'gnre': ('genre',   None),
# gnre	Genre		1 | 0	text | uint8	iTunes 4.0
# tmpo	BPM		21	uint8		iTunes 4.0
# rtng	Rating/Advisory	21	uint8		iTunes 4.0
# stik	?? (stik)	21	uint8		??
# pcst	Podcast		21	uint8		iTunes 4.9
# tvnn	TV Network Name	1	text		iTunes 6.0
# tvsh	TV Show Name	1	text		iTunes 6.0
# tven	TV Episode No	1	text		iTunes 6.0
# tvsn	TV Season	21	uint8		iTunes 6.0
# tves	TV Episode	21	uint8		iTunes 6.0
# pgap	Gapless Play	21	uin8		iTunes 7.0
}

MP4DescriptorMap = {
    0x03: 'MP4ESDescr',
    0x04: 'MP4DecConfigDescr',
    0x05: 'MP4DecSpecificDescr',
    0x06: 'MP4SLConfigDescr',
}

MP4ObjectTypeMap = {
    0x20: 'MPEG4Visual',
    0x40: 'MPEG4Audio',
}

MP4ProfileMap = {
    1:  "AAC Main",
    2:  "LC-AAC",
    3:  "AAC SSR",
    4:  "AAC LTP",
    5:  "HE-AAC",
    6:  "Scalable",
    7:  "TwinVQ",
    8:  "CELP",
    9:  "HVXC",
    12: "TTSI",
    13: "Main Synthetic Profile",
    14: "Wavetable synthesis",
    15: "General MIDI",
    16: "Algorithmic Synthesis and Audio FX",
    17: "LC-AAC with error recovery",
    19: "AAC LTP with error recovery",
    20: "AAC SSR with error recovery",
    21: "TwinVQ with error recovery",
    22: "BSAC with error recovery",
    23: "AAC LD with error recovery",
    24: "CELP with error recovery",
    25: "HXVC with error recovery",
    26: "HILN with error recovery",
    27: "Parametric with error recovery",
}

H264ProfileMap = {
    66:  "BP",
    77:  "MP",
    88:  "EP",
    100: "HP",
    110: "H10P",
    144: "H444P",
}


def chop(s):
    if s: return (ord(s[0]), s[1:])
    return (0, "")

def dictremove(d, rlist):
    for r in rlist:
        if r in d:
            del d[r]


class QTParser:
    def __init__(self, f, verbose=False):
        self.f = f
        self.verbose = verbose
        self.info = {}
        self.time_scale = 1
        self.tracks = {}
        self.trackid = None
        self.artwork = []
        self.errors = []

        self.f.seek(0, 2)
        self.info['size'] = self.f.tell()
        self.parse_container(0, self.info['size'])

    def log_path(self, path, atom, size, start=None):
        if not self.verbose: return
        if start is None:
            print "%s%s (%d bytes)" % ("  " * len(path), atom, size)
        else:
            print "%s%s (%d bytes @ %d)" % ("  " * len(path), atom, size, start)

    def err(self, path, message):
        self.errors.append((self.repr_path(path), message))

    def reject(self, path, size, minsize, need_track=True):
        atom = path[-1]
        if need_track:
            if self.trackid is None:
                return self.err(path, "%s outside of a track" % atom)
            if not(self.trackid in self.tracks):
                return True
        if size < minsize:
            return self.err(path, "atom too small")
        return False

    def gettrack(self, prop, default=None):
        return self.tracks[self.trackid].get(prop, default)
    def settrack(self, prop, value):
        self.tracks[self.trackid][prop] = value

    def repr_path(self, path):
        if not path: return "<root>"
        return ".".join(path)

    def parse_container(self, start=0, size=0, path=[]):
        end = start + size
        while (start + 8) < end:
            self.f.seek(start)
            head = self.f.read(8)
            start += 8
            size = struct.unpack(">L", head[:4])[0] - 8
            if size < 0:
                return self.err(path, "invalid sub-atom size")
            atom = head[4:].strip("\0 ").replace('\xa9', '$')
            if not atom:
                break
            self.log_path(path, atom, size, start)
            if atom in QTMetaDataMap:
                alias = 'container'
            else:
                alias = QTAtomTypeMap.get(atom, atom)
            try:
                parser = getattr(self, "parse_" + alias)
            except AttributeError:
                parser = None
            if parser:
                parser(start, min(size, end - start), path + [atom])
            start += size
        if start < end:
            return self.err(path, "%d orphaned bytes" % (end - start))
        if start > end:
            return self.err(path, "%d missing bytes" % (start - end))

    def parse_trak(self, start, size, path):
        self.track = None
        self.parse_container(start, size, path)
        self.track = None

    def parse_mvhd(self, start, size, path):
        if self.reject(path, size, 20, False): return
        data = self.f.read(20)
        self.time_scale, length = struct.unpack(">LL", data[12:])
        self.info['length'] = float(length) / self.time_scale

    def parse_tkhd(self, start, size, path):
        if self.reject(path, size, 24, False): return
        data = self.f.read(min(size, 84))
        self.trackid, dummy, length = struct.unpack(">LLL", data[12:24])
        if not self.trackid in self.tracks:
            self.tracks[self.trackid] = {}
        self.settrack('length', float(length) / self.time_scale)
        if len(data) >= 84:
            w, h = struct.unpack(">LL", data[76:84])
            self.settrack('width', w >> 16)
            self.settrack('height', h >> 16)

    def parse_mdhd(self, start, size, path):
        if self.reject(path, size, 20): return
        data = self.f.read(20)
        time_scale, length = struct.unpack(">LL", data[12:])
        self.settrack('length', float(length) / time_scale)

    def parse_hdlr(self, start, size, path):
        if 'udta' in path:
            return
        if self.reject(path, size, 12): return
        data = self.f.read(12)
        try:
            self.tracks[self.trackid]['type'] = QTTrackTypeMap[data[8:]]
        except KeyError:
            del self.tracks[self.trackid]

    def parse_stsd(self, start, size, path):
        if self.reject(path, size, 8): return
        data = self.f.read(8)
        count = struct.unpack(">L", data[4:8])[0]
        end = start + size
        start += 8
        media_type = self.gettrack('type')
        for i in xrange(count):
            if start > (end - 16):
                return self.err(path, "description #%d too small" % (i+1))
            self.f.seek(start)
            data = self.f.read(16)
            start += 16
            size = struct.unpack(">L", data[:4])[0] - 16
            format = data[4:8].strip("\0 ")
            refidx = struct.unpack(">H", data[14:])[0]
            self.log_path(path, format, size, start)
            try:
                parser = getattr(self, "parse_stsd_" + media_type)
            except KeyError:
                if not i: self.err(path, "descriptions found, but no handler defined")
                parser = None
            except AttributeError:
                parser = None
            if parser:
                self.settrack('format', format)
                parser(start, min(size, end - start), path + [format])
            start += size

    def parse_stsd_audio(self, start, size, path):
        if self.reject(path, size, 20): return
        data = self.f.read(20)
        version, rev, ven, chan, res, compid, packsize, rate_hi, rate_lo = \
            struct.unpack(">HHLHHHHHH", data)
        if version == 0:
            hsize = 20
        elif version == 1:
            hsize = 24
        else:
            return self.err(path, "unknown audio stream description version")
        if size < hsize:
            return self.err(path, "stream description too small")
        start += hsize
        size -= hsize
        self.settrack('channels', chan)
        self.settrack('bits per sample', res)
        self.settrack('sample rate', rate_hi)
        if self.gettrack('length'):
            self.settrack('sample count', int(rate_hi * self.gettrack('length') + 0.5))
        self.parse_container(start, size, path)

    def parse_stsd_video(self, start, size, path):
        if self.reject(path, size, 70): return
        version, rev, ven, tq, sq, w, h, hres, vres, zero, frames = \
            struct.unpack(">HHLLLHHLLLH", self.f.read(34))
        if (w != self.gettrack('width')) or (h != self.gettrack('height')):
            self.err(path, "video size doesn't match track header value")
        data = self.f.read(32)
        clen = ord(data[0])
        if clen > 31:
            self.err(path, "invalid compressor name length")
        elif clen:
            self.settrack('compressor', data[1:clen+1])
        self.parse_container(start + 70, size - 70, path)

    def parse_avcC(self, start, size, path):
        if self.reject(path, size, 4): return
        data = self.f.read(4)
        profile = H264ProfileMap.get(ord(data[1]), None)
        level = ord(data[3])
        if level % 10:
            level = "%d.%d" % (level / 10, level % 10)
        else:
            level = str(level / 10)
        if (level == "1.1") and (ord(data[2]) & 0x10):
            level = "1b"
        format = "H.264"
        if profile: format += " " + profile
        self.settrack('video format', format + "@L" + level)

    def parse_esds(self, start, size, path):
        try:
            if not(path[-2] in ('mp4a', 'mp4v')):
                return  # unknown format, ignore it
        except IndexError:
            return self.err(path, "esds atom found at root level")
        if self.reject(path, size, 4, False): return
        self.f.seek(start + 4)
        self.parse_mp4desc(path, self.f.read(size - 4))

    def parse_mp4desc(self, path, data):
        while data:
            tag, data = chop(data)
            size = 0
            while True:
                if not data:
                    return self.err(path, "descriptor ends while decoding length")
                byte, data = chop(data)
                size = (size << 7) | (byte & 0x7F)
                if not(byte & 0x80): break
            if size > len(data):
                self.err(path, "%d missing bytes in descriptor" % (size - len(data)))
                size = len(data)
            tag = MP4DescriptorMap.get(tag, "0x%02X" % tag)
            self.log_path(path, tag, size)
            try:
                parser = getattr(self, "parse_" + tag)
            except AttributeError:
                parser = None
            if parser:
                parser(path + [tag], data[:size])
            data = data[size:]

    def parse_MP4ESDescr(self, path, data):
        if self.reject(path, len(data), 3, False): return
        esid, flags = struct.unpack(">BH", data[:3])
        data = data[3:]
        if flags & 0x80:  # stream_dependence
            if self.reject(path, len(data), 2, False): return
            data = data[2:]
        if flags & 0x40:  # URL
            if self.reject(path, len(data), 1, False): return
            size, data = chop(data)
            if self.reject(path, len(data), size, False): return
            data = data[size:]
        if flags & 0x20:  # ocr_stream
            if self.reject(path, len(data), 2, False): return
            data = data[2:]
        self.parse_mp4desc(path, data)

    def parse_MP4DecConfigDescr(self, path, data):
        if self.reject(path, len(data), 13, False): return
        otid, flags, buf_hi, buf_lo, rate_max, rate_avg = \
            struct.unpack(">BBBHLL", data[:13])
        self.settrack('bitrate', int(rate_avg / 1000))
        objtype = MP4ObjectTypeMap.get(otid, None)
        if not objtype: return   # some unknown format
        self.parse_mp4desc(path + [objtype], data[13:])

    def parse_MP4DecSpecificDescr(self, path, data):
        try:
            parser = getattr(self, "parse_MP4DecSpecificDescr_" + path[-2])
        except AttributeError:
            return  # unknown format
        except IndexError:
            return self.err("internal error")
        parser(path, data)

    def parse_MP4DecSpecificDescr_MPEG4Audio(self, path, data):
        if self.reject(path, len(data), 2, False): return
        a, data = chop(data)
        b, data = chop(data)
        profile = (a >> 3) & 0x1F
        freq = ((a << 1) | (b >> 7)) & 0x0F
        try:
            self.settrack('filetype', "MPEG-4 " + MP4ProfileMap[profile])
        except KeyError:
            pass
        if freq == 15:
            if self.reject(path, len(data), 3, False): return
            freq = b & 0x7F
            b, data = chop(data)
            freq = (freq << 7) | b
            b, data = chop(data)
            freq = (freq << 7) | b
            b, data = chop(data)
            freq = (freq << 1) | (b >> 7)
        else:
            try:
                freq = (96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350)[freq]
            except IndexError:
                self.err(path, "invalid sampling rate code %d" % freq)
                freq = 0
        if freq:
            ref = self.gettrack('sample rate')
            if not ref:
                self.settrack('sample rate', freq)
            elif freq != ref:
                self.err(path, "sample rate in AAC descriptor (%d) doesn't match sample rate in stream description (%d)" % (freq, ref))
        if data:
            return self.err(path, "descriptor is longer than expected")

    def parse_MP4DecSpecificDescr_MPEG4Visual(self, path, data):
        self.settrack('video format', 'MPEG-4 ASP')

    def parse_meta(self, start, size, path):
        self.parse_container(start + 4, size - 4, path)

    def parse_data(self, start, size, path):
        if self.reject(path, size, 8, False): return
        try:
            parser, key = QTMetaDataMap[path[-2]]
        except IndexError:
            return self.err(path, "data atom found at root level")
        except KeyError:
            return self.err(path, "no parser defined for this atom")
        format = struct.unpack(">L", self.f.read(8)[:4])[0] & 0x00FFFFFF
        try:
            parser = getattr(self, "format_" + parser)
        except AttributeError:
            return self.err(path, "format parser `%s' doesn't exist" % parser)
        res = parser(path, self.f.read(size - 8))
        if key:
            if res is None:
                return self.err(path, "decoding failed, no value assigned")
            self.info[key] = res

    def format_text(self, path, data):
        data = data.strip("\0")
        if data.startswith("\xfeff"):
            return unicode(data, 'utf_16')
        else:
            return unicode(data, 'utf_8')

    def format_year(self, path, data):
        data = data.strip("\0").split('-', 1)[0]
        try:
            return int(data)
        except ValueError:
            return self.err(path, "invalid date format")

    def format_byte(self, path, data):
        if not data:
            return self.err(path, "zero-length data block")
        return ord(data[0])

    def format_genre(self, path, data):
        if not data:
            return self.err(path, "zero-length data block")
        genre = ID3v1Genres.get(ord(data[-1]) - 1, None)
        if genre: self.info["genre"] = genre

    def format_track(self, path, data, item='track'):
        if self.reject(path, len(data), 6, False): return
        current, total = struct.unpack(">HH", data[2:6])
        if current: self.info["%s number" % item] = current
        if total: self.info["total %ss" % item] = total

    def format_disc(self, path, data):
        return self.format_track(path, data, 'disc')

    def format_artwork(self, path, data):
        self.artwork.append(data)

    def format_flag(self, path, data):
        return len(data.strip("\0")) != 0

    def get_repear_info(self):
        info = {}
        have_video = False
        have_audio = False
        for track in self.tracks.itervalues():
            ttype = track.get('type', '?')
            if not(have_audio) and (ttype == 'audio'):
                ainfo = track.copy()
                dictremove(ainfo, ('type', 'width', 'height'))
                info.update(ainfo)
                have_audio = True
            if not(have_video) and (ttype == 'video'):
                vinfo = track.copy()
                dictremove(vinfo, ('type',))
                if have_audio: dictremove(vinfo, ('format', ))
                info.update(vinfo)
                have_video = True
        info.update(self.info)
        if ('album artist' in info) and not('artist' in info):
            info['artist'] = info['album artist']
        if have_video:
            info['filetype'] = "MPEG-4 Video file"
        elif not('filetype' in info):
            info['filetype'] = "MPEG-4 Audio File"
        return info

################################################################################

def dump_dict(d):
    keys = d.keys()
    keys.sort()
    for key in keys:
        print "    %s = %s" % (key, repr(d[key]))

if __name__ == "__main__":
    qt = QTParser(file(sys.argv[1], "rb"), True)
    print
    
    print "Raw file information:"
    dump_dict(qt.info)
    for track in qt.tracks:
        print "Raw track information (id %s):" % track
        dump_dict(qt.tracks[track])
    print
    
    print "rePear-compliant information:"
    dump_dict(qt.get_repear_info())
    print

    if qt.errors:
        print "Errors:"
        for e in qt.errors: print "    %s: %s" % e
        print
