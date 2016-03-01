__author__ = 'mike'
from time import clock
import RockPy3
import numpy as np

from RockPy3.core import io


class Vsm(io.ftype):
    standard_calibration_exponent = -3

    @staticmethod
    def get_segment_start_idx(data):
        for i, v in enumerate(data):
            if v.startswith('Segment'):
                return i

    @staticmethod
    def get_data_index(data):
        # min(i for i, v in enumerate(self.raw_data) if v.startswith('+') or v.startswith('-'))
        for i, v in enumerate(data):
            if v.startswith('+') or v.startswith('-'):
                return i

    @staticmethod
    def split_data(data):
        out = []
        aux = []
        for l in data:
            if not l:
                out.append(aux)
                aux = []
            else:
                l = [float(i) for i in l.split(',')]
                aux.append(l)
        return np.array(out)

    @staticmethod
    def get_segment_raw(data):
        out = []
        for i in data:
            if not i:
                return out
            else:
                out.append(i)

    def __init__(self, dfile, dialect=None):
        super(Vsm, self).__init__(dfile=dfile, dialect=dialect)
        raw_data = self.simple_import()

        # successively remove data from the raw_data
        self.micromag = raw_data.pop(0)
        self.mtype = raw_data.pop(0)

        # remove last line with ' MicroMag 2900/3900 Data File ends'
        raw_data.pop(-1)

        self.segment_start_idx = self.get_segment_start_idx(
            raw_data)  # [i for i, v in enumerate(self.raw_data) if v.startswith('Segment')][0]

        # get the info header raw data
        # the data starts from line 1 up to the line where it sais 'Segments'
        self.info_header_raw = raw_data[
                               1:self.segment_start_idx + 1]  # [self.raw_data.pop(0) for i in range(0, self.segment_start_idx)][1:]

        raw_data = raw_data[self.segment_start_idx:]  # remove header from raw_data
        self.info_header = self.get_measurement_infos()

        # check the calibration factor
        self.calibration_factor = self.info_header['calibration factor']

        if np.floor(np.log10(self.calibration_factor)) != 0:
            self.correct_exp = np.power(10, np.floor(np.log10(self.calibration_factor)))
            RockPy3.logger.warning(
                'CALIBRATION FACTOR (cf) seems to be wrong. Generally the exponent of the cf is -3 here: {}. Data is corrected'.format(
                    int(np.floor(np.log10(self.calibration_factor)))))
        else:
            self.correct_exp = None

        # remove all data points from raw data
        self.data_idx = self.get_data_index(raw_data)
        self.segment_raw = self.get_segment_raw(raw_data[:self.data_idx])

        self._data = raw_data[self.data_idx:-1]  # [self.raw_data.pop(self.data_idx) for i in range(self.data_idx, len(self.raw_data) - 1)]

        self.header, self.units = self.get_header(raw_data[len(self.segment_raw):self.data_idx])

        # micromag header with all the settings
        self.measurement_info = self.get_measurement_infos()

    # @property
    # def temperature(self):
    #     if self.measurement_info['temperature (measured)'] != 'N/A':
    #         return self.measurement_info['temperature (measured)']

    def get_segments_from_data(self):
        # the length of each field is calculated using the last line of the segments.
        # That line has a ',' at the point where we want to break, the index of the comma is used
        # to separate the line
        field_lengths = [0] + [i for i, v in enumerate(self.segment_raw[-1]) if v == ',']
        field_lengths.append(len(self.segment_raw[0]))

        # separate and join the lines
        seg_text = [i for i in self.segment_raw if not i[0].isdigit() if i]

        # split lines
        seg_text = [[seg[v:field_lengths[i + 1]].strip()
                     for seg in seg_text] for i, v in enumerate(field_lengths[:-1])]
        # join texts
        seg_text = [' '.join(i).lower().rstrip() for i in seg_text]

        seg_nums = [i for i in self.segment_raw if i[0].isdigit()]
        # seg_text = list(map(str.lower, seg_text))
        # # convert and
        seg_nums = [map(self.convert2float_or_str, j.split(',')) for j in seg_nums]
        seg_nums = list(map(list, zip(*seg_nums)))

        # quick check if this makes sense
        if len(seg_nums[0]) != self.measurement_info['number of segments']:
            self.log.error('NUMBER OF SEGMENTS IS WRONG')

        return dict(zip(seg_text, seg_nums))

    def get_data(self):
        # get the empty line numbers
        empty_lines = [0] + [i for i, v in enumerate(self._data) if not v] + [len(self._data)]
        data = np.array([np.array([i.split(',') for i in self._data[v: empty_lines[i + 1]] if i]).astype(float)
                         for i, v in enumerate(empty_lines[:-1])])
        # data = self.split_data(self._data)
        if self.correct_exp:
            moment_idx = [i for i, v in enumerate(self.header) if v in ('moment', 'remanence', 'induced')]
            for idx in moment_idx:
                for i, d in enumerate(data):
                    data[i][:, idx] *= self.correct_exp

        return data

    # def get_data(self):
    #     data = self.split_data(self._data)

    @staticmethod
    def get_header(data):
        data = [[j for j in i.split(' ') if j] for i in data if i]

        # correct Am^2 sign
        for i, v in enumerate(data[1]):
            if 'Am' in v:
                data[1][i] = 'A m^2'
        return [i.lower() for i in data[0]], data[1]

    @staticmethod
    def split_comma_float(item):
        if item:
            return map(float, item.split(','))

    def get_measurement_infos(self):
        """
        takes the raw data and creates a dictionary with the measurement infos
        """

        def separate(line):
            if line:
                if any(j in line for j in ('+', '-', '\"')):
                    splitter = 30
                else:
                    splitter = 31
                if line[splitter + 1:].rstrip():
                    out = (line[:splitter].rstrip().lower(), self.convert2float_or_str(line[splitter + 1:].strip()))

                    if out[1] == 'Yes':
                        return (line[:splitter].rstrip().lower(), True)
                    if out[1] == 'No':
                        return (line[:splitter].rstrip().lower(), False)
                    else:
                        return out

        t = [i.split('  ') for i in self.info_header_raw]
        t = [[j for j in i if j] for i in t]
        t = [tuple(i) for i in t if len(i) > 1]
        data = {i[0].lower(): i[1] for i in t}

        for k, v in data.items():
            with RockPy3.ignored(ValueError):
                data[k] = float(v)
            if v == 'Yes':
                data[k] = True
            if v == 'No':
                data[k] = False
        # data = self.info_header_raw
        # data = [i for i in map(separate, data) if i and i[1]]
        return dict(data)

    def check_calibration_factor(self):
        pass


if __name__ == '__main__':
    # wrong_exp = RockPy3.test_data_path+'/hys_vsm_wrong_exponent.001'
    correct_exp = RockPy3.test_data_path + '/FeNi_FeNi20-Jz000\'-G03_HYS_VSM#50,3[mg]_[]_[]##STD020.003'
    # correct = Vsm(dfile=correct_exp)
    # vsm = Vsm(dfile=correct_exp)
    s = RockPy3.Sample()
    s.add_measurement(fpath=correct_exp)
