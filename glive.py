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


import os
import gtk
import pygtk
pygtk.require('2.0')
import gst
import pygst
pygst.require('0.10')
import time
import gobject
gobject.threads_init()

import logging
logger = logging.getLogger('record:glive.py')

from sugar.activity.activity import get_activity_root

from instance import Instance
from constants import Constants
import utils
import ui

TMP_OGG = os.path.join(get_activity_root(), 'instance', 'output.ogg')

PLAYBACK_WIDTH  = 640
PLAYBACK_HEIGHT = 480

OGG_TRAITS = {
        0: { 'width': 160, 'height': 120, 'quality': 16 },
        1: { 'width': 400, 'height': 300, 'quality': 16 },
        2: { 'width': 640, 'height': 480, 'quality': 16 } }

class Glive:
    def play(self):
        logger.debug('play')

        if not self.play_pipe:
            self.src_str = \
                    'v4l2src ' \
                    '! video/x-raw-yuv,width=%s,height=%s ' \
                    % (PLAYBACK_WIDTH, PLAYBACK_HEIGHT)
            self.play_str = \
                    'xvimagesink force-aspect-ratio=true name=xsink'

            self.play_pipe = gst.parse_launch(
                    '%s ' \
                    '! valve name=valve ' \
                    '! queue name=queue ' \
                    '! %s' \
                    % (self.src_str, self.play_str))
            self.valve = self.play_pipe.get_by_name('valve')
            
            def message_cb(bus, message):
                if message.type == gst.MESSAGE_ERROR:
                    err, debug = message.parse_error()
                    logger.error('play_pipe: %s %s' % (err, debug))

                    if not self.fallback:
                        logger.warning('use fallback_bin')
                        self.fallback = True

                        self.play_str = \
                                'ffmpegcolorspace ' \
                                '! ximagesink force-aspect-ratio=true ' \
                                    ' name=xsink'

                        self.play_pipe.remove(
                                self.play_pipe.get_by_name('xsink'))

                        c = gst.element_factory_make('ffmpegcolorspace')
                        s = gst.element_factory_make('ximagesink', 'xsink')
                        s.props.force_aspect_ratio = True

                        self.play_pipe.add(c, s)
                        gst.element_link_many(
                                self.play_pipe.get_by_name('queue'), c, s)

                        if [i for i in self.pipeline.get_state() \
                                if id(i) == id(gst.STATE_PLAYING)]:
                            self.pipeline = None
                            self._switch_pipe(self.play_pipe)

            bus = self.play_pipe.get_bus()
            bus.add_signal_watch()
            bus.connect('message', message_cb)

        self._switch_pipe(self.play_pipe)

    def thumb_play(self, use_fallback=False):
        if not self.fallback and not use_fallback:
            # use xv to scale video
            self.play()
            return

        logger.debug('thumb_play')

        if not self.fallback_pipe:
            self.fallback_pipe = gst.parse_launch(
                    '%s ' \
                    '! queue ' \
                    '! videoscale ' \
                    '! video/x-raw-yuv,width=%s,height=%s ' \
                    '! ffmpegcolorspace ' \
                    '! ximagesink force-aspect-ratio=true name=xsink' \
                    % (self.src_str, ui.UI.dim_PIPW, ui.UI.dim_PIPH))

            def message_cb(bus, message):
                if message.type == gst.MESSAGE_ERROR:
                    err, debug = message.parse_error()
                    logger.error('fallback_pipe: %s %s' % (err, debug))

            bus = self.fallback_pipe.get_bus()
            bus.add_signal_watch()
            bus.connect('message', message_cb)

        self._switch_pipe(self.fallback_pipe)

    def pause(self):
        logger.debug('pause')
        if self.pipeline:
            self.pipeline.set_state(gst.STATE_PAUSED)

    def stop(self):
        logger.debug('stop')
        if self.pipeline:
            self.pipeline.set_state(gst.STATE_NULL)

    def takePhoto(self, after_photo_cb=None):
        logger.debug('takePhoto')

        if not self.photo:
            def sink_handoff(sink, buffer, pad, self):
                sink.props.signal_handoffs = False

                pixbuf = gtk.gdk.pixbuf_loader_new_with_mime_type('image/jpeg')
                pixbuf.write(buffer)
                pixbuf.close()

                structure = gst.Structure('record.photo')
                structure['pixbuf'] = pixbuf.get_pixbuf()
                msg = gst.message_new_custom(gst.MESSAGE_APPLICATION, sink,
                        structure)
                self.play_pipe.get_bus().post(msg)

            self.photo = gst.element_factory_make('ffmpegcolorspace')
            self.photo_jpegenc = gst.element_factory_make('jpegenc')
            self.photo_sink = gst.element_factory_make('fakesink')
            self.photo_sink.connect('handoff', sink_handoff, self)

            def message_cb(bus, message, self):
                if message.type == gst.MESSAGE_APPLICATION \
                        and message.structure.get_name() == 'record.photo':
                    self.valve.props.drop = True
                    self.play_pipe.remove(self.photo)
                    self.play_pipe.remove(self.photo_jpegenc)
                    self.play_pipe.remove(self.photo_sink)
                    self.valve.link(self.play_pipe.get_by_name('queue'))
                    self.valve.props.drop = False
                    self.after_photo_cb(self, message.structure['pixbuf'])

            bus = self.play_pipe.get_bus()
            bus.add_signal_watch()
            bus.connect('message', message_cb, self)

        def process_cb(self, pixbuf):
            self.ca.m.savePhoto(pixbuf)
            self._switch_pipe(self.play_pipe)

        self.after_photo_cb = after_photo_cb and after_photo_cb or process_cb

        self.valve.props.drop = True
        self.valve.unlink(self.play_pipe.get_by_name('queue'))
        self.play_pipe.add(self.photo, self.photo_jpegenc, self.photo_sink)
        gst.element_link_many(self.valve, self.photo, self.photo_jpegenc,
                self.photo_sink)
        self.photo_sink.props.signal_handoffs = True
        self.valve.props.drop = False

        self._switch_pipe(self.play_pipe)

    def startRecordingVideo(self, quality):
        logger.debug('startRecordingVideo quality=%s' % quality)

        if True:
            # XXX re-create pipe every time 
            # to supress gst glitches during the second invoking
            if self.video_pipe:
                del self.video_pipe

            self.video_pipe = gst.parse_launch( \
                    '%s ' \
                    '! tee name=tee ' \
                    'tee.! queue ! %s ' \
                    'tee.! queue ' \
                    '! ffmpegcolorspace ' \
                    '! videorate skip_to_first=true ' \
                    '! video/x-raw-yuv,framerate=10/1 ' \
                    '! videoscale ' \
                    '! video/x-raw-yuv,width=%s,height=%s ' \
                    '! theoraenc quality=%s ' \
                    '! oggmux name=mux ' \
                    '! filesink location=%s ' \
                    'alsasrc ' \
                    '! queue ' \
                    '! audioconvert ' \
                    '! vorbisenc name=vorbisenc ' \
                    '! mux.' \
                    % (self.src_str, self.play_str,
                        OGG_TRAITS[quality]['width'],
                        OGG_TRAITS[quality]['height'],
                        OGG_TRAITS[quality]['quality'], TMP_OGG))

            def message_cb(bus, message, self):
                if message.type == gst.MESSAGE_ERROR:
                    err, debug = message.parse_error()
                    logger.error('video_pipe: %s %s' % (err, debug))

            bus = self.video_pipe.get_bus()
            bus.add_signal_watch()
            bus.connect('message', message_cb, self)

        def process_cb(self, pixbuf):
            taglist = self.getTags(Constants.TYPE_VIDEO)
            vorbisenc = self.video_pipe.get_by_name('vorbisenc')
            vorbisenc.merge_tags(taglist, gst.TAG_MERGE_REPLACE_ALL)

            self.pixbuf = pixbuf
            self._switch_pipe(self.video_pipe)

        self.ogg_quality = quality
        # take photo first
        self.takePhoto(process_cb)

    def stopRecordingVideo(self):
        logger.debug('stopRecordingVideo')

        self._switch_pipe(self.play_pipe)

        if (not os.path.exists(TMP_OGG)):
            self.ca.m.cannotSaveVideo()
            self.ca.m.stoppedRecordingVideo()
            return

        if (os.path.getsize(TMP_OGG) <= 0):
            self.ca.m.cannotSaveVideo()
            self.ca.m.stoppedRecordingVideo()
            return

        ogg_w = OGG_TRAITS[self.ogg_quality]['width']
        ogg_h = OGG_TRAITS[self.ogg_quality]['height']

        thumb = self.pixbuf.scale_simple(ogg_w, ogg_h, gtk.gdk.INTERP_HYPER)
        self.ca.ui.setPostProcessPixBuf(thumb)
        self.ca.m.saveVideo(thumb, TMP_OGG, ogg_w, ogg_h)
        self.ca.m.stoppedRecordingVideo()
        self.ca.ui.updateVideoComponents()

    def startRecordingAudio(self):
        logger.debug('startRecordingAudio')

        if not self.audio_pipe:
            self.audio_pipe = gst.parse_launch( \
                    '%s ' \
                    '! queue ' \
                    '! %s ' \
                    'alsasrc ' \
                    '! queue ' \
                    '! audioconvert ' \
                    '! vorbisenc name=vorbisenc ' \
                    '! oggmux ' \
                    '! filesink location=%s ' \
                    % (self.src_str, self.play_str, TMP_OGG))

            def message_cb(bus, message, self):
                if message.type == gst.MESSAGE_ERROR:
                    err, debug = message.parse_error()
                    logger.error('audio_pipe: %s %s' % (err, debug))

            bus = self.audio_pipe.get_bus()
            bus.add_signal_watch()
            bus.connect('message', message_cb, self)

        def process_cb(self, pixbuf):
            taglist = self.getTags(Constants.TYPE_AUDIO)
            cover = utils.getStringFromPixbuf(pixbuf)
            taglist[gst.TAG_EXTENDED_COMMENT] = 'coverart=%s' % cover

            vorbisenc = self.audio_pipe.get_by_name('vorbisenc')
            vorbisenc.merge_tags(taglist, gst.TAG_MERGE_REPLACE_ALL)

            self.pixbuf = pixbuf
            self._switch_pipe(self.audio_pipe)

        # take photo first
        self.takePhoto(process_cb)

    def stopRecordingAudio( self ):
        logger.debug('stopRecordingAudio')

        self._switch_pipe(self.play_pipe)

        if (not os.path.exists(TMP_OGG)):
            self.ca.m.cannotSaveVideo()
            return
        if (os.path.getsize(TMP_OGG) <= 0):
            self.ca.m.cannotSaveVideo()
            return

        self.ca.ui.setPostProcessPixBuf(self.pixbuf)
        self.ca.m.saveAudio(TMP_OGG, self.pixbuf)

    def abandonMedia(self):
        logger.debug('abandonMedia')
        self.stop()

        if (self.AUDIO_TRANSCODE_ID != 0):
            gobject.source_remove(self.AUDIO_TRANSCODE_ID)
            self.AUDIO_TRANSCODE_ID = 0
        if (self.TRANSCODE_ID != 0):
            gobject.source_remove(self.TRANSCODE_ID)
            self.TRANSCODE_ID = 0
        if (self.VIDEO_TRANSCODE_ID != 0):
            gobject.source_remove(self.VIDEO_TRANSCODE_ID)
            self.VIDEO_TRANSCODE_ID = 0

        if (os.path.exists(TMP_OGG)):
            os.remove(TMP_OGG)

    def __init__(self, pca):
        self.window = None
        self.ca = pca

        self.pipeline = None
        self.play_pipe = None
        self.fallback_pipe = None
        self.photo = None
        self.video_pipe = None
        self.audio_pipe = None

        self.fallback = False

    def _switch_pipe(self, new_pipe):
        if self.pipeline != new_pipe:
            if self.pipeline:
                self.pipeline.set_state(gst.STATE_NULL)
            self.pipeline = new_pipe

        if self.pipeline:
            xsink = new_pipe.get_by_name('xsink')
            if xsink:
                xsink.set_xwindow_id(self.window.window.xid)
            self.pipeline.set_state(gst.STATE_PLAYING)

    def getTags( self, type ):
        tl = gst.TagList()
        tl[gst.TAG_ARTIST] = str(Instance.nickName)
        tl[gst.TAG_COMMENT] = "sugar"
        #this is unfortunately, unreliable
        #record.Record.log.debug("self.ca.metadata['title']->" + str(self.ca.metadata['title']) )
        tl[gst.TAG_ALBUM] = "sugar" #self.ca.metadata['title']
        tl[gst.TAG_DATE] = utils.getDateString(int(time.time()))
        stringType = Constants.mediaTypes[type][Constants.keyIstr]
        tl[gst.TAG_TITLE] = Constants.istrBy % {"1":stringType, "2":str(Instance.nickName)}
        return tl

class LiveVideoWindow(gtk.Window):
    def __init__(self, bgd ):
        gtk.Window.__init__(self)

        self.glive = None

        self.modify_bg( gtk.STATE_NORMAL, bgd )
        self.modify_bg( gtk.STATE_INSENSITIVE, bgd )
        self.unset_flags(gtk.DOUBLE_BUFFERED)
        self.set_flags(gtk.APP_PAINTABLE)

    def set_glive(self, pglive):
        self.glive = pglive
        self.glive.window = self
