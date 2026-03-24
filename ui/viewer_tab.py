import logging
import math
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QGridLayout, QScrollArea, QPushButton, QSplitter
from PySide6.QtCore import Qt, Signal
from ui.stream_tile import StreamTile
from core.stream_worker import StreamWorker

class ViewerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel: Tree View
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_deselect_all = QPushButton("Deselect All")
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        left_layout.addLayout(btn_layout)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Cameras / Channels")
        left_layout.addWidget(self.tree)
        self.splitter.addWidget(left_panel)
        
        # Right Panel: Grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(5)
        self.scroll_area.setWidget(self.grid_container)
        self.splitter.addWidget(self.scroll_area)
        
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter)
        
        self.tree.itemChanged.connect(self.on_item_changed)
        
        self.active_streams = {} # { (ip, ch_num): (worker, tile) }
        self.devices_data = {} # { ip: device_info }

    def add_device(self, device_info):
        ip = device_info['ip']
        self.devices_data[ip] = device_info
        
        # Add to Tree
        device_item = QTreeWidgetItem(self.tree)
        device_item.setText(0, f"{ip} ({device_info.get('manufacturer', 'Unknown')})")
        device_item.setExpanded(True)
        
        for ch in device_info.get('channels', []):
            ch_item = QTreeWidgetItem(device_item)
            res_str = f" [{ch['resolution']}]" if ch.get('resolution') else ""
            ch_item.setText(0, f"Channel {ch['channel_number']} - {ch['name']}{res_str}")
            ch_item.setCheckState(0, Qt.Checked if ch.get('enabled', True) else Qt.Unchecked)
            ch_item.setData(0, Qt.UserRole, (ip, ch['channel_number']))

    def on_item_changed(self, item, column):
        data = item.data(0, Qt.UserRole)
        if not data: return # Probably a root device item
        
        ip, ch_num = data
        enabled = (item.checkState(0) == Qt.Checked)
        
        if enabled:
            self._start_stream(ip, ch_num)
        else:
            self._stop_stream(ip, ch_num)
            
        self._update_grid_layout()

    def _start_stream(self, ip, ch_num):
        if (ip, ch_num) in self.active_streams: return
        
        device = self.devices_data.get(ip)
        if not device: return
        
        # Find channel info
        ch_info = next((c for c in device['channels'] if c['channel_number'] == ch_num), None)
        if not ch_info: return
        
        # Create Tile
        tile = StreamTile(ch_info)
        
        # Create Worker
        rtsp_url = ch_info.get('sub_stream_uri')
        if not rtsp_url:
            tile.update_status("failed")
            self.active_streams[(ip, ch_num)] = (None, tile)
            return

        worker = StreamWorker(rtsp_url, ch_num)
        worker.frame_ready.connect(tile.update_frame)
        worker.status_changed.connect(tile.update_status)
        worker.start()
        
        self.active_streams[(ip, ch_num)] = (worker, tile)

    def _stop_stream(self, ip, ch_num):
        if (ip, ch_num) in self.active_streams:
            worker, tile = self.active_streams.pop((ip, ch_num))
            if worker:
                worker.stop()
            tile.deleteLater()

    def _update_grid_layout(self):
        # Clear current grid
        for i in reversed(range(self.grid_layout.count())): 
            self.grid_layout.itemAt(i).widget().setParent(None)
            
        active_tiles = [v[1] for v in self.active_streams.values()]
        count = len(active_tiles)
        if count == 0: return
        
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)
        
        for idx, tile in enumerate(active_tiles):
            r = idx // cols
            c = idx % cols
            self.grid_layout.addWidget(tile, r, c)
