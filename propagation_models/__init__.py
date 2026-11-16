import importlib, pkgutil
from .base import (PropagationModel, SimContext, Tx, LinkResult, sun_alt, sun_decl,
                   gc_distance, gc_intermediate, C_KM_PER_MS)

DEFAULT_MODEL = "Klassisch (heuristisch)"


def _all_subclasses(cls):
    for s in cls.__subclasses__():
        yield s
        yield from _all_subclasses(s)


def _discover():
    for m in pkgutil.iter_modules(__path__):
        if m.name == "base": continue
        try: importlib.import_module(f".{m.name}", __name__)
        except Exception as e: print(f"Ausbreitungsmodell '{m.name}' nicht ladbar: {e}")
    return {c.name: c for c in _all_subclasses(PropagationModel) if c.name}


_MODELS = _discover()


def available_models():
    """Namen aller Modelle; das Standardmodell zuerst."""
    return sorted(_MODELS, key=lambda n: (n != DEFAULT_MODEL, n.lower()))


def create_model(name):
    return _MODELS.get(name, _MODELS[DEFAULT_MODEL])()
