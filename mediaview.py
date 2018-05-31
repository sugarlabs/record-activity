# Copyright (C) 2011, One Laptop per Child (3bc80c7)

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
import logging
from gettext import gettext as _

from gi.repository import GObject, Gdk, GdkX11, Gtk, GdkPixbuf, GstVideo

import constants
import utils

logger = logging.getLogger('mediaview')

COLOR_BLACK = Gdk.color_parse('#000000')
COLOR_WHITE = Gdk.color_parse('#ffffff')
COLOR_GREY = Gdk.color_parse('#808080')


def fit_image(width_image, height_image, width_screen, height_screen):

    ratio_image = float(width_image) / float(height_image)
    ratio_screen = float(width_screen) / float(height_screen)

    if ratio_screen > ratio_image:
        width_scaled = width_image * height_screen / height_image
        height_scaled = height_screen
    else:
        width_scaled = width_screen
        height_scaled = height_image * width_screen / width_image

    return (width_scaled, height_scaled)


class XoIcon(Gtk.Image):
    def __init__(self):
        Gtk.Image.__init__(self)

    def set_colors(self, stroke, fill):
        pixbuf = utils.load_colored_svg('xo-guy.svg', stroke, fill)
        self.set_from_pixbuf(pixbuf)


class InfoView(Gtk.EventBox):
    """
    A metadata view/edit widget, that presents a primary view area in the top
    right and a secondary view area in the bottom left.
    """
    __gsignals__ = {
        'primary-allocated': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        'secondary-allocated': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        'tags-changed': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_OBJECT,)),
    }

    def __init__(self):
        Gtk.EventBox.__init__(self)
        self.modify_bg(Gtk.StateType.NORMAL, COLOR_GREY)

        self.connect('size-allocate', self._size_allocate)

        self._outer_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                   spacing=7)
        self.add(self._outer_vbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._outer_vbox.pack_start(hbox, True, True, 0)

        inner_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                             spacing=5)
        hbox.pack_start(inner_vbox, True, True, 6)

        author_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        inner_vbox.pack_start(author_hbox, False, True, 0)

        label = Gtk.Label()
        label.set_markup('<b>' + _('Author:') + '</b>')
        author_hbox.pack_start(label, False, True, 0)

        self._xo_icon = XoIcon()
        author_hbox.pack_start(self._xo_icon, False, True, 0)

        self._author_label = Gtk.Label()
        author_hbox.pack_start(self._author_label, False, True, 0)

        self._date_label = Gtk.Label()
        self._date_label.set_line_wrap(True)
        alignment = Gtk.Alignment.new(0.0, 0.5, 0.0, 0.0)
        alignment.add(self._date_label)
        inner_vbox.pack_start(alignment, False, True, 0)

        label = Gtk.Label()
        label.set_markup('<b>' + _('Tags:') + '</b>')
        alignment = Gtk.Alignment.new(0.0, 0.5, 0.0, 0.0)
        alignment.add(label)
        inner_vbox.pack_start(alignment, False, True, 0)

        self.textview = Gtk.TextView()
        self._tags_buffer = self.textview.get_buffer()
        self._tags_buffer.connect('changed', self._tags_changed)
        inner_vbox.pack_start(self.textview, True, True, 0)

        # the main viewing widget will be painted exactly on top of this one
        alignment = Gtk.Alignment.new(1.0, 0.0, 0.0, 0.0)
        self._view_bg = Gtk.EventBox()
        self._view_bg.modify_bg(Gtk.StateType.NORMAL, COLOR_BLACK)
        alignment.add(self._view_bg)
        hbox.pack_start(alignment, False, True, 0)

        # the secondary viewing widget will be painted exactly on top of this one
        alignment = Gtk.Alignment.new(0.0, 1.0, 0.0, 0.0)
        self._live_bg = Gtk.EventBox()
        self._live_bg.modify_bg(Gtk.StateType.NORMAL, COLOR_BLACK)
        alignment.add(self._live_bg)
        self._outer_vbox.pack_start(alignment, False, True, 0)

    def fit_to_allocation(self, width, height):
        a = float(Gdk.Screen.width()) / float(Gdk.Screen.height())
        if a < 1.4:
            # main viewing area: 50% of each dimension for 4:3 displays
            scale = 0.5
        else:
            # main viewing area: 75% of each dimension for 16:9 displays
            scale = 0.75
        w = int(width * scale)
        h = int(height * scale)
        self._view_bg.set_size_request(w, h)

        # live area: 1/4 of each dimension
        scale = 0.25
        w = int(width * scale)
        h = int(height * scale)
        self._live_bg.set_size_request(w, h)

    def show(self):
        self.show_all()

    def set_author(self, name, stroke, fill):
        self._xo_icon.set_colors(stroke, fill)
        self._author_label.set_text(name)

    def set_date(self, date):
        self._date_label.set_markup('<b>' + _('Date:') + '</b> ' + date)

    def set_tags(self, tags):
        self._tags_buffer.set_text(tags)

    def _size_allocate(self, widget, allocation):
        self.emit('primary-allocated', self._view_bg.get_allocation())
        self.emit('secondary-allocated', self._live_bg.get_allocation())

    def _tags_changed(self, widget):
        self.emit('tags-changed', widget)


class VideoBox(Gtk.DrawingArea):
    """
    For rendering a GStreamer video sink onto.
    """
    def __init__(self, name):
        self._name = name
        Gtk.DrawingArea.__init__(self)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.POINTER_MOTION_HINT_MASK)

        self._xid = None
        self._sink = None
        self.connect('realize', self._realize_cb)
        self.connect('draw', self._draw_cb)

    def _draw_cb(self, widget, cr):
        if self._sink:
            # logger.debug('%s _draw_cb with _sink' % self._name)
            self._sink.expose()
        else:
            # logger.debug('%s _draw_cb without _sink' % self._name)
            cr.rectangle(0, 0,
                widget.get_allocated_width(), widget.get_allocated_height())
            cr.set_source_rgb(0.0, 0.0, 0.0)
            cr.fill()
        return False

    def _realize_cb(self, widget):
        # logger.debug('%s _realize_cb' % self._name)
        self._xid = self.get_window().get_xid()

    def set_sink(self, sink):
        if sink is not None:
            # logger.debug('%s set_sink on' % self._name)
            if hasattr(sink.props, "handle_events"):
                sink.props.handle_events = False
            sink.set_window_handle(self._xid)
        else:
            # logger.debug('%s set_sink off' % self._name)
            pass
        self._sink = sink


class FullscreenButton(Gtk.EventBox):
    def __init__(self):
        Gtk.EventBox.__init__(self)

        path = os.path.join(constants.GFX_PATH, 'max-reduce.svg')
        self._enlarge_pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        self.width = self._enlarge_pixbuf.get_width()
        self.height = self._enlarge_pixbuf.get_height()

        path = os.path.join(constants.GFX_PATH, 'max-enlarge.svg')
        self._reduce_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, self.width, self.height)

        self._image = Gtk.Image()
        self.set_enlarge()
        self._image.show()
        self.add(self._image)

    def set_enlarge(self):
        self._image.set_from_pixbuf(self._enlarge_pixbuf)

    def set_reduce(self):
        self._image.set_from_pixbuf(self._reduce_pixbuf)


class InfoButton(Gtk.EventBox):
    def __init__(self):
        Gtk.EventBox.__init__(self)

        path = os.path.join(constants.GFX_PATH, 'corner-info.svg')
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        self.width = pixbuf.get_width()
        self.height = pixbuf.get_height()

        self._image = Gtk.Image.new_from_pixbuf(pixbuf)
        self._image.show()
        self.add(self._image)


class ImageBox(Gtk.EventBox):
    def __init__(self):
        Gtk.EventBox.__init__(self)
        self._pixbuf = None
        self._image = Gtk.Image()
        self.width = self.height = None  # after scaling
        self.add(self._image)

    def show(self):
        self._image.show()
        Gtk.EventBox.show(self)

    def hide(self):
        self._image.hide()
        Gtk.EventBox.hide(self)

    def clear(self):
        self._image.clear()
        self._pixbuf = None

    def set_pixbuf(self, pixbuf):
        self._pixbuf = pixbuf

    def set_size(self, width, height):
        if not self._pixbuf:
            return

        (self.width, self.height) = fit_image(self._pixbuf.get_width(),
                                              self._pixbuf.get_height(),
                                              width, height)

        if self.height == 0:
            self.height = 1

        pixbuf = self._pixbuf.scale_simple(self.width, self.height,
                                           GdkPixbuf.InterpType.BILINEAR)
        self._image.set_from_pixbuf(pixbuf)
        self._image.set_size_request(width, height)

class MediaView(Gtk.EventBox):
    """
    A widget to show the main record UI with a video feed, but with some
    extra features: possibility to show images, information UI about media,
    etc.

    It is made complicated because under the UI design, some widgets need
    to be placed on top of others. In GTK+, this is not trivial. We achieve
    this here by relying on the fact that GDK+ specifically allows us to
    raise specific windows, and by packing all our Z-order-sensitive widgets
    into EventBoxes (which have their own windows).
    """
    __gtype_name__ = "MediaView"
    __gsignals__ = {
        'media-clicked': (GObject.SignalFlags.RUN_LAST, None, ()),
        'pip-clicked': (GObject.SignalFlags.RUN_LAST, None, ()),
        'fullscreen-clicked': (GObject.SignalFlags.RUN_LAST, None, ()),
        'info-clicked': (GObject.SignalFlags.RUN_LAST, None, ()),
        'tags-changed': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_OBJECT,)),
    }

    MODE_LIVE = 0
    MODE_PHOTO = 1
    MODE_VIDEO = 2
    MODE_STILL = 3
    MODE_INFO_PHOTO = 4
    MODE_INFO_VIDEO = 5

    def __init__(self):
        self._mode = None
        self._controls_shown = False
        self._show_controls_timer = None
        self._hide_controls_timer = None

        Gtk.EventBox.__init__(self)
        self.connect('size-allocate', self._size_allocate)
        self.connect('motion-notify-event', self._motion_notify)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.POINTER_MOTION_HINT_MASK)

        self._fixed = Gtk.Fixed()
        self.add(self._fixed)

        self.info_view = InfoView()
        self.info_view.connect('primary-allocated', self._info_view_primary_allocated)
        self.info_view.connect('secondary-allocated', self._info_view_secondary_allocated)
        self.info_view.connect('tags-changed', self._info_view_tags_changed)
        self._fixed.put(self.info_view, 0, 0)

        self._image_box = ImageBox()
        self._image_box.connect('button-release-event', self._image_clicked)
        self._fixed.put(self._image_box, 0, 0)

        self._video = VideoBox('one')
        self._video.connect('button-release-event', self._video_clicked)
        self._fixed.put(self._video, 0, 0)

        self._video2 = VideoBox('two')
        self._video2.connect('button-release-event', self._video2_clicked)
        self._fixed.put(self._video2, 0, 0)

        self._info_button = InfoButton()
        self._info_button.connect('button-release-event', self._info_clicked)
        self._fixed.put(self._info_button, 0, 0)

        self._fullscreen_button = FullscreenButton()
        self._fullscreen_button.connect('button-release-event',
                                        self._fullscreen_clicked)
        self._fixed.put(self._fullscreen_button, 0, 0)

        self._switch_mode(MediaView.MODE_LIVE)

    def _size_allocate(self, widget, allocation):
        # logger.debug('MediaView._size_allocate %r x %r' %
        #     (allocation.width, allocation.height))

        def defer():
            self._place_widgets()
            return False

        GObject.timeout_add(20, defer)  # prevent a delayed image symptom
        self.disconnect_by_func(self._size_allocate)

    def _motion_notify(self, widget, event):
        if not self._controls_shown:
            if self._show_controls_timer:
                GObject.source_remove(self._show_controls_timer)
            self._show_controls_timer = GObject.timeout_add(10,
                                                            self._show_controls)

        if self._hide_controls_timer:
            GObject.source_remove(self._hide_controls_timer)
        self._hide_controls_timer = GObject.timeout_add(2000,
                                                        self._hide_controls)

    def _show_controls(self):
        logger.debug('_show_controls')
        if self._mode in (MediaView.MODE_LIVE, MediaView.MODE_VIDEO,
                          MediaView.MODE_PHOTO, MediaView.MODE_STILL):
            self._fullscreen_button.show()

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._info_button.show()

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._video.show()

        self._show_controls_timer = None
        self._controls_shown = True
        return False

    def _hide_controls(self):
        logger.debug('_hide_controls')
        self._fullscreen_button.hide()
        if self._mode not in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._info_button.hide()

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._video.hide()

        self._hide_controls_timer = None
        self._controls_shown = False
        return False

    def _place_widgets(self):
        logger.debug('_place_widgets')

        w = self.get_allocated_width()
        h = self.get_allocated_height()

        self._image_box.hide()
        self._video.hide()
        self._video2.hide()
        self.info_view.hide()
        self._info_button.hide()

        border = 5
        x = w - border - self._fullscreen_button.width
        y = border
        self._fixed.move(self._fullscreen_button, x, y)

        info_x = w - self._info_button.width
        info_y = h - self._info_button.height
        self._fixed.move(self._info_button, info_x, info_y)

        if self._mode == MediaView.MODE_LIVE:
            self._fixed.move(self._video, 0, 0)
            self._video.set_size_request(w, h)
            self._video.queue_resize()
            self._video.show()
            self._image_box.clear()
        elif self._mode == MediaView.MODE_VIDEO:
            self._fixed.move(self._video2, 0, 0)
            self._video2.set_size_request(w, h)
            self._video2.queue_resize()
            self._video2.show()
            self._image_box.clear()

            vid_h = h / 6
            vid_w = w / 6
            self._video.set_size_request(vid_w, vid_h)
            self._video.queue_resize()

            border = 20
            vid_x = border
            vid_y = h - border - vid_h
            self._fixed.move(self._video, vid_x, vid_y)
        elif self._mode == MediaView.MODE_PHOTO:
            self._fixed.move(self._image_box, 0, 0)
            self._image_box.set_size(w, h)
            self._image_box.show()

            vid_h = self._image_box.height / 6
            vid_w = self._image_box.width / 6
            self._video.set_size_request(vid_w, vid_h)
            self._video.queue_resize()

            border = 20
            vid_x = border
            vid_y = h - border - vid_h
            self._fixed.move(self._video, vid_x, vid_y)
        elif self._mode == MediaView.MODE_STILL:
            self._fixed.move(self._image_box, 0, 0)
            self._image_box.set_size(w, h)
            self._image_box.show()
        elif self._mode in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._fullscreen_button.hide()
            self.info_view.set_size_request(w, h)
            self.info_view.fit_to_allocation(w, h)
            self.info_view.show()
            self._info_button.show()

    def _info_view_primary_allocated(self, widget, allocation):
        if self._mode == MediaView.MODE_INFO_PHOTO:
            self._fixed.move(self._image_box, allocation.x, allocation.y)
            self._image_box.set_size(allocation.width, allocation.height)
            self._image_box.show()
        elif self._mode == MediaView.MODE_INFO_VIDEO:
            self._fixed.move(self._video2, allocation.x, allocation.y)
            self._video2.set_size_request(allocation.width, allocation.height)
            self._video2.show()

    def _info_view_secondary_allocated(self, widget, allocation):
        if self._mode in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._fixed.move(self._video, allocation.x, allocation.y)
            self._video.set_size_request(allocation.width, allocation.height)
            self._video.show()

    def _info_view_tags_changed(self, widget, tbuffer):
        self.emit('tags-changed', tbuffer)

    def _switch_mode(self, new_mode):
        if self._mode == MediaView.MODE_LIVE and new_mode == MediaView.MODE_LIVE:
            return
        self._mode = new_mode

        if self._controls_shown:
            if self._hide_controls_timer:
                GObject.source_remove(self._hide_controls_timer)
            self._hide_controls()

        self._place_widgets()

    def _image_clicked(self, widget, event):
        self.emit('media-clicked')

    def _video_clicked(self, widget, event):
        if self._mode != MediaView.MODE_LIVE:
            self.emit('pip-clicked')

    def _video2_clicked(self, widget, event):
        self.emit('media-clicked')

    def _fullscreen_clicked(self, widget, event):
        self.emit('fullscreen-clicked')

    def _info_clicked(self, widget, event):
        self.emit('info-clicked')

    def _show_info(self, mode, author, stroke, fill, date, tags):
        self.info_view.set_author(author, stroke, fill)
        self.info_view.set_date(date)
        self.info_view.set_tags(tags)
        self._switch_mode(mode)

    def show_info_photo(self, author, stroke, fill, date, tags):
        self._show_info(MediaView.MODE_INFO_PHOTO, author, stroke, fill, date, tags)

    def show_info_video(self, author, stroke, fill, date, tags):
        self._show_info(MediaView.MODE_INFO_VIDEO, author, stroke, fill, date, tags)

    def set_fullscreen(self, fullscreen):
        if self._controls_shown:
            if self._hide_controls_timer:
                GObject.source_remove(self._hide_controls_timer)
            self._hide_controls()

        if fullscreen:
            self._fullscreen_button.set_reduce()
        else:
            self._fullscreen_button.set_enlarge()

        self.connect('size-allocate', self._size_allocate)
        self._video.set_size_request(-1, -1)
        self._video2.set_size_request(-1, -1)
        self._image_box.set_size(1, 1)
        Gtk.EventBox.queue_resize(self)

    # can be called from GStreamer thread, must not do any GTK+ stuff
    def set_video_sink(self, sink):
        self._video.set_sink(sink)

    # can be called from GStreamer thread, must not do any GTK+ stuff
    def set_video2_sink(self, sink):
        self._video2.set_sink(sink)

    def show_still(self, pixbuf):
        # don't modify the original...
        pixbuf = pixbuf.copy()
        pixbuf.saturate_and_pixelate(pixbuf, 0, 0)
        self._image_box.set_pixbuf(pixbuf)
        self._switch_mode(MediaView.MODE_STILL)

    def show_photo(self, path):
        if path:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            self._image_box.set_pixbuf(pixbuf)
        self._switch_mode(MediaView.MODE_PHOTO)

    def show_video(self):
        self._switch_mode(MediaView.MODE_VIDEO)

    def show_live(self):
        self._switch_mode(MediaView.MODE_LIVE)

    def show(self):
        self._fixed.show()
        Gtk.EventBox.show(self)

    def hide(self):
        self._fixed.hide()
        Gtk.EventBox.hide(self)

