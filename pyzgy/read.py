import struct

import numpy as np
import segyio
from segyio import _segyio

from openzgy.api import ZgyReader
from .loader import ZgyLoader


class SeismicReader:
    def __init__(self, filename):
        if isinstance(filename, ZgyReader):
            self._filename = filename._fd._name
            self.filehandle = filename
        else:
            self._filename = filename
            self.filehandle = ZgyReader(self._filename)
        self.loader = ZgyLoader(self.filehandle)

        self.n_ilines, self.n_xlines, self.n_samples = self.filehandle.size
        self.tracecount = self.n_xlines * self.n_ilines

        self.ilines = self.get_haxis(0)
        self.xlines = self.get_haxis(1)

        self.samples = np.arange(self.filehandle.zstart,
                                 self.filehandle.zstart+self.n_samples*self.filehandle.zinc,
                                 self.filehandle.zinc)

        self.corners = self.filehandle.corners
        self.annotstart = self.filehandle.annotstart
        self.annotinc = self.filehandle.annotinc
        self.zinc = self.filehandle.zinc

        self.easting_inc_il = (self.corners[1][0] - self.corners[0][0]) / (self.filehandle.size[0] - 1)
        self.northing_inc_il = (self.corners[1][1] - self.corners[0][1]) / (self.filehandle.size[0] - 1)
        self.easting_inc_xl = (self.corners[2][0] - self.corners[0][0]) / (self.filehandle.size[1] - 1)
        self.northing_inc_xl = (self.corners[2][1] - self.corners[0][1]) / (self.filehandle.size[1] - 1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.filehandle.close()

    @staticmethod
    def coord_to_index(coord, coords, include_stop=False):
        try:
            index = np.where(coords == coord)[0][0]
        except:
            if include_stop and (coord == coords[-1] + (coords[-1] - coords[-2])):
                return len(coords)
            raise IndexError("Coordinate {} not in axis".format(coord))
        return index

    def get_haxis(self, idx):
        return np.arange(int(self.filehandle.annotstart[idx]),
                         int(self.filehandle.annotstart[idx] + self.filehandle.size[idx]*self.filehandle.annotinc[idx]),
                         int(self.filehandle.annotinc[idx]), dtype=np.intc)

    def read_inline_number(self, il_no):
        """Reads one inline from ZGY file

        Parameters
        ----------
        il_no : int
            The inline number

        Returns
        -------
        inline : numpy.ndarray of float32, shape: (n_xlines, n_samples)
            The specified inline, decompressed
        """
        return self.read_inline(self.coord_to_index(il_no, self.ilines))

    def read_inline(self, il_idx):
        """Reads one inline from ZGY file

        Parameters
        ----------
        il_idx : int
            The ordinal number of the inline in the file

        Returns
        -------
        inline : numpy.ndarray of float32, shape: (n_xlines, n_samples)
            The specified inline, decompressed
        """
        return self.loader.load_inline_chunk(64*(il_idx//64))[il_idx % 64, :, :].copy()

    def read_crossline_number(self, xl_no):
        """Reads one crossline from ZGY file

        Parameters
        ----------
        xl_no : int
            The crossline number

        Returns
        -------
        crossline : numpy.ndarray of float32, shape: (n_ilines, n_samples)
            The specified crossline, decompressed
        """
        return self.read_crossline(self.coord_to_index(xl_no, self.xlines))

    def read_crossline(self, xl_idx):
        """Reads one crossline from ZGY file

        Parameters
        ----------
        xl_idx : int
            The ordinal number of the crossline in the file

        Returns
        -------
        crossline : numpy.ndarray of float32, shape: (n_ilines, n_samples)
            The specified crossline, decompressed
        """
        return self.loader.load_crossline_chunk(64 * (xl_idx // 64))[:, xl_idx % 64, :].copy()

    def read_zslice_coord(self, samp_no):
        """Reads one zslice from ZGY file (time or depth, depending on file contents)

        Parameters
        ----------
        samp_no : int
            The sample time/depth to return a zslice from

        Returns
        -------
        zslice : numpy.ndarray of float32, shape: (n_ilines, n_xlines)
            The specified zslice (time or depth, depending on file contents), decompressed
        """
        return self.read_zslice(self.coord_to_index(samp_no, self.samples))

    def read_zslice(self, z_idx):
        """Reads one zslice from ZGY file (time or depth, depending on file contents)

        Parameters
        ----------
        z_idx : int
            The ordinal number of the zslice in the file

        Returns
        -------
        zslice : numpy.ndarray of float32, shape: (n_ilines, n_xlines)
            The specified zslice (time or depth, depending on file contents), decompressed
        """
        return self.loader.load_zslice_chunk(64 * (z_idx // 64))[:, :, z_idx % 64].copy()

    def read_subvolume(self, min_il, max_il, min_xl, max_xl, min_z, max_z):
        """Reads a sub-volume from ZGY file

        Parameters
        ----------
        min_il : int
            The index of the first inline to get from the cube. Use 0 to for the first inline in the cube
        max_il : int
            The index of the last inline to get, non inclusive. To get one inline, use max_il = min_il + 1

        min_xl : int
            The index of the first crossline to get from the cube. Use 0 for the first crossline in the cube
        max_xl : int
            The index of the last crossline to get, non inclusive. To get one crossline, use max_xl = min_xl + 1

        min_z : int
            The index of the first time sample to get from the cube. Use 0 for the first time sample in the cube
        max_z : int
            The index of the last time sample to get, non inclusive. To get one time sample, use max_z = min_z + 1

        Returns
        -------
        subvolume : numpy.ndarray of float32, shape (max_il - min_il, max_xl - min_xl, max_z - min_z)
            The specified subvolume, decompressed
        """
        buf = np.zeros((max_il-min_il, max_xl-min_xl, max_z-min_z), dtype=np.float32)
        self.filehandle.read((min_il, min_xl, min_z), buf)
        return buf

    def read_volume(self):
        """Reads the whole volume from ZGY file

        Returns
        -------
        volume : numpy.ndarray of float32, shape (n_ilines, n_xline, n_samples)
            The whole volume, decompressed
        """
        return self.read_subvolume(0, self.n_ilines,
                                   0, self.n_xlines,
                                   0, self.n_samples)

    def get_trace(self, index):
        """Reads one trace from ZGY file

        Parameters
        ----------
        index : int
            The ordinal number of the trace in the file

        Returns
        -------
        trace : numpy.ndarray of float32, shape (n_samples)
            A single trace, decompressed
        """
        if not 0 <= index < self.n_ilines * self.n_xlines:
            raise IndexError("Index {} is out of range, total traces is {}".format(index,
                                                                                   self.n_ilines * self.n_xlines))

        il, xl = index // self.n_xlines, index % self.n_xlines
        return self.loader.load_trace_chunk(64*(il//64), 64*(xl//64))[il % 64, xl % 64, :].copy()

    def gen_cdp_x(self, il_coord, xl_coord):
        """Generates the CDP X coordinate from an iline and xline pair.

        Parameters
        ----------
        il_coord : int
           The iline index of the cube.
        xl_coord : int
           The xline index of the cube.

        Returns
        -------
        cdp_x : float
            The corresponding cartesian x coordinate
        """
        return (
            self.corners[0][0]
            + il_coord * self.easting_inc_il
            + xl_coord * self.easting_inc_xl
        )

    def gen_cdp_y(self, il_coord, xl_coord):
        """Generates the CDP Y coordinate from an iline and xline pair.

        Parameters
        ----------
        il_coord : int
           The iline index of the cube.
        xl_coord : int
           The xline index of the cube.

        Returns
        -------
        cdp_y : float
            The corresponding cartesian y coordinate
        """
        return (
            self.corners[0][1]
            + il_coord * self.northing_inc_il
            + xl_coord * self.northing_inc_xl
        )

    def gen_trace_header(self, index):
        """Generates one trace header from ZGY file,
        note that only a few SEG-Y header values can be
        recovered from ZGY files: TRACE_SAMPLE_COUNT, TRACE_SAMPLE_INTERVAL, CDP_X, CDP_Y, INLINE_3D, CROSSLINE_3D

        Parameters
        ----------
        index : int
            The ordinal number of the trace header in the file

        Returns
        -------
        header : dict
            A single header as a dictionary of headerword-value pairs
        """
        if not 0 <= index < self.n_ilines * self.n_xlines:
            raise IndexError(self.range_error.format(index, 0, self.tracecount))

        xl_coord, il_coord = index % self.n_xlines, index // self.n_xlines

        cdp_x = int(round(100.0 * self.gen_cdp_x(il_coord, xl_coord)))
        cdp_y = int(round(100.0 * self.gen_cdp_y(il_coord, xl_coord)))

        inline_3d = int(self.annotstart[0] + il_coord * self.annotinc[0])
        crossline_3d = int(self.annotstart[1] + xl_coord * self.annotinc[1])

        header = bytearray(240)
        header[70:72] = struct.pack(">h", -100)  # A scalar of -100 is implicit in supplying UTM coordinates in cm
        header[180:184] = struct.pack(">i", cdp_x)
        header[184:188] = struct.pack(">i", cdp_y)
        header[188:192] = struct.pack(">i", inline_3d)
        header[192:196] = struct.pack(">i", crossline_3d)
        header[114:116] = struct.pack(">H", self.n_samples)  # Samples per trace
        header[116:118] = struct.pack(">H", int(self.zinc * 1000))  # Sample interval (μs/m)

        return segyio.segy.Field(header, kind='trace')


# Copyright 2021, Equinor
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
