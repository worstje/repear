#!/usr/bin/env python
#
# last.fm scrobbling library for rePear, the iPod database management tool
# Copyright (C) 2008 Martin J. Fiedler <martin.fiedler@gmx.net>
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

import sys, urllib, urllib2, re, time, md5, types, fnmatch, os

try:
    import repear
    client_id = "rpr"
    client_ver = repear.__version__
except (ImportError, NameError, AttributeError):
    client_id = "tst"
    client_ver = "1.0"
server = "http://post.audioscrobbler.com:80/"
protocol_version = "1.2"
max_queue = 50


def utf8urlencode(x):
    if type(x) != types.UnicodeType:
        x = unicode(x, sys.getfilesystemencoding(), 'replace')
    return urllib.quote(x.encode('utf-8', 'replace'))


class ScrobbleError(Exception): pass


class Scrobbler:
    def __init__(self, user=None, password=None):
        self.user = user
        self.password = password
        self.excludes = []
        self.queue = []
        self.index = {}

    def _add(self, item):
        key = "&".join(map(str, item[:3])).lower()
        if not(key in self.index):
            self.queue.append(item)
            self.index[key] = True

    def config(self, filename):
        try:
            f = file(filename, "r")
            for line in f:
                line = line.split(';', 1)[0]
                if not(line) or not('=' in line):
                    continue
                key, value = [x.strip() for x in line.split('=', 1)]
                key = key.lower()
                if key.startswith("user"):
                    self.user = value
                elif key.startswith("pass"):
                    self.password = value
                elif key.startswith("exclude"):
                    if value[0] == "/":
                        value = value[1:]
                    if os.path.isdir(value):
                        if value[-1] != "/":
                            value += "/"
                        value += "*"
                    self.excludes.append(value.lower())
            f.close()
        except IOError:
            return False
        return not(not(self.user)) and not(not(self.password))

    def load(self, filename):
        try:
            f = file(filename, "r")
            for line in f:
                line = line.strip().split('&')
                try:
                    line[0] = long(line[0])
                except ValueError:
                    line = []
                if len(line) == 6:
                    self._add(tuple(line))
            f.close()
        except IOError:
            return False
        return True

    def save(self, filename):
        data = "\n".join(["&".join(map(str, item)) for item in self.queue]) + "\n"
        try:
            f = file(filename, "w")
            f.write(data)
            f.close()
        except IOError:
            return False
        return True

    def __iadd__(self, item):
        self.enqueue(item)
        return self
    def enqueue(self, item):
        path = item.get('original path', None) or item.get('path', None)
        if self.excludes and path:
            if type(path) == types.UnicodeType:
                path = path.encode(sys.getfilesystemencoding(), 'replace')
            path = path.lower()
            for pattern in self.excludes:
                if fnmatch.fnmatch(path, pattern):
                    return
        try:
            artist = utf8urlencode(item['artist'])
            title = utf8urlencode(item['title'])
            length = str(long(item['length']))
            playtime = long(item['last played time'])
        except KeyError:
            return
        album = utf8urlencode(item.get('album', ''))
        track = str(item.get('track number', ''))
        self._add((playtime, artist, title, length, album, track))

    def scrobble(self):
        if not(self.user) or not(self.password):
            raise ScrobbleError, "user name or password missing"
        if not(self.queue):
            return

        # build authentication request
        if re.match(r'^[0-9a-fA-F]{32}$', self.password):
            self.password = self.password.lower()
        else:
            self.password = md5.md5(self.password).hexdigest()
        timestamp = str(long(time.time()))
        auth = md5.md5(self.password + timestamp).hexdigest()
        req = urllib2.Request(
            "%s?hs=true&p=%s&c=%s&v=%s&u=%s&t=%s&a=%s" % \
            (server, protocol_version, client_id, client_ver, self.user, timestamp, auth))

        # send and read authentication request
        try:
            res = urllib2.urlopen(req).read()
#            res = "OK\nfoobar\n\nhttp://localhost:1337/foo"
        except urllib2.HTTPError, e:
            raise ScrobbleError, "HTTP %d in authentication phase" % e.code
        except urllib2.URLError, e:
            raise ScrobbleError, "network error in authentication phase: %s" % e.reason.args[1]
        except IOError:
            raise ScrobbleError, "read error in authentication phase"
        res = [line.strip() for line in res.split("\n")]
        code = res[0].split()[0].upper()

        # check authentication response
        if code == "BANNED":
            raise ScrobbleError, "client banned"
        elif code == "BADAUTH":
            raise ScrobbleError, "invalid username or password"
        elif code == "BADTIME":
            raise ScrobbleError, "system clock is skewed"
        elif code == "FAILED":
            raise ScrobbleError, res[0].split(" ", 1)[-1]
        elif code != "OK":
            raise ScrobbleError, "invalid answer from server: " + res[0]
        try:
            sid = res[1]
            url = res[3]
        except IndexError:
            raise ScrobbleError, "malformed authentication response"
        if not url.startswith("http://"):
            raise ScrobbleError, "malformed authentication response"

        # submit queued items
        self.queue.sort()
        while self.queue:
            # build POST request string
            data = "s=" + sid
            for i in xrange(min(len(self.queue), 50)):
                playtime, artist, title, length, album, track = self.queue[i]
                data += "&a[%d]=%s&t[%d]=%s&i[%d]=%d&o[%d]=P&r[%d]=&l[%d]=%s&b[%d]=%s&n[%d]=%s&m[%d]=" % \
                    (i, artist, i, title, i, playtime, i, i, i, length, i, album, i, track, i)
#            print data

            # send and read submission request
            try:
                res = urllib2.urlopen(url, data).read()
#                res = "mist"
            except urllib2.HTTPError, e:
                raise ScrobbleError, "HTTP %d in submission phase" % e.code
            except urllib2.URLError, e:
                raise ScrobbleError, "network error in submission phase: %s" % e.reason.args[1]
            except IOError:
                raise ScrobbleError, "read error in submission phase"
            res = res.strip().split("\n", 1)[0].strip()
            code = res.split()[0].upper()

            # check response
            if code == "BADSESSION":
                raise ScrobbleError, "invalid session while submitting"
            elif code == "FAILED":
                raise ScrobbleError, res.split(" ", 1)[-1]
            elif code != "OK":
                raise ScrobbleError, "invalid answer from server: " + res

            # finally, remove items from the queue
            del self.queue[:max_queue]


if __name__ == "__main__":
    s = Scrobbler()
    s.load()
    print "old queue:", len(s.queue), "items"
    s += {
        'last played time': 1205685904L,
        'album': u'Story of Ohm',
        'artist': u'paniq',
        'length': 310.43918367346942,
        'title': u'Liberation',
        'track number': 4,
    }
    s += {
        'last played time': 1205686220L,
        'album': u'Story of Ohm',
        'artist': u'paniq',
        'length': 228.04897959183674,
        'title': u'Story of Ohm',
        'track number': 6,
    }
    print "new queue:", len(s.queue), "items"
    try:
        s.scrobble()
    except ScrobbleError, e:
        print e
    print "after scrobbling:", len(s.queue), "items"
    s.save()
