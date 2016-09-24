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

from gi.repository import GObject, Gst

import logging
logger = logging.getLogger('record:gplay.py')

class Gplay(GObject.GObject):
    __gsignals__ = {
        'playback-status-changed': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT, GObject.TYPE_FLOAT)),
    }

    def __init__(self, activity_obj):
        super(type(self), self).__init__()
        self.activity = activity_obj
        self._playback_monitor_handler = None
        self._player = Gst.ElementFactory.make('playbin')
        if self._player is None:
            logger.error('no playbin')

        bus = self._player.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self._bus_error)
        bus.connect('message::eos', self._bus_eos)

    def _bus_error(self, bus, message):
        err, debug = message.parse_error()
        logger.error('bus error=%s debug=%s' % (err, debug))

    def _bus_eos(self, bus, message):
        self.stop()

    def set_location(self, location):
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
            location = duration * (position / 100)

        event = Gst.Event.new_seek(1.0, Gst.Format.TIME,
                                   Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                                   Gst.SeekType.SET, location,
                                   Gst.SeekType.NONE, 0)
        self._player.send_event(event)

    def pause(self):
        self._player.set_state(Gst.State.PAUSED)

    def play(self):
        if self.get_state() == Gst.State.PLAYING:
            return

        if not self._player.props.video_sink:
            sink = Gst.ElementFactory.make('xvimagesink')
            if sink is None:
                logger.error('no xvimagesink')

            sink.props.force_aspect_ratio = True
            self._player.props.video_sink = sink

        self.activity.set_gplay_sink(self._player.props.video_sink)
        self._player.set_state(Gst.State.PLAYING)
        self._emit_playback_status(0)

        self._playback_monitor_handler = GObject.timeout_add(100, self._playback_monitor)

    def _playback_monitor(self):
        try:
            _, position = self._player.query_position(Gst.Format.TIME)
            _, duration = self._player.query_duration(Gst.Format.TIME)
        except Gst.QueryError:
            return True

        value = float(position * 100) / float(duration + 1)
        self._emit_playback_status(value)
        return True

    def _emit_playback_status(self, position):
        state = self._player.get_state(Gst.CLOCK_TIME_NONE)[1]
        self.emit('playback-status-changed', state, position)

    def get_state(self):
        return self._player.get_state(Gst.CLOCK_TIME_NONE)[1]

    def stop(self):
        if self._playback_monitor_handler:
            GObject.source_remove(self._playback_monitor_handler)
            self._playback_monitor_handler = None

        self._player.set_state(Gst.State.NULL)
        self._emit_playback_status(0)

