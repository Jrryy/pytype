"""Add metaclasses to classes."""

# NOTE: This implements the decorators found in the `six` library. Tests can be
# found in tests/test_six_overlay, since that is currently the only way to
# trigger them in inference.

import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import class_mixin
from pytype import function

log = logging.getLogger(__name__)


class AddMetaclassInstance(abstract.BaseValue):
  """AddMetaclass instance (constructed by AddMetaclass.call())."""

  def __init__(self, meta, vm, module_name):
    super().__init__("AddMetaclassInstance", vm)
    self.meta = meta
    self.module_name = module_name

  def call(self, node, unused, args):
    if len(args.posargs) != 1:
      sig = function.Signature.from_param_names(
          "%s.add_metaclass" % self.module_name, ("cls",))
      raise function.WrongArgCount(sig, args, self.vm)
    cls_var = args.posargs[0]
    for b in cls_var.bindings:
      cls = b.data
      log.debug("Adding metaclass %r to class %r", self.meta, cls)
      cls.cls = self.meta
      # For metaclasses defined natively or using with_metaclass, the
      # metaclass's initializer is called in vm.make_class. However, with
      # add_metaclass, the metaclass is not known until the decorator fires.
      if isinstance(cls, class_mixin.Class):
        node = cls.call_metaclass_init(node)
    return node, cls_var


class AddMetaclass(abstract.PyTDFunction):
  """Implements the add_metaclass decorator."""

  @classmethod
  def make(cls, name, vm, module_name):
    self = super().make(name, vm, module_name)
    self.module_name = module_name
    return self

  def call(self, node, unused_func, args):
    """Adds a metaclass."""
    self.match_args(node, args)
    meta = abstract_utils.get_atomic_value(
        args.posargs[0], default=self.vm.convert.unsolvable)
    return node, AddMetaclassInstance(
        meta, self.vm, self.module_name).to_variable(node)


class WithMetaclassInstance(abstract.BaseValue, class_mixin.Class):
  """Anonymous class created by with_metaclass."""

  def __init__(self, vm, cls, bases):
    super().__init__("WithMetaclassInstance", vm)
    class_mixin.Class.init_mixin(self, cls)
    self.bases = bases

  def get_own_attributes(self):
    if isinstance(self.cls, class_mixin.Class):
      return self.cls.get_own_attributes()
    else:
      return set()

  def get_own_abstract_methods(self):
    if isinstance(self.cls, class_mixin.Class):
      return self.cls.get_own_abstract_methods()
    else:
      return set()


class WithMetaclass(abstract.PyTDFunction):
  """Implements with_metaclass."""

  def call(self, node, unused_func, args):
    """Creates an anonymous class to act as a metaclass."""
    self.match_args(node, args)
    meta = abstract_utils.get_atomic_value(
        args.posargs[0], default=self.vm.convert.unsolvable)
    bases = args.posargs[1:]
    result = WithMetaclassInstance(self.vm, meta, bases).to_variable(node)
    return node, result
