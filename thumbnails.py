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

from button import Button
from p5_button import P5Button
from polygon import Polygon
from color import Color


class Thumbnails(P5Button):

	def __init__(self, pc):
		P5Button.__init__(self)
		self.c = pc
		self.c._thumbs = self
		self.noloop()

		self.bw = 155
		self.tw = 107
		self.numButts = 7
		self.buttXOffset = 0
		self.th = None
		self.tpoly = None
		self.tscale = None
		self.dpoly = None

		self.thumbs = []
		self.deletes = []


	def addThumb(self, mimg, mpath):
		if (self.th == None):
			self.th = (self.tw*mimg.get_height())/mimg.get_width()
			self.tscale = float(self.th)/float(mimg.get_height())

			self.buttXOffset = (self._w - (self.bw*self.numButts))/2

			d = 15 + 8
			xs = []
			ys = []
			xs.append(d)
			ys.append(d)
			xs.append(d+self.tw)
			ys.append(d)
			xs.append(d+self.tw)
			ys.append(d+self.th)
			xs.append(d)
			ys.append(self.th)
			self.tpoly = Polygon( xs, ys )

			dxs = []
			dys = []
			dxs.append( (d + self.tw)-25 )
			dys.append( 5 + d + self.th )
			dxs.append( d + self.tw )
			dys.append( 5 + d + self.th )
			dxs.append( d + self.tw )
			dys.append( 5 + d + self.tw + 25 )
			dxs.append( (d + self.tw)-25 )
			dys.append( 5 + d + self.tw + 25 )
			self.dpoly = Polygon( dxs, dys )

		#only keep 5 buttons around
		if ( len(self.thumbs)>=self.numButts):
			byeButt = self.thumbs.pop(0)
			byeButt.removeActionListener(self)
			self._butts.remove( byeButt )
			byeDel = self.deletes.pop(0)
			byeDel.removeActionListener(self)
			self._butts.remove( byeDel )


		#make the new button
		button = Button( self.tpoly, 0, 0 )

		#need to generate thumbnail version here
		thumbImg = cairo.ImageSurface( cairo.FORMAT_ARGB32, self.tw, self._h )
		tctx = cairo.Context(thumbImg)
		tctx.scale( self.tscale, self.tscale )
		tctx.set_source_surface( mimg, 0, 0 )
		tctx.paint()

		button.setImage( thumbImg )
		button.setActionCommand( mpath )
		button.addActionListener( self )
		self._butts.append( button )
		self.thumbs.append( button )

		delButton = Button( self.dpoly, 0, 0 )
		delButton.setActionCommand( "delete-"+mpath )
		delButton.addActionListener( self )
		self._butts.append( delButton )
		self.deletes.append( delButton )

		self.updateThumbs()


	def delThumb(self, path):
		del_index = -1
		for i in range( 0, len(self.thumbs) ):
			butt = self.thumbs[i]
			if (butt.getActionCommand() == path):
				del_index = i

		if (del_index != -1):
			thmb = self.thumbs.pop( del_index )
			delt = self.deletes.pop( del_index )
			self._butts.remove( thmb )
			self._butts.remove( delt )
			self.updateThumbs()

		self.updateThumbs()
		self.c.showVid()
		os.remove( path )


	def updateThumbs(self):
		#update all buttons' positions here
		for i in range ( 0, len(self.thumbs) ):
			self.thumbs[i]._offX = self.buttXOffset+(i*self.bw)
			self.deletes[i]._offX = self.buttXOffset+(i*self.bw)

		#repaint
		self.redraw()


	def draw(self, ctx, w, h):
		P5Button.draw(self, ctx, w, h )
		self.background( ctx, self.c._colThumbTray, w, h )

		#draw buttons
		ctx.set_antialias( cairo.ANTIALIAS_SUBPIXEL )
		for i in range ( 0, len(self.thumbs) ):
			butt = self.thumbs[i]
			ctx.identity_matrix( )
			ctx.translate( butt._offX, 0 )
			ctx.translate( 15, 15 )
			self.c.thumbSvg.render_cairo(ctx)
			ctx.translate( 8, 8 )
			ctx.set_source_surface(butt._img, 0, 0)
			ctx.paint()
			ctx.translate( self.tw-25, 5 + self.th )
			self.c.closeSvg.render_cairo(ctx)

		ctx.set_antialias( cairo.ANTIALIAS_NONE )


	def fireButton(self, actionCommand):
		if (actionCommand.startswith("delete-")):
			self.delThumb( actionCommand[7:] )
		else:
			self.c.showImg( actionCommand )