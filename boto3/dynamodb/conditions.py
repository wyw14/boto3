# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
import operator
import re
from collections import namedtuple
from decimal import Decimal

from boto3.compat import collections_abc
from boto3.dynamodb.types import (
    BINARY,
    BINARY_SET,
    BOOLEAN,
    LIST,
    MAP,
    NULL,
    NUMBER,
    NUMBER_SET,
    STRING,
    STRING_SET,
    Binary,
)
from boto3.exceptions import (
    DynamoDBNeedsConditionError,
    DynamoDBNeedsKeyConditionError,
    DynamoDBOperationNotSupportedError,
)

ATTR_NAME_REGEX = re.compile(r'[^.\[\]]+(?![^\[]*\])')


class ConditionBase:
    expression_format = ''
    expression_operator = ''
    has_grouped_values = False

    def __init__(self, *values):
        self._values = values

    def __and__(self, other):
        if not isinstance(other, ConditionBase):
            raise DynamoDBOperationNotSupportedError('AND', other)
        return And(self, other)

    def __or__(self, other):
        if not isinstance(other, ConditionBase):
            raise DynamoDBOperationNotSupportedError('OR', other)
        return Or(self, other)

    def __invert__(self):
        return Not(self)

    def get_expression(self):
        return {
            'format': self.expression_format,
            'operator': self.expression_operator,
            'values': self._values,
        }

    def evaluate(self, item):
        """Evaluate the condition locally against a single Python item.

        This applies the condition tree (built with ``Key``/``Attr``) to an
        in-memory item, as represented by a dictionary of Python values, and
        returns whether or not the item matches without making any call to
        DynamoDB. The supported Python value conventions are the same as
        :class:`boto3.dynamodb.types.TypeSerializer`/``TypeDeserializer``
        (e.g. ``Decimal`` for numbers, ``None`` for the DynamoDB NULL type).

        Neither the condition nor the item are modified. A result of ``True``
        only means the local item satisfies the condition; it is not a
        replacement for the expression validation performed by DynamoDB.

        :type item: dict
        :param item: The item to evaluate the condition against.

        :rtype: bool
        :returns: True if the item satisfies the condition, False otherwise.

        :raises TypeError: The item or one of its values uses a type that
            DynamoDB does not support (e.g. ``float``), or a condition is
            applied to values of incompatible types (e.g. ordering a map).
        :raises ValueError: The condition references a malformed document
            path (e.g. ``Attr('a..b')``) or an invalid ``attribute_type``
            token.
        """
        return ConditionExpressionEvaluator().evaluate(self, item)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            if self._values == other._values:
                return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class AttributeBase:
    def __init__(self, name):
        self.name = name

    def __and__(self, value):
        raise DynamoDBOperationNotSupportedError('AND', self)

    def __or__(self, value):
        raise DynamoDBOperationNotSupportedError('OR', self)

    def __invert__(self):
        raise DynamoDBOperationNotSupportedError('NOT', self)

    def eq(self, value):
        """Creates a condition where the attribute is equal to the value.

        :param value: The value that the attribute is equal to.
        """
        return Equals(self, value)

    def lt(self, value):
        """Creates a condition where the attribute is less than the value.

        :param value: The value that the attribute is less than.
        """
        return LessThan(self, value)

    def lte(self, value):
        """Creates a condition where the attribute is less than or equal to the
           value.

        :param value: The value that the attribute is less than or equal to.
        """
        return LessThanEquals(self, value)

    def gt(self, value):
        """Creates a condition where the attribute is greater than the value.

        :param value: The value that the attribute is greater than.
        """
        return GreaterThan(self, value)

    def gte(self, value):
        """Creates a condition where the attribute is greater than or equal to
           the value.

        :param value: The value that the attribute is greater than or equal to.
        """
        return GreaterThanEquals(self, value)

    def begins_with(self, value):
        """Creates a condition where the attribute begins with the value.

        :param value: The value that the attribute begins with.
        """
        return BeginsWith(self, value)

    def between(self, low_value, high_value):
        """Creates a condition where the attribute is greater than or equal
        to the low value and less than or equal to the high value.

        :param low_value: The value that the attribute is greater than or equal to.
        :param high_value: The value that the attribute is less than or equal to.
        """
        return Between(self, low_value, high_value)

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.name == other.name

    def __ne__(self, other):
        return not self.__eq__(other)


class ConditionAttributeBase(ConditionBase, AttributeBase):
    """This base class is for conditions that can have attribute methods.

    One example is the Size condition. To complete a condition, you need
    to apply another AttributeBase method like eq().
    """

    def __init__(self, *values):
        ConditionBase.__init__(self, *values)
        # This is assuming the first value to the condition is the attribute
        # in which can be used to generate its attribute base.
        AttributeBase.__init__(self, values[0].name)

    def __eq__(self, other):
        return ConditionBase.__eq__(self, other) and AttributeBase.__eq__(
            self, other
        )

    def __ne__(self, other):
        return not self.__eq__(other)


class ComparisonCondition(ConditionBase):
    expression_format = '{0} {operator} {1}'


class Equals(ComparisonCondition):
    expression_operator = '='


class NotEquals(ComparisonCondition):
    expression_operator = '<>'


class LessThan(ComparisonCondition):
    expression_operator = '<'


class LessThanEquals(ComparisonCondition):
    expression_operator = '<='


class GreaterThan(ComparisonCondition):
    expression_operator = '>'


class GreaterThanEquals(ComparisonCondition):
    expression_operator = '>='


class In(ComparisonCondition):
    expression_operator = 'IN'
    has_grouped_values = True


class Between(ConditionBase):
    expression_operator = 'BETWEEN'
    expression_format = '{0} {operator} {1} AND {2}'


class BeginsWith(ConditionBase):
    expression_operator = 'begins_with'
    expression_format = '{operator}({0}, {1})'


class Contains(ConditionBase):
    expression_operator = 'contains'
    expression_format = '{operator}({0}, {1})'


class Size(ConditionAttributeBase):
    expression_operator = 'size'
    expression_format = '{operator}({0})'


class AttributeType(ConditionBase):
    expression_operator = 'attribute_type'
    expression_format = '{operator}({0}, {1})'


class AttributeExists(ConditionBase):
    expression_operator = 'attribute_exists'
    expression_format = '{operator}({0})'


class AttributeNotExists(ConditionBase):
    expression_operator = 'attribute_not_exists'
    expression_format = '{operator}({0})'


class And(ConditionBase):
    expression_operator = 'AND'
    expression_format = '({0} {operator} {1})'


class Or(ConditionBase):
    expression_operator = 'OR'
    expression_format = '({0} {operator} {1})'


class Not(ConditionBase):
    expression_operator = 'NOT'
    expression_format = '({operator} {0})'


class Key(AttributeBase):
    pass


class Attr(AttributeBase):
    """Represents an DynamoDB item's attribute."""

    def ne(self, value):
        """Creates a condition where the attribute is not equal to the value

        :param value: The value that the attribute is not equal to.
        """
        return NotEquals(self, value)

    def is_in(self, value):
        """Creates a condition where the attribute is in the value,

        :type value: list
        :param value: The value that the attribute is in.
        """
        return In(self, value)

    def exists(self):
        """Creates a condition where the attribute exists."""
        return AttributeExists(self)

    def not_exists(self):
        """Creates a condition where the attribute does not exist."""
        return AttributeNotExists(self)

    def contains(self, value):
        """Creates a condition where the attribute contains the value.

        :param value: The value the attribute contains.
        """
        return Contains(self, value)

    def size(self):
        """Creates a condition for the attribute size.

        Note another AttributeBase method must be called on the returned
        size condition to be a valid DynamoDB condition.
        """
        return Size(self)

    def attribute_type(self, value):
        """Creates a condition for the attribute type.

        :param value: The type of the attribute.
        """
        return AttributeType(self, value)


BuiltConditionExpression = namedtuple(
    'BuiltConditionExpression',
    [
        'condition_expression',
        'attribute_name_placeholders',
        'attribute_value_placeholders',
    ],
)


class ConditionExpressionBuilder:
    """This class is used to build condition expressions with placeholders"""

    def __init__(self):
        self._name_count = 0
        self._value_count = 0
        self._name_placeholder = 'n'
        self._value_placeholder = 'v'

    def _get_name_placeholder(self):
        return f"#{self._name_placeholder}{self._name_count}"

    def _get_value_placeholder(self):
        return f":{self._value_placeholder}{self._value_count}"

    def reset(self):
        """Resets the placeholder name and values"""
        self._name_count = 0
        self._value_count = 0

    def build_expression(self, condition, is_key_condition=False):
        """Builds the condition expression and the dictionary of placeholders.

        :type condition: ConditionBase
        :param condition: A condition to be built into a condition expression
            string with any necessary placeholders.

        :type is_key_condition: Boolean
        :param is_key_condition: True if the expression is for a
            KeyConditionExpression. False otherwise.

        :rtype: (string, dict, dict)
        :returns: Will return a string representing the condition with
            placeholders inserted where necessary, a dictionary of
            placeholders for attribute names, and a dictionary of
            placeholders for attribute values. Here is a sample return value:

            ('#n0 = :v0', {'#n0': 'myattribute'}, {':v1': 'myvalue'})
        """
        if not isinstance(condition, ConditionBase):
            raise DynamoDBNeedsConditionError(condition)
        attribute_name_placeholders = {}
        attribute_value_placeholders = {}
        condition_expression = self._build_expression(
            condition,
            attribute_name_placeholders,
            attribute_value_placeholders,
            is_key_condition=is_key_condition,
        )
        return BuiltConditionExpression(
            condition_expression=condition_expression,
            attribute_name_placeholders=attribute_name_placeholders,
            attribute_value_placeholders=attribute_value_placeholders,
        )

    def _build_expression(
        self,
        condition,
        attribute_name_placeholders,
        attribute_value_placeholders,
        is_key_condition,
    ):
        expression_dict = condition.get_expression()
        replaced_values = []
        for value in expression_dict['values']:
            # Build the necessary placeholders for that value.
            # Placeholders are built for both attribute names and values.
            replaced_value = self._build_expression_component(
                value,
                attribute_name_placeholders,
                attribute_value_placeholders,
                condition.has_grouped_values,
                is_key_condition,
            )
            replaced_values.append(replaced_value)
        # Fill out the expression using the operator and the
        # values that have been replaced with placeholders.
        return expression_dict['format'].format(
            *replaced_values, operator=expression_dict['operator']
        )

    def _build_expression_component(
        self,
        value,
        attribute_name_placeholders,
        attribute_value_placeholders,
        has_grouped_values,
        is_key_condition,
    ):
        # Continue to recurse if the value is a ConditionBase in order
        # to extract out all parts of the expression.
        if isinstance(value, ConditionBase):
            return self._build_expression(
                value,
                attribute_name_placeholders,
                attribute_value_placeholders,
                is_key_condition,
            )
        # If it is not a ConditionBase, we can recurse no further.
        # So we check if it is an attribute and add placeholders for
        # its name
        elif isinstance(value, AttributeBase):
            if is_key_condition and not isinstance(value, Key):
                raise DynamoDBNeedsKeyConditionError(
                    f'Attribute object {value.name} is of type {type(value)}. '
                    f'KeyConditionExpression only supports Attribute objects '
                    f'of type Key'
                )
            return self._build_name_placeholder(
                value, attribute_name_placeholders
            )
        # If it is anything else, we treat it as a value and thus placeholders
        # are needed for the value.
        else:
            return self._build_value_placeholder(
                value, attribute_value_placeholders, has_grouped_values
            )

    def _build_name_placeholder(self, value, attribute_name_placeholders):
        attribute_name = value.name
        # Figure out which parts of the attribute name that needs replacement.
        attribute_name_parts = ATTR_NAME_REGEX.findall(attribute_name)

        # Add a temporary placeholder for each of these parts.
        placeholder_format = ATTR_NAME_REGEX.sub('%s', attribute_name)
        str_format_args = []
        for part in attribute_name_parts:
            name_placeholder = self._get_name_placeholder()
            self._name_count += 1
            str_format_args.append(name_placeholder)
            # Add the placeholder and value to dictionary of name placeholders.
            attribute_name_placeholders[name_placeholder] = part
        # Replace the temporary placeholders with the designated placeholders.
        return placeholder_format % tuple(str_format_args)

    def _build_value_placeholder(
        self, value, attribute_value_placeholders, has_grouped_values=False
    ):
        # If the values are grouped, we need to add a placeholder for
        # each element inside of the actual value.
        if has_grouped_values:
            placeholder_list = []
            for v in value:
                value_placeholder = self._get_value_placeholder()
                self._value_count += 1
                placeholder_list.append(value_placeholder)
                attribute_value_placeholders[value_placeholder] = v
            # Assuming the values are grouped by parenthesis.
            # IN is the currently the only one that uses this so it maybe
            # needed to be changed in future.
            return f"({', '.join(placeholder_list)})"
        # Otherwise, treat the value as a single value that needs only
        # one placeholder.
        else:
            value_placeholder = self._get_value_placeholder()
            self._value_count += 1
            attribute_value_placeholders[value_placeholder] = value
            return value_placeholder


# Sentinel for a document path that cannot be resolved against an item.
# This is intentionally different from None, which represents the DynamoDB
# NULL type for an attribute that does exist.
class _MissingType:
    def __repr__(self):
        return '<MISSING>'


_MISSING = _MissingType()

_ATTRIBUTE_TYPES = (
    STRING,
    NUMBER,
    BINARY,
    STRING_SET,
    NUMBER_SET,
    BINARY_SET,
    NULL,
    BOOLEAN,
    MAP,
    LIST,
)

# Types that support the ordering comparison operators (<, <=, >, >=).
_ORDERABLE_TYPES = (NUMBER, STRING, BINARY)

_COMPARISON_OPERATORS = {
    '<': operator.lt,
    '<=': operator.le,
    '>': operator.gt,
    '>=': operator.ge,
}


def _get_dynamodb_type(value):
    """Return the DynamoDB type of a Python value.

    Follows the same Python to DynamoDB type conventions as
    :class:`boto3.dynamodb.types.TypeSerializer`, including rejecting float
    values in favor of ``Decimal``. Container types are validated
    recursively so an unsupported nested value is reported instead of
    being matched against silently.
    """
    # bool must be checked before int because True/False are ints in Python.
    if value is None:
        return NULL
    if isinstance(value, bool):
        return BOOLEAN
    if isinstance(value, (int, Decimal)):
        return NUMBER
    if isinstance(value, float):
        raise TypeError(
            'Float types are not supported. Use Decimal types instead.'
        )
    if isinstance(value, str):
        return STRING
    if isinstance(value, (Binary, bytearray, bytes)):
        return BINARY
    if isinstance(value, collections_abc.Set):
        element_types = {_get_dynamodb_type(element) for element in value}
        if len(element_types) == 1:
            (element_type,) = element_types
            if element_type == NUMBER:
                return NUMBER_SET
            if element_type == STRING:
                return STRING_SET
            if element_type == BINARY:
                return BINARY_SET
        raise TypeError(
            f'Unsupported set value {value!r}: DynamoDB sets must be '
            f'non-empty and contain only numbers, strings or binaries.'
        )
    if isinstance(value, collections_abc.Mapping):
        for nested_value in value.values():
            _get_dynamodb_type(nested_value)
        return MAP
    if isinstance(value, (list, tuple)):
        for nested_value in value:
            _get_dynamodb_type(nested_value)
        return LIST
    raise TypeError(f'Unsupported type "{type(value)}" for value "{value}"')


def _as_binary(value):
    if isinstance(value, Binary):
        return value.value
    return bytes(value)


def _values_equal(left, right):
    """Compare two values using DynamoDB equality semantics.

    Values of different DynamoDB types are never equal. In particular a
    BOOL is never equal to a NUMBER, so Python's ``True == 1`` does not
    apply. Container values are compared structurally so that rule holds
    for nested values as well.
    """
    left_type = _get_dynamodb_type(left)
    right_type = _get_dynamodb_type(right)
    if left_type != right_type:
        return False
    if left_type == BINARY:
        return _as_binary(left) == _as_binary(right)
    if left_type == LIST:
        if len(left) != len(right):
            return False
        return all(
            _values_equal(left_value, right_value)
            for left_value, right_value in zip(left, right)
        )
    if left_type == MAP:
        if set(left.keys()) != set(right.keys()):
            return False
        return all(_values_equal(left[key], right[key]) for key in left)
    if left_type == BINARY_SET:
        return {_as_binary(value) for value in left} == {
            _as_binary(value) for value in right
        }
    if left_type in (STRING_SET, NUMBER_SET):
        return set(left) == set(right)
    # NULL, BOOLEAN, NUMBER, STRING: regular Python equality is correct
    # once the DynamoDB types are known to be the same (int/Decimal for
    # NUMBER, and bool is never compared against a number here).
    return left == right


def _compare(left, right, symbol):
    """Apply an ordering comparison using DynamoDB semantics."""
    left_type = _get_dynamodb_type(left)
    right_type = _get_dynamodb_type(right)
    if left_type != right_type or left_type not in _ORDERABLE_TYPES:
        raise TypeError(
            f'The {symbol} operator can only compare two values of the same '
            f'NUMBER (N), STRING (S) or BINARY (B) type, but got values of '
            f'type {left_type} and {right_type}.'
        )
    if left_type == BINARY:
        left = _as_binary(left)
        right = _as_binary(right)
    return _COMPARISON_OPERATORS[symbol](left, right)


def _get_size(value, path):
    """Return the DynamoDB size() of an existing attribute value."""
    value_type = _get_dynamodb_type(value)
    if value_type == STRING:
        return len(value.encode('utf-8'))
    if value_type == BINARY:
        return len(_as_binary(value))
    if value_type in (LIST, MAP, STRING_SET, NUMBER_SET, BINARY_SET):
        return len(value)
    raise TypeError(
        f'The size() function cannot be applied to attribute {path!r} of '
        f'type {value_type}: it supports STRING (S), BINARY (B), LIST (L), '
        f'MAP (M), STRING_SET (SS), NUMBER_SET (NS) and BINARY_SET (BS).'
    )


class ConditionExpressionEvaluator:
    """Locally evaluates DynamoDB condition expression trees against items.

    This is the offline counterpart of :class:`ConditionExpressionBuilder`:
    instead of serializing a condition tree into a ConditionExpression
    string, it evaluates the same tree against an in-memory item (a dict of
    Python values) and returns whether the item matches. It can be used to
    verify Key/Attr filtering logic without contacting DynamoDB.

    Evaluation follows the DynamoDB condition rules:

    * Comparisons (``=``, ``<>``, ``<``, ``<=``, ``>``, ``>=``), ``IN``,
      ``BETWEEN``, ``begins_with``, ``contains``, ``size``,
      ``attribute_type``, ``attribute_exists`` and
      ``attribute_not_exists`` are supported, as well as the ``AND``,
      ``OR`` and ``NOT`` condition combinations.
    * Nested document paths (``a.b``, ``a[0].b``) are resolved against the
      item. A path that cannot be resolved is treated as a missing
      attribute, which is distinct from an existing attribute whose value
      is ``None`` (the DynamoDB NULL type).
    * Equality is type aware: a BOOL and a NUMBER never compare equal even
      though Python considers ``True == 1``.
    * Numbers may be ``int`` or ``decimal.Decimal``, as produced by
      :class:`boto3.dynamodb.types.TypeDeserializer`; ``float`` is rejected.
    * Unsupported Python types or conditions that are invalid for the
      resolved value types raise an exception instead of evaluating to a
      potentially wrong result.

    Neither the condition tree nor the item are modified. A match reported
    by this evaluator only means the local item satisfies the condition; it
    is not a replacement for the expression validation performed by the
    DynamoDB service.
    """

    def evaluate(self, condition, item):
        """Evaluate a condition tree against a single item.

        :type condition: ConditionBase
        :param condition: The condition (e.g. built with ``Key``/``Attr``)
            to evaluate.

        :type item: dict
        :param item: The item to evaluate the condition against.

        :rtype: bool
        :returns: True if the item satisfies the condition, False otherwise.

        :raises DynamoDBNeedsConditionError: If ``condition`` is not a
            ``ConditionBase`` instance.
        :raises TypeError: If the item is not a dict, if it contains
            unsupported value types, or if a condition cannot be applied
            to the resolved value types.
        :raises ValueError: If the condition references a malformed
            document path or an invalid ``attribute_type`` token.
        """
        if not isinstance(condition, ConditionBase):
            raise DynamoDBNeedsConditionError(condition)
        if not isinstance(item, collections_abc.Mapping):
            raise TypeError(
                f'Expected a dict item to evaluate but got value {item!r} '
                f'of type {type(item).__name__}.'
            )
        return self._evaluate_node(condition, item)

    def _evaluate_node(self, node, item):
        handler = self._handlers.get(type(node))
        if handler is None:
            if not isinstance(node, ConditionBase):
                raise DynamoDBNeedsConditionError(node)
            raise TypeError(
                f'Conditions of type {type(node).__name__} cannot be '
                f'evaluated locally.'
            )
        return bool(handler(self, node, item))

    def _eval_comparison(self, condition, item):
        # Both sides are evaluated before checking for a missing attribute,
        # so an invalid literal type is reported even when the attribute is
        # missing.
        left = self._resolve_operand(condition._values[0], item)
        right = self._resolve_operand(condition._values[1], item)
        if left is _MISSING or right is _MISSING:
            # A comparison against an attribute that does not exist always
            # evaluates to false (this also covers size() of a missing
            # attribute).
            return False
        symbol = condition.expression_operator
        if symbol == '=':
            return _values_equal(left, right)
        if symbol == '<>':
            return not _values_equal(left, right)
        return _compare(left, right, symbol)

    def _eval_in(self, condition, item):
        value = self._resolve_operand(condition._values[0], item)
        candidates = condition._values[1]
        if not isinstance(candidates, (list, tuple)):
            raise TypeError(
                f'The IN operator expects a list of values but got '
                f'{candidates!r} of type {type(candidates).__name__}.'
            )
        # Validate every candidate even when the attribute is missing, so
        # unsupported operand types are reported instead of hidden.
        for candidate in candidates:
            _get_dynamodb_type(candidate)
        if value is _MISSING:
            return False
        return any(
            _values_equal(value, candidate) for candidate in candidates
        )

    def _eval_between(self, condition, item):
        value = self._resolve_operand(condition._values[0], item)
        low_value = self._resolve_operand(condition._values[1], item)
        high_value = self._resolve_operand(condition._values[2], item)
        if value is _MISSING:
            return False
        return _compare(value, low_value, '>=') and _compare(
            value, high_value, '<='
        )

    def _eval_begins_with(self, condition, item):
        value = self._resolve_operand(condition._values[0], item)
        prefix = self._resolve_operand(condition._values[1], item)
        if value is _MISSING:
            return False
        value_type = _get_dynamodb_type(value)
        prefix_type = _get_dynamodb_type(prefix)
        if value_type == STRING and prefix_type == STRING:
            return value.startswith(prefix)
        if value_type == BINARY and prefix_type == BINARY:
            return _as_binary(value).startswith(_as_binary(prefix))
        raise TypeError(
            'begins_with can only be applied to two STRING (S) values or '
            f'two BINARY (B) values, but got {value_type} and {prefix_type}.'
        )

    def _eval_contains(self, condition, item):
        value = self._resolve_operand(condition._values[0], item)
        operand = self._resolve_operand(condition._values[1], item)
        if value is _MISSING:
            return False
        value_type = _get_dynamodb_type(value)
        operand_type = _get_dynamodb_type(operand)
        if value_type == STRING:
            if operand_type != STRING:
                raise TypeError(
                    'contains can only check for a substring with a STRING '
                    f'(S) operand, but got {operand_type}.'
                )
            return operand in value
        if value_type == LIST:
            return any(
                _values_equal(element, operand) for element in value
            )
        if value_type == STRING_SET:
            if operand_type != STRING:
                raise TypeError(
                    'contains on a STRING_SET (SS) requires a STRING (S) '
                    f'operand, but got {operand_type}.'
                )
            return operand in value
        if value_type == NUMBER_SET:
            if operand_type != NUMBER:
                raise TypeError(
                    'contains on a NUMBER_SET (NS) requires a NUMBER (N) '
                    f'operand, but got {operand_type}.'
                )
            return operand in value
        if value_type == BINARY_SET:
            if operand_type != BINARY:
                raise TypeError(
                    'contains on a BINARY_SET (BS) requires a BINARY (B) '
                    f'operand, but got {operand_type}.'
                )
            operand = _as_binary(operand)
            return operand in {_as_binary(element) for element in value}
        raise TypeError(
            f'contains is not supported for attributes of type {value_type}; '
            'it supports STRING (S), LIST (L), STRING_SET (SS), '
            'NUMBER_SET (NS) and BINARY_SET (BS).'
        )

    def _eval_size(self, condition, item):
        raise TypeError(
            'A size() condition is not a complete condition and cannot be '
            'evaluated on its own; it must be compared with a number, for '
            'example Attr("a").size().eq(3).'
        )

    def _eval_attribute_type(self, condition, item):
        attribute = condition._values[0]
        attribute_type = condition._values[1]
        if (
            not isinstance(attribute_type, str)
            or attribute_type not in _ATTRIBUTE_TYPES
        ):
            raise ValueError(
                f'Invalid attribute_type {attribute_type!r}; it must be one '
                f'of: {", ".join(_ATTRIBUTE_TYPES)}.'
            )
        value = self._resolve_path(attribute.name, item)
        if value is _MISSING:
            return False
        return _get_dynamodb_type(value) == attribute_type

    def _eval_attribute_exists(self, condition, item):
        attribute = condition._values[0]
        # An existing NULL attribute (value None) still exists.
        return self._resolve_path(attribute.name, item) is not _MISSING

    def _eval_attribute_not_exists(self, condition, item):
        attribute = condition._values[0]
        return self._resolve_path(attribute.name, item) is _MISSING

    def _eval_and(self, condition, item):
        # Evaluate both sides eagerly so an invalid branch is reported
        # instead of being skipped by short-circuiting.
        left_result = self._evaluate_node(condition._values[0], item)
        right_result = self._evaluate_node(condition._values[1], item)
        return left_result and right_result

    def _eval_or(self, condition, item):
        left_result = self._evaluate_node(condition._values[0], item)
        right_result = self._evaluate_node(condition._values[1], item)
        return left_result or right_result

    def _eval_not(self, condition, item):
        return not self._evaluate_node(condition._values[0], item)

    def _resolve_operand(self, operand, item):
        # size() can appear as the operand of another condition, e.g.
        # Attr('a').size().eq(3) builds Equals(Size(Attr('a')), 3). Size is
        # both a ConditionBase and an AttributeBase, so it must be handled
        # first.
        if isinstance(operand, Size):
            attribute = operand._values[0]
            value = self._resolve_path(attribute.name, item)
            if value is _MISSING:
                return _MISSING
            return _get_size(value, attribute.name)
        if isinstance(operand, AttributeBase):
            return self._resolve_path(operand.name, item)
        if isinstance(operand, ConditionBase):
            raise TypeError(
                f'Cannot use a {type(operand).__name__} condition as an '
                f'operand when evaluating a condition locally.'
            )
        # Validate literal operands so unsupported types raise explicitly.
        _get_dynamodb_type(operand)
        return operand

    def _resolve_path(self, path, item):
        current = item
        for kind, token in self._parse_document_path(path):
            if kind == 'name':
                if (
                    isinstance(current, collections_abc.Mapping)
                    and token in current
                ):
                    current = current[token]
                else:
                    return _MISSING
            else:
                if (
                    isinstance(current, (list, tuple))
                    and 0 <= token < len(current)
                ):
                    current = current[token]
                else:
                    return _MISSING
        return current

    @staticmethod
    def _parse_document_path(path):
        """Parse a DynamoDB document path into name and list index tokens."""
        if not isinstance(path, str) or not path:
            raise ValueError(f'Invalid document path: {path!r}')
        tokens = []
        position = 0
        end = len(path)
        while position < end:
            name_start = position
            while position < end and path[position] not in ('.', '[', ']'):
                position += 1
            if position == name_start:
                raise ValueError(f'Invalid document path: {path!r}')
            tokens.append(('name', path[name_start:position]))
            while position < end and path[position] == '[':
                closing = path.find(']', position + 1)
                if closing == -1:
                    raise ValueError(f'Invalid document path: {path!r}')
                index_value = path[position + 1 : closing]
                if not index_value or not all(
                    '0' <= character <= '9' for character in index_value
                ):
                    raise ValueError(f'Invalid document path: {path!r}')
                tokens.append(('index', int(index_value)))
                position = closing + 1
            if position == end:
                break
            if path[position] != '.':
                raise ValueError(f'Invalid document path: {path!r}')
            position += 1
            if position == end or path[position] in ('.', '[', ']'):
                raise ValueError(f'Invalid document path: {path!r}')
        return tokens


ConditionExpressionEvaluator._handlers = {
    Equals: ConditionExpressionEvaluator._eval_comparison,
    NotEquals: ConditionExpressionEvaluator._eval_comparison,
    LessThan: ConditionExpressionEvaluator._eval_comparison,
    LessThanEquals: ConditionExpressionEvaluator._eval_comparison,
    GreaterThan: ConditionExpressionEvaluator._eval_comparison,
    GreaterThanEquals: ConditionExpressionEvaluator._eval_comparison,
    In: ConditionExpressionEvaluator._eval_in,
    Between: ConditionExpressionEvaluator._eval_between,
    BeginsWith: ConditionExpressionEvaluator._eval_begins_with,
    Contains: ConditionExpressionEvaluator._eval_contains,
    Size: ConditionExpressionEvaluator._eval_size,
    AttributeType: ConditionExpressionEvaluator._eval_attribute_type,
    AttributeExists: ConditionExpressionEvaluator._eval_attribute_exists,
    AttributeNotExists: (
        ConditionExpressionEvaluator._eval_attribute_not_exists
    ),
    And: ConditionExpressionEvaluator._eval_and,
    Or: ConditionExpressionEvaluator._eval_or,
    Not: ConditionExpressionEvaluator._eval_not,
}
