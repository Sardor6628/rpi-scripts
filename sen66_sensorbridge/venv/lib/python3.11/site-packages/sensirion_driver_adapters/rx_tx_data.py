# -*- coding: utf-8 -*-
# (c) Copyright 2021 Sensirion AG, Switzerland

import logging
import re
import struct
from functools import reduce
from typing import Iterable, Tuple

log = logging.getLogger(__name__)


def array_to_integer(element_bit_width: int, data: Iterable[int]) -> int:
    return reduce(lambda x, y: (x << element_bit_width) | y, data, 0)


class TxData:
    """Models the tx data that is exchanged. It is primarily a descriptor that knows how to convert structured
    data into a list of raw bytes"""

    ARRAY_MATCH = re.compile(r'(?P<length>(\d+)(?P<descriptor>[bBshHiIfd]))$')  # searches for an array

    def __init__(self, cmd_id, descriptor, device_busy_delay=0.0, slave_address=None, ignore_ack=False):
        self._cmd_id = cmd_id
        self._command_width = 2
        if descriptor.startswith('>B'):
            self._command_width = 1
        self._descriptor = descriptor
        self._slave_address = slave_address
        self._device_busy_delay = device_busy_delay
        self._ignore_acknowledge = ignore_ack
        array_fields = re.findall(self.ARRAY_MATCH, descriptor)
        self._string_len = 0
        if not any(array_fields):
            return
        if len(array_fields) > 1:
            raise NotImplementedError("A transfer cannot contain more than one string field!")
        self._array_len = int(array_fields[0][1])  # array length for use in struct
        self.element_descriptor = array_fields[0][2]  # element descriptor for use in struct

    @property
    def cmd_id(self):
        return self._cmd_id

    @cmd_id.setter
    def cmd_id(self, value):
        self._cmd_id = value

    def pack(self, args=None):
        argument_list = args if args is not None else []
        descriptor, data_to_pack = self._prepare_pack(argument_list)
        return bytearray(struct.pack(descriptor, *data_to_pack))

    @property
    def command_width(self):
        return self._command_width

    @property
    def slave_address(self):
        return self._slave_address

    @property
    def device_busy_delay(self):
        return self._device_busy_delay

    @property
    def ignore_acknowledge(self):
        return self._ignore_acknowledge

    def _string_to_bytes(self, string_param):
        assert self._array_len > 0, "Invalid string descriptor"
        if len(string_param) > self._array_len:
            string_param = string_param[:self._array_len]
            log.warning("Truncating string!")
        return string_param.encode()

    def _prepare_pack(self, argument_list) -> Tuple[str, list]:
        """
        Prepare the data list and the descriptor for packing the data.

        We require this in order to be able to test.

        :param argument_list: The list of data that will be packed

        :returns: A tuple with the descriptor and an array with the processed input. Strings are encoded into bytearray
        and the descriptor may be updated if the data ends with an array (SHDLC supports variable array length)
        """
        data_to_pack = [self.cmd_id]
        descriptor = self._descriptor
        for arg in argument_list:
            if isinstance(arg, str):  # strings need to be encoded
                arg_str = self._string_to_bytes(arg)
                descriptor = self.ARRAY_MATCH.sub(f'{len(arg_str)}{self.element_descriptor}', descriptor, 1)
                data_to_pack.append(arg_str)
            elif isinstance(arg, (list, tuple)):  # list or tuple values
                descriptor = self.ARRAY_MATCH.sub(f'{len(arg)}{self.element_descriptor}', descriptor, 1)
                data_to_pack.extend(arg)
            else:
                data_to_pack.append(arg)
        return descriptor, data_to_pack


class RxData:
    """Descriptor for data to be received"""

    field_match = re.compile(r'(?P<length>\d*)(?P<descriptor>([hHbBiI?sqQfd]))')
    array_match = re.compile(r'(?P<length>\d+)(?P<descriptor>([hHbBiI?sqQfd]))')
    element_size_map = {'B': 8, 'I': 32, 'H': 16}

    def __init__(self, descriptor=None, convert_to_int=False):
        self._descriptor = descriptor
        self._rx_length = 0
        self._conversion_function = None
        if self._descriptor is None:
            return
        self._rx_length = struct.calcsize(self._descriptor)
        match = RxData.array_match.search(descriptor)
        self._contains_array = match is not None
        self._convert_to_int = convert_to_int

    @property
    def rx_length(self):
        return self._rx_length

    def unpack(self, data):
        if self._contains_array:
            return self.unpack_dynamic_sized(data)
        return struct.unpack(self._descriptor, data)

    def unpack_dynamic_sized(self, data):
        """
        Unpacks data returned by a sensor.

        For SHDLC always this function is used. For i2c all responses that contain arrays are unpacked with this
        function.
        Reasoning:
            struct.pack() returns a tuple of values. In the python code an array is treated as one value. Hence, a
            descriptor in the form I8b would be unpacked as a tuple with 9 values but the driver would expect only
            two return values, an integer and an array containing the 8 bytes.
        """
        byte_order_specifier = self._descriptor[0]
        descriptor_pos, data_pos = 1, 0
        unpacked = []
        match = self.field_match.match(self._descriptor, descriptor_pos)
        while match:
            descriptor = match.group('descriptor')
            elem_size = struct.calcsize(descriptor)
            elem_bit_width = elem_size * 8
            length = match.group('length')
            descriptor_pos += len(length) + len(descriptor)
            if length:
                field_len = 0
                is_string = descriptor == 's'
                for i in range(data_pos, min(data_pos + elem_size * int(length), len(data))):
                    if data[i] == 0 and is_string:  # in SHDLC we have 0 delimited arrays
                        break
                    field_len += 1
                descriptor = f'{byte_order_specifier}{field_len // elem_size}{descriptor}'
                val = struct.unpack_from(descriptor, data, data_pos)
                if self._convert_to_int:
                    val = array_to_integer(elem_bit_width, val)
                elif is_string:  # a string
                    val = val[0].decode()
                unpacked.append(val)
            else:
                descriptor = f"{byte_order_specifier} {descriptor}"
                unpacked.extend(struct.unpack_from(descriptor, data, data_pos))
            data_pos += elem_size
            match = self.field_match.match(self._descriptor, descriptor_pos)
        return tuple(unpacked)
