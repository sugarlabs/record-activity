# Copyright (C) 2008, Media Modifications Ltd.
# Copyright (C) 2013, Sugar Labs

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
import subprocess
import logging
import shutil
from gettext import gettext as _
from gettext import ngettext

import gi
vs = {'Gdk': '3.0', 'Gst': '1.0', 'Gtk': '3.0', 'SugarExt': '1.0',
      'PangoCairo': '1.0', 'GstVideo': '1.0'}
for api, ver in vs.iteritems():
    gi.require_version(api, ver)

from gi.repository import GObject, Gdk, GdkPixbuf, Gtk, Pango, PangoCairo, Gst, GstVideo, SugarExt
import cairo

GObject.threads_init()
Gst.init(None)

from sugar3.activity import activity
from sugar3.graphics.alert import Alert
from sugar3.graphics.icon import Icon
from sugar3.graphics.toolcombobox import ToolComboBox
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.radiotoolbutton import RadioToolButton
from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.graphics.menuitem import MenuItem
from sugar3.graphics import style
from sugar3.graphics.tray import HTray

from model import Model
from button import RecdButton
import constants
from instance import Instance
import utils
from mediaview import MediaView
import hw

logger = logging.getLogger('record.py')
COLOR_BLACK = Gdk.color_parse('#000000')
COLOR_WHITE = Gdk.color_parse('#ffffff')

TIMER_VALUES = [0, 5, 10]
DURATION_VALUES = [2, 4, 6]
QUALITY_VALUES = ['low', 'high']

#Gst.debug_set_active(True)
#Gst.debug_set_colored(False)
#if logging.getLogger().level <= logging.DEBUG:
#Gst.debug_set_default_threshold(Gst.DebugLevel.WARNING)
#else:
# Gst.debug_set_default_threshold(Gst.DebugLevel.ERROR)


class Record(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        if Gst.version() == (1L, 0L, 10L, 0L):
            return self._incompatible()

        self.props.enable_fullscreen_mode = False
        Instance(self)

        self.connect("notify::active", self.__active_cb)

        #the main classes
        self.model = Model(self)
        self.ui_init()

        #CSCL
        self.connect("shared", self._shared_cb)
        if self.get_shared_activity():
            #have you joined or shared this activity yourself?
            if self.get_shared():
                self._joined_cb(self)
            else:
                self.connect("joined", self._joined_cb)

        # Realize the video view widget so that it knows its own window XID
        self._media_view.realize_video()

        # Changing to the first toolbar kicks off the rest of the setup
        if self.model.get_has_camera():
            self.model.change_mode(constants.MODE_PHOTO)
        else:
            self.model.change_mode(constants.MODE_AUDIO)

        # Restore critical hidden mixer controls to default
        model = hw.get_xo_version()
        if model == 1.75 or model == 4:
            args = ['amixer', 'set', 'Analog Mic Boost', "100%"]
            try:
                subprocess.check_output(args)
            except:
                pass

        self._old_cursor = self.get_window().get_cursor()

        # testing restarter
        ct = os.stat('go').st_ctime
        def restarter():
            if os.stat('go').st_ctime != ct:
                self.close()
                os.execv('/usr/bin/sugar-activity', ['sugar-activity'])
                return False
            return True
        GObject.timeout_add(233, restarter)

    def _incompatible(self):
        ''' Display abbreviated activity user interface with alert '''
        toolbox = ToolbarBox()
        stop = StopButton(self)
        toolbox.toolbar.add(stop)
        self.set_toolbar_box(toolbox)

        title = _('Activity not compatible with this system.')
        msg = _('Please downgrade activity and try again.')
        alert = Alert(title=title, msg=msg)
        alert.add_button(0, 'Stop', Icon(icon_name='activity-stop'))
        self.add_alert(alert)

        label = Gtk.Label(_('Uh oh, GStreamer is too old.'))
        self.set_canvas(label)

        alert.connect('response', self.__incompatible_response_cb)
        stop.connect('clicked', self.__incompatible_stop_clicked_cb,
                     alert)

        self.show_all()

    def __incompatible_stop_clicked_cb(self, button, alert):
        self.remove_alert(alert)

    def __incompatible_response_cb(self, alert, response):
        self.remove_alert(alert)
        self.close()

    def read_file(self, path):
        if hasattr(self, 'model'):
            self.model.read_file(path)

    def write_file(self, path):
        if hasattr(self, 'model'):
            self.model.write_file(path)

    def close(self, **kwargs):
        if hasattr(self, 'model'):
            self.model.close()
        activity.Activity.close(self, **kwargs)

    def __active_cb(self, widget, pspec):
        self.model.set_visible(self.props.active)

    def _shared_cb(self, activity):
        self.model.collab.set_activity_shared()

    def _joined_cb(self, activity):
        self.model.collab.joined()

    def ui_init(self):
        self._fullscreen = False
        self._showing_info = False

        # FIXME: if _thumb_tray becomes some kind of button group, we wouldn't
        # have to track which recd is active
        self._active_recd = None

        self.connect_after('key-press-event', self._key_pressed)

        self._active_toolbar_idx = 0

        toolbar_box = ToolbarBox()
        activity_button = ActivityToolbarButton(self)
        toolbar_box.toolbar.insert(activity_button, 0)
        self.set_toolbar_box(toolbar_box)
        self._toolbar = self.get_toolbar_box().toolbar

        tool_group = None
        if self.model.get_has_camera():
            self._photo_button = RadioToolButton()
            self._photo_button.props.group = tool_group
            tool_group = self._photo_button
            self._photo_button.props.icon_name = 'camera-external'
            self._photo_button.props.label = _('Photo')
            self._photo_button.props.tooltip = _('Picture camera mode\n\nWhen the record button is pressed,\ntake one picture from the camera.')
            self._photo_button.mode = constants.MODE_PHOTO
            self._photo_button.connect('clicked', self._mode_button_clicked)
            self._toolbar.insert(self._photo_button, -1)

            self._video_button = RadioToolButton()
            self._video_button.props.group = tool_group
            self._video_button.props.icon_name = 'media-video'
            self._video_button.props.label = _('Video')
            self._video_button.props.tooltip = _('Video camera mode\n\nWhen the record button is pressed,\ntake photographs many times a second,\nand record sound using the microphone,\nuntil the button is pressed again.')
            self._video_button.mode = constants.MODE_VIDEO
            self._video_button.connect('clicked', self._mode_button_clicked)
            self._toolbar.insert(self._video_button, -1)
        else:
            self._photo_button = None
            self._video_button = None

        self._audio_button = RadioToolButton()
        self._audio_button.props.group = tool_group
        self._audio_button.props.icon_name = 'media-audio'
        self._audio_button.props.label = _('Audio')
        self._audio_button.props.tooltip = _('Audio recording mode\n\nWhen the record button is pressed,\ntake one photograph,\nand record sound using the microphone,\nuntil the button is pressed again.')
        self._audio_button.mode = constants.MODE_AUDIO
        self._audio_button.connect('clicked', self._mode_button_clicked)
        self._toolbar.insert(self._audio_button, -1)

        self._toolbar.insert(Gtk.SeparatorToolItem(), -1)

        self._toolbar_controls = RecordControl(self._toolbar)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self._toolbar.insert(separator, -1)
        self._toolbar.insert(StopButton(self), -1)
        self.get_toolbar_box().show_all()

        self._media_view = MediaView()
        self._media_view.connect('media-clicked',
                                 self._media_view_media_clicked)
        self._media_view.connect('pip-clicked', self._media_view_pip_clicked)
        self._media_view.connect('info-clicked', self._media_view_info_clicked)
        self._media_view.connect('fullscreen-clicked',
                                 self._media_view_fullscreen_clicked)
        self._media_view.connect('tags-changed', self._media_view_tags_changed)
        self._media_view.show()

        self._controls_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        trim_height_shutter_button = 7
        self._controls_hbox.set_size_request(-1, style.GRID_CELL_SIZE +
                                                 trim_height_shutter_button)

        self._shutter_button = ShutterButton()
        self._shutter_button.set_tooltip_text(_("Record"))
        self._shutter_button.connect("clicked", self._shutter_clicked)
        self._shutter_button.modify_bg(Gtk.StateType.NORMAL, COLOR_BLACK)
        self._controls_hbox.pack_start(self._shutter_button, True, False, 0)

        self._countdown_image = CountdownImage()
        self._controls_hbox.pack_start(self._countdown_image, True, False, 0)

        self._play_button = PlayButton()
        self._play_button.connect('clicked', self._play_pause_clicked)
        self._controls_hbox.pack_start(self._play_button, False, True, 0)

        self._playback_scale = PlaybackScale(self.model)
        self._controls_hbox.pack_start(self._playback_scale, True, True, 0)

        self._progress = ProgressInfo()
        self._controls_hbox.pack_start(self._progress, True, True, 0)

        self._title_label = Gtk.Label()
        self._title_label.set_markup("<b><span foreground='white'>"+_('Title:')+'</span></b>')
        self._controls_hbox.pack_start(self._title_label, False, True, 0)

        self._title_entry = Gtk.Entry()
        self._title_entry.modify_bg(Gtk.StateType.INSENSITIVE, COLOR_BLACK)
        self._title_entry.connect('changed', self._title_changed)
        self._controls_hbox.pack_start(self._title_entry, expand=True, fill=True, padding=10)
        self._controls_hbox.show()

        height_tray = 150  # height of tray

        self._thumb_tray = HTray(hexpand=True, height_request=height_tray)
        self._thumb_tray.show_all()

        self._media_view.set_size_request(-1, Gdk.Screen.height() - \
            style.GRID_CELL_SIZE * 2 - height_tray - trim_height_shutter_button)

        main_box = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
        main_box.add(self._media_view)
        main_box.add(self._controls_hbox)
        main_box.add(self._thumb_tray)
        main_box.show()
        self.set_canvas(main_box)
        main_box.get_parent().modify_bg(Gtk.StateType.NORMAL, COLOR_BLACK)

    def serialize(self):
        data = {}

        data['timer'] = self._toolbar_controls.get_timer_idx()
        data['duration'] = self._toolbar_controls.get_duration_idx()
        data['quality'] = self._toolbar_controls.get_quality()

        return data

    def deserialize(self, data):
        self._toolbar_controls.set_timer_idx(data.get('timer', 0))
        self._toolbar_controls.set_duration_idx(data.get('duration', 0))
        self._toolbar_controls.set_quality(data.get('quality', 0))

    def _key_pressed(self, widget, event):
        key = event.keyval
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK

        if (ctrl and key == Gdk.KEY_space) or \
            key == Gdk.KEY_KP_Page_Up:  # game key O

            if self._shutter_button.props.visible:
                if self._shutter_button.props.sensitive:
                    self._shutter_button.clicked()
            else:  # return to live mode
                self.model.set_state(constants.STATE_READY)
            return True

        if self.model.ui_frozen():
            return True

        if ctrl and key == Gdk.KEY_c:
            self._copy_to_clipboard(self._active_recd)
            return True

        if key == Gdk.KEY_i:
            self._toggle_info()
            return True

        if key == Gdk.KEY_Escape and self._fullscreen:
            self._toggle_fullscreen()
            return True

        # if viewing media, return to live mode
        if key == Gdk.KEY_Escape and \
            self.model.get_state() == constants.STATE_READY:

            self.model.set_state(constants.STATE_READY)
            return True

        return False

    def _play_pause_clicked(self, widget):
        self.model.play_pause()

    def set_mode(self, mode):
        self._toolbar_controls.set_mode(mode)

    # can be called from GStreamer thread, so must not do any GTK+ stuff
    def set_glive_sink(self, sink):
        return self._media_view.set_video_sink(sink)

    # can be called from GStreamer thread, so must not do any GTK+ stuff
    def set_gplay_sink(self, sink):
        return self._media_view.set_video2_sink(sink)

    def get_selected_quality(self):
        return self._toolbar_controls.get_quality()

    def get_selected_timer(self):
        return self._toolbar_controls.get_timer()

    def get_selected_duration(self):
        return self._toolbar_controls.get_duration() * 60  # convert to secs

    def set_progress(self, value, text):
        self._progress.set_progress(value)
        self._progress.set_text(text)

    def set_countdown(self, value):
        if value == 0:
            self._shutter_button.show()
            self._countdown_image.hide()
            self._countdown_image.clear()
            return

        self._shutter_button.hide()
        self._countdown_image.show()
        self._countdown_image.set_value(value)

    def _title_changed(self, widget):
        self._active_recd.setTitle(self._title_entry.get_text())

    def _media_view_media_clicked(self, widget):
        if self._play_button.props.visible and self._play_button.props.sensitive:
            self._play_button.clicked()

    def _media_view_pip_clicked(self, widget):
        # clicking on the PIP always returns to live mode
        self.model.set_state(constants.STATE_READY)

    def _media_view_info_clicked(self, widget):
        self._toggle_info()

    def _toggle_info(self):
        recd = self._active_recd
        if not recd:
            return

        if self._showing_info:
            self._show_recd(recd, play=False)
            return

        self._showing_info = True
        if self.model.get_mode() in (constants.MODE_PHOTO, constants.MODE_AUDIO):
            func = self._media_view.show_info_photo
        else:
            func = self._media_view.show_info_video

        self._play_button.hide()
        self._progress.hide()
        self._playback_scale.hide()
        self._title_entry.set_text(recd.title)
        self._title_entry.show()
        self._title_label.show()

        func(recd.recorderName, recd.colorStroke, recd.colorFill, utils.getDateString(recd.time), recd.tags)

    def _media_view_fullscreen_clicked(self, widget):
        self._toggle_fullscreen()

    def _media_view_tags_changed(self, widget, tbuffer):
        text = tbuffer.get_text(tbuffer.get_start_iter(), tbuffer.get_end_iter())
        self._active_recd.setTags(text)

    def _toggle_fullscreen(self):
        if not self._fullscreen:
            self.get_toolbar_box().hide()
            self._thumb_tray.hide()
        else:
            self.get_toolbar_box().show()
            self._thumb_tray.show()

        self._fullscreen = not self._fullscreen
        self._media_view.set_fullscreen(self._fullscreen)

    def _mode_button_clicked(self, button):
        self.model.change_mode(button.mode)

    def _shutter_clicked(self, arg):
        self.model.do_shutter()

    def set_shutter_sensitive(self, value):
        self._shutter_button.set_sensitive(value)

    def set_state(self, state):
        radio_state = (state == constants.STATE_READY)
        for item in (self._photo_button, self._audio_button, self._video_button):
            if item:
                item.set_sensitive(radio_state)

        self._showing_info = False
        if state == constants.STATE_READY:
            self._set_cursor_default()
            self._active_recd = None
            self._title_entry.hide()
            self._title_label.hide()
            self._play_button.hide()
            self._playback_scale.hide()
            self._progress.hide()
            self._controls_hbox.set_child_packing(self._shutter_button, expand=True, fill=False, padding=0, pack_type=Gtk.PackType.START)
            self._shutter_button.set_normal()
            self._shutter_button.set_sensitive(True)
            self._shutter_button.show()
            self._media_view.show_live()
        elif state == constants.STATE_RECORDING:
            self._shutter_button.set_recording()
            self._controls_hbox.set_child_packing(self._shutter_button, expand=False, fill=False, padding=0, pack_type=Gtk.PackType.START)
            self._progress.show()
        elif state == constants.STATE_PROCESSING:
            self._set_cursor_busy()
            self._shutter_button.hide()
            self._progress.show()
        elif state == constants.STATE_DOWNLOADING:
            self._shutter_button.hide()
            self._progress.show()

    def set_paused(self, value):
        if value:
            self._play_button.set_play()
        else:
            self._play_button.set_pause()

    def _thumbnail_clicked(self, button, recd):
        if self.model.ui_frozen():
            return

        self._active_recd = recd
        self._show_recd(recd)

    def add_thumbnail(self, recd):
        button = RecdButton(recd)
        clicked_handler = button.connect("clicked", self._thumbnail_clicked, recd)
        remove_handler = button.connect("remove-requested", self._remove_recd)
        clipboard_handler = button.connect("copy-clipboard-requested", self._thumbnail_copy_clipboard)
        button.handler_ids = (clicked_handler, remove_handler, clipboard_handler)
        button.show()
        self._thumb_tray.add_item(button)
        self._thumb_tray.scroll_to_item(button)

    def _copy_to_clipboard(self, recd):
        if recd == None:
            return
        if not recd.isClipboardCopyable():
            return

        media_path = recd.getMediaFilepath()
        tmp_path = utils.getUniqueFilepath(media_path, 0)
        shutil.copyfile(media_path, tmp_path)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        data = [Gtk.TargetEntry.new('text/uri-list', 0, 0)]

        # XXX SL#4307 - until set_with_data bindings are fixed upstream
        if hasattr(clipboard, 'set_with_data'):
            clipboard.set_with_data(data, self._clipboard_get,
                                    self._clipboard_clear, tmp_path)
        else:
            SugarExt.clipboard_set_with_data(clipboard, data,
                                             self._clipboard_get,
                                             self._clipboard_clear, tmp_path)


    def _clipboard_get(self, clipboard, selection_data, info, path):
        selection_data.set_uris(["file://" + path])

    def _clipboard_clear(self, clipboard, path):
        if os.path.exists(path):
            os.unlink(path)

    def _thumbnail_copy_clipboard(self, recdbutton):
        self._copy_to_clipboard(recdbutton.get_recd())

    def _remove_recd(self, recdbutton):
        recd = recdbutton.get_recd()
        self.model.delete_recd(recd)
        if self._active_recd == recd:
            self.model.set_state(constants.STATE_READY)

        self._remove_thumbnail(recdbutton)

    def _remove_thumbnail(self, recdbutton):
        for handler in recdbutton.handler_ids:
            recdbutton.disconnect(handler)

        self._thumb_tray.remove_item(recdbutton)
        recdbutton.cleanup()

    def remove_all_thumbnails(self):
        for child in self._thumb_tray.get_children():
            self._remove_thumbnail(child)

    def show_still(self, pixbuf):
        self._media_view.show_still(pixbuf)

    def _show_photo(self, recd):
        path = self._get_photo_path(recd)
        self._media_view.show_photo(path)
        self._title_entry.set_text(recd.title)
        self._title_entry.show()
        self._title_label.show()
        self._shutter_button.hide()
        self._progress.hide()

    def _show_audio(self, recd, play):
        self._progress.hide()
        self._shutter_button.hide()
        self._title_entry.hide()
        self._title_label.hide()
        self._play_button.show()
        self._playback_scale.show()
        path = recd.getAudioImageFilepath()
        self._media_view.show_photo(path)
        if play:
            self.model.play_audio(recd)

    def _show_video(self, recd, play):
        self._progress.hide()
        self._shutter_button.hide()
        self._title_entry.hide()
        self._title_label.hide()
        self._play_button.show()
        self._playback_scale.show()
        self._media_view.show_video()
        if play:
            self.model.play_video(recd)

    def set_playback_scale(self, value):
        self._playback_scale.set_value(value)

    def _get_photo_path(self, recd):
        # FIXME should live (partially) in recd?

        #downloading = self.ca.requestMeshDownload(recd)
        #self.MESHING = downloading

        if True: #not downloading:
            #self.progressWindow.updateProgress(0, "")
            return recd.getMediaFilepath()

        #maybe it is not downloaded from the mesh yet...
        #but we can show the low res thumb in the interim
        return recd.getThumbFilepath()

    def _show_recd(self, recd, play=True):
        self._showing_info = False

        if recd.buddy and not recd.downloadedFromBuddy:
            self.model.request_download(recd)
        elif recd.type == constants.TYPE_PHOTO:
            self._show_photo(recd)
        elif recd.type == constants.TYPE_AUDIO:
            self._show_audio(recd, play)
        elif recd.type == constants.TYPE_VIDEO:
            self._show_video(recd, play)

    def remote_recd_available(self, recd):
        if recd == self._active_recd:
            self._show_recd(recd)

    def update_download_progress(self, recd):
        if recd != self._active_recd:
            return

        if not recd.meshDownloading:
            msg = _('Download failed.')
        elif recd.meshDownloadingProgress:
            msg = _('Downloading...')
        else:
            msg = _('Requesting...')

        self.set_progress(recd.meshDownlodingPercent, msg)

    def _set_cursor_busy(self):
        self._old_cursor = self.get_window().get_cursor()
        self.get_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))
        Gdk.flush()

    def _set_cursor_default(self):
        self.get_window().set_cursor(self._old_cursor)
        Gdk.flush()


class PlaybackScale(Gtk.HScale):
    def __init__(self, model):
        logger.debug('PlaybackScale: __init__')
        self.model = model
        self._change_handler = None
        self._adjustment = Gtk.Adjustment(0.0, 0.0, 100.0, 0.1, 1.0, 1.0)
        Gtk.HScale.__init__(self, adjustment=self._adjustment)

        self.set_draw_value(False)
        self.connect('button-press-event', self._button_press)
        self.connect('button-release-event', self._button_release)

    def set_value(self, value):
        logger.debug('PlaybackScale: set_value %.2f' % value)
        if self._change_handler:
            self.handler_block(self._change_handler)
        self._adjustment.set_value(value)
        if self._change_handler:
            self.handler_unblock(self._change_handler)

    def _value_changed(self, scale):
        value = self._adjustment.get_value()
        logger.debug('PlaybackScale: _value_changed %.2f' % value)
        self.model.seek_do(value)

    def _button_press(self, widget, event):
        logger.debug('PlaybackScale: _button_press')
        self.model.seek_start()
        self._change_handler = self.connect('value-changed',
                                            self._value_changed)

    def _button_release(self, widget, event):
        logger.debug('PlaybackScale: _button_release')
        self.disconnect(self._change_handler)
        self._change_handler = None
        self.model.seek_end()


class ProgressInfo(Gtk.VBox):
    def __init__(self):
        super(type(self), self).__init__()

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.modify_bg(Gtk.StateType.NORMAL, COLOR_BLACK)
        self._progress_bar.modify_bg(Gtk.StateType.INSENSITIVE, COLOR_BLACK)
        self.pack_start(self._progress_bar, expand=True, fill=True, padding=5)

        self._label = Gtk.Label()
        self._label.modify_fg(Gtk.StateType.NORMAL, COLOR_WHITE)
        self.pack_start(self._label, expand=True, fill=True, padding=0)

    def show(self):
        self._progress_bar.show()
        self._label.show()
        super(type(self), self).show()

    def hide(self):
        self._progress_bar.hide()
        self._label.hide()
        super(type(self), self).hide()

    def set_progress(self, value):
        self._progress_bar.set_fraction(value)

    def set_text(self, text):
        self._label.set_text(text)


class CountdownImage(Gtk.Image):
    def __init__(self):
        super(type(self), self).__init__()
        self._countdown_images = {}

    def _generate_image(self, num):
        w = 55
        h = w
        pixmap = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
        ctx = cairo.Context(pixmap)
        ctx.rectangle(0, 0, w, h)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()

        x = 0
        y = 4
        ctx.translate(x, y)
        circle_path = os.path.join(constants.GFX_PATH, 'media-circle.png')
        surface = cairo.ImageSurface.create_from_png(circle_path)
        ctx.set_source_surface(surface, 0, 0)
        ctx.paint()
        ctx.translate(-x, -y)

        ctx.set_source_rgb(255, 255, 255)
        pctx = PangoCairo.create_context(ctx)
        play = PangoCairo.create_layout(ctx)
        font = Pango.FontDescription("sans 30")
        play.set_font_description(font)
        play.set_text(str(num), -1)
        ink, log = play.get_pixel_extents()
        logger.error('ink %r', (ink.x, ink.y, ink.width, ink.height))
        #logger.error('log %r', (log.x, log.y, log.width, log.height))
        # FIXME: SEGFAULTS HERE
        ctx.translate(-ink.x, -ink.y)
        xoff = (w - ink.width) / 2
        yoff = (h - ink.height) / 2
        ctx.translate(xoff, yoff)
        ctx.translate(-3, 0)
        PangoCairo.show_layout(pctx, play)
        return pixmap

    def set_value(self, num):
        if num not in self._countdown_images:
            self._countdown_images[num] = self._generate_image(num)

        self.set_from_pixmap(self._countdown_images[num], None)


class ShutterButton(Gtk.Button):
    def __init__(self):
        Gtk.Button.__init__(self)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_focus_on_click(False)
        self.modify_bg(Gtk.StateType.ACTIVE, COLOR_BLACK)

        path = os.path.join(constants.GFX_PATH, 'media-record.png')
        self._rec_image = Gtk.Image.new_from_file(path)

        path = os.path.join(constants.GFX_PATH, 'media-record-red.png')
        self._rec_red_image = Gtk.Image.new_from_file(path)

        path = os.path.join(constants.GFX_PATH, 'media-insensitive.png')
        self._insensitive_image = Gtk.Image.new_from_file(path)

        self.set_normal()

    def set_sensitive(self, sensitive):
        if sensitive:
            self.set_image(self._rec_image)
        else:
            self.set_image(self._insensitive_image)
        super(type(self), self).set_sensitive(sensitive)

    def set_normal(self):
        self.set_image(self._rec_image)

    def set_recording(self):
        self.set_image(self._rec_red_image)


class PlayButton(Gtk.Button):
    def __init__(self):
        super(type(self), self).__init__()
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_focus_on_click(False)
        self.modify_bg(Gtk.StateType.ACTIVE, COLOR_BLACK)

        path = os.path.join(constants.GFX_PATH, 'media-play.png')
        self._play_image = Gtk.Image.new_from_file(path)

        path = os.path.join(constants.GFX_PATH, 'media-pause.png')
        self._pause_image = Gtk.Image.new_from_file(path)

        self.set_play()

    def set_play(self):
        self.set_image(self._play_image)

    def set_pause(self):
        self.set_image(self._pause_image)


class RecordControl():

    def __init__(self, toolbar):

        self._timer_value = TIMER_VALUES[0]
        self._timer_button = ToolButton('timer-0')
        self._timer_button.set_tooltip(_('Select timer'))
        self._timer_button.connect('clicked', self._timer_selection_cb)
        toolbar.insert(self._timer_button, -1)
        self._setup_timer_palette()

        self._duration_value = DURATION_VALUES[0]
        self._duration_button = ToolButton('duration-2')
        self._duration_button.set_tooltip(_('Select duration'))
        self._duration_button.connect('clicked', self._duration_selection_cb)
        toolbar.insert(self._duration_button, -1)
        self._setup_duration_palette()

        self._quality_value = 0
        self._quality_button = ToolButton('low-quality')
        self._quality_button.set_tooltip(_('Select quality'))
        self._quality_button.connect('clicked', self._quality_selection_cb)
        toolbar.insert(self._quality_button, -1)
        self._setup_quality_palette()

    def _timer_selection_cb(self, widget):
        if self._timer_palette:

            if not self._timer_palette.is_up():
                self._timer_palette.popup(immediate=True)
            else:
                self._timer_palette.popdown(immediate=True)
            return

    def _setup_timer_palette(self):
        self._timer_palette = self._timer_button.get_palette()

        for seconds in TIMER_VALUES:
            if seconds == 0:
                text = _('Immediate')
            else:
                text = ngettext('%s second', '%s seconds', seconds) % seconds
            menu_item = MenuItem(icon_name='timer-%d' % (seconds),
                                 text_label=text)
            menu_item.connect('activate', self._timer_selected_cb, seconds)
            self._timer_palette.menu.append(menu_item)
            menu_item.show()

    def _timer_selected_cb(self, button, seconds):
        self.set_timer_idx(TIMER_VALUES.index(seconds))

    def _duration_selection_cb(self, widget):
        if self._duration_palette:
            if not self._duration_palette.is_up():
                self._duration_palette.popup(immediate=True)
            else:
                self._duration_palette.popdown(immediate=True)
            return

    def _setup_duration_palette(self):
        self._duration_palette = self._duration_button.get_palette()
        for minutes in DURATION_VALUES:
            if minutes == 0:
                text = gtk.Label(_('Immediate'))
            else:
                text = ngettext('%s minute', '%s minutes', minutes) % minutes
            menu_item = MenuItem(icon_name='duration-%d' % (minutes),
                                 text_label=text)
            menu_item.connect('activate', self._duration_selected_cb, minutes)
            self._duration_palette.menu.append(menu_item)
            menu_item.show()

    def _duration_selected_cb(self, button, minutes):
        self.set_duration_idx(DURATION_VALUES.index(minutes))

    def _quality_selection_cb(self, widget):
        if self._quality_palette:
            if not self._quality_palette.is_up():
                self._quality_palette.popup(immediate=True)
            else:
                self._quality_palette.popdown(immediate=True)
            return

    def _setup_quality_palette(self):
        self._quality_palette = self._quality_button.get_palette()
        for quality in QUALITY_VALUES:
            text = _('%s quality') % (quality)
            menu_item = MenuItem(icon_name=quality + '-quality',
                                 text_label=text)
            menu_item.connect('activate', self._quality_selected_cb, quality)
            self._quality_palette.menu.append(menu_item)
            menu_item.show()

    def _quality_selected_cb(self, button, quality):
        self.set_quality(QUALITY_VALUES.index(quality))

    def set_mode(self, mode):
        if mode == constants.MODE_PHOTO:
            self._quality_button.set_sensitive(False)
            self._timer_button.set_sensitive(True)
            self._duration_button.set_sensitive(False)
        if mode == constants.MODE_VIDEO:
            self._quality_button.set_sensitive(True)
            self._timer_button.set_sensitive(True)
            self._duration_button.set_sensitive(True)
        if mode == constants.MODE_AUDIO:
            self._quality_button.set_sensitive(False)
            self._timer_button.set_sensitive(True)
            self._duration_button.set_sensitive(True)

    def get_timer(self):
        return self._timer_value

    def get_timer_idx(self):
        if self._timer_value in TIMER_VALUES:
            return TIMER_VALUES.index(self._timer_value)
        else:
            return TIMER_VALUES[0]

    def set_timer_idx(self, idx):
        self._timer_value = TIMER_VALUES[idx]
        if hasattr(self, '_timer_button'):
            self._timer_button.set_icon_name('timer-%d' % (self._timer_value))

    def get_duration(self):
        return self._duration_value

    def get_duration_idx(self):
        if self._duration_value in DURATION_VALUES:
            return DURATION_VALUES.index(self._duration_value)
        else:
            return DURATION_VALUES[0]

    def set_duration_idx(self, idx):
        self._duration_value = DURATION_VALUES[idx]
        if hasattr(self, '_duration_button'):
            self._duration_button.set_icon_name(
                'duration-%d' % (self._duration_value))

    def get_quality(self):
        return self._quality_value

    def set_quality(self, idx):
        self._quality_value = idx
        if hasattr(self, '_quality_button'):
            self._quality_button.set_icon_name('%s-quality' % (QUALITY_VALUES[idx]))
