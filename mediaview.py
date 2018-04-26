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

class XoIcon(Gtk.Image):
    def __init__(self):
        super(type(self), self).__init__()

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
        super(type(self), self).__init__()
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

        textview = Gtk.TextView()
        self._tags_buffer = textview.get_buffer()
        self._tags_buffer.connect('changed', self._tags_changed)
        inner_vbox.pack_start(textview, True, True, 0)

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

    def fit_to_allocation(self, allocation):
        # main viewing area: 50% of each dimension
        scale = 0.5
        w = int(allocation.width * scale)
        h = int(allocation.height * scale)
        self._view_bg.set_size_request(w, h)

        # live area: 1/4 of each dimension
        scale = 0.25
        w = int(allocation.width * scale)
        h = int(allocation.height * scale)
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
        self.emit('primary-allocated', self._view_bg.allocation)
        self.emit('secondary-allocated', self._live_bg.allocation)

    def _tags_changed(self, widget):
        self.emit('tags-changed', widget)


class VideoBox(Gtk.DrawingArea):
    """
    For rendering a GStreamer video sink onto.
    """
    def __init__(self):
        GObject.GObject.__init__(self)
        self.set_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.POINTER_MOTION_HINT_MASK |
                        Gdk.EventMask.EXPOSURE_MASK |
                        Gdk.EventMask.KEY_PRESS_MASK |
                        Gdk.EventMask.KEY_RELEASE_MASK)

        self.set_app_paintable(True)
        self.set_double_buffered(False)

        self._xid = None
        self._sink = None
        self.connect('realize', self._realize_cb)
        self.connect('draw', self._draw_cb)

    def _draw_cb(self, widget, cr):
        if self._sink:
            self._sink.expose()
            return False
        else:
            cr.rectangle(0, 0, widget.get_allocated_width(), widget.get_allocated_height())
            cr.set_source_rgb(0.25, 0.25, 0.25)
            cr.fill()
            return True

    def _realize_cb(self, widget):
        self._xid = self.get_window().get_xid()

    # can be called from GStreamer thread, must not do any GTK+ stuff
    def set_sink(self, sink):
        self._sink = sink
        sink.set_window_handle(self._xid)


class FullscreenButton(Gtk.EventBox):
    def __init__(self):
        super(type(self), self).__init__()

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
        super(type(self), self).__init__()

        path = os.path.join(constants.GFX_PATH, 'corner-info.svg')
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        self.width = pixbuf.get_width()
        self.height = pixbuf.get_height()

        self._image = Gtk.Image.new_from_pixbuf(pixbuf)
        self._image.show()
        self.add(self._image)


class ImageBox(Gtk.EventBox):
    def __init__(self):
        super(type(self), self).__init__()
        self._pixbuf = None
        self._image = Gtk.Image()
        self.add(self._image)

    def show(self):
        self._image.show()
        super(type(self), self).show()

    def hide(self):
        self._image.hide()
        super(type(self), self).hide()

    def clear(self):
        self._image.clear()
        self._pixbuf = None

    def set_pixbuf(self, pixbuf):
        self._pixbuf = pixbuf

    def set_size(self, width, height):
        if self._pixbuf:
            if width == self._pixbuf.get_width() and height == self._pixbuf.get_height():
                pixbuf = self._pixbuf
            else:
                pixbuf = self._pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)

            self._image.set_from_pixbuf(pixbuf)

        self._image.set_size_request(width, height)
        self.set_size_request(width, height)

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
        'full-clicked': (GObject.SignalFlags.RUN_LAST, None, ()),
        'info-clicked': (GObject.SignalFlags.RUN_LAST, None, ()),
        'tags-changed': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_OBJECT,)),
    }

    MODE_LIVE = 0
    MODE_PHOTO = 1
    MODE_VIDEO = 2
    MODE_STILL = 3
    MODE_INFO_PHOTO = 4
    MODE_INFO_VIDEO = 5

    @staticmethod
    def _raise_widget(widget):
        widget.show()
        widget.realize()
        widget.get_window().raise_()

    def __init__(self):
        self._mode = None
        self._allocation = None
        self._hide_controls_timer = None

        super(type(self), self).__init__()
        self.connect('size-allocate', self._size_allocate)
        self.connect('motion-notify-event', self._motion_notify)
        self.set_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.POINTER_MOTION_HINT_MASK)

        self._fixed = Gtk.Fixed()
        self.add(self._fixed)

        self._info_view = InfoView()
        self._info_view.connect('primary-allocated', self._info_view_primary_allocated)
        self._info_view.connect('secondary-allocated', self._info_view_secondary_allocated)
        self._info_view.connect('tags-changed', self._info_view_tags_changed)
        self._fixed.put(self._info_view, 0, 0)

        self._image_box = ImageBox()
        self._image_box.connect('button-release-event', self._image_clicked)
        self._fixed.put(self._image_box, 0, 0)

        self._video = VideoBox()
        self._video.connect('button-release-event', self._video_clicked)
        self._fixed.put(self._video, 0, 0)

        self._video2 = VideoBox()
        self._video2.connect('button-release-event', self._video2_clicked)
        self._fixed.put(self._video2, 0, 0)

        self._info_button = InfoButton()
        self._info_button.connect('button-release-event', self._info_clicked)
        self._fixed.put(self._info_button, 0, 0)

        self._full_button = FullscreenButton()
        self._full_button.connect('button-release-event', self._full_clicked)
        self._fixed.put(self._full_button, 0, 0)

        self._switch_mode(MediaView.MODE_LIVE)

    def _size_allocate(self, widget, allocation):
        # First check if we've already processed an allocation of this size.
        # This is necessary because the operations we do in response to the
        # size allocation cause another size allocation to happen.
        if self._allocation == allocation:
            return

        self._allocation = allocation
        self._place_widgets()

    def _motion_notify(self, widget, event):
        if self._hide_controls_timer:
            # remove timer, it will be reprogrammed right after
            GObject.source_remove(self._hide_controls_timer)
        else:
            self._show_controls()

        self._hide_controls_timer = GObject.timeout_add(2000, self._hide_controls)

    def _show_controls(self):
        if self._mode in (MediaView.MODE_LIVE, MediaView.MODE_VIDEO, MediaView.MODE_PHOTO, MediaView.MODE_STILL):
            self._raise_widget(self._full_button)

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._raise_widget(self._info_button)

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._raise_widget(self._video)

    def _hide_controls(self):
        if self._hide_controls_timer:
            GObject.source_remove(self._hide_controls_timer)
            self._hide_controls_timer = None

        self._full_button.hide()
        if self._mode not in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._info_button.hide()

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._video.hide()

        return False

    def _place_widgets(self):
        allocation = self._allocation

        self._image_box.hide()
        self._video.hide()
        self._video2.hide()
        self._info_view.hide()
        self._info_button.hide()

        border = 5
        full_button_x = allocation.width - border - self._full_button.width
        full_button_y = border
        self._fixed.move(self._full_button, full_button_x, full_button_y)

        info_x = allocation.width - self._info_button.width
        info_y = allocation.height - self._info_button.height
        self._fixed.move(self._info_button, info_x, info_y)

        if self._mode == MediaView.MODE_LIVE:
            self._fixed.move(self._video, 0, 0)
            self._video.set_size_request(allocation.width, allocation.height)
            self._video.show()
            self._image_box.clear()
        elif self._mode == MediaView.MODE_VIDEO:
            self._fixed.move(self._video2, 0, 0)
            self._video2.set_size_request(allocation.width, allocation.height)
            self._video2.show()
            self._image_box.clear()

            vid_h = allocation.height / 6
            vid_w = allocation.width / 6
            self._video.set_size_request(vid_w, vid_h)

            border = 20
            vid_x = border
            vid_y = allocation.height - border - vid_h
            self._fixed.move(self._video, vid_x, vid_y)
        elif self._mode == MediaView.MODE_PHOTO:
            self._fixed.move(self._image_box, 0, 0)
            self._image_box.set_size(allocation.width, allocation.height)
            self._image_box.show()

            vid_h = allocation.height / 6
            vid_w = allocation.width / 6
            self._video.set_size_request(vid_w, vid_h)

            border = 20
            vid_x = border
            vid_y = allocation.height - border - vid_h
            self._fixed.move(self._video, vid_x, vid_y)
        elif self._mode == MediaView.MODE_STILL:
            self._fixed.move(self._image_box, 0, 0)
            self._image_box.set_size(allocation.width, allocation.height)
            self._image_box.show()
        elif self._mode in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._full_button.hide()
            self._info_view.set_size_request(allocation.width, allocation.height)
            self._info_view.fit_to_allocation(allocation)
            self._info_view.show()
            self._raise_widget(self._info_button)

    def _info_view_primary_allocated(self, widget, allocation):
        if self._mode == MediaView.MODE_INFO_PHOTO:
            self._fixed.move(self._image_box, allocation.x, allocation.y)
            self._image_box.set_size(allocation.width, allocation.height)
            self._raise_widget(self._image_box)
        elif self._mode == MediaView.MODE_INFO_VIDEO:
            self._fixed.move(self._video2, allocation.x, allocation.y)
            self._video2.set_size_request(allocation.width, allocation.height)
            self._raise_widget(self._video2)

    def _info_view_secondary_allocated(self, widget, allocation):
        if self._mode in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._fixed.move(self._video, allocation.x, allocation.y)
            self._video.set_size_request(allocation.width, allocation.height)
            self._raise_widget(self._video)

    def _info_view_tags_changed(self, widget, tbuffer):
        self.emit('tags-changed', tbuffer)

    def _switch_mode(self, new_mode):
        if self._mode == MediaView.MODE_LIVE and new_mode == MediaView.MODE_LIVE:
            return
        self._mode = new_mode

        if self._hide_controls_timer:
            GObject.source_remove(self._hide_controls_timer)
            self._hide_controls_timer = None

        if self._allocation:
            self._place_widgets()

    def _image_clicked(self, widget, event):
        self.emit('media-clicked')

    def _video_clicked(self, widget, event):
        if self._mode != MediaView.MODE_LIVE:
            self.emit('pip-clicked')

    def _video2_clicked(self, widget, event):
        self.emit('media-clicked')

    def _full_clicked(self, widget, event):
        self.emit('full-clicked')

    def _info_clicked(self, widget, event):
        self.emit('info-clicked')

    def _show_info(self, mode, author, stroke, fill, date, tags):
        self._info_view.set_author(author, stroke, fill)
        self._info_view.set_date(date)
        self._info_view.set_tags(tags)
        self._switch_mode(mode)

    def show_info_photo(self, author, stroke, fill, date, tags):
        self._show_info(MediaView.MODE_INFO_PHOTO, author, stroke, fill, date, tags)

    def show_info_video(self, author, stroke, fill, date, tags):
        self._show_info(MediaView.MODE_INFO_VIDEO, author, stroke, fill, date, tags)

    def set_fullscreen(self, fullscreen):
        if self._hide_controls_timer:
            GObject.source_remove(self._hide_controls_timer)
            self._hide_controls_timer = None

        if fullscreen:
            self._full_button.set_reduce()
        else:
            self._full_button.set_enlarge()

    def realize_video(self):
        self._video.realize()
        self._video2.realize()

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
        super(type(self), self).show()

    def hide(self):
        self._fixed.hide()
        super(type(self), self).hide()

