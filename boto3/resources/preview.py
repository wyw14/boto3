# Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# https://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

"""Offline request previews for model-defined resource actions.

This module answers the question: *if* ``resource.action_name(**kwargs)``
were called right now, which low-level service operation would be
invoked and with what parameters?

Unlike actually calling the action, a preview:

* never sends a service request and never touches the low-level client
  (so no credentials are resolved or refreshed);
* never calls ``load()`` on the resource and never mutates the cached
  ``resource.meta.data``;
* reports where every merged parameter value came from; and
* lists request parameter targets that depend on resource data which has
  not been loaded yet instead of fabricating a value for them.

Only actions generated from the resource JSON model (including a
resource's ``load`` action) can be previewed. Custom-injected methods,
waiters, collections, subresource factories and reference properties
are not model-defined request actions and raise
:class:`~boto3.exceptions.UnsupportedResourceActionError`.
"""

import copy
from collections import namedtuple

import jmespath
from botocore import xform_name

from ..exceptions import (
    UnknownResourceActionError,
    UnsupportedResourceActionError,
)
from .params import build_param_structure

# Origin labels used in ``ActionRequestPreview.origins``.
ORIGIN_IDENTIFIER = 'identifier'
ORIGIN_DATA = 'data'
ORIGIN_CONSTANT = 'constant'
ORIGIN_INPUT = 'input'

_CONSTANT_SOURCES = ('string', 'integer', 'boolean')

_UNLOADED = object()


class ActionRequestPreview(
    namedtuple(
        'ActionRequestPreview',
        ['service_name', 'operation_name', 'params', 'origins', 'unresolved'],
    )
):
    """The offline preview of a single resource action invocation.

    :ivar service_name: The low-level service name, e.g. ``'sqs'``.
    :vartype service_name: str
    :ivar operation_name: The name of the low-level client operation that
        the action invokes (snake case, as it is looked up on the client),
        e.g. ``'send_message'``.
    :vartype operation_name: str
    :ivar params: The parameters that would be sent to the operation,
        after merging model-defined parameters with the caller-supplied
        keyword arguments. This is an independent copy and may be mutated
        freely.
    :vartype params: dict
    :ivar origins: A nested structure mirroring ``params`` in which every
        leaf is one of :data:`ORIGIN_IDENTIFIER`, :data:`ORIGIN_DATA`,
        :data:`ORIGIN_CONSTANT` or :data:`ORIGIN_INPUT`, describing where
        the corresponding value came from.
    :vartype origins: dict
    :ivar unresolved: Request parameter ``target`` paths whose values
        depend on resource data that has not been loaded yet. The preview
        never loads this data, so these targets are absent from
        ``params`` and the request is incomplete.
    :vartype unresolved: list(str)
    """

    __slots__ = ()

    @property
    def is_complete(self):
        """``True`` when no parameters depend on unloaded data."""
        return not self.unresolved


def preview_resource_action(resource, action_name, **kwargs):
    """Build an offline preview of a model-defined resource action.

    This performs exactly the same parameter construction as calling the
    action would (see :func:`boto3.resources.params.create_request_parameters`
    followed by ``params.update(kwargs)``), including nested reverse
    JMESPath targets and top-level caller overrides, but stops short of
    invoking the low-level client operation.

    :type resource: :py:class:`~boto3.resources.base.ServiceResource`
    :param resource: The resource instance the action would be called on.
    :type action_name: str
    :param action_name: The snake-case name of the model-defined action,
        e.g. ``'send_message'``. ``'load'`` and ``'reload'`` are accepted
        when the resource model defines a load action.
    :param kwargs: The keyword arguments that would be passed to the
        action. These override any model-defined parameter sharing the
        same top-level target name.
    :rtype: :class:`ActionRequestPreview`
    :raises UnknownResourceActionError: If ``action_name`` is neither a
        model-defined action nor any other attribute of the resource.
    :raises UnsupportedResourceActionError: If ``action_name`` refers to
        an attribute that is not a model-defined request action, such as
        a custom-injected method, waiter, collection or subresource.
    :raises NotImplementedError: If the model uses a parameter source
        type that the request builder does not support.
    """
    request_model = _get_request_model(resource, action_name)

    params = {}
    origins = {}
    unresolved = []

    for param in request_model.params:
        source = param.source

        if source == 'identifier':
            origin = ORIGIN_IDENTIFIER
            # Identifiers are read from the instance exactly like the
            # real action does; they are plain stored values and never
            # trigger a load or a client call.
            value = getattr(resource, xform_name(param.name))
        elif source == 'data':
            origin = ORIGIN_DATA
            value = _get_cached_data_member(resource, param.path)
            if value is _UNLOADED:
                # The resource data has not been loaded. Unlike the real
                # action we must not call load(), and we must not invent
                # a value for this target. Record it and leave the target
                # out of the merged parameters.
                unresolved.append(param.target)
                continue
        elif source in _CONSTANT_SOURCES:
            origin = ORIGIN_CONSTANT
            value = param.value
        elif source == 'input':
            # The model expects the caller to supply this value; it is
            # only present when the caller provided a matching kwarg.
            continue
        else:
            raise NotImplementedError(f'Unsupported source type: {source}')

        # Deep copy every value pulled off the resource/model so that
        # mutating the preview cannot affect cached resource data or
        # shared model definitions.
        value = copy.deepcopy(value)

        # Use the very same reverse-JMESPath builder as the real action
        # for both ``params`` and ``origins``. Both start empty and are
        # fed the same targets in the same order, so ``origins`` mirrors
        # ``params`` exactly, including list indexing behaviour.
        build_param_structure(params, param.target, value)
        build_param_structure(origins, param.target, origin)

    # Caller-supplied kwargs win at the top level, matching the real
    # action's ``params.update(kwargs)`` semantics. Values are deep copied
    # so the preview cannot mutate the caller's input containers.
    for key, value in kwargs.items():
        params[key] = copy.deepcopy(value)
        origins[key] = _stamp_origin(value, ORIGIN_INPUT)

    return ActionRequestPreview(
        service_name=resource.meta.service_name,
        operation_name=xform_name(request_model.operation),
        params=params,
        origins=origins,
        unresolved=unresolved,
    )


def _get_cached_data_member(resource, path):
    """Return a cached data member without ever loading the resource.

    Mirrors :func:`boto3.resources.params.get_data_member` except that
    ``None`` cached data yields the ``_UNLOADED`` sentinel instead of
    triggering ``load()`` or raising.
    """
    data = resource.meta.data
    if data is None:
        return _UNLOADED
    return jmespath.search(path, data)


def _stamp_origin(value, origin):
    """Build an origins tree for a caller-supplied value."""
    if isinstance(value, dict):
        return {
            key: _stamp_origin(item, origin) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_stamp_origin(item, origin) for item in value]
    return origin


def _get_request_model(resource, action_name):
    """Look up the request model for ``action_name`` or raise."""
    resource_model = getattr(resource.meta, 'resource_model', None)

    action = None
    if resource_model is not None:
        if action_name in ('load', 'reload') and resource_model.load:
            action = resource_model.load
        else:
            for modeled_action in resource_model.actions:
                if modeled_action.name == action_name:
                    action = modeled_action
                    break

    if action is not None and action.request is not None:
        return action.request

    available = _available_action_names(resource_model)
    resource_name = type(resource).__name__
    description = _describe_nonmodeled_attribute(resource, action_name)
    if description is not None:
        raise UnsupportedResourceActionError(
            resource_name, action_name, description, available
        )
    raise UnknownResourceActionError(resource_name, action_name, available)


def _available_action_names(resource_model):
    names = []
    if resource_model is not None:
        if resource_model.load:
            names.append('load')
        names.extend(action.name for action in resource_model.actions)
    return sorted(names)


def _describe_nonmodeled_attribute(resource, name):
    """Describe a non-modeled class/instance attribute, if one exists.

    Class dictionaries (rather than instance attribute access) are used
    deliberately so that descriptors such as reference/collection
    properties cannot be triggered, which keeps the preview offline.
    """
    for base in type(resource).__mro__:
        if name in getattr(base, '__dict__', {}):
            return _describe_attribute(base.__dict__[name])
    if name in getattr(resource, '__dict__', {}):
        return _describe_attribute(resource.__dict__[name])
    return None


def _describe_attribute(attribute):
    if isinstance(attribute, property):
        return (
            'it is a property (a collection, reference or identifier), '
            'not a model-defined request action'
        )
    if callable(attribute):
        return (
            'it is a custom-injected or otherwise non-modeled method, '
            'not an action generated from the resource model'
        )
    return f'it is a non-action attribute of type {type(attribute).__name__}'
