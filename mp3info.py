#!/usr/bin/env python
#
# audio file information library for rePear, the iPod database management tool
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

import sys, re, zlib, struct, os, stat
import qtparse


################################################################################
## a sh*tload of constants                                                    ##
################################################################################

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


ID3v2FrameMap = {
    "TIT1": "content group",
    "TIT2": "title",
    "TIT3": "subtitle",
    "TALB": "album",
    "TOAL": "original album",
    "TRCK": "/track number/total tracks",
    "TPOS": "/disc number/total discs",
    "TPE1": "artist",
    "TPE2": "band",
    "TPE3": "conductor",
    "TPE4": "interpreted by",
    "TOPE": "original artist",
    "TEXT": "lyrics",
    "TOLY": "original lyrics",
    "TCOM": "composer",
    "TMCL": "musician credits",
    "TIPL": "involved people",
    "TENC": "encoded by",
    "TBPM": "#BPM",
    "TYER": "#year",
#   "TLEN": "length",  # unreliable, rather use Xing/FhG tags or scan the file
    "TKEY": "initial key",
    "TLAN": "language",
    "TCON": "genre",
    "TFLT": "file type",
    "TMED": "media type",
    "TMOO": "mood",
    "TCOP": "copyright",
    "TPRO": "produced",
    "TPUB": "publisher",
    "TOWN": "owner",
    "TRSN": "station name",
    "TRSO": "station owner",
    "TOFN": "original file name",
    "TDLY": "playlist delay",
    "TDEN": "encoding time",
    "TDOR": "original release time",
    "TDRC": "recording time",
    "TDRL": "release time",
    "TDTG": "tagging time",
    "TSSE": "encoding settings",
    "TSOA": "album sort order",
    "TSOP": "performer sort order",
    "TSOT": "title sort order",
    "WCOM": "commercial information URL",
    "WCOP": "copyright URL",
    "WOAF": "audio file URL",
    "WOAR": "artist URL",
    "WOAS": "audio source URL",
    "WORS": "station URL",
    "WPAY": "payment URL",
    "WPUB": "publisher URL",
    "COMM": "comment"
}

RE_ID3v2_Frame_Type = re.compile(r'[A-Z0-9]{4}')
RE_ID3v2_Strip_Genre = re.compile(r'\([0-9]+\)(.*)')


################################################################################
## ID3v1 decoder                                                              ##
################################################################################

def GetID3v1(f, info):
    try:
        f.seek(-128, 2)
        data = f.read(128)
    except IOError:
        return 0
    if len(data)!=128 or data[:3]!="TAG":
        return 0
    info['tag'] = "id3v1"
    field = data[3:33].split("\0",1)[0].strip()
    if field: info['title'] = unicode(field, sys.getfilesystemencoding(), 'replace')
    field = data[33:63].split("\0",1)[0].strip()
    if field: info['artist'] = unicode(field, sys.getfilesystemencoding(), 'replace')
    field = data[63:93].split("\0",1)[0].strip()
    if field: info['album'] = unicode(field, sys.getfilesystemencoding(), 'replace')
    field = data[93:97].split("\0",1)[0].strip()
    if field:
        try:
            info['year'] = int(field)
        except ValueError:
            pass
    field = data[97:127].split("\0",1)[0].strip()
    if field: info['comment'] = unicode(field, sys.getfilesystemencoding(), 'replace')
    if data[125]=='\0' and data[126]!='\0':
        info['track number'] = ord(data[126])
    try:
        info['genre'] = ID3v1Genres[ord(data[127])]
    except KeyError:
        pass
    return -128


################################################################################
## ID3v2 decoder                                                              ##
################################################################################

def DecodeInteger(s):
    res = 0
    for c in s:
        res = (res << 8) | ord(c)
    return res

def DecodeSyncsafeInteger(s):
    res = 0
    for c in s:
        res = (res << 7) | (ord(c) & 0x7F)
    return res


def GetCharset(encoding):
    if encoding=="\1":  return "utf_16"
    if encoding=="\2":  return "utf_16_be"
    if encoding=="\3":  return "utf_8"
    else:               return "iso-8859-1"


def GetEndID3v2(f, offset=0):
    try:
        f.seek(offset-10, 2)
        marker = f.read(10)
        if len(marker)!=10 or marker[:3]!="3DI":
            return None
        size = DecodeSyncsafeInteger(marker[-4:]) + 10
        f.seek(offset-10-size, 2)
        data = f.read(size)
        if len(data)!=size or data[:3]!="ID3":
            return None
        return data
    except IOError:
        return None


def GetStartID3v2(f):
    try:
        f.seek(0)
        marker = f.read(10)
        if len(marker)!=10 or marker[:3]!="ID3":
            return None
        size = DecodeSyncsafeInteger(marker[-4:])
        payload = f.read(size)
        if len(payload)!=size:
            return None
        return marker+payload
    except IOError:
        return None


def DecodeID3v2(data, info):
    info['tag'] = "id3v2.%d.%d" % (ord(data[3]), ord(data[4]))
    if ord(data[3]) >= 4:
        decode_size = DecodeSyncsafeInteger
    else:
        decode_size = DecodeInteger

    # parse header flags, strip header(s)
    flags = ord(data[5])
    data = data[10:]
    if flags & 0x40:  # extended header
        size = decode_size(data[:4])
        data = data[size:]

    # parse frames
    while len(data)>=10:
        frame = data[:4]
        if not RE_ID3v2_Frame_Type.match(frame):
            break  # invalid frame name or start of padding => bail out
        size = decode_size(data[4:8])
        payload = data[10:size+10]
        flags = ord(data[9])
        if flags & 0x02:
            payload = payload.replace("\xff\0", "\xff")
        if flags & 0x04:
            try:
                payload = zlib.decompress(payload)
            except zlib.error:
                continue  # this frame is broken
        HandleID3v2Frame(frame, payload, flags, info)
        data = data[size+10:]


def HandleID3v2Frame(frame, payload, flags, info):
    text = None
    if not payload: return  # empty payload

    if frame[0]=='T' and frame!="TXXX":
        # text frame
        charset = GetCharset(payload[0])
        text = unicode(payload[1:], charset, 'replace').split(u'\0', 1)[0]

    elif frame[0]=='W' and frame!="WXXX":
        # URL
        text = unicode(payload.split("\0", 1)[0], "iso-8859-1", 'replace')

    elif frame=="COMM":
        # comment
        charset = GetCharset(payload[0])
        lang = payload[1:4].split("\0", 1)[0]
        parts = unicode(payload[4:], charset, 'replace').split(u'\0', 2)
        if len(parts)<2: return  # broken frame
        text = parts[1]

    if text:  ##### apply the current textual frame ####
        key = ID3v2FrameMap.get(frame, frame)
        text = text.strip()

        if frame=="TCON":  # strip crappy numerical genre comment
            m = RE_ID3v2_Strip_Genre.match(text.encode('iso-8859-1', 'replace'))
            if m: text = m.group(1)

        if key[0]=="#":  # numerical key
            try:
                text = int(text.strip())
            except ValueError:
                return  # broken frame
            key = key[1:]

        if key[0]=="/":  # multipart numerical key
            keys = key[1:].split("/")
            values = text.split("/")
            for key, value in zip(keys, values):
                try:
                    info[key] = int(value)
                except:
                    pass
            return  # already done here

        info[key] = text


################################################################################
## ultra-simple (and not very fault-tolerant) Ogg Vorbis metadata decoder     ##
################################################################################

def DecodeVorbisHeader(f, info):
    try:
        f.seek(0)
        data = f.read(4096)   # almost one page, should be enough
    except IOError:
        return False
    if data[:4]!="OggS": return False  # no Ogg -- don't bother
    data = data.split("vorbis", 3)
    if len(data)!=4: return False  # no Vorbis packets
    info['format'] = "ogg"  # at this point, we can assume the stream is valid
    info['filetype'] = "Ogg Vorbis"
    data = data[2]
    if len(data)<8: return True  # comment packet too short

    # encoder version
    size = struct.unpack("<L", data[:4])[0]
    if size: info['encoder'] = unicode(data[4:size+4], "utf_8", 'replace')
    data = data[size+4:]

    # field count
    if len(data)<8: return True  # comment packet too short
    count = struct.unpack("<L", data[:4])[0]
    data = data[4:]

    # field data
    for i in xrange(count):
        if len(data)<4: break  # comment packet too short
        size = struct.unpack("<L", data[:4])[0]
        if size:
            line = data[4:size+4]
            if "=" in line:
                key, value = line.split('=', 1)
                value = value.strip()
                if key=="TRACKNUMBER":
                    try:
                        info["track number"] = int(value)
                    except ValueError:
                        pass
                else:
                    info[key.lower()] = unicode(value, "utf_8", 'replace')
        data = data[size+4:]

    return True


################################################################################
## MP3 frame parser                                                           ##
################################################################################

mp3_bitrates = [
    [0,  8, 16, 24, 32, 40, 48, 56, 64, 80, 96,112,128,144,160,0],
    [0, 32, 40, 48, 56, 64, 80, 96,112,128,160,192,224,256,320,0]
]

mp3_samplerates = [
    [22050,24000,16000,0x0FFFFFFF],
    [44100,48000,32000,0x0FFFFFFF]
]


def IsValidMP3Header(header):
    return (len(header) == 4) \
       and ( header[0]         == 0xFF) \
       and ((header[1] & 0xF0) == 0xF0) \
       and ((header[1] & 0x06) == 0x02) \
       and ((header[2] & 0xF0) != 0xF0) \
       and  (header[2] & 0xF0)          \
       and ((header[2] & 0x0C) != 0x0C)


def ScanMP3(f, info, start_offset=0):
    try:
        f.seek(start_offset)
        sample = f.read(64*1024)  # the MP3 stuff should start in the first 64k

        # search for the start of the MP3 data part
        pos = 0
        while True:
            pos = sample.find("\xff", pos)
            if pos<0: return False
            if IsValidMP3Header(map(ord, sample[pos:pos+4])): break
            pos += 1
        f.seek(start_offset + pos)

    except IOError:
        return False

    # init global statistics
    total_samples = 0
    total_frames = 0
    total_bytes = 0
    used_bitrates = {}
    force_vbr = False
    data = ""

    # scan the file
    while True:
        try:
            header=f.read(4)
        except IOError:
            break
        if len(header)!=4: break

        # reject frames that do not look like MP3
        header = map(ord, header)
        if not IsValidMP3Header(header):
            # OK, this file is broken. try to re-synchronize.
            resync_pos = f.tell()
            try:
                # search for the first 8 bits of a frame sync marker in the
                # next 4 KiB
                pos = f.read(4096).find("\xff")
            except IOError:
                break
            if pos < 0:
                break
            else:
                f.seek(resync_pos + pos)
                continue

        # calculate details
        version = (header[1]>>3) & 1
        samples = 576 * (version+1)
        b2 = header[2]
        bitrate = mp3_bitrates[version][b2>>4]
        samplerate = mp3_samplerates[version][(b2>>2) & 3]
        padding = (b2>>1) & 1
        framesize = 72000 * (version+1) * bitrate / samplerate + padding

        # skip frame data
        try:
            frame = f.read(framesize-4)
            # accumulate the data of the first 10 frames
            if total_frames < 10:
                data += frame
        except IOError:
            break

        # fix statistics
        total_samples += samples
        total_frames += 1
        total_bytes += framesize
        used_bitrates[bitrate] = None

        # after 10 frames, check for Xing/LAME/FhG headers
        if total_frames == 10:
            valid = False
            # check for Xing/LAME VBR header
            p2 = data.find("Xing\0\0\0")
            if (p2 > 0) and (ord(data[p2 + 7]) & 1):
                force_vbr = True
            # check for LAME CBR header
            p = data.find("Info\0\0\0")
            if force_vbr or ((p > 0) and (ord(data[p + 7]) & 1)):
                if force_vbr: p = p2
                total_frames, total_bytes = struct.unpack(">ii", data[p+8:p+16])
                if not(ord(data[p + 7]) & 2):
                    total_bytes = info['size']  # size not specified, estimate
                total_samples = total_frames * samples
                valid = True
            # check for FhG header
            else:
                p = data.find("VBRI\0\1")
                if p > 0:
                    force_vbr = True
                    total_bytes, total_frames = struct.unpack(">ii", data[p+10:p+18])
                    total_samples = total_frames * samples
                    valid = True
            # final sanity check
            if valid:
                if (total_frames < 10) or (total_bytes < 1000) or (total_bytes > info['size']):
                    valid = False
                if valid:
                    # verify computed bitrate
                    check_bitrate = total_bytes*8*0.001/total_frames/samples*samplerate
                    if force_vbr:
                        # valid range for VBR files: all the way through
                        min_rate = 30.0
                        max_rate = 330.0
                    else:
                        # valid range for CBR files: current bitrate +/- 10%
                        min_rate = bitrate * 0.9
                        max_rate = bitrate * 1.1
                    valid = (check_bitrate > min_rate) and (check_bitrate < max_rate)
                if valid:
                    break
                else:
                    # this didn't work out, continue conventionally
                    total_samples = 10 * samples
                    total_frames = 10
                    total_bytes = 0
                    force_vbr = False

    # scan complete, finish things
    if total_frames < 10:
        return False   # less than 10 frames? that's a little bit short ...
    info['filetype'] = "MPEG-%d Audio Layer 3" % (2-version)
    info['sample rate'] = samplerate
    info['sample count'] = total_samples
    info['length'] = total_samples * 1.0 / samplerate
    if force_vbr or (len(used_bitrates) > 1):
        info['format'] = "mp3-vbr"
        info['bitrate'] = int(total_bytes*8*0.001 / info['length'])
    else:
        info['format'] = "mp3-cbr"
        info['bitrate'] = bitrate
    return True


################################################################################
## MP4 decoder wrapper                                                        ##
################################################################################

def DecodeMP4(f, info):
    try:
        f.seek(0)
        first_atom = f.read(8)[4:]
    except IOError:
        return False
    if not(first_atom in ('moov', 'ftyp')):
        return False  # no MP4 file
    try:
        qt = qtparse.QTParser(f)
    except IOError:
        return False
    info.update(qt.get_repear_info())
    del qt
    return True


################################################################################
## toplevel GetAudioFileInfo() function                                       ##
################################################################################

def GetAudioFileInfo(filename, stat_only=False):
    try:
        s = os.stat(filename)
    except OSError:
        return None

    if not stat.S_ISREG(s[stat.ST_MODE]):
        return None
    info = {'path': filename, 'size':s[stat.ST_SIZE], 'mtime':s[stat.ST_MTIME]}
    if stat_only: return info

    # try to extract a track number from the file name
    track = 0
    for c in os.path.split(filename)[-1]:
        if c in "0123456789":
            track = (10 * track) + ord(c) - 48
        else:
            break
    if track:
        info['track number'] = track

    # open the file
    try:
        f = file(filename, "rb")
    except IOError:
        return None

    # MP4 probing
    if DecodeMP4(f, info):
        return info

    # Ogg Vorbis probing
    if DecodeVorbisHeader(f, info):
        return info

    # some ID3 probing
    end_offset = GetID3v1(f, info)
    id3v2_data = GetEndID3v2(f, end_offset)
    if id3v2_data:
        DecodeID3v2(id3v2_data, info)
    id3v2_data = GetStartID3v2(f)
    if id3v2_data:
        start_offset = len(id3v2_data)
        DecodeID3v2(id3v2_data, info)
    else:
        start_offset = 0
    ScanMP3(f, info, start_offset)

    return info


################################################################################
## a demo main function                                                       ##
################################################################################

if __name__=="__main__":
    if len(sys.argv)<2:
        print "Usage:", sys.argv[0], "<FILES>..."
        sys.exit(1)
    for filename in sys.argv[1:]:
        print
        print "[%s]" % filename
        info = GetAudioFileInfo(filename)
        if not info: continue
        keys = info.keys()
        keys.sort()
        fmt = "%%-%ds= %%s" % (max(map(len, keys)) + 1)
        for key in keys:
            value = info[key]
            try:
                value = value.encode('iso-8859-1', 'replace')
            except:
                pass
            print fmt % (key, value)
        print
