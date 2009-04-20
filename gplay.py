#Copyright (c) 2008, Media Modifications Ltd.

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

#look at jukeboxactivity.py

import gtk
import pygtk
pygtk.require('2.0')
import sys
import pygst
pygst.require('0.10')
import gst
import gst.interfaces
import gobject
import time
gobject.threads_init()

import logging
logger = logging.getLogger('record:gplay.py')

import record

class Gplay:

    def __init__(self, ca):
        self.ca = ca
        self.window = None
        self.players = []
        self.playing = False

        self.player = gst.element_factory_make('playbin')

        bus = self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.add_signal_watch()
        bus.connect('message', self._onMessageCb)

    def _onMessageCb(self, bus, message):
        if message.type == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            logger.error('_onMessageCb: error=%s debug=%s' % (err, debug))

    def setLocation(self, location):
        if (self.player.get_property('uri') == location):
            self.seek(gst.SECOND*0)
            return

        self.player.set_state(gst.STATE_READY)
        self.player.set_property('uri', location)
        ext = location[len(location)-3:]
        record.Record.log.debug("setLocation: ext->"+str(ext))
        if (ext == "jpg"):
            self.pause()


    def queryPosition(self):
        "Returns a (position, duration) tuple"
        try:
            position, format = self.player.query_position(gst.FORMAT_TIME)
        except:
            position = gst.CLOCK_TIME_NONE

        try:
            duration, format = self.player.query_duration(gst.FORMAT_TIME)
        except:
            duration = gst.CLOCK_TIME_NONE

        return (position, duration)


    def seek(self, location):
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE, gst.SEEK_TYPE_SET, location, gst.SEEK_TYPE_NONE, 0)
        res = self.player.send_event(event)
        if res:
            self.player.set_new_stream_time(0L)


    def pause(self):
        self.playing = False
        self.player.set_state(gst.STATE_PAUSED)


    def play(self):
        if not self.player.props.video_sink:
            if self.ca.glive.fallback:
                sink = gst.element_factory_make('ximagesink')
            else:
                sink = gst.element_factory_make('xvimagesink')
            sink.props.force_aspect_ratio = True
            self.player.props.video_sink = sink

        self.player.props.video_sink.set_xwindow_id(self.window.window.xid)
        self.playing = True
        self.player.set_state(gst.STATE_PLAYING)


    def stop(self):
        self.playing = False
        self.player.set_state(gst.STATE_NULL)


    def get_state(self, timeout=1):
        return self.player.get_state(timeout=timeout)


    def is_playing(self):
        return self.playing


class PlayVideoWindow(gtk.Window):
    def __init__(self, bgd):
        gtk.Window.__init__(self)

        self.modify_bg( gtk.STATE_NORMAL, bgd )
        self.modify_bg( gtk.STATE_INSENSITIVE, bgd )
        self.unset_flags(gtk.DOUBLE_BUFFERED)
        self.set_flags(gtk.APP_PAINTABLE)
