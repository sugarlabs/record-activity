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
import logging
import shutil
from gettext import gettext as _
from gettext import ngettext

import gtk
from gtk import gdk
import cairo
import pango
import pangocairo
import pygst
pygst.require('0.10')
import gst

from sugar.activity import activity
from sugar.graphics.toolcombobox import ToolComboBox
from sugar.graphics.toolbarbox import ToolbarBox
from sugar.graphics.toolbarbox import ToolbarButton
from sugar.graphics.radiotoolbutton import RadioToolButton
from sugar.activity.widgets import StopButton
from sugar.activity.widgets import ActivityToolbarButton

from model import Model
from button import RecdButton
import constants
from instance import Instance
import utils
from tray import HTray
from mediaview import MediaView
import hw
from iconcombobox import IconComboBox

logger = logging.getLogger('record.py')
COLOR_BLACK = gdk.color_parse('#000000')
COLOR_WHITE = gdk.color_parse('#ffffff')

gst.debug_set_active(True)
gst.debug_set_colored(False)
if logging.getLogger().level <= logging.DEBUG:
    gst.debug_set_default_threshold(gst.LEVEL_WARNING)
else:
    gst.debug_set_default_threshold(gst.LEVEL_ERROR)

class Record(activity.Activity):
    def __init__(self, handle):
        super(Record, self).__init__(handle)
        self.props.enable_fullscreen_mode = False
        Instance(self)

        self.add_events(gtk.gdk.VISIBILITY_NOTIFY_MASK)
        self.connect("visibility-notify-event", self._visibility_changed)

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

    def read_file(self, path):
        self.model.read_file(path)

    def write_file(self, path):
        self.model.write_file(path)

    def close(self):
        self.model.gplay.stop()
        self.model.glive.stop()
        super(Record, self).close()

    def _visibility_changed(self, widget, event):
        self.model.set_visible(event.state != gtk.gdk.VISIBILITY_FULLY_OBSCURED)

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

        self._toolbar_box = ToolbarBox()
        activity_button = ActivityToolbarButton(self)
        self._toolbar_box.toolbar.insert(activity_button, 0)
        self.set_toolbar_box(self._toolbar_box)
        self._toolbar = self.get_toolbar_box().toolbar

        tool_group = None
        if self.model.get_has_camera():
            self._photo_button = RadioToolButton()
            self._photo_button.props.group = tool_group
            tool_group = self._photo_button
            self._photo_button.props.icon_name = 'camera-external'
            self._photo_button.props.label = _('Photo')
            self._photo_button.mode = constants.MODE_PHOTO
            self._photo_button.connect('clicked', self._mode_button_clicked)
            self._toolbar.insert(self._photo_button, -1)

            self._video_button = RadioToolButton()
            self._video_button.props.group = tool_group
            self._video_button.props.icon_name = 'media-video'
            self._video_button.props.label = _('Video')
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
        self._audio_button.mode = constants.MODE_AUDIO
        self._audio_button.connect('clicked', self._mode_button_clicked)
        self._toolbar.insert(self._audio_button, -1)

        self._toolbar.insert(gtk.SeparatorToolItem(), -1)

        self._toolbar_controls = RecordControl(self._toolbar)

        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self._toolbar.insert(separator, -1)
        self._toolbar.insert(StopButton(self), -1)
        self.get_toolbar_box().show_all()

        main_box = gtk.VBox()
        self.set_canvas(main_box)
        main_box.get_parent().modify_bg(gtk.STATE_NORMAL, COLOR_BLACK)
        main_box.show()

        self._media_view = MediaView()
        self._media_view.connect('media-clicked', self._media_view_media_clicked)
        self._media_view.connect('pip-clicked', self._media_view_pip_clicked)
        self._media_view.connect('info-clicked', self._media_view_info_clicked)
        self._media_view.connect('full-clicked', self._media_view_full_clicked)
        self._media_view.connect('tags-changed', self._media_view_tags_changed)
        self._media_view.show()

        self._controls_hbox = gtk.HBox()
        self._controls_hbox.show()

        self._shutter_button = ShutterButton()
        self._shutter_button.connect("clicked", self._shutter_clicked)
        self._controls_hbox.pack_start(self._shutter_button, expand=True, fill=False)

        self._countdown_image = CountdownImage()
        self._controls_hbox.pack_start(self._countdown_image, expand=True, fill=False)

        self._play_button = PlayButton()
        self._play_button.connect('clicked', self._play_pause_clicked)
        self._controls_hbox.pack_start(self._play_button, expand=False)

        self._playback_scale = PlaybackScale(self.model)
        self._controls_hbox.pack_start(self._playback_scale, expand=True, fill=True)

        self._progress = ProgressInfo()
        self._controls_hbox.pack_start(self._progress, expand=True, fill=True)

        self._title_label = gtk.Label()
        self._title_label.set_markup("<b><span foreground='white'>"+_('Title:')+'</span></b>')
        self._controls_hbox.pack_start(self._title_label, expand=False)

        self._title_entry = gtk.Entry()
        self._title_entry.modify_bg(gtk.STATE_INSENSITIVE, COLOR_BLACK)
        self._title_entry.connect('changed', self._title_changed)
        self._controls_hbox.pack_start(self._title_entry, expand=True, fill=True, padding=10)

        container = RecordContainer(self._media_view, self._controls_hbox)
        main_box.pack_start(container, expand=True, fill=True, padding=6)
        container.show()

        self._thumb_tray = HTray()
        self._thumb_tray.set_size_request(-1, 150)
        main_box.pack_end(self._thumb_tray, expand=False)
        self._thumb_tray.show_all()

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
        if self.model.ui_frozen():
            return False

        key = event.keyval

        if key == gtk.keysyms.KP_Page_Up: # game key O
            if self._shutter_button.props.visible:
                if self._shutter_button.props.sensitive:
                    self._shutter_button.clicked()
            else: # return to live mode
                self.model.set_state(constants.STATE_READY)
        elif key == gtk.keysyms.c and event.state == gdk.CONTROL_MASK:
            self._copy_to_clipboard(self._active_recd)
        elif key == gtk.keysyms.i:
            self._toggle_info()
        elif key == gtk.keysyms.Escape:
            if self._fullscreen:
                self._toggle_fullscreen()

        return False

    def _play_pause_clicked(self, widget):
        self.model.play_pause()

    def set_mode(self, mode):
        self._toolbar_controls.set_mode(mode)

    # can be called from gstreamer thread, so must not do any GTK+ stuff
    def set_glive_sink(self, sink):
        return self._media_view.set_video_sink(sink)

    # can be called from gstreamer thread, so must not do any GTK+ stuff
    def set_gplay_sink(self, sink):
        return self._media_view.set_video2_sink(sink)

    def get_selected_quality(self):
        return self._toolbar_controls.get_quality()

    def get_selected_timer(self):
        return self._toolbar_controls.get_timer()

    def get_selected_duration(self):
        return self._toolbar_controls.get_duration()

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

    def _media_view_full_clicked(self, widget):
        self._toggle_fullscreen()

    def _media_view_tags_changed(self, widget, tbuffer):
        text = tbuffer.get_text(tbuffer.get_start_iter(), tbuffer.get_end_iter())
        self._active_recd.setTags(text)

    def _toggle_fullscreen(self):
        if not self._fullscreen:
            self._toolbar_box.hide()
            self._thumb_tray.hide()
        else:
            self._toolbar_box.show()
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
            self._controls_hbox.set_child_packing(self._shutter_button, expand=True, fill=False, padding=0, pack_type=gtk.PACK_START)
            self._shutter_button.set_normal()
            self._shutter_button.set_sensitive(True)
            self._shutter_button.show()
            self._media_view.show_live()
        elif state == constants.STATE_RECORDING:
            self._shutter_button.set_recording()
            self._controls_hbox.set_child_packing(self._shutter_button, expand=False, fill=False, padding=0, pack_type=gtk.PACK_START)
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

    def add_thumbnail(self, recd, scroll_to_end):
        button = RecdButton(recd)
        clicked_handler = button.connect("clicked", self._thumbnail_clicked, recd)
        remove_handler = button.connect("remove-requested", self._remove_recd)
        clipboard_handler = button.connect("copy-clipboard-requested", self._thumbnail_copy_clipboard)
        button.set_data('handler-ids', (clicked_handler, remove_handler, clipboard_handler))
        self._thumb_tray.add_item(button)
        button.show()
        if scroll_to_end:
            self._thumb_tray.scroll_to_end()

    def _copy_to_clipboard(self, recd):
        if recd == None:
            return
        if not recd.isClipboardCopyable():
            return

        media_path = recd.getMediaFilepath()
        tmp_path = utils.getUniqueFilepath(media_path, 0)
        shutil.copyfile(media_path, tmp_path)
        gtk.Clipboard().set_with_data([('text/uri-list', 0, 0)], self._clipboard_get, self._clipboard_clear, tmp_path)

    def _clipboard_get(self, clipboard, selection_data, info, path):
        selection_data.set("text/uri-list", 8, "file://" + path)

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
        handlers = recdbutton.get_data('handler-ids')
        for handler in handlers:
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
        self.window.set_cursor(gdk.Cursor(gdk.WATCH))

    def _set_cursor_default(self):
        self.window.set_cursor(None)

class RecordContainer(gtk.Container):
    """
    A custom Container that contains a media view area, and a controls hbox.

    The controls hbox is given the first height that it requests, locked in
    for the duration of the widget.
    The media view is given the remainder of the space, but is constrained to
    a strict 4:3 ratio, therefore deducing its width.
    The controls hbox is given the same width, and both elements are centered
    horizontall.y
    """
    __gtype_name__ = 'RecordContainer'

    def __init__(self, media_view, controls_hbox):
        self._media_view = media_view
        self._controls_hbox = controls_hbox
        self._controls_hbox_height = 0
        super(RecordContainer, self).__init__()

        for widget in (self._media_view, self._controls_hbox):
            if widget.flags() & gtk.REALIZED:
                widget.set_parent_window(self.window)

            widget.set_parent(self)

    def do_realize(self):
        self.set_flags(gtk.REALIZED)

        self.window = gdk.Window(
            self.get_parent_window(),
            window_type=gdk.WINDOW_CHILD,
            x=self.allocation.x,
            y=self.allocation.y,
            width=self.allocation.width,
            height=self.allocation.height,
            wclass=gdk.INPUT_OUTPUT,
            colormap=self.get_colormap(),
            event_mask=self.get_events() | gdk.VISIBILITY_NOTIFY_MASK | gdk.EXPOSURE_MASK)
        self.window.set_user_data(self)

        self.set_style(self.style.attach(self.window))

        for widget in (self._media_view, self._controls_hbox):
            widget.set_parent_window(self.window)
        self.queue_resize()

    # GTK+ contains on exit if remove is not implemented
    def do_remove(self, widget):
        pass

    def do_size_request(self, req):
        # always request 320x240 (as a minimum for video)
        req.width = 320
        req.height = 240

        self._media_view.size_request()

        w, h = self._controls_hbox.size_request()

        # add on height requested by controls hbox
        if self._controls_hbox_height == 0:
            self._controls_hbox_height = h

        req.height += self._controls_hbox_height

    @staticmethod
    def _constrain_4_3(width, height):
        if (width % 4 == 0) and (height % 3 == 0) and ((width / 4) * 3) == height:
            return width, height # nothing to do

        ratio = 4.0 / 3.0
        if ratio * height > width:
            width = (width / 4) * 4
            height = int(width / ratio)
        else:
            height = (height / 3) * 3
            width = int(ratio * height)

        return width, height 

    @staticmethod
    def _center_in_plane(plane_size, size):
        return (plane_size - size) / 2

    def do_size_allocate(self, allocation):
        self.allocation = allocation

        # give the controls hbox the height that it requested
        remaining_height = self.allocation.height - self._controls_hbox_height

        # give the mediaview the rest, constrained to 4/3 and centered
        media_view_width, media_view_height = self._constrain_4_3(self.allocation.width, remaining_height)
        media_view_x = self._center_in_plane(self.allocation.width, media_view_width)
        media_view_y = self._center_in_plane(remaining_height, media_view_height)

        # send allocation to mediaview
        alloc = gdk.Rectangle()
        alloc.width = media_view_width
        alloc.height = media_view_height
        alloc.x = media_view_x
        alloc.y = media_view_y
        self._media_view.size_allocate(alloc)

        # position hbox at the bottom of the window, with the requested height,
        # and the same width as the media view
        alloc = gdk.Rectangle()
        alloc.x = media_view_x
        alloc.y = self.allocation.height - self._controls_hbox_height
        alloc.width = media_view_width
        alloc.height = self._controls_hbox_height
        self._controls_hbox.size_allocate(alloc)

        if self.flags() & gtk.REALIZED:
            self.window.move_resize(*allocation)

    def do_forall(self, include_internals, callback, data):
        for widget in (self._media_view, self._controls_hbox):
            callback(widget, data)

class PlaybackScale(gtk.HScale):
    def __init__(self, model):
        self.model = model
        self._change_handler = None
        self._playback_adjustment = gtk.Adjustment(0.0, 0.00, 100.0, 0.1, 1.0, 1.0)
        super(PlaybackScale, self).__init__(self._playback_adjustment)

        self.set_draw_value(False)
        self.set_update_policy(gtk.UPDATE_CONTINUOUS)
        self.connect('button-press-event', self._button_press)
        self.connect('button-release-event', self._button_release)

    def set_value(self, value):
        self._playback_adjustment.set_value(value)

    def _value_changed(self, scale):
        self.model.do_seek(scale.get_value())

    def _button_press(self, widget, event):
        self.model.start_seek()
        self._change_handler = self.connect('value-changed', self._value_changed)

    def _button_release(self, widget, event):
        self.disconnect(self._change_handler)
        self._change_handler = None
        self.model.end_seek()


class ProgressInfo(gtk.VBox):
    def __init__(self):
        super(ProgressInfo, self).__init__()

        self._progress_bar = gtk.ProgressBar()
        self._progress_bar.modify_bg(gtk.STATE_NORMAL, COLOR_BLACK)
        self._progress_bar.modify_bg(gtk.STATE_INSENSITIVE, COLOR_BLACK)
        self.pack_start(self._progress_bar, expand=True, fill=True, padding=5)

        self._label = gtk.Label()
        self._label.modify_fg(gtk.STATE_NORMAL, COLOR_WHITE)
        self.pack_start(self._label, expand=True, fill=True)

    def show(self):
        self._progress_bar.show()
        self._label.show()
        super(ProgressInfo, self).show()

    def hide(self):
        self._progress_bar.hide()
        self._label.hide()
        super(ProgressInfo, self).hide()

    def set_progress(self, value):
        self._progress_bar.set_fraction(value)

    def set_text(self, text):
        self._label.set_text(text)


class CountdownImage(gtk.Image):
    def __init__(self):
        super(CountdownImage, self).__init__()
        self._countdown_images = {}

    def _generate_image(self, num):
        w = 55
        h = w
        pixmap = gdk.Pixmap(self.get_window(), w, h, -1)
        ctx = pixmap.cairo_create()
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
        pctx = pangocairo.CairoContext(ctx)
        play = pctx.create_layout()
        font = pango.FontDescription("sans 30")
        play.set_font_description(font)
        play.set_text(str(num))
        dim = play.get_pixel_extents()
        ctx.translate(-dim[0][0], -dim[0][1])
        xoff = (w - dim[0][2]) / 2
        yoff = (h - dim[0][3]) / 2
        ctx.translate(xoff, yoff)
        ctx.translate(-3, 0)
        pctx.show_layout(play)
        return pixmap

    def set_value(self, num):
        if num not in self._countdown_images:
            self._countdown_images[num] = self._generate_image(num)

        self.set_from_pixmap(self._countdown_images[num], None)


class ShutterButton(gtk.Button):
    def __init__(self):
        gtk.Button.__init__(self)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_focus_on_click(False)
        self.modify_bg(gtk.STATE_ACTIVE, COLOR_BLACK)

        path = os.path.join(constants.GFX_PATH, 'media-record.png')
        self._rec_image = gtk.image_new_from_file(path)

        path = os.path.join(constants.GFX_PATH, 'media-record-red.png')
        self._rec_red_image = gtk.image_new_from_file(path)

        path = os.path.join(constants.GFX_PATH, 'media-insensitive.png')
        self._insensitive_image = gtk.image_new_from_file(path)

        self.set_normal()

    def set_sensitive(self, sensitive):
        if sensitive:
            self.set_image(self._rec_image)
        else:
            self.set_image(self._insensitive_image)
        super(ShutterButton, self).set_sensitive(sensitive)

    def set_normal(self):
        self.set_image(self._rec_image)

    def set_recording(self):
        self.set_image(self._rec_red_image)


class PlayButton(gtk.Button):
    def __init__(self):
        super(PlayButton, self).__init__()
        self.set_relief(gtk.RELIEF_NONE)
        self.set_focus_on_click(False)
        self.modify_bg(gtk.STATE_ACTIVE, COLOR_BLACK)

        path = os.path.join(constants.GFX_PATH, 'media-play.png')
        self._play_image = gtk.image_new_from_file(path)

        path = os.path.join(constants.GFX_PATH, 'media-pause.png')
        self._pause_image = gtk.image_new_from_file(path)

        self.set_play()

    def set_play(self):
        self.set_image(self._play_image)

    def set_pause(self):
        self.set_image(self._pause_image)


class RecordControl():

    def __init__(self, toolbar):
        self._timer_combo = TimerCombo()
        toolbar.insert(self._timer_combo, -1)

        self._duration_combo = DurationCombo()
        toolbar.insert(self._duration_combo, -1)

        preferences_toolbar = gtk.Toolbar()
        combo = gtk.combo_box_new_text()
        self.quality = ToolComboBox(combo=combo, label_text=_('Quality:'))
        self.quality.combo.append_text(_('Low'))
        if hw.get_xo_version() != 1:
            # Disable High quality on XO-1. The system simply isn't beefy
            # enough for recording to work well.
            self.quality.combo.append_text(_('High'))
        self.quality.combo.set_active(0)
        self.quality.show_all()
        preferences_toolbar.insert(self.quality, -1)

        preferences_button = ToolbarButton()
        preferences_button.set_page(preferences_toolbar)
        preferences_button.props.icon_name = 'preferences-system'
        preferences_button.props.label = _('Preferences')
        toolbar.insert(preferences_button, -1)

    def set_mode(self, mode):
        if mode == constants.MODE_PHOTO:
            self.quality.set_sensitive(True)
            self._timer_combo.set_sensitive(True)
            self._duration_combo.set_sensitive(False)
        if mode == constants.MODE_VIDEO:
            self.quality.set_sensitive(True)
            self._timer_combo.set_sensitive(True)
            self._duration_combo.set_sensitive(True)
        if mode == constants.MODE_AUDIO:
            self.quality.set_sensitive(False)
            self._timer_combo.set_sensitive(True)
            self._duration_combo.set_sensitive(True)

    def get_timer(self):
        return self._timer_combo.get_value()

    def get_timer_idx(self):
        return self._timer_combo.get_value_idx()

    def set_timer_idx(self, idx):
        self._timer_combo.set_value_idx(idx)

    def get_duration(self):
        return self._duration_combo.get_value()

    def get_duration_idx(self):
        return self._duration_combo.get_value_idx()

    def set_duration_idx(self, idx):
        return self._duration_combo.set_value_idx(idx)

    def get_quality(self):
        return self.quality.combo.get_active()

    def set_quality(self, idx):
        self.quality.combo.set_active(idx)


class TimerCombo(IconComboBox):
    TIMERS = (0, 5, 10)

    def __init__(self):
        super(TimerCombo, self).__init__('timer')
        
        for i in self.TIMERS:
            if i == 0:
                self.append_item(i, _('Immediate'))
            else:
                string = TimerCombo._seconds_string(i)
                self.append_item(i, string)
        self.combo.set_active(0)

    def get_value(self):
        return TimerCombo.TIMERS[self.combo.get_active()]

    def get_value_idx(self):
        return self.combo.get_active()

    def set_value_idx(self, idx):
        self.combo.set_active(idx)

    @staticmethod
    def _seconds_string(x):
        return ngettext('%s second', '%s seconds', x) % x


class DurationCombo(IconComboBox):
    DURATIONS = (2, 4, 6)

    def __init__(self):
        super(DurationCombo, self).__init__('duration')

        for i in self.DURATIONS:
            string = DurationCombo._minutes_string(i)
            self.append_item(i, string)
        self.combo.set_active(0)

    def get_value(self):
        return 60 * self.DURATIONS[self.combo.get_active()]

    def get_value_idx(self):
        return self.combo.get_active()

    def set_value_idx(self, idx):
        self.combo.set_active(idx)

    @staticmethod
    def _minutes_string(x):
        return ngettext('%s minute', '%s minutes', x) % x
