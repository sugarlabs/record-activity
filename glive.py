# Copyright (C) 2008, Media Modifications Ltd.
# Copyright (C) 2011, One Laptop per Child

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

import os
from gettext import gettext as _
import time

from gi.repository import GLib, GObject, Gst

import logging

from instance import Instance
import constants
import utils

logger = logging.getLogger('glive')


class Glive:
    def __init__(self, activity_obj, model):
        logger.debug('__init__')
        self.activity = activity_obj
        self.model = model
        self._camera_device_name = '/dev/video0'

        self._has_camera = os.access(self._camera_device_name, os.F_OK)

        self._pixbuf = None
        self._audio_pixbuf = None
        self._video_pixbuf = None

        self._xid = None
        self._sink = None

        self._pipeline = self._make_photo_pipeline()

    def get_has_camera(self):
        logger.debug('get_has_camera %r', self._has_camera)
        return self._has_camera

    def switch_camera(self):
        camera_devices = ['/dev/video0', '/dev/video1']
        index = camera_devices.index(self._camera_device_name)
        next = index + 1
        if next >= len(camera_devices):
            next = 0
        logging.error('Setting device %s', camera_devices[next])
        self._camera_device_name = camera_devices[next]
        self.stop()
        self._pipeline = self._make_photo_pipeline()
        self.play()

    def _make_photo_pipeline(self):
        """
        create a Gst.Pipeline for
        - displaying camera video on display,
        - capturing photographs,
        """

        if self._has_camera:
            args = {'src': 'v4l2src device={0}'.format(self._camera_device_name),
                    'cap': 'video/x-raw,framerate=10/1'}
        else:
            args = {'src': 'videotestsrc pattern=black',
                    'cap': 'video/x-raw,framerate=5/1,width=640,height=480'}

        cmd = '{src} name=src ! {cap} ' \
            '! videorate ' \
            '! tee name=tee ' \
            'tee.! videoconvert ! queue leaky=2 ! autovideosink sync=false ' \
            'tee.! videoconvert ! queue ! gdkpixbufsink name=photo'

        pipeline = Gst.parse_launch(cmd.format(**args))
        bus = pipeline.get_bus()
        bus.add_signal_watch()

        photo = pipeline.get_by_name('photo')

        def on_message_cb(bus, msg):
            if msg.get_structure() is not None:
                if msg.get_structure().get_name() == 'pixbuf':
                    self._pixbuf = photo.get_property('last-pixbuf')
            if msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                logger.error('bus error=%s debug=%s' % (err, debug))

        bus.connect('message', on_message_cb)

        bus.enable_sync_message_emission()

        def on_sync_message_cb(bus, msg):
            if msg.get_structure().get_name() == 'prepare-window-handle':
                self.activity.set_glive_sink(msg.src)

        bus.connect('sync-message::element', on_sync_message_cb)
        return pipeline

    def play(self):
        logger.debug('play')
        if self._get_state() == Gst.State.PLAYING:
            return

        self._pipeline.set_state(Gst.State.PLAYING)  # asynchronous

    def stop(self):
        logger.debug('stop')
        if self._get_state() == Gst.State.NULL:
            return

        self._pipeline.set_state(Gst.State.NULL)  # synchronous
        self.activity.set_glive_sink(None)

    def _get_state(self):
        return self._pipeline.get_state(Gst.CLOCK_TIME_NONE)[1]

    def take_photo(self):
        logger.debug('take_photo')
        if self._has_camera:
            self.model.save_photo(self._pixbuf)

    def record_audio(self):
        logger.debug('record_audio')

        # take a photograph
        self._audio_pixbuf = self._pixbuf
        self.model.still_ready(self._audio_pixbuf)

        # make a pipeline to record and encode audio to file
        ogg = os.path.join(Instance.instancePath, "output.ogg")
        cmd = 'autoaudiosrc name=src ' \
            '! audioconvert ' \
            '! queue max-size-time=30000000000 ' \
            'max-size-bytes=0 max-size-buffers=0 ' \
            '! vorbisenc name=vorbis ! oggmux ' \
            '! filesink location=%s' % ogg
        self._audio = Gst.parse_launch(cmd)

        # attach useful tags
        taglist = self._get_tags(constants.TYPE_AUDIO)
        if self._audio_pixbuf:
            pixbuf_b64 = utils.getStringEncodedFromPixbuf(self._audio_pixbuf)
            taglist.add_value(Gst.TagMergeMode.APPEND,
                              Gst.TAG_EXTENDED_COMMENT,
                              "coverart=" + pixbuf_b64)

        vorbis = self._audio.get_by_name('vorbis')
        vorbis.merge_tags(taglist, Gst.TagMergeMode.REPLACE_ALL)

        # detect end of stream
        bus = self._audio.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._audio_on_message_cb, ogg)

        # stop the live view
        self._pipeline.set_state(Gst.State.NULL)  # synchronous

        # start audio pipeline recording
        self._audio.set_state(Gst.State.PLAYING)  # asynchronous

    def stop_recording_audio(self):
        logger.debug('stop_recording_audio')

        # ask for stream to end
        self._audio.get_by_name('src').send_event(Gst.Event.new_eos())

    def _audio_on_message_cb(self, bus, msg, ogg):
        if msg.type != Gst.MessageType.EOS:
            return True

        logger.debug('_audio_on_message_cb Gst.MessageType.EOS')
        GObject.idle_add(self._stop_recording_audio, ogg)
        return False

    def _stop_recording_audio(self, ogg):
        logger.debug('_stop_recording_audio')

        # save audio file
        self.model.save_audio(ogg, self._audio_pixbuf)

        # remove the audio pipeline
        self._audio.get_bus().remove_signal_watch()
        self._audio.set_state(Gst.State.NULL)  # synchronous
        self._audio = None
        return False

    def record_video(self, quality):
        logger.debug('record_video')
        if not self._has_camera:
            return

        # stop the live view
        self._pipeline.set_state(Gst.State.NULL)  # synchronous

        # take a photograph
        self._video_pixbuf = self._pixbuf
        self.model.still_ready(self._video_pixbuf)

        # make a pipeline to record video and audio to file
        ogv = os.path.join(Instance.instancePath, "output.ogv")
        cmd = 'autovideosrc name=vsrc ! video/x-raw,width=640,height=480 ' \
            '! timeoverlay ' \
            '! videoconvert ' \
            '! videorate max-rate=10 ' \
            '! queue max-size-time=30000000000 ' \
            'max-size-bytes=0 max-size-buffers=0 ' \
            '! theoraenc name=theora ' \
            '! mux. ' \
            'autoaudiosrc name=asrc ' \
            '! audiorate ' \
            '! audioconvert ' \
            '! queue max-size-time=30000000000 ' \
            'max-size-bytes=0 max-size-buffers=0 ' \
            '! vorbisenc name=vorbis ! mux. ' \
            'oggmux name=mux ! filesink location=%s' % ogv
        self._video = Gst.parse_launch(cmd)

        # attach useful tags
        taglist = self._get_tags(constants.TYPE_VIDEO)
        if self._video_pixbuf:
            pixbuf_b64 = utils.getStringEncodedFromPixbuf(self._video_pixbuf)
            taglist.add_value(Gst.TagMergeMode.APPEND,
                              Gst.TAG_EXTENDED_COMMENT,
                              "coverart=" + pixbuf_b64)

        theora = self._video.get_by_name('theora')
        vorbis = self._video.get_by_name('vorbis')
        vorbis.merge_tags(taglist, Gst.TagMergeMode.REPLACE_ALL)

        # set quality
        if quality == 0:
            theora.props.quality = 24
            vorbis.props.quality = 0.2
        if quality == 1:
            theora.props.quality = 52
            vorbis.props.quality = 0.4

        # detect end of stream
        bus = self._video.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._video_on_message_cb, ogv)

        # start video pipeline recording
        self._video.set_state(Gst.State.PLAYING)  # asynchronous

    def stop_recording_video(self):
        logger.debug('stop_recording_video')
        if not self._has_camera:
            return

        # ask for stream to end
        self._video.get_by_name('vsrc').send_event(Gst.Event.new_eos())
        self._video.get_by_name('asrc').send_event(Gst.Event.new_eos())

    def _video_on_message_cb(self, bus, msg, ogv):
        if msg.type != Gst.MessageType.EOS:
            return True

        logger.debug('_video_on_message_cb Gst.MessageType.EOS')
        GObject.idle_add(self._stop_recording_video, ogv)
        return False

    def _stop_recording_video(self, ogv):
        logger.debug('_stop_recording_video')

        # save video file
        self.model.save_video(ogv, self._video_pixbuf)

        # remove the video pipeline
        self._video.get_bus().remove_signal_watch()
        self._video.set_state(Gst.State.NULL)  # synchronous
        self._video = None
        return False

    def _get_tags(self, mediatype):
        tl = Gst.TagList.new_empty()

        def _set(tag, value):
            tl.add_value(Gst.TagMergeMode.APPEND, tag, value)
        _set(Gst.TAG_ARTIST, self.model.get_nickname())
        _set(Gst.TAG_COMMENT, "olpc")
        _set(Gst.TAG_ALBUM, "olpc")
        date = GLib.Date.new()
        date.set_time_t(time.time())
        _set(Gst.TAG_DATE, date)
        stringType = constants.MEDIA_INFO[mediatype]['istr']

        # Translators: photo by photographer, e.g. "Photo by Mary"
        title = _('%(type)s by %(name)s') % {'type': stringType,
                                             'name': self.model.get_nickname()}
        _set(Gst.TAG_TITLE, title)
        return tl
