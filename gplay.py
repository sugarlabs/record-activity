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

import gobject
gobject.threads_init()
import pygst
pygst.require('0.10')
import gst

import logging
logger = logging.getLogger('gplay')

class Gplay(gobject.GObject):
    __gsignals__ = {
        'playback-status-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT, gobject.TYPE_FLOAT)),
    }

    def __init__(self, activity_obj):
        logger.debug('__init__')
        gobject.GObject.__init__(self)
        self.activity = activity_obj
        self._playback_monitor_handler = None
        self._player = gst.element_factory_make('playbin')

        bus = self._player.get_bus()
        bus.add_signal_watch()

        def on_error_cb(bus, msg):
            err, debug = msg.parse_error()
            logger.error('bus error=%s debug=%s' % (err, debug))

        bus.connect('message::error', on_error_cb)

        def on_eos_cb(bus, msg):
            logger.debug('message::eos')
            self.stop()

        bus.connect('message::eos', on_eos_cb)

    def get_state(self):
        return self._player.get_state()[1]

    def set_location(self, location):
        logger.debug('set location %r', location)
        if self._player.get_property('uri') == location:
            self.seek(0)
            return

        self._player.set_state(gst.STATE_READY)
        self._player.set_property('uri', location)

    def seek(self, position):
        try:
            duration = self._player.query_duration(gst.FORMAT_TIME, None)[0]
        except gst.QueryError:
            return

        if position == 0:
            location = 0
        else:
            location = int(duration * position / 100)

        logger.debug('seek %.2f%% of %.2f which is %d' %
                     (position, duration, location))

        event = gst.event_new_seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE, gst.SEEK_TYPE_SET, location, gst.SEEK_TYPE_NONE, 0)
        res = self._player.send_event(event)

    def play(self):
        logger.debug('play')

        if not self._player.props.video_sink:
            sink = gst.element_factory_make('xvimagesink')
            sink.props.force_aspect_ratio = True
            self._player.props.video_sink = sink

        self.activity.set_gplay_sink(self._player.props.video_sink)

        self._player.set_state(gst.STATE_PLAYING)

        self._playback_monitor()
        self._playback_monitor_handler = gobject.timeout_add(
            100, self._playback_monitor)

    def _playback_monitor(self):
        try:
            position = self._player.query_position(gst.FORMAT_TIME)[0]
            duration = self._player.query_duration(gst.FORMAT_TIME)[0]
        except gst.QueryError:
            return True

        if duration == 0:  # duration may not yet be known
            return True

        value = position * 100.0 / duration
        self._emit_playback_status(value)
        return True

    def _emit_playback_status(self, position):
        self.emit('playback-status-changed', self.get_state(), position)

    def pause(self):
        logger.debug('pause')
        if self.get_state() == gst.STATE_PAUSED:
            return

        self._player.set_state(gst.STATE_PAUSED)

        self._playback_monitor()

        if self._playback_monitor_handler:
            gobject.source_remove(self._playback_monitor_handler)
            self._playback_monitor_handler = None

    def stop(self):
        logger.debug('stop')
        if self._playback_monitor_handler:
            gobject.source_remove(self._playback_monitor_handler)
            self._playback_monitor_handler = None

        self._player.set_state(gst.STATE_NULL)
        self._emit_playback_status(0)
