import os
import gtk
from gtk import gdk
import gobject
import math
import cairo
import rsvg

from button import Button
from p5_button import P5Button
from polygon import Polygon
from color import Color


class MenuBar(P5Button):

	def __init__(self, pc):
		P5Button.__init__(self)
		self.c = pc
		self.c._mb = self
		self.noloop()

		#make our polygon... todo: get the ht from the superclass
		ht = 75
		xs = []
		ys = []
		xs.append(0)
		ys.append(0)
		xs.append(ht)
		ys.append(0)
		xs.append(ht)
		ys.append(ht)
		xs.append(0)
		ys.append(ht)
		self.bpoly = Polygon( xs, ys )

		#and add the mode buttons
		self.photoButton = Button( self.bpoly, 15, 0 )
		self.photoButton.setActionCommand("photo")
		self.photoButton.addActionListener( self )
		self.photoXOff = (75-self.c.menubarPhoto.props.width) / 2
		self.photoYOff = (75-self.c.menubarPhoto.props.height) / 2
		self._butts.append( self.photoButton )

		self.videoButton = Button( self.bpoly, ht+30, 0 )
		self.videoButton.setActionCommand("video")
		self.videoButton.addActionListener( self )
		self.videoXOff = (75-self.c.menubarVideo.props.width) / 2
		self.videoYOff = (75-self.c.menubarVideo.props.height) / 2
		self._butts.append( self.videoButton )

	def draw(self, ctx, w, h):
		P5Button.draw(self, ctx, w, h )
		self.background( ctx, self.c._colMenuBar, w, h )

		#draw buttons (todo: move the painting of svg into the button code)
		ctx.set_antialias( cairo.ANTIALIAS_SUBPIXEL )
		for i in range ( 0, len(self._butts) ):
			butt = self._butts[i]
			ctx.identity_matrix( )
			ctx.translate( butt._offX, 0 )
			if (i==0):
				if (self.c.isPhotoMode()):
					self.fillShape( ctx, self.bpoly, self.c._colWhite )
				ctx.translate( self.photoXOff-1, self.photoYOff )
				self.c.menubarPhoto.render_cairo( ctx )
			if (i==1):
				if (self.c.isVideoMode()):
					self.fillShape( ctx, self.bpoly, self.c._colWhite )
				ctx.translate( self.videoXOff-1, self.videoYOff )
				self.c.menubarVideo.render_cairo( ctx )

		ctx.set_antialias( cairo.ANTIALIAS_NONE )

	def fireButton(self, actionCommand):
		if (self.c.UPDATING):
			return

		if (actionCommand.startswith("video")):
			self.c.doVideoMode()
		elif (actionCommand.startswith("photo")):
			self.c.doPhotoMode()
