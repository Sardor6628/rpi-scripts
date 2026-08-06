# -*- coding: utf-8 -*-
# (c) Copyright 2025 Sensirion AG, Switzerland

import sys
from typing import no_type_check


@no_type_check
def get_annotations(obj, *, glob=None, loc=None, eval_str=False):
    """
    get the annotations on a python version < 3.10

    @param obj: The generic class that acts as a type factory
    @param glob: The global namespace to be used in eval
    @param loc: The local namespace to be used in eval
    @param eval_str: The generic class that acts as a type factory
    """

    def stringify(val):
        if isinstance(val, str):
            if isinstance(obj, type):
                return eval(val, sys.modules[obj.__module__].__dict__, dict(vars(obj)))
            else:
                glob_ns = glob if glob is not None else globals()
                loc_ns = loc if loc is not None else locals()
                return eval(val, glob_ns, loc_ns)
        return val

    if isinstance(obj, type):
        ann = obj.__dict__.get('__annotations__', None)
    else:
        ann = getattr(obj, '__annotations__', None)
    if ann is None:
        return dict()
    if eval_str:
        return {key: stringify(value) for key, value in ann.items()}
    return ann
