# Copyright (c) 2008, Media Modifications Ltd.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from gi.repository import GObject, Gst

import logging
logger = logging.getLogger('gplay.py')

class Gplay(GObject.GObject):
    __gsignals__ = {
        'playback-status-changed': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT, GObject.TYPE_FLOAT)),
    }

    def __init__(self, activity_obj):
        logger.debug('__init__')
        GObject.GObject.__init__(self)
        self.activity = activity_obj
        self._playback_monitor_handler = None
        self._player = Gst.ElementFactory.make('playbin', 'playbin')
        if self._player is None:
            logger.error('no playbin')

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

        bus.enable_sync_message_emission()
        def on_sync_message_cb(bus, msg):
            if msg.get_structure().get_name() == 'prepare-window-handle':
                logger.debug('sync-message::element:prepare-window-handle')
                self.activity.set_gplay_sink(msg.src)

        bus.connect('sync-message::element', on_sync_message_cb)

    def get_state(self):
        return self._player.get_state(Gst.CLOCK_TIME_NONE)[1]

    def set_location(self, location):
        logger.debug('set location %r', location)
        if self._player.get_property('uri') == location:
            self.seek(0)
            return

        self._player.set_state(Gst.State.READY)
        self._player.set_property('uri', location)

    def seek(self, position):
        if position == 0:
            location = 0
        else:
            _, duration = self._player.query_duration(Gst.Format.TIME)
            location = int(duration * position / 100)

        logger.debug('seek %.2f%% of %.2f which is %d' %
                     (position, duration, location))

        seek = self._player.seek_simple(Gst.Format.TIME,
                                 Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                                 location)
        #self._player.get_state(1000000000)  # debugging; wait for seek

    def play(self):
        logger.debug('play')

        self._player.set_state(Gst.State.PLAYING)
        #self._player.get_state(1000000000)  # debugging; wait for play

        self._playback_monitor()
        self._playback_monitor_handler = GObject.timeout_add(50, self._playback_monitor)

    def _playback_monitor(self):
        try:
            _, position = self._player.query_position(Gst.Format.TIME)
            _, duration = self._player.query_duration(Gst.Format.TIME)
        except Gst.QueryError:
            return True

        if duration == 0:  # duration may not yet be known
            return True

        value = position * 100 / duration
        self._emit_playback_status(value)
        return True

    def _emit_playback_status(self, position):
        self.emit('playback-status-changed', self.get_state(), position)

    def pause(self):
        logger.debug('pause')
        if self.get_state() == Gst.State.PAUSED:
            return

        self._player.set_state(Gst.State.PAUSED)  # asynchronous
        #self._player.get_state(1000000000)  # debugging; wait for pause

        self._playback_monitor()

        GObject.source_remove(self._playback_monitor_handler)
        self._playback_monitor_handler = None

    def stop(self):
        logger.debug('stop')
        if self._playback_monitor_handler:
            GObject.source_remove(self._playback_monitor_handler)
            self._playback_monitor_handler = None

        self._player.set_state(Gst.State.NULL)
        self._emit_playback_status(0)
