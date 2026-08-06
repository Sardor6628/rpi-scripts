# -*- coding: utf-8 -*-
# (c) Copyright 2024 Sensirion AG, Switzerland
from __future__ import annotations

import functools
import types
import sys
from ctypes import (LittleEndianStructure, BigEndianStructure,
                    Array, Structure)

from typing import TypeVar, Any, Callable, Type, no_type_check, Dict

# the function get annotation is only available in python from version 3.10 upwards
# earlier versions require another implementation
if sys.version_info.major < 3:
    raise NotImplementedError("C-struct cannot be used with python 2.x or older")
if sys.version_info.minor < 10:
    from sensirion_driver_support_types.py_legacy import get_annotations
else:
    from inspect import get_annotations

T = TypeVar('T')
LittleEndian = LittleEndianStructure
BigEndian = BigEndianStructure

"""
This module provides a metaclass for defining generic c-structs.
Such a generic c-struct is instantiated by giving the byte order and the packing as parameters for the generic type.
The result is a dynamically generated python type the derives from ctypes.Structure. It allows to define
not only the memory layout for this structure but also the default values.

The defaults are overwritten when an object is created and the new values are passed to the constructor.
All fields are also accessible as members of the object.

The functionality of the type `ctypes.Structure` is extended with convenience functions to print an object in a
readable way, to reconstruct it from a byte array and to access the default values.


# Example:

ByteArray = c_uint8*4  # define the type byte array with the syntax of ctypes

@little_endian
class SimpleLittleEndian(metaclass=CStructTemplate):
    f1: c_uint16 = 0xA55A
    f2: c_uint16 = 0x55AA

@little_endian
class NestedStruct(metaclass=CStructTemplate):
    f1: c_uint32 = c_uint32(0x89ABCDEF)
    ba: ByteArray4 = ByteArray4(1, 2, 3, 4)
    s1: SimpleLittleEndian = SimpleLittleEndian(f1=0xBBBB)  # structures can be nested
    s2: SimpleLittleEndian = SimpleLittleEndian(f2=0xBBBB)

c_obj = NestedStruct()
c_obj.ba[2] = 15

print(c_obj)

More examples on how to use the c-structures can be found in the tests.

"""


class CStruct(Structure):
    """
    Dummy class to give typing some information about the interface of the dynamic class.
    This class  is only used in type annotations
    """

    def __bytes__(self) -> bytes:
        """Implements SupportsBytes"""
        raise NotImplementedError()

    def __init__(self, **kwargs) -> None:
        """Implements a constructor with kwargs only"""
        raise NotImplementedError()

    def get_defaults(self) -> Dict[str, Any]:
        """"""
        raise NotImplementedError()


def little_endian(cls=None, /, pack=1) -> Type[CStruct] | Callable:
    """Decorator to get a little endian structure with the defined packing amd default values

    @param cls: The decorated class
    @param pack: The pack size. Defaults to 1 since most applications will use the c_struct template to define
                 byte strings with specified format and values.
    """

    @functools.wraps(cls)
    def create_little_endian_cls(c):
        return no_type_check(c[LittleEndian, pack])

    if cls is None:
        return create_little_endian_cls
    else:
        return create_little_endian_cls(cls)


def big_endian(cls=None, /, pack=1) -> Type[CStruct] | Callable:
    """
    Decorator to get a big endian structure with the defined packing and default values

    @param cls: The decorated class
    @param pack: The pack size. Defaults to 1 since most applications will use the c_struct template to define
                 byte strings with specified format and values.
    """

    @functools.wraps(cls)
    def create_big_endian_cls(c) -> Type[CStruct]:
        return c[BigEndian, pack]

    if cls is None:
        return create_big_endian_cls
    else:
        return create_big_endian_cls(cls)


def format_cstruct(c_value: Structure) -> str:
    """
    Creates a readable representation of the c_value

    @param c_value: The structure to be formatted.
    @return A string representation of the structure.
    """

    def repr_impl(obj, depth):
        indentation = ' ' * depth * 4
        if isinstance(obj, Structure):
            lines = [f"c_struct {obj.__class__.__name__.split('_')[-1]} {{"]
            for f in obj.get_field_names():
                lines.append(f"\n{indentation}{f} : {repr_impl(getattr(obj, f), depth + 1)}")
            lines.append(f"\n{indentation}}}")
            return "".join(lines)
        elif isinstance(obj, Array):
            repr_txt = "["
            array_depth = depth
            for i in obj:
                if isinstance(i, Structure):
                    array_depth = depth + 1
                    repr_txt += f"\n{indentation}"
                repr_txt += f'{repr_impl(i, array_depth)}, '
            repr_txt += "]"
            return repr_txt
        else:
            return obj.__repr__()

    return repr_impl(c_value, 1)


class CStructTemplate(type):
    """Metaclass that acts as a type generator for CStructs with default values"""

    def __new__(cls, name, bases, attrs):
        attrs['cls_dict'] = {}
        attrs['__class_getitem__'] = CStructTemplate.class_getitem
        return super().__new__(cls, name, bases, attrs)

    def __class_getitem__(cls, item) -> Structure:
        """Support for type hints and IDE's"""
        raise NotImplementedError()

    @staticmethod
    def from_bytes(_: bytes) -> Structure:
        """Support for type hints and IDE's"""
        raise NotImplementedError()

    @staticmethod
    def class_getitem(cls, item) -> type[CStruct]:
        """
        Create a new type depending on the type parameters in item.

        @param cls: The generic class that acts as a type factory
        @param item: The type parameters that are used to create the new type
        """
        pack = 1
        if isinstance(item, type):
            base = item
        elif isinstance(item, tuple):
            base = item[0]
            pack = item[1]
        elif isinstance(item, types.EllipsisType):
            base = Structure
        else:
            raise ValueError(f"Invalid type parameter {item} for c-structure.")
        new_type = cls.cls_dict.get((base, pack))
        if new_type is None:
            class_name = f"_cstruct_{cls.__name__}[{base.__name__[0]}{pack}]"
            new_type = type(class_name,
                            (base,),  # base needs to come after mixin !!
                            {  # metadata for ctype.Structure
                                '_pack_': pack,
                                '_fields_': CStructTemplate.get_fields(cls),
                                # python object
                                '__init__': CStructTemplate._create_init(base.__name__),
                                '__repr__': format_cstruct,
                                # helper methods for generated object type
                                '_defaults': CStructTemplate.get_defaults(cls),
                                'from_bytes': CStructTemplate._create_from_bytes(),
                                'get_field_names': CStructTemplate.get_field_names,
                                'get_defaults': CStructTemplate.get_obj_defaults,
                            })
            cls.cls_dict[(base, pack)] = new_type
        return new_type

    @staticmethod
    def get_fields(cls):
        return [(name, type_expression)
                for name, type_expression in get_annotations(cls, eval_str=True).items()]

    @staticmethod
    def get_defaults(cls):
        """Generate the default value dictionary from the template class"""
        return {f[0]: getattr(cls, f[0]) for f in CStructTemplate.get_fields(cls)}

    @staticmethod
    def _create_init(base_class: str) -> Callable[[Dict[str, Any]], None]:
        """
        Generate a generic constructor for the new type.

        The base class is a type parameter that is applied. The way of generating this method is inspired from
        the dataclasses module.
        """
        fn_txt = ("def create_fun():\n"
                  "    from copy import deepcopy\n"
                  f"    def __init__(self, **kwargs) -> None:\n"
                  "        actual_args = deepcopy(self.get_defaults())\n"
                  "        actual_args.update(kwargs)\n"
                  f"        {base_class}.__init__(self, **actual_args)\n"
                  "    return __init__\n")
        ns: Dict[str, Any] = {}
        exec(fn_txt, globals(), ns)
        return ns['create_fun']()

    @staticmethod
    def _create_from_bytes() -> Callable[[bytes], Structure]:
        """
        Generate helper function to create a new object from a byte array.

        The way of generating this method is inspired from
        the dataclasses module.
        """
        fn_txt = ("def create_fun():\n"
                  "    from ctypes import sizeof, addressof, memmove\n"
                  "    @classmethod\n"
                  "    def from_bytes(cls, data) -> Structure:\n"
                  "        c_obj = cls()\n"
                  "        if len(data) < sizeof(c_obj):\n"
                  "            raise BufferError('Not enough data')\n"
                  "        memmove(addressof(c_obj), data[:sizeof(c_obj)], sizeof(c_obj))\n"
                  "        return c_obj\n"
                  "    return from_bytes\n")
        ns: Dict[str, Any] = {}
        exec(fn_txt, globals(), ns)
        return ns['create_fun']()

    @staticmethod
    def get_obj_defaults(obj) -> Dict[str, Any]:
        return obj._defaults  # noqa  -> the attribute is part of the dynamic class

    @staticmethod
    def get_field_names(cls):
        return [name for name, type in cls._fields_]  # noqa
