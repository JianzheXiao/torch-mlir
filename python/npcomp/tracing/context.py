#  Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
#  See https://llvm.org/LICENSE.txt for license information.
#  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

from typing import Optional

import contextlib
import threading

import numpy as np


class TracingError(Exception):
  pass


class TraceContext:
  """Context for intercepting array traces.

  Context manager:
  ----------------
  Instances act as context managers, the inner-most of which can be
  queried with current() or optional_current().

    >>> with TraceContext(desc=1) as tc:
    ...   print(tc)
    ...   print(TraceContext.current())
    <TraceContext 1>
    <TraceContext 1>
    >>> print(TraceContext.optional_current())
    None
    >>> TraceContext.current()
    Traceback (most recent call last):
    ...
    RuntimeError: No active TraceContext

  Unique ids:
  -----------
  Many things in tracing require a context-local id.

    >>> with TraceContext() as tc:
    ...   print(tc.get_next_id())
    ...   print(tc.get_next_id())
    1
    2

  """
  _local = threading.local()
  __slots__ = [
    "_desc",
    "_next_id",
    "active",
  ]
  def __init__(self, desc=None):
    self._desc = desc
    self._next_id = 1
    self.active = False

  def _handle_ufunc(self, ufunc, method, inputs, kwargs):
    """Handles a ufunc invocation involving at least one TracedArray."""
    raise NotImplementedError()

  def get_next_id(self):
    """Gets the next unique id for the context."""
    rv = self._next_id
    self._next_id += 1
    return rv

  @classmethod
  def _get_context_stack(cls):
    try:
      return cls._local.s
    except AttributeError:
      cls._local.s = []
      return cls._local.s

  @classmethod
  def optional_current(cls) -> Optional["TraceContext"]:
    s = cls._get_context_stack()
    if s: 
      return s[-1]
    else:
      return None
  
  @classmethod
  def current(cls) -> "TraceContext":
    c = cls.optional_current()
    if c is None:
      raise RuntimeError("No active TraceContext")
    return c

  def __enter__(self):
    s = self._get_context_stack()
    if s:
      s[-1].active = False
    s.append(self)
    self.active = True
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    s = self._get_context_stack()
    s.pop()
    self.active = False
    if s:
      s[-1].active = True

  def __repr__(self):
    return "<TraceContext %r>" % self._desc


def _assert_active(tc: TraceContext):
  assert tc.active, (
    "Attempt to trace an action on an inactive trace context: %r" % tc)


class TracedArray(np.lib.mixins.NDArrayOperatorsMixin):
  """An array that traces its operations.

  Unique ids:
  -----------
    >>> tc = TraceContext()
    >>> TracedArray(tc=tc)
    <TracedArray 1>
    >>> TracedArray(tc=tc)
    <TracedArray 2>
  """
  def __init__(self, tc: Optional[TraceContext] = None):
    self._tc = tc if tc is not None else TraceContext.current()
    self._uid = self._tc.get_next_id()

  def __hash__(self):
    return id(self)

  @property
  def uid(self):
    return self._uid

  def __repr__(self):
    return "<TracedArray %d>" % self._uid

  def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
    tc = self._tc
    _assert_active(tc)
    return tc._handle_ufunc(ufunc, method, inputs, kwargs)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
