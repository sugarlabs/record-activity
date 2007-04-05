import os
import gtk
from gtk import gdk
import gobject
import math
import cairo
import pygtk
pygtk.require('2.0')
import rsvg
import pango

from polygon import Polygon
from color import Color
from p5_button import P5Button
from controller import Controller
from button import Button

class Image_Display(P5Button):

	def __init__(self, pc):
		P5Button.__init__(self)
		self.c = pc
		self.c._id = self
		self.noloop()
		self.ac_shutter = "shutter"

		self.firstTime = True


	def draw(self, ctx, w, h):
		P5Button.draw(self, ctx, w, h )
		self.background( ctx, self.c._colBlack, self._w, self._h )

		#draw the background polaroid
		polMargin = 15
		ctx.translate( (self._w/2)-(self.c.polSvg.props.width/2), (self._h/2)-(self.c.polSvg.props.height/2) )
		ctx.set_antialias( cairo.ANTIALIAS_SUBPIXEL )
		self.c.polSvg.render_cairo(ctx)
		ctx.set_antialias( cairo.ANTIALIAS_NONE )
		ctx.identity_matrix( )

		ctx.set_antialias( cairo.ANTIALIAS_SUBPIXEL )
		sx = (self._w/2)-(self.c.camSvg.props.width/2)
		sy = ((self._h/2)-(self.c.polSvg.props.height/2)) + polMargin + 480 + polMargin
		ctx.translate( sx, sy)
		if (not self.isImg()):
			self.c.camSvg.render_cairo(ctx)
		else:
			self.c.camInvSvg.render_cairo(ctx)
		ctx.set_antialias( cairo.ANTIALIAS_NONE )
		ctx.identity_matrix( )

		if (self.firstTime):
			self.firstTime = False
			self.makeShutterButton( sx, sy )

		if (self.isImg()):
			self.drawImage( ctx )



	def makeShutterButton( self, sx, sy ):
		xs = []
		ys = []
		xs.append( 0 )
		ys.append( 0 )
		xs.append( self.c.camSvg.props.width )
		ys.append( 0 )
		xs.append( self.c.camSvg.props.width )
		ys.append( self.c.camSvg.props.height )
		xs.append( 0 )
		ys.append( self.c.camSvg.props.height )
		poly = Polygon( xs, ys )
		button = Button( poly, sx, sy )
		button.setActionCommand(self.ac_shutter)
		button.addActionListener( self )
		self._butts.append( button )


	def drawImage( self, ctx ):
		ix = ((self._w/2)-(self.c.polSvg.props.width/2)) + 15 + 1
		iy = ((self._h/2)-(self.c.polSvg.props.height/2)) + 15
		ctx.translate( ix, iy )
		ctx.set_source_surface( self.c._img, 0, 0 )
		ctx.paint( )
		ctx.identity_matrix( )


	def isImg( self ):
		return (not self.c._img == None)


	def fireButton(self, actionCommand):
		if (actionCommand == self.ac_shutter):
			if (self.c._img == None):
				self.c.takeSnapshot( )
			else:
				#actually, you never get called since gplay is in your head
				#so we handle your click over there
				#todo: how to pass clicks down
				self.c.showVid( )

