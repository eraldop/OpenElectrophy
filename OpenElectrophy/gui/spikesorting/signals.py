# -*- coding: utf-8 -*-
"""
Theses widget display individual spike on signals.

"""





from .base import *

from ..viewers import TimeSeeker
from ..guiutil import *

import pyqtgraph as pg

class MyViewBox(pg.ViewBox):
    clicked_at_x = pyqtSignal(float)
    yzoom_in = pyqtSignal()
    yzoom_out = pyqtSignal()
    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
    def mouseClickEvent(self, ev):
        #~ self.clicked_at_x.emit(self.mapSceneToView(ev.pos()).x())
        self.clicked_at_x.emit(self.mapToView(ev.pos()).x())
        
        #~ print ev.screenPos(), ev.pos(), self.mapSceneToView(ev.pos())
        #~ ev.ignore()
        ev.accept()
        
    def mouseDragEvent(self, ev):
        ev.ignore()
    def wheelEvent(self, ev):
        #~ ev.ignore()
        #~ self.wheeled.emit()
        if ev.delta()>0:
            self.yzoom_in.emit()
        else:
            self.yzoom_out.emit()
        ev.accept()

class SignalAndSpike(SpikeSortingWidgetBase):
    
    refresh_on = [  ]
    icon_name = 'analogsignal.png'
    
    sig_name = None
    
    def __init__(self,**kargs):
        super(SignalAndSpike, self).__init__(**kargs)
        
        # TODO : add global UI option for this
        #~ self.auto_zoom_x = True
        #~ self.auto_zoom_x = False
        
        sps = self.spikesorter
        self.timerSeeker = TimeSeeker(show_play = False)
        
        self.sigs = getattr(self.spikesorter, self.sig_name)
        
        self.view = pg.GraphicsView()
        l = pg.GraphicsLayout()
        self.view.setCentralItem(l)
        
        self.plots = [ ]
        self.curves = [ ]
        for i in range(sps.trodness):
            l.nextRow()
            viewBox = MyViewBox()
            plot = l.addPlot(viewBox = viewBox)
            self.plots.append(plot)
            plot.hideButtons()
            curve = plot.plot([np.nan], [np.nan], pen = 'w')
            self.curves.append(curve)
            viewBox.disableAutoRange()
            if i!=sps.trodness-1:
                plot.hideAxis('bottom')
            viewBox.yzoom_in.connect(lambda : self.yzoom(.8))
            viewBox.yzoom_out.connect(lambda : self.yzoom(1.2))
            viewBox.clicked_at_x.connect(self.clicked_at_x)
        
        self.scatters = [ {} for i in range(sps.trodness) ]
        
        self.timerSeeker.fast_time_changed.connect(self.seek)
        

        self.time_by_seg = np.zeros(len(sps.segs), dtype = float)
        for s,seg in enumerate(sps.segs):
            self.time_by_seg[s]= sps.segs[s].analogsignals[0].t_start.magnitude
        

        param_global = [
                        {'name': 'auto_zoom_on_select', 'type': 'bool', 'value': True },
                        {'name': 'zoom_size', 'type': 'float', 'value':  0.05, 'step' : 0.001 },
                        ]        
        self.params = pg.parametertree.Parameter.create( name='Global options', type='group',
                                                    children = param_global)
        self.treeParam = pg.parametertree.ParameterTree(parent  = self)
        self.treeParam.header().hide()
        self.treeParam.setParameters(self.params, showTop=True)
        self.treeParam.setWindowTitle(u'Options for signal viewer')
        self.treeParam.setWindowFlags(Qt.Window)

        
        self.createToolBar()
        self.mainLayout.addWidget(self.toolbar)
        
        self.mainLayout.addWidget(self.view)
        self.mainLayout.addWidget(self.timerSeeker)
        

    
    def createToolBar(self):
        sps = self.spikesorter
        tb = self.toolbar = QToolBar()
        
        #Seg selection
        but = QPushButton('<')
        but.clicked.connect(self.prev_segment)
        tb.addWidget(but)
        self.combo = QComboBox()
        tb.addWidget(self.combo)
        self.combo.addItems([ 'Segment {}'.format(i) for i in range(len(sps.segs)) ])
        but = QPushButton('>')
        but.clicked.connect(self.next_segment)
        tb.addWidget(but)
        self.num_seg = 0
        self.combo.currentIndexChanged.connect(self.refresh)
        tb.addSeparator()
        
        # winsize
        self.xsize = .5
        tb.addWidget(QLabel(u'X size (s)'))
        self.xsize_changer = SpinAndSliderWidget(value = self.xsize, limits = [0.001, 10.],orientation  = Qt.Horizontal)
        self.xsize_changer.sigChanged.connect(self.xsize_changed)
        tb.addWidget(self.xsize_changer)
        tb.addSeparator()
        self.xsize_changer.sigChanged.connect(self.refresh, type = Qt.QueuedConnection)
        
        
        # ylims
        self.ylims = [0.,0.]
        for sig in self.sigs.reshape(-1).tolist():
            self.ylims[0] = min(self.ylims[0], sig.min())
            self.ylims[1] = max(self.ylims[1], sig.max())
        
        tb.addWidget(QLabel(u'Y limits'))
        
        self.ylims_changer = RangeWidget(value = self.ylims, orientation  = Qt.Horizontal)
        self.ylims_changer.sigChanged.connect(self.ylims_changed)
        tb.addWidget(self.ylims_changer)
        tb.addSeparator()
        self.ylims_changer.sigChanged.connect(self.refresh, type = Qt.QueuedConnection)

        
        # add spike
        self.act_add_one_spike = QAction(u'+', self,icon =QIcon(':/list-add.png'), checkable = True)
        tb.addAction(self.act_add_one_spike)
        self.act_enable_spike_selection = QAction(u'+', self,icon =QIcon(':/color-picker.png'), checkable = True)
        tb.addAction(self.act_enable_spike_selection)
        self.act_open_pref = QAction(u'+', self,icon =QIcon(':/preferences-system.png'), checkable = True)
        tb.addAction(self.act_open_pref)
        self.act_open_pref.triggered.connect(self.open_preference)
        
    
    def xsize_changed(self):
        self.xsize = self.xsize_changer.value()
    
    def ylims_changed(self):
        self.ylims = self.ylims_changer.value()
    

    def seek(self, t):
        sps = self.spikesorter
        s =  self.combo.currentIndex()
        if sps.spike_index_array is not None:
            sl = sps.seg_spike_slices[s]
            sel = sps.selected_spikes[sl]
            pos = sps.spike_index_array[s]
        
        self.time_by_seg[s] = t
        sr = sps.sig_sampling_rate.rescale('Hz').magnitude
        
        t1,t2 = t-self.xsize/3. , t+self.xsize*2/3.
        
        # Chunk of signal
        ind_start = int(np.rint((t1-sps.seg_t_start[s].rescale('s').magnitude)*sr))
        ind_stop = int(np.rint((t2-sps.seg_t_start[s].rescale('s').magnitude)*sr))
        if ind_start<0:
            ind_start=0
            t1 = float(sps.seg_t_start[s].magnitude)
        if ind_stop>self.sigs[0,s].size:
            ind_stop=self.sigs[0,s].size
            t2 = float(sps.seg_t_stop[s].magnitude)
        t_vect = np.arange(0,ind_stop-ind_start, dtype='f')/sr+t1
        for i in range(sps.trodness):
            if t_vect.size:
                self.curves[i].setData(t_vect, self.sigs[i,s][ind_start:ind_stop])
            else:
                self.curves[i].setData( [np.nan], [np.nan])

        #Spike
        if sps.spike_index_array is not None:
            inwindow = (pos>ind_start) & (pos<ind_stop)
            
            # Selected spikes
            ind = pos[sel & inwindow]
            #~ print ind, ind_start, sel.dtype, sel.shape
            for i, scatter in enumerate(self.scatters):
                color = QColor( 'magenta')
                color.setAlpha(160)
                if 'sel' not in scatter:
                    scatter['sel'] = pg.ScatterPlotItem(x=t_vect[ind-ind_start], y=self.sigs[i,s][ind], 
                                                                        pen=None, brush=color, size=15, pxMode = True)
                    self.plots[i].addItem(scatter['sel'])
                else :
                    scatter['sel'].setData(t_vect[ind-ind_start], self.sigs[i,s][ind])
            
            # remove old ones
            for i, scatter in enumerate(self.scatters):
                for c in scatter.keys():
                    if c not in sps.cluster_names:
                        self.plots[i].removeItem(scatter[c])
                        scatter.pop(c)
                        
                        
            # Spikes by cluster
            vpos = pos[inwindow]
            for c in sps.cluster_names.keys():
                clusters = sps.spike_clusters[sl][inwindow]
                ind = vpos[clusters == c]
                r,g,b = sps.cluster_colors[c]
                color = QColor( r*255,g*255,b*255  )
                for i, scatter in enumerate(self.scatters):
                    if c in scatter:
                        if sps.active_cluster[c]:
                            scatter[c].setData(t_vect[ind-ind_start], self.sigs[i,s][ind])
                        else:
                            scatter[c].setData([], [])
                    else:
                        if sps.active_cluster[c]:
                            scatter[c] = pg.ScatterPlotItem(x=t_vect[ind-ind_start], y=self.sigs[i,s][ind], 
                                                                            pen=None, brush=color, size=10, pxMode = True)
                            self.plots[i].addItem(scatter[c])
                            scatter[c].sigClicked.connect(self.item_clicked)
                        #~ scatter[c].vb = self.plots[i].vb

        for plot in self.plots:
            #~ print t1, t2
            plot.setXRange( t1, t2, padding = 0.0)
            plot.setYRange( *self.ylims , padding = 0.0)
    


        
    
    def refresh(self):
        sps = self.spikesorter
        s =  self.combo.currentIndex()
        
        t_start = sps.seg_t_start[s]
        t_stop = sps.seg_t_stop[s]
        self.timerSeeker.set_start_stop(t_start.magnitude-.05,t_stop.magnitude+.05, seek = False)
        self.timerSeeker.seek(self.time_by_seg[s])
        
        for c in sps.cluster_names.keys():
            r,g,b = sps.cluster_colors[c]
            color = QColor( r*255,g*255,b*255  )
            for i, scatter in enumerate(self.scatters):
                if c in scatter:
                    scatter[c].setBrush(color)
                    
    def on_spike_selection_changed(self):
        # selected spikes are done like a standard spiketrains with magenta color
        sps = self.spikesorter
        
        
        
        if sps.spike_index_array is not None:
            if self.params.param('auto_zoom_on_select').value() and np.sum( sps.selected_spikes)==1:
                num, = np.where(sps.selected_spikes)
                s = sps.get_seg_from_num(num)
                s2 =  self.combo.currentIndex()
                if s !=s2:
                    self.combo.setCurrentIndex(s)
                sl = sps.seg_spike_slices[s]
                sel = sps.selected_spikes[sl]
                pos = sps.spike_index_array[s]

                self.xsize = self.params.param('zoom_size').value()
                t = (pos[sel]/sps.sig_sampling_rate+sps.seg_t_start[s]).simplified.magnitude
                self.seek(t)
                self.refresh()
    
    def prev_segment(self):
        self.change_segment(self.num_seg - 1)
        
    def next_segment(self):
        self.change_segment(self.num_seg + 1)

    def change_segment(self, n):
        sps = self.spikesorter
        self.num_seg  =  n
        if self.num_seg<0:
            self.num_seg = len(sps.segs)-1
        if self.num_seg==len(sps.segs):
            self.num_seg = 0
        self.combo.setCurrentIndex(self.num_seg)
    
    def yzoom(self, factor):
        if self.ylims[0]<0 and self.ylims[1]>0:
            self.ylims[0] = factor*self.ylims[0]
            self.ylims[1] = factor*self.ylims[1]
        else:
            m = np.mean(self.ylims)
            d = np.diff(self.ylims)[0]
            self.ylims[0] = m - (d/2)*factor
            self.ylims[1] = m + (d/2)*factor
        #~ self.ylims_changer.set_ylims(self.ylims)
        self.ylims_changer.setValue(self.ylims)
        self.refresh()
    
    def clicked_at_x(self, x):
    #~ def add_one_spike(self, ev):
        #~ print ev
        s =  self.combo.currentIndex()
        sps = self.spikesorter
        if self.act_add_one_spike.isChecked():
            #~ plot = self.sender()
            #~ x = plot.vb.mapSceneToView(ev.pos()).x()
            
            c = 0 #TODO
            #~ print 'add_spike at ', x, 'seg ',s, 'cluster', c
            sps.add_one_spike(s, x, c = c)
            self.spike_clusters_changed.emit()
            self.refresh()
        
        #~ elif self.act_enable_spike_selection.isChecked():
            #~ print 'select spiek at', x, s
            
            #~ sr = sps.sig_sampling_rate.rescale('Hz').magnitude
            #~ ind_clicked = int(np.rint((x-sps.seg_t_start[s].rescale('s').magnitude)*sr))            
            #~ pos = sps.spike_index_array[s]
            #~ nearest = np.argmin(abs(pos-ind_clicked))
            #~ print ind_clicked, nearest
    
    def item_clicked(self, plot, points):
        if self.act_enable_spike_selection.isChecked()and len(points)==1:
            s =  self.combo.currentIndex()
            sps = self.spikesorter
            
            x = points[0].pos().x()
            sr = sps.sig_sampling_rate.rescale('Hz').magnitude
            ind_clicked = int(np.rint((x-sps.seg_t_start[s].rescale('s').magnitude)*sr))            
            pos = sps.spike_index_array[s]
            
            sps.selected_spikes[:] = False
            sl = sps.seg_spike_slices[s]
            sps.selected_spikes[sl] = ind_clicked == pos
            self.spike_selection_changed.emit()
            self.refresh()
    
    def open_preference(self):
        if not self.treeParam.isVisible():
            self.treeParam.show()
        else:
            self.treeParam.hide()
            

class FullBandSignal(SignalAndSpike):
    name = 'Full band signal'
    refresh_on = [ 'full_band_sigs', 'spike_index_array',  'spike_clusters', ]
    sig_name = 'full_band_sigs'
    

class FilteredBandSignal(SignalAndSpike):
    name = 'Filtered band signal'
    refresh_on = [ 'filtered_sigs', 'spike_index_array',  'spike_clusters', ]
    sig_name = 'filtered_sigs'








class SignalStatistics(SpikeSortingWidgetBase):
    name = 'Signal statistics'
    refresh_on = [ 'filtered_sigs', ]
    icon_name = 'plot-waveform.png'
    
    
    def __init__(self,**kargs):
        super(SignalStatistics, self).__init__(**kargs)
        self.canvas = SimpleCanvasAndTool( )
        #~ self.canvas = SimpleCanvas( )
        self.mainLayout.addWidget(self.canvas)
        self.fig = self.canvas.fig
        
        sps = self.spikesorter
        
        self.axs = [ ]
        ax = None
        for j in range(sps.trodness):
            ax = self.fig.add_subplot(sps.trodness,1,j+1, sharex = ax, sharey = ax)
            self.axs.append(ax)

    
    def refresh(self):
        
        sps = self.spikesorter
        for ax in self.axs:
            ax.clear()
        
        if sps.filtered_sigs is None: return
        
        # stats
        min, max = np.inf, -np.inf
        all_mean = np.zeros( ( len(sps.segs), sps.trodness) ,dtype = 'f')
        all_std = np.zeros( ( len(sps.segs), sps.trodness) ,dtype = 'f')
        all_median = np.zeros( ( len(sps.segs), sps.trodness) ,dtype = 'f')
        for i in range(len(sps.segs)):
            for j in range(sps.trodness):
                mi, ma = sps.filtered_sigs[j,i].min() , sps.filtered_sigs[j,i].max()
                if mi < min : min=mi
                if ma > max: max=ma
                all_mean[i,j] = np.mean(sps.filtered_sigs[j,i]) 
                all_std[i,j] =  np.std(sps.filtered_sigs[j,i])
                all_median[i,j] =np.median(sps.filtered_sigs[j,i])
        
        # histo
        nbins = 1000.
        bins = np.arange(min,max, (max-min)/nbins)
        for j in range(sps.trodness):
            ax = self.axs[j]
            ax.axhline( np.mean(all_mean[:,j]) , color = 'r')
            ax.axhline( np.mean(all_median[:,j]) , color = 'g')
            ax.axhline( np.mean(all_mean[:,j]) + np.sqrt(np.mean(all_std[:,j]**2)) , color = 'r' , linestyle = '--')
            ax.axhline( np.mean(all_mean[:,j]) - np.sqrt(np.mean(all_std[:,j]**2)) , color = 'r' , linestyle = '--')
            
            counts = np.zeros( (bins.shape[0]-1), dtype = 'i')
            for i in range(len(sps.segs)):
                count, _ = np.histogram(sps.filtered_sigs[j,i] , bins = bins)
                counts += count
            ax.plot( counts, bins[:-1])



