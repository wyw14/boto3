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
import copy
from decimal import Decimal

import pytest

from boto3.dynamodb.conditions import (
    And,
    Attr,
    AttributeExists,
    AttributeNotExists,
    AttributeType,
    BeginsWith,
    Between,
    ConditionExpressionBuilder,
    ConditionExpressionEvaluator,
    Contains,
    Equals,
    GreaterThan,
    GreaterThanEquals,
    In,
    Key,
    LessThan,
    LessThanEquals,
    Not,
    NotEquals,
    Or,
    Size,
)
from boto3.dynamodb.types import Binary
from boto3.exceptions import (
    DynamoDBNeedsConditionError,
    DynamoDBNeedsKeyConditionError,
    DynamoDBOperationNotSupportedError,
)
from tests import unittest


class TestK(unittest.TestCase):
    def setUp(self):
        self.attr = Key('mykey')
        self.attr2 = Key('myotherkey')
        self.value = 'foo'
        self.value2 = 'foo2'

    def test_and(self):
        with pytest.raises(DynamoDBOperationNotSupportedError, match=r'AND'):
            self.attr & self.attr2

    def test_or(self):
        with pytest.raises(DynamoDBOperationNotSupportedError, match=r'OR'):
            self.attr | self.attr2

    def test_not(self):
        with pytest.raises(DynamoDBOperationNotSupportedError, match=r'NOT'):
            ~self.attr

    def test_eq(self):
        assert self.attr.eq(self.value) == Equals(self.attr, self.value)

    def test_lt(self):
        assert self.attr.lt(self.value) == LessThan(self.attr, self.value)

    def test_lte(self):
        assert self.attr.lte(self.value) == LessThanEquals(
            self.attr, self.value
        )

    def test_gt(self):
        assert self.attr.gt(self.value) == GreaterThan(self.attr, self.value)

    def test_gte(self):
        assert self.attr.gte(self.value) == GreaterThanEquals(
            self.attr, self.value
        )

    def test_begins_with(self):
        assert self.attr.begins_with(self.value) == BeginsWith(
            self.attr, self.value
        )

    def test_between(self):
        assert self.attr.between(self.value, self.value2) == Between(
            self.attr, self.value, self.value2
        )

    def test_attribute_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        assert self.attr is not attr_copy
        assert self.attr == attr_copy

    def test_eq_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.eq(self.value)
        comp2 = attr_copy.eq(self.value)
        assert comp == comp2

    def test_eq_inequality(self):
        attr_copy = copy.deepcopy(self.attr)
        assert self.attr.eq(self.value) != attr_copy.eq(self.value2)

    def test_lt_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.lt(self.value)
        comp2 = attr_copy.lt(self.value)
        assert comp == comp2

    def test_lte_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.lte(self.value)
        comp2 = attr_copy.lte(self.value)
        assert comp == comp2

    def test_gt_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.gt(self.value)
        comp2 = attr_copy.gt(self.value)
        assert comp == comp2

    def test_gte_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.gte(self.value)
        comp2 = attr_copy.gte(self.value)
        assert comp == comp2

    def test_begins_with_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.begins_with(self.value)
        comp2 = attr_copy.begins_with(self.value)
        assert comp == comp2

    def test_between_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.between(self.value, self.value2)
        comp2 = attr_copy.between(self.value, self.value2)
        assert comp == comp2


class TestA(TestK):
    def setUp(self):
        self.attr = Attr('mykey')
        self.attr2 = Attr('myotherkey')
        self.value = 'foo'
        self.value2 = 'foo2'

    def test_ne(self):
        assert self.attr.ne(self.value) == NotEquals(self.attr, self.value)

    def test_is_in(self):
        assert self.attr.is_in([self.value]) == In(self.attr, [self.value])

    def test_exists(self):
        assert self.attr.exists() == AttributeExists(self.attr)

    def test_not_exists(self):
        assert self.attr.not_exists() == AttributeNotExists(self.attr)

    def test_contains(self):
        assert self.attr.contains(self.value) == Contains(
            self.attr, self.value
        )

    def test_size(self):
        assert self.attr.size() == Size(self.attr)

    def test_attribute_type(self):
        assert self.attr.attribute_type(self.value) == AttributeType(
            self.attr, self.value
        )

    def test_ne_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.ne(self.value)
        comp2 = attr_copy.ne(self.value)
        assert comp == comp2

    def test_is_in_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.is_in([self.value])
        comp2 = attr_copy.is_in([self.value])
        assert comp == comp2

    def test_exists_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.exists()
        comp2 = attr_copy.exists()
        assert comp == comp2

    def test_not_exists_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.not_exists()
        comp2 = attr_copy.not_exists()
        assert comp == comp2

    def test_contains_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.contains(self.value)
        comp2 = attr_copy.contains(self.value)
        assert comp == comp2

    def test_size_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.size()
        comp2 = attr_copy.size()
        assert comp == comp2

    def test_attribute_type_equality(self):
        attr_copy = copy.deepcopy(self.attr)
        comp = self.attr.attribute_type(self.value)
        comp2 = attr_copy.attribute_type(self.value)
        assert comp == comp2


class TestConditions(unittest.TestCase):
    def setUp(self):
        self.value = Attr('mykey')
        self.value2 = 'foo'

    def build_and_assert_expression(
        self, condition, reference_expression_dict
    ):
        expression_dict = condition.get_expression()
        assert expression_dict == reference_expression_dict

    def test_equal_operator(self):
        cond1 = Equals(self.value, self.value2)
        cond2 = Equals(self.value, self.value2)
        assert cond1 == cond2

    def test_equal_operator_type(self):
        cond1 = Equals(self.value, self.value2)
        cond2 = NotEquals(self.value, self.value2)
        assert cond1 != cond2

    def test_equal_operator_value(self):
        cond1 = Equals(self.value, self.value2)
        cond2 = Equals(self.value, self.value)
        assert cond1 != cond2

    def test_not_equal_operator(self):
        cond1 = Equals(self.value, self.value2)
        cond2 = NotEquals(self.value, self.value)
        assert cond1 != cond2

    def test_and_operator(self):
        cond1 = Equals(self.value, self.value2)
        cond2 = Equals(self.value, self.value2)
        assert cond1 & cond2 == And(cond1, cond2)

    def test_and_operator_throws_excepetion(self):
        cond1 = Equals(self.value, self.value2)
        with pytest.raises(DynamoDBOperationNotSupportedError, match=r'AND'):
            cond1 & self.value2

    def test_or_operator(self):
        cond1 = Equals(self.value, self.value2)
        cond2 = Equals(self.value, self.value2)
        assert cond1 | cond2 == Or(cond1, cond2)

    def test_or_operator_throws_excepetion(self):
        cond1 = Equals(self.value, self.value2)
        with pytest.raises(DynamoDBOperationNotSupportedError, match=r'OR'):
            cond1 | self.value2

    def test_not_operator(self):
        cond1 = Equals(self.value, self.value2)
        assert ~cond1 == Not(cond1)

    def test_eq(self):
        self.build_and_assert_expression(
            Equals(self.value, self.value2),
            {
                'format': '{0} {operator} {1}',
                'operator': '=',
                'values': (self.value, self.value2),
            },
        )

    def test_ne(self):
        self.build_and_assert_expression(
            NotEquals(self.value, self.value2),
            {
                'format': '{0} {operator} {1}',
                'operator': '<>',
                'values': (self.value, self.value2),
            },
        )

    def test_lt(self):
        self.build_and_assert_expression(
            LessThan(self.value, self.value2),
            {
                'format': '{0} {operator} {1}',
                'operator': '<',
                'values': (self.value, self.value2),
            },
        )

    def test_lte(self):
        self.build_and_assert_expression(
            LessThanEquals(self.value, self.value2),
            {
                'format': '{0} {operator} {1}',
                'operator': '<=',
                'values': (self.value, self.value2),
            },
        )

    def test_gt(self):
        self.build_and_assert_expression(
            GreaterThan(self.value, self.value2),
            {
                'format': '{0} {operator} {1}',
                'operator': '>',
                'values': (self.value, self.value2),
            },
        )

    def test_gte(self):
        self.build_and_assert_expression(
            GreaterThanEquals(self.value, self.value2),
            {
                'format': '{0} {operator} {1}',
                'operator': '>=',
                'values': (self.value, self.value2),
            },
        )

    def test_in(self):
        cond = In(self.value, (self.value2))
        self.build_and_assert_expression(
            cond,
            {
                'format': '{0} {operator} {1}',
                'operator': 'IN',
                'values': (self.value, (self.value2)),
            },
        )
        assert cond.has_grouped_values

    def test_bet(self):
        self.build_and_assert_expression(
            Between(self.value, self.value2, 'foo2'),
            {
                'format': '{0} {operator} {1} AND {2}',
                'operator': 'BETWEEN',
                'values': (self.value, self.value2, 'foo2'),
            },
        )

    def test_beg(self):
        self.build_and_assert_expression(
            BeginsWith(self.value, self.value2),
            {
                'format': '{operator}({0}, {1})',
                'operator': 'begins_with',
                'values': (self.value, self.value2),
            },
        )

    def test_cont(self):
        self.build_and_assert_expression(
            Contains(self.value, self.value2),
            {
                'format': '{operator}({0}, {1})',
                'operator': 'contains',
                'values': (self.value, self.value2),
            },
        )

    def test_ae(self):
        self.build_and_assert_expression(
            AttributeExists(self.value),
            {
                'format': '{operator}({0})',
                'operator': 'attribute_exists',
                'values': (self.value,),
            },
        )

    def test_ane(self):
        self.build_and_assert_expression(
            AttributeNotExists(self.value),
            {
                'format': '{operator}({0})',
                'operator': 'attribute_not_exists',
                'values': (self.value,),
            },
        )

    def test_size(self):
        self.build_and_assert_expression(
            Size(self.value),
            {
                'format': '{operator}({0})',
                'operator': 'size',
                'values': (self.value,),
            },
        )

    def test_size_can_use_attr_methods(self):
        size = Size(self.value)
        self.build_and_assert_expression(
            size.eq(self.value),
            {
                'format': '{0} {operator} {1}',
                'operator': '=',
                'values': (size, self.value),
            },
        )

    def test_size_can_use_and(self):
        size = Size(self.value)
        ae = AttributeExists(self.value)
        self.build_and_assert_expression(
            size & ae,
            {
                'format': '({0} {operator} {1})',
                'operator': 'AND',
                'values': (size, ae),
            },
        )

    def test_attribute_type(self):
        self.build_and_assert_expression(
            AttributeType(self.value, self.value2),
            {
                'format': '{operator}({0}, {1})',
                'operator': 'attribute_type',
                'values': (self.value, self.value2),
            },
        )

    def test_and(self):
        cond1 = Equals(self.value, self.value2)
        cond2 = Equals(self.value, self.value2)
        and_cond = And(cond1, cond2)
        self.build_and_assert_expression(
            and_cond,
            {
                'format': '({0} {operator} {1})',
                'operator': 'AND',
                'values': (cond1, cond2),
            },
        )

    def test_or(self):
        cond1 = Equals(self.value, self.value2)
        cond2 = Equals(self.value, self.value2)
        or_cond = Or(cond1, cond2)
        self.build_and_assert_expression(
            or_cond,
            {
                'format': '({0} {operator} {1})',
                'operator': 'OR',
                'values': (cond1, cond2),
            },
        )

    def test_not(self):
        cond = Equals(self.value, self.value2)
        not_cond = Not(cond)
        self.build_and_assert_expression(
            not_cond,
            {
                'format': '({operator} {0})',
                'operator': 'NOT',
                'values': (cond,),
            },
        )


class TestConditionExpressionBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = ConditionExpressionBuilder()

    def assert_condition_expression_build(
        self,
        condition,
        ref_string,
        ref_names,
        ref_values,
        is_key_condition=False,
    ):
        exp_string, names, values = self.builder.build_expression(
            condition, is_key_condition=is_key_condition
        )
        assert exp_string == ref_string
        assert names == ref_names
        assert values == ref_values

    def test_bad_input(self):
        a = Attr('myattr')
        with pytest.raises(DynamoDBNeedsConditionError):
            self.builder.build_expression(a)

    def test_build_expression_eq(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.eq('foo'), '#n0 = :v0', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

    def test_reset(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.eq('foo'), '#n0 = :v0', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

        self.assert_condition_expression_build(
            a.eq('foo'), '#n1 = :v1', {'#n1': 'myattr'}, {':v1': 'foo'}
        )

        self.builder.reset()
        self.assert_condition_expression_build(
            a.eq('foo'), '#n0 = :v0', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

    def test_build_expression_lt(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.lt('foo'), '#n0 < :v0', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

    def test_build_expression_lte(self):
        a1 = Attr('myattr')
        self.assert_condition_expression_build(
            a1.lte('foo'), '#n0 <= :v0', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

    def test_build_expression_gt(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.gt('foo'), '#n0 > :v0', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

    def test_build_expression_gte(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.gte('foo'), '#n0 >= :v0', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

    def test_build_expression_begins_with(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.begins_with('foo'),
            'begins_with(#n0, :v0)',
            {'#n0': 'myattr'},
            {':v0': 'foo'},
        )

    def test_build_expression_between(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.between('foo', 'foo2'),
            '#n0 BETWEEN :v0 AND :v1',
            {'#n0': 'myattr'},
            {':v0': 'foo', ':v1': 'foo2'},
        )

    def test_build_expression_ne(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.ne('foo'), '#n0 <> :v0', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

    def test_build_expression_in(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.is_in([1, 2, 3]),
            '#n0 IN (:v0, :v1, :v2)',
            {'#n0': 'myattr'},
            {':v0': 1, ':v1': 2, ':v2': 3},
        )

    def test_build_expression_exists(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.exists(), 'attribute_exists(#n0)', {'#n0': 'myattr'}, {}
        )

    def test_build_expression_not_exists(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.not_exists(), 'attribute_not_exists(#n0)', {'#n0': 'myattr'}, {}
        )

    def test_build_contains(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.contains('foo'),
            'contains(#n0, :v0)',
            {'#n0': 'myattr'},
            {':v0': 'foo'},
        )

    def test_build_size(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.size(), 'size(#n0)', {'#n0': 'myattr'}, {}
        )

    def test_build_size_with_other_conditons(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.size().eq(5), 'size(#n0) = :v0', {'#n0': 'myattr'}, {':v0': 5}
        )

    def test_build_attribute_type(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            a.attribute_type('foo'),
            'attribute_type(#n0, :v0)',
            {'#n0': 'myattr'},
            {':v0': 'foo'},
        )

    def test_build_and(self):
        a = Attr('myattr')
        a2 = Attr('myattr2')
        self.assert_condition_expression_build(
            a.eq('foo') & a2.eq('bar'),
            '(#n0 = :v0 AND #n1 = :v1)',
            {'#n0': 'myattr', '#n1': 'myattr2'},
            {':v0': 'foo', ':v1': 'bar'},
        )

    def test_build_or(self):
        a = Attr('myattr')
        a2 = Attr('myattr2')
        self.assert_condition_expression_build(
            a.eq('foo') | a2.eq('bar'),
            '(#n0 = :v0 OR #n1 = :v1)',
            {'#n0': 'myattr', '#n1': 'myattr2'},
            {':v0': 'foo', ':v1': 'bar'},
        )

    def test_build_not(self):
        a = Attr('myattr')
        self.assert_condition_expression_build(
            ~a.eq('foo'), '(NOT #n0 = :v0)', {'#n0': 'myattr'}, {':v0': 'foo'}
        )

    def test_build_attribute_with_attr_value(self):
        a = Attr('myattr')
        value = Attr('myreference')
        self.assert_condition_expression_build(
            a.eq(value),
            '#n0 = #n1',
            {'#n0': 'myattr', '#n1': 'myreference'},
            {},
        )

    def test_build_with_is_key_condition(self):
        k = Key('myattr')
        self.assert_condition_expression_build(
            k.eq('foo'),
            '#n0 = :v0',
            {'#n0': 'myattr'},
            {':v0': 'foo'},
            is_key_condition=True,
        )

    def test_build_with_is_key_condition_throws_error(self):
        a = Attr('myattr')
        with pytest.raises(DynamoDBNeedsKeyConditionError):
            self.builder.build_expression(a.eq('foo'), is_key_condition=True)

    def test_build_attr_map(self):
        a = Attr('MyMap.MyKey')
        self.assert_condition_expression_build(
            a.eq('foo'),
            '#n0.#n1 = :v0',
            {'#n0': 'MyMap', '#n1': 'MyKey'},
            {':v0': 'foo'},
        )

    def test_build_attr_list(self):
        a = Attr('MyList[0]')
        self.assert_condition_expression_build(
            a.eq('foo'), '#n0[0] = :v0', {'#n0': 'MyList'}, {':v0': 'foo'}
        )

    def test_build_nested_attr_map_list(self):
        a = Attr('MyMap.MyList[2].MyElement')
        self.assert_condition_expression_build(
            a.eq('foo'),
            '#n0.#n1[2].#n2 = :v0',
            {'#n0': 'MyMap', '#n1': 'MyList', '#n2': 'MyElement'},
            {':v0': 'foo'},
        )

    def test_build_double_nested_and_or(self):
        a = Attr('myattr')
        a2 = Attr('myattr2')
        self.assert_condition_expression_build(
            (a.eq('foo') & a2.eq('foo2')) | (a.eq('bar') & a2.eq('bar2')),
            '((#n0 = :v0 AND #n1 = :v1) OR (#n2 = :v2 AND #n3 = :v3))',
            {
                '#n0': 'myattr',
                '#n1': 'myattr2',
                '#n2': 'myattr',
                '#n3': 'myattr2',
            },
            {':v0': 'foo', ':v1': 'foo2', ':v2': 'bar', ':v3': 'bar2'},
        )


class TestConditionExpressionEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = ConditionExpressionEvaluator()
        self.item = {
            'pk': 'user-1',
            'sort': '2024',
            'age': 30,
            'score': Decimal('9.5'),
            'active': True,
            'enabled': False,
            'name': 'alice',
            'empty': '',
            'data': b'hello world',
            'tags': ['admin', 'dev'],
            'nums': [1, 2, 3],
            'flags': [True, False],
            'string_set': {'a', 'b'},
            'number_set': {1, 2, 3},
            'binary_set': {b'x', b'y'},
            'meta': {
                'nested': {'value': Decimal('7'), 'name': 'deep'},
                'list': [{'id': 'first'}, {'id': 'second'}],
                'empty_list': [],
            },
            'matrix': [[0, 1], [2, 3]],
            'null_attr': None,
            'unicode': '\u4f60\u597d',
        }

    def assert_matches(self, condition, item=None):
        item = self.item if item is None else item
        # The convenience method and the evaluator class must agree and both
        # return an actual bool.
        result = self.evaluator.evaluate(condition, item)
        assert result is True
        assert condition.evaluate(item) is True

    def assert_does_not_match(self, condition, item=None):
        item = self.item if item is None else item
        result = self.evaluator.evaluate(condition, item)
        assert result is False
        assert condition.evaluate(item) is False

    # -- Key/Attr equality -------------------------------------------------

    def test_key_eq_match(self):
        self.assert_matches(Key('pk').eq('user-1'))

    def test_key_eq_no_match(self):
        self.assert_does_not_match(Key('pk').eq('user-2'))

    def test_eq_string_case_sensitive(self):
        self.assert_does_not_match(Attr('name').eq('Alice'))

    def test_ne_string(self):
        self.assert_matches(Attr('name').ne('bob'))
        self.assert_does_not_match(Attr('name').ne('alice'))

    def test_numeric_comparisons(self):
        self.assert_matches(Attr('age').lt(31))
        self.assert_matches(Attr('age').lte(30))
        self.assert_matches(Attr('age').gt(29))
        self.assert_matches(Attr('age').gte(30))
        self.assert_does_not_match(Attr('age').lt(30))
        self.assert_does_not_match(Attr('age').gt(30))

    def test_numeric_comparisons_with_decimal(self):
        self.assert_matches(Attr('score').eq(Decimal('9.5')))
        self.assert_matches(Attr('score').eq(Decimal('9.50')))
        self.assert_matches(Attr('score').gt(9))
        self.assert_matches(Attr('score').lte(Decimal('10')))
        self.assert_does_not_match(Attr('score').gt(Decimal('9.5')))

    def test_bool_is_not_number(self):
        # Python considers True == 1, but DynamoDB BOOL and NUMBER are
        # distinct types.
        self.assert_does_not_match(Attr('active').eq(1))
        self.assert_does_not_match(Attr('age').eq(True))
        self.assert_matches(Attr('active').ne(1))
        self.assert_matches(Attr('active').eq(True))
        self.assert_matches(Attr('enabled').eq(False))

    def test_bool_number_distinction_inside_containers(self):
        # Python considers [True, False] == [1, 0] and {'b': True} ==
        # {'b': 1}, but DynamoDB BOOL and NUMBER stay distinct inside
        # containers as well.
        self.assert_does_not_match(Attr('nums').eq([1, True, 3]))
        self.assert_does_not_match(Attr('flags').eq([1, 0]))
        self.assert_does_not_match(
            Attr('meta.nested').eq(
                {'value': True, 'name': 'deep'}
            )
        )

    def test_equality_across_different_types_is_false(self):
        self.assert_does_not_match(Attr('name').eq(30))
        self.assert_does_not_match(Attr('age').eq('30'))
        self.assert_does_not_match(Attr('active').eq('true'))
        self.assert_does_not_match(Attr('null_attr').eq(False))

    def test_null_equality(self):
        self.assert_matches(Attr('null_attr').eq(None))
        self.assert_does_not_match(Attr('name').eq(None))

    def test_ordering_mismatched_types_raises(self):
        with pytest.raises(TypeError, match='operator'):
            Attr('active').lt(1).evaluate(self.item)
        with pytest.raises(TypeError, match='operator'):
            Attr('name').gt(0).evaluate(self.item)
        with pytest.raises(TypeError, match='operator'):
            Attr('null_attr').lte(None).evaluate(self.item)
        with pytest.raises(TypeError, match='operator'):
            Attr('tags').gt(['a']).evaluate(self.item)

    def test_string_ordering(self):
        self.assert_matches(Attr('name').gte('alice'))
        self.assert_matches(Attr('name').lt('bob'))

    def test_binary_equality(self):
        self.assert_matches(Attr('data').eq(b'hello world'))
        self.assert_matches(Attr('data').eq(bytearray(b'hello world')))
        self.assert_matches(Attr('data').eq(Binary(b'hello world')))
        self.assert_does_not_match(Attr('data').eq(b'hello'))

    def test_binary_ordering(self):
        self.assert_matches(Attr('data').gt(b'aaaaa'))
        self.assert_matches(Attr('data').lte(b'zzzzz'))

    def test_map_and_list_structural_equality(self):
        self.assert_matches(
            Attr('meta').eq(
                {
                    'nested': {'value': Decimal('7'), 'name': 'deep'},
                    'list': ({'id': 'first'}, {'id': 'second'}),
                    'empty_list': [],
                }
            )
        )
        self.assert_does_not_match(Attr('tags').eq(['admin']))
        self.assert_does_not_match(
            Attr('meta').eq(
                {
                    'nested': {'value': Decimal('8'), 'name': 'deep'},
                    'list': [{'id': 'first'}, {'id': 'second'}],
                    'empty_list': [],
                }
            )
        )

    # -- missing attributes ------------------------------------------------

    def test_missing_attribute_comparisons_are_false(self):
        self.assert_does_not_match(Attr('missing').eq('x'))
        self.assert_does_not_match(Attr('missing').ne('x'))
        self.assert_does_not_match(Attr('missing').lt(1))
        self.assert_does_not_match(Attr('missing').gte(1))

    def test_missing_nested_path_is_false(self):
        self.assert_does_not_match(Attr('meta.nested.missing').eq('x'))
        self.assert_does_not_match(Attr('meta.missing.value').eq('x'))
        self.assert_does_not_match(Attr('meta.nested.value.deep').eq('x'))
        self.assert_does_not_match(Attr('tags[5]').eq('admin'))
        self.assert_does_not_match(Attr('meta.list[2].id').eq('third'))
        self.assert_does_not_match(Attr('meta.list[0].missing').eq('x'))
        self.assert_does_not_match(Attr('matrix[0][2]').eq(1))
        self.assert_does_not_match(Attr('meta.nested[0]').exists())
        self.assert_does_not_match(Attr('tags.foo').exists())

    # -- IN ----------------------------------------------------------------

    def test_in_match(self):
        self.assert_matches(Attr('name').is_in(['bob', 'alice']))
        self.assert_matches(Attr('age').is_in([29, 30]))
        self.assert_matches(Attr('age').is_in([Decimal('30')]))

    def test_in_no_match(self):
        self.assert_does_not_match(Attr('name').is_in(['bob', 'carol']))

    def test_in_type_aware(self):
        self.assert_does_not_match(Attr('active').is_in([1]))
        self.assert_does_not_match(Attr('age').is_in([True]))

    def test_in_missing_attribute(self):
        self.assert_does_not_match(Attr('missing').is_in(['x']))

    def test_in_empty_list(self):
        self.assert_does_not_match(Attr('name').is_in([]))

    def test_in_with_tuple(self):
        self.assert_matches(Attr('name').is_in(('bob', 'alice')))

    def test_in_invalid_candidates_raises(self):
        with pytest.raises(TypeError, match='IN operator'):
            Attr('name').is_in('alice').evaluate(self.item)

    # -- BETWEEN -----------------------------------------------------------

    def test_between_inclusive(self):
        self.assert_matches(Attr('age').between(30, 40))
        self.assert_matches(Attr('age').between(20, 30))
        self.assert_does_not_match(Attr('age').between(31, 40))

    def test_between_strings_and_decimal(self):
        self.assert_matches(Attr('sort').between('2023', '2025'))
        self.assert_matches(Attr('score').between(9, Decimal('10')))

    def test_between_missing_attribute(self):
        self.assert_does_not_match(Attr('missing').between(1, 2))

    def test_between_type_mismatch_raises(self):
        with pytest.raises(TypeError, match='operator'):
            Attr('active').between(False, True).evaluate(self.item)

    # -- begins_with -------------------------------------------------------

    def test_begins_with_string(self):
        self.assert_matches(Attr('name').begins_with('al'))
        self.assert_does_not_match(Attr('name').begins_with('Al'))
        self.assert_does_not_match(Attr('name').begins_with('bob'))

    def test_begins_with_binary(self):
        self.assert_matches(Attr('data').begins_with(b'hello'))
        self.assert_matches(
            Attr('data').begins_with(Binary(b'hello'))
        )
        self.assert_does_not_match(Attr('data').begins_with(b'world'))

    def test_begins_with_missing_attribute(self):
        self.assert_does_not_match(Attr('missing').begins_with('x'))

    def test_begins_with_wrong_types_raises(self):
        with pytest.raises(TypeError, match='begins_with'):
            Attr('age').begins_with(1).evaluate(self.item)
        with pytest.raises(TypeError, match='begins_with'):
            Attr('name').begins_with(b'al').evaluate(self.item)

    # -- contains ----------------------------------------------------------

    def test_contains_string_substring(self):
        self.assert_matches(Attr('name').contains('lic'))
        self.assert_does_not_match(Attr('name').contains('xyz'))

    def test_contains_list_element(self):
        self.assert_matches(Attr('tags').contains('dev'))
        self.assert_does_not_match(Attr('tags').contains('owner'))
        self.assert_matches(Attr('nums').contains(2))
        self.assert_matches(Attr('nums').contains(Decimal('2')))
        self.assert_matches(Attr('flags').contains(True))
        self.assert_does_not_match(Attr('flags').contains(1))
        self.assert_matches(
            Attr('meta.list').contains({'id': 'first'})
        )
        self.assert_does_not_match(
            Attr('meta.list').contains({'id': 'missing'})
        )

    def test_contains_sets(self):
        self.assert_matches(Attr('string_set').contains('a'))
        self.assert_does_not_match(Attr('string_set').contains('c'))
        self.assert_matches(Attr('number_set').contains(3))
        self.assert_matches(Attr('number_set').contains(Decimal('1')))
        self.assert_matches(Attr('binary_set').contains(b'x'))
        self.assert_matches(
            Attr('binary_set').contains(Binary(b'y'))
        )
        self.assert_does_not_match(Attr('binary_set').contains(b'z'))

    def test_contains_missing_attribute(self):
        self.assert_does_not_match(Attr('missing').contains('x'))

    def test_contains_unsupported_attribute_type_raises(self):
        with pytest.raises(TypeError, match='contains'):
            Attr('age').contains(1).evaluate(self.item)
        with pytest.raises(TypeError, match='contains'):
            Attr('meta').contains('nested').evaluate(self.item)
        with pytest.raises(TypeError, match='contains'):
            Attr('null_attr').contains(None).evaluate(self.item)

    def test_contains_wrong_operand_type_raises(self):
        with pytest.raises(TypeError, match='STRING'):
            Attr('name').contains(1).evaluate(self.item)
        with pytest.raises(TypeError, match='NUMBER'):
            Attr('number_set').contains('1').evaluate(self.item)
        with pytest.raises(TypeError, match='BINARY'):
            Attr('binary_set').contains('x').evaluate(self.item)

    # -- size --------------------------------------------------------------

    def test_size_string_uses_utf8_byte_length(self):
        self.assert_matches(Attr('name').size().eq(5))
        self.assert_matches(Attr('unicode').size().eq(6))
        self.assert_does_not_match(Attr('unicode').size().eq(2))

    def test_size_binary_list_map_set(self):
        self.assert_matches(Attr('data').size().eq(11))
        self.assert_matches(Attr('tags').size().eq(2))
        self.assert_matches(Attr('meta').size().eq(3))
        self.assert_matches(Attr('number_set').size().eq(3))
        self.assert_matches(Attr('meta.empty_list').size().eq(0))

    def test_size_comparisons(self):
        self.assert_matches(Attr('tags').size().gte(2))
        self.assert_matches(Attr('tags').size().lt(3))
        self.assert_does_not_match(Attr('tags').size().eq(3))
        self.assert_matches(Attr('name').size().between(1, 10))

    def test_size_missing_attribute_is_false(self):
        self.assert_does_not_match(Attr('missing').size().eq(0))
        self.assert_does_not_match(Attr('missing').size().gt(0))

    def test_size_unsupported_type_raises(self):
        with pytest.raises(TypeError, match='size'):
            Attr('age').size().eq(30).evaluate(self.item)
        with pytest.raises(TypeError, match='size'):
            Attr('active').size().gt(0).evaluate(self.item)
        with pytest.raises(TypeError, match='size'):
            Attr('null_attr').size().eq(0).evaluate(self.item)

    def test_bare_size_condition_raises(self):
        with pytest.raises(TypeError, match='complete condition'):
            Attr('name').size().evaluate(self.item)

    # -- attribute_type / exists ------------------------------------------

    def test_attribute_types(self):
        for name, dynamodb_type in [
            ('name', 'S'),
            ('age', 'N'),
            ('score', 'N'),
            ('data', 'B'),
            ('string_set', 'SS'),
            ('number_set', 'NS'),
            ('binary_set', 'BS'),
            ('null_attr', 'NULL'),
            ('active', 'BOOL'),
            ('meta', 'M'),
            ('tags', 'L'),
        ]:
            self.assert_matches(Attr(name).attribute_type(dynamodb_type))

    def test_attribute_type_does_not_match(self):
        self.assert_does_not_match(Attr('name').attribute_type('N'))
        self.assert_does_not_match(Attr('active').attribute_type('N'))
        self.assert_does_not_match(Attr('age').attribute_type('BOOL'))

    def test_attribute_type_missing_attribute(self):
        self.assert_does_not_match(Attr('missing').attribute_type('S'))

    def test_attribute_type_invalid_token_raises(self):
        with pytest.raises(ValueError, match='attribute_type'):
            Attr('name').attribute_type('X').evaluate(self.item)
        with pytest.raises(ValueError, match='attribute_type'):
            Attr('name').attribute_type(1).evaluate(self.item)

    def test_exists_and_not_exists_distinguish_null(self):
        self.assert_matches(Attr('null_attr').exists())
        self.assert_does_not_match(Attr('null_attr').not_exists())
        self.assert_does_not_match(Attr('missing').exists())
        self.assert_matches(Attr('missing').not_exists())
        self.assert_matches(Attr('meta.nested.value').exists())
        self.assert_does_not_match(Attr('meta.nested.missing').exists())

    # -- nested document paths --------------------------------------------

    def test_nested_map_path(self):
        self.assert_matches(Attr('meta.nested.name').eq('deep'))
        self.assert_matches(
            Attr('meta.nested.value').gte(7)
        )

    def test_nested_list_index_path(self):
        self.assert_matches(Attr('tags[0]').eq('admin'))
        self.assert_matches(
            Attr('meta.list[1].id').eq('second')
        )
        self.assert_matches(Attr('matrix[1][0]').eq(2))

    def test_malformed_paths_raise(self):
        for path in [
            '',
            'a..b',
            '.a',
            'a.',
            'a[',
            'a[]',
            'a[x]',
            'a]',
            'a.[0]',
            'a[0]..b',
        ]:
            with pytest.raises(ValueError, match='document path'):
                Attr(path).exists().evaluate(self.item)

    # -- AND / OR / NOT ----------------------------------------------------

    def test_and_combination(self):
        self.assert_matches(
            Attr('age').gt(20) & Attr('name').begins_with('al')
        )
        self.assert_does_not_match(
            Attr('age').gt(20) & Attr('name').begins_with('bo')
        )

    def test_or_combination(self):
        self.assert_matches(
            Attr('age').lt(10) | Attr('active').eq(True)
        )
        self.assert_does_not_match(
            Attr('age').lt(10) | Attr('active').eq(False)
        )

    def test_not_combination(self):
        self.assert_matches(~Attr('name').eq('bob'))
        self.assert_does_not_match(~Attr('name').eq('alice'))

    def test_not_missing_comparison_is_true(self):
        self.assert_matches(~Attr('missing').eq(1))
        self.assert_matches(
            Attr('missing').not_exists() | Attr('missing').ne(1)
        )

    def test_nested_and_or_not(self):
        condition = (
            (Attr('age').gte(30) & Attr('active').eq(True))
            | ~Attr('name').begins_with('z')
        )
        self.assert_matches(condition)
        condition = ~(
            Attr('name').eq('alice') | Attr('name').eq('bob')
        )
        self.assert_does_not_match(condition)

    def test_unsupported_branch_is_still_reported(self):
        # Both branches of an AND are evaluated so an invalid branch cannot
        # be hidden by the other branch being false.
        condition = Attr('missing').eq(1) & Attr('active').lt(1)
        with pytest.raises(TypeError):
            condition.evaluate(self.item)

    # -- error handling ----------------------------------------------------

    def test_non_condition_raises(self):
        with pytest.raises(DynamoDBNeedsConditionError):
            self.evaluator.evaluate(Attr('pk'), self.item)
        with pytest.raises(DynamoDBNeedsConditionError):
            self.evaluator.evaluate('pk = :v', self.item)

    def test_non_mapping_item_raises(self):
        with pytest.raises(TypeError, match='dict item'):
            Key('pk').eq('x').evaluate([])
        with pytest.raises(TypeError, match='dict item'):
            Key('pk').eq('x').evaluate('not-a-dict')

    def test_float_values_raise(self):
        with pytest.raises(TypeError, match='Float'):
            Attr('score').eq(9.5).evaluate({'score': Decimal('9.5')})
        with pytest.raises(TypeError, match='Float'):
            Attr('x').eq(1).evaluate({'x': 1.0})
        with pytest.raises(TypeError, match='Float'):
            Attr('x').eq(1).evaluate({'x': [1.0]})

    def test_unsupported_python_type_raises(self):
        with pytest.raises(TypeError, match='Unsupported type'):
            Attr('x').eq(1).evaluate({'x': object()})
        with pytest.raises(TypeError, match='Unsupported set'):
            Attr('x').contains(1).evaluate({'x': {1, 'a'}})
        with pytest.raises(TypeError, match='Unsupported set'):
            Attr('x').contains('y').evaluate({'x': set()})

    def test_invalid_candidate_type_in_in_raises_even_when_missing(self):
        with pytest.raises(TypeError, match='Float'):
            Attr('missing').is_in([1.0]).evaluate(self.item)

    # -- non-mutation ------------------------------------------------------

    def test_evaluation_does_not_mutate_item(self):
        item = copy.deepcopy(self.item)
        condition = (
            Attr('meta.nested.value').gt(1)
            & Attr('meta.list[1].id').begins_with('sec')
            & Attr('number_set').contains(2)
        )
        condition.evaluate(item)
        assert item == self.item

    def test_evaluation_does_not_mutate_condition(self):
        condition = Attr('name').eq('alice') & Attr('age').gt(20)
        snapshot = copy.deepcopy(condition)
        for _ in range(3):
            assert condition.evaluate(self.item) is True
        assert condition == snapshot
        assert condition.get_expression() == snapshot.get_expression()

    def test_evaluator_can_be_reused(self):
        condition = Key('pk').eq('user-1')
        for _ in range(3):
            assert self.evaluator.evaluate(condition, self.item) is True
