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
import base64
import copy
import json
from decimal import Decimal

from boto3.dynamodb.table import BatchWriter
from boto3.dynamodb.types import Binary, TypeSerializer
from boto3.exceptions import DynamoDBBatchWriterByteBudgetExceededError
from tests import mock, unittest


class BaseTransformationTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.client = mock.Mock()
        self.client.batch_write_item.return_value = {'UnprocessedItems': {}}
        self.table_name = 'tablename'
        self.flush_amount = 2
        self.batch_writer = BatchWriter(
            self.table_name, self.client, self.flush_amount
        )

    def assert_batch_write_calls_are(self, expected_batch_writes):
        assert self.client.batch_write_item.call_count == len(
            expected_batch_writes
        )
        batch_write_calls = [
            args[1] for args in self.client.batch_write_item.call_args_list
        ]
        assert batch_write_calls == expected_batch_writes

    def test_batch_write_does_not_immediately_write(self):
        self.batch_writer.put_item(Item={'Hash': 'foo'})
        assert not self.client.batch_write_item.called

    def test_batch_write_flushes_at_flush_amount(self):
        self.batch_writer.put_item(Item={'Hash': 'foo1'})
        self.batch_writer.put_item(Item={'Hash': 'foo2'})
        expected = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                ]
            }
        }
        self.assert_batch_write_calls_are([expected])

    def test_multiple_flushes_reset_items_to_put(self):
        self.batch_writer.put_item(Item={'Hash': 'foo1'})
        self.batch_writer.put_item(Item={'Hash': 'foo2'})
        self.batch_writer.put_item(Item={'Hash': 'foo3'})
        self.batch_writer.put_item(Item={'Hash': 'foo4'})
        # We should have two batch calls, one for foo1,foo2 and
        # one for foo3,foo4.
        first_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                ]
            }
        }
        second_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo4'}}},
                ]
            }
        }
        self.assert_batch_write_calls_are([first_batch, second_batch])

    def test_can_handle_puts_and_deletes(self):
        self.batch_writer.put_item(Item={'Hash': 'foo1'})
        self.batch_writer.delete_item(Key={'Hash': 'foo2'})
        expected = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'DeleteRequest': {'Key': {'Hash': 'foo2'}}},
                ]
            }
        }
        self.assert_batch_write_calls_are([expected])

    def test_multiple_batch_calls_with_mixed_deletes(self):
        self.batch_writer.put_item(Item={'Hash': 'foo1'})
        self.batch_writer.delete_item(Key={'Hash': 'foo2'})
        self.batch_writer.delete_item(Key={'Hash': 'foo3'})
        self.batch_writer.put_item(Item={'Hash': 'foo4'})
        first_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'DeleteRequest': {'Key': {'Hash': 'foo2'}}},
                ]
            }
        }
        second_batch = {
            'RequestItems': {
                self.table_name: [
                    {'DeleteRequest': {'Key': {'Hash': 'foo3'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo4'}}},
                ]
            }
        }
        self.assert_batch_write_calls_are([first_batch, second_batch])

    def test_unprocessed_items_added_to_next_batch(self):
        self.client.batch_write_item.side_effect = [
            {
                'UnprocessedItems': {
                    self.table_name: [
                        {'PutRequest': {'Item': {'Hash': 'foo2'}}}
                    ],
                },
            },
            # Then the last response shows that everything went through
            {'UnprocessedItems': {}},
        ]
        self.batch_writer.put_item(Item={'Hash': 'foo1'})
        self.batch_writer.put_item(Item={'Hash': 'foo2'})
        self.batch_writer.put_item(Item={'Hash': 'foo3'})

        # We should have sent two batch requests consisting of 2
        # 2 requests.  foo1,foo2 and foo2,foo3.
        # foo2 is sent twice because the first response has it listed
        # as an unprocessed item which means it needs to be part
        # of the next batch.
        first_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                ]
            }
        }
        second_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                ]
            }
        }
        self.assert_batch_write_calls_are([first_batch, second_batch])

    def test_all_items_flushed_on_exit(self):
        with self.batch_writer as b:
            b.put_item(Item={'Hash': 'foo1'})
        self.assert_batch_write_calls_are(
            [
                {
                    'RequestItems': {
                        self.table_name: [
                            {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                        ]
                    },
                },
            ]
        )

    def test_never_send_more_than_max_batch_size(self):
        # Suppose the server sends backs a response that indicates that
        # all the items were unprocessed.
        self.client.batch_write_item.side_effect = [
            {
                'UnprocessedItems': {
                    self.table_name: [
                        {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                        {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                    ],
                },
            },
            {
                'UnprocessedItems': {
                    self.table_name: [
                        {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                    ],
                },
            },
            {'UnprocessedItems': {}},
        ]
        with BatchWriter(self.table_name, self.client, flush_amount=2) as b:
            b.put_item(Item={'Hash': 'foo1'})
            b.put_item(Item={'Hash': 'foo2'})
            b.put_item(Item={'Hash': 'foo3'})

        # Note how we're never sending more than flush_amount=2.
        first_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                ]
            }
        }
        # Even when the server sends us unprocessed items of 2 elements,
        # we'll still only send 2 at a time, in order.
        second_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                ]
            }
        }
        # And then we still see one more unprocessed item so
        # we need to send another batch.
        third_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                ]
            }
        }
        self.assert_batch_write_calls_are(
            [first_batch, second_batch, third_batch]
        )

    def test_repeated_flushing_on_exit(self):
        # We're going to simulate unprocessed_items
        # returning multiple unprocessed items across calls.
        self.client.batch_write_item.side_effect = [
            {
                'UnprocessedItems': {
                    self.table_name: [
                        {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                        {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                    ],
                },
            },
            {
                'UnprocessedItems': {
                    self.table_name: [
                        {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                    ],
                },
            },
            {'UnprocessedItems': {}},
        ]
        with BatchWriter(self.table_name, self.client, flush_amount=4) as b:
            b.put_item(Item={'Hash': 'foo1'})
            b.put_item(Item={'Hash': 'foo2'})
            b.put_item(Item={'Hash': 'foo3'})
        # So when we exit, we expect three calls.
        # First we try the normal batch write with 3 items:
        first_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                ]
            }
        }
        # Then we see two unprocessed items so we send another batch.
        second_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                ]
            }
        }
        # And then we still see one more unprocessed item so
        # we need to send another batch.
        third_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                ]
            }
        }
        self.assert_batch_write_calls_are(
            [first_batch, second_batch, third_batch]
        )

    def test_auto_dedup_for_dup_requests(self):
        with BatchWriter(
            self.table_name,
            self.client,
            flush_amount=5,
            overwrite_by_pkeys=["pkey", "skey"],
        ) as b:
            # dup 1
            b.put_item(
                Item={'pkey': 'foo1', 'skey': 'bar1', 'other': 'other1'}
            )
            b.put_item(
                Item={'pkey': 'foo1', 'skey': 'bar1', 'other': 'other2'}
            )
            # dup 2
            b.delete_item(
                Key={
                    'pkey': 'foo1',
                    'skey': 'bar2',
                }
            )
            b.put_item(
                Item={'pkey': 'foo1', 'skey': 'bar2', 'other': 'other3'}
            )
            # dup 3
            b.put_item(
                Item={'pkey': 'foo2', 'skey': 'bar2', 'other': 'other3'}
            )
            b.delete_item(
                Key={
                    'pkey': 'foo2',
                    'skey': 'bar2',
                }
            )
            # dup 4
            b.delete_item(
                Key={
                    'pkey': 'foo2',
                    'skey': 'bar3',
                }
            )
            b.delete_item(
                Key={
                    'pkey': 'foo2',
                    'skey': 'bar3',
                }
            )
            # 5
            b.delete_item(
                Key={
                    'pkey': 'foo3',
                    'skey': 'bar3',
                }
            )
            # 2nd batch
            b.put_item(
                Item={'pkey': 'foo1', 'skey': 'bar1', 'other': 'other1'}
            )
            b.put_item(
                Item={'pkey': 'foo1', 'skey': 'bar1', 'other': 'other2'}
            )

        first_batch = {
            'RequestItems': {
                self.table_name: [
                    {
                        'PutRequest': {
                            'Item': {
                                'pkey': 'foo1',
                                'skey': 'bar1',
                                'other': 'other2',
                            }
                        }
                    },
                    {
                        'PutRequest': {
                            'Item': {
                                'pkey': 'foo1',
                                'skey': 'bar2',
                                'other': 'other3',
                            }
                        }
                    },
                    {
                        'DeleteRequest': {
                            'Key': {
                                'pkey': 'foo2',
                                'skey': 'bar2',
                            }
                        }
                    },
                    {
                        'DeleteRequest': {
                            'Key': {
                                'pkey': 'foo2',
                                'skey': 'bar3',
                            }
                        }
                    },
                    {
                        'DeleteRequest': {
                            'Key': {
                                'pkey': 'foo3',
                                'skey': 'bar3',
                            }
                        }
                    },
                ]
            }
        }
        second_batch = {
            'RequestItems': {
                self.table_name: [
                    {
                        'PutRequest': {
                            'Item': {
                                'pkey': 'foo1',
                                'skey': 'bar1',
                                'other': 'other2',
                            }
                        }
                    },
                ]
            }
        }
        self.assert_batch_write_calls_are([first_batch, second_batch])

    def test_added_unsent_request_not_flushed_put(self):
        # If n requests that get sent fail to process where n = flush_amount
        # and at least one more request gets created before the second attempt,
        # then previously if n requests were successful on the next run and
        # returned an empty dict, _item_buffer would be emptied before sending
        # the next batch of n requests
        self.client.batch_write_item.side_effect = [
            {
                'UnprocessedItems': {
                    self.table_name: [
                        {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                        {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                    ],
                },
            },
            {
                'UnprocessedItems': {},
            },
            {
                'UnprocessedItems': {},
            },
        ]
        self.batch_writer.put_item({'Hash': 'foo1'})
        self.batch_writer.put_item({'Hash': 'foo2'})
        self.batch_writer.put_item({'Hash': 'foo3'})
        self.assertIn(
            {'PutRequest': {'Item': {'Hash': 'foo3'}}},
            self.batch_writer._items_buffer,
        )
        batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo1'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo2'}}},
                ]
            }
        }
        final_batch = {
            'RequestItems': {
                self.table_name: [
                    {'PutRequest': {'Item': {'Hash': 'foo3'}}},
                    {'PutRequest': {'Item': {'Hash': 'foo4'}}},
                ]
            }
        }
        # same batch sent twice since all failed on first try
        # and flush_items = 2
        self.assert_batch_write_calls_are([batch, batch])
        # test that the next two items get sent
        self.batch_writer.put_item({'Hash': 'foo4'})
        self.assert_batch_write_calls_are([batch, batch, final_batch])
        # the buffer should be empty now
        self.assertEqual(self.batch_writer._items_buffer, [])

    def test_added_unsent_request_not_flushed_delete(self):
        # If n requests that get sent fail to process where n = flush_amount
        # and at least one more request gets created before the second attempt,
        # then previously if n requests were successful on the next run and
        # returned an empty dict, _item_buffer would be emptied before sending
        # the next batch of n requests
        self.client.batch_write_item.side_effect = [
            {
                'UnprocessedItems': {
                    self.table_name: [
                        {'DeleteRequest': {'Key': {'Hash': 'foo1'}}},
                        {'DeleteRequest': {'Key': {'Hash': 'foo2'}}},
                    ],
                },
            },
            {
                'UnprocessedItems': {},
            },
            {
                'UnprocessedItems': {},
            },
        ]
        self.batch_writer.delete_item({'Hash': 'foo1'})
        self.batch_writer.delete_item({'Hash': 'foo2'})
        self.batch_writer.delete_item({'Hash': 'foo3'})
        self.assertIn(
            {'DeleteRequest': {'Key': {'Hash': 'foo3'}}},
            self.batch_writer._items_buffer,
        )
        batch = {
            'RequestItems': {
                self.table_name: [
                    {'DeleteRequest': {'Key': {'Hash': 'foo1'}}},
                    {'DeleteRequest': {'Key': {'Hash': 'foo2'}}},
                ]
            }
        }
        final_batch = {
            'RequestItems': {
                self.table_name: [
                    {'DeleteRequest': {'Key': {'Hash': 'foo3'}}},
                    {'DeleteRequest': {'Key': {'Hash': 'foo4'}}},
                ]
            }
        }
        # same batch sent twice since all failed on first try
        # and flush_items = 2
        self.assert_batch_write_calls_are([batch, batch])
        # test that the next two items get sent
        self.batch_writer.delete_item({'Hash': 'foo4'})
        self.assert_batch_write_calls_are([batch, batch, final_batch])
        # the buffer should be empty now
        self.assertEqual(self.batch_writer._items_buffer, [])


def _encode_wire_binary(value):
    # Independent re-implementation of botocore's JSON blob handling used
    # by the tests below to compute the expected wire payload size without
    # relying on BatchWriter's own measurement code.
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).strip().decode('utf-8')
    if isinstance(value, list):
        return [_encode_wire_binary(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode_wire_binary(item) for key, item in value.items()}
    return value


def _request_items_byte_size(table_name, requests):
    serializer = TypeSerializer()
    serialized_requests = []
    for request in requests:
        if request.get('PutRequest'):
            values = request['PutRequest']['Item']
            request = {
                'PutRequest': {
                    'Item': {
                        key: serializer.serialize(value)
                        for key, value in values.items()
                    }
                }
            }
        else:
            values = request['DeleteRequest']['Key']
            request = {
                'DeleteRequest': {
                    'Key': {
                        key: serializer.serialize(value)
                        for key, value in values.items()
                    }
                }
            }
        serialized_requests.append(_encode_wire_binary(request))
    request_items = {table_name: serialized_requests}
    return len(json.dumps(request_items).encode('utf-8'))


class TestBatchWriterByteBudget(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.client = mock.Mock()
        self.client.batch_write_item.return_value = {'UnprocessedItems': {}}
        self.table_name = 'tablename'
        self.put = lambda value: {'PutRequest': {'Item': {'Hash': value}}}
        self.delete = lambda value: {'DeleteRequest': {'Key': {'Hash': value}}}

    def batch_writer(
        self,
        flush_amount=25,
        request_byte_budget=None,
        overwrite_by_pkeys=None,
        side_effect=None,
    ):
        if side_effect is not None:
            self.client.batch_write_item.side_effect = side_effect
        return BatchWriter(
            self.table_name,
            self.client,
            flush_amount=flush_amount,
            overwrite_by_pkeys=overwrite_by_pkeys,
            request_byte_budget=request_byte_budget,
        )

    def sent_batches(self):
        return [
            call_args[1]['RequestItems'][self.table_name]
            for call_args in self.client.batch_write_item.call_args_list
        ]

    def test_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            BatchWriter(self.table_name, self.client, request_byte_budget=0)
        with self.assertRaises(ValueError):
            BatchWriter(self.table_name, self.client, request_byte_budget=-1)
        with self.assertRaises(TypeError):
            BatchWriter(
                self.table_name, self.client, request_byte_budget='100'
            )
        with self.assertRaises(TypeError):
            BatchWriter(self.table_name, self.client, request_byte_budget=True)
        self.assertEqual(self.client.batch_write_item.call_count, 0)

    def test_no_budget_keeps_count_only_behavior(self):
        # A float is rejected by TypeSerializer, but without a budget the
        # measurement never runs and the request is handed straight to the
        # client exactly like the historical behavior.
        writer = self.batch_writer(flush_amount=2)
        writer.put_item(Item={'Hash': 1.5})
        writer.put_item(Item={'Hash': 'x' * 10000})
        self.assertEqual(self.client.batch_write_item.call_count, 1)
        self.assertEqual(
            self.sent_batches()[0],
            [
                {'PutRequest': {'Item': {'Hash': 1.5}}},
                {'PutRequest': {'Item': {'Hash': 'x' * 10000}}},
            ],
        )

    def test_count_boundary_still_applies_with_generous_budget(self):
        writer = self.batch_writer(
            flush_amount=2, request_byte_budget=2_000_000
        )
        for value in ('foo1', 'foo2', 'foo3', 'foo4'):
            writer.put_item(Item={'Hash': value})
        self.assertEqual(
            self.sent_batches(),
            [
                [self.put('foo1'), self.put('foo2')],
                [self.put('foo3'), self.put('foo4')],
            ],
        )

    def test_batch_equal_to_budget_is_sent(self):
        one = _request_items_byte_size(self.table_name, [self.put('foo1')])
        two = _request_items_byte_size(
            self.table_name, [self.put('foo1'), self.put('foo2')]
        )
        self.assertGreater(two, one)
        # A budget exactly equal to the two-item payload keeps both buffered
        # together (equality is allowed) until the third item arrives.
        writer = self.batch_writer(request_byte_budget=two)
        writer.put_item(Item={'Hash': 'foo1'})
        writer.put_item(Item={'Hash': 'foo2'})
        self.assertEqual(self.client.batch_write_item.call_count, 0)
        writer.put_item(Item={'Hash': 'foo3'})
        with writer:
            pass
        self.assertEqual(
            self.sent_batches(),
            [
                [self.put('foo1'), self.put('foo2')],
                [self.put('foo3')],
            ],
        )

    def test_one_byte_less_splits_one_earlier(self):
        two = _request_items_byte_size(
            self.table_name, [self.put('foo1'), self.put('foo2')]
        )
        writer = self.batch_writer(request_byte_budget=two - 1)
        writer.put_item(Item={'Hash': 'foo1'})
        writer.put_item(Item={'Hash': 'foo2'})
        writer.put_item(Item={'Hash': 'foo3'})
        with writer:
            pass
        self.assertEqual(
            self.sent_batches(),
            [
                [self.put('foo1')],
                [self.put('foo2')],
                [self.put('foo3')],
            ],
        )

    def test_single_request_over_budget_raises_and_is_never_sent(self):
        one = _request_items_byte_size(self.table_name, [self.put('foo1')])
        writer = self.batch_writer(request_byte_budget=one - 1)
        with self.assertRaises(
            DynamoDBBatchWriterByteBudgetExceededError
        ) as ctx:
            writer.put_item(Item={'Hash': 'foo1'})
        self.assertEqual(ctx.exception.request_size, one)
        self.assertEqual(ctx.exception.byte_budget, one - 1)
        self.assertEqual(ctx.exception.table_name, self.table_name)
        self.assertEqual(self.client.batch_write_item.call_count, 0)
        # The unsendable request is not dropped; it is still buffered.
        self.assertEqual(writer._items_buffer, [self.put('foo1')])

    def test_prefix_flushed_before_oversized_request_raises(self):
        one = _request_items_byte_size(self.table_name, [self.put('foo1')])
        huge = self.put('y' * 1000)
        huge_size = _request_items_byte_size(self.table_name, [huge])
        self.assertGreater(huge_size, one)
        writer = self.batch_writer(request_byte_budget=one)
        writer.put_item(Item={'Hash': 'foo1'})
        # foo1 alone fits (equality), the huge item does not.
        with self.assertRaises(
            DynamoDBBatchWriterByteBudgetExceededError
        ) as ctx:
            writer.put_item(Item={'Hash': 'y' * 1000})
        self.assertEqual(ctx.exception.request_size, huge_size)
        # The fitting prefix was sent exactly once, the huge item was not.
        self.assertEqual(self.sent_batches(), [[self.put('foo1')]])
        self.assertEqual(writer._items_buffer, [huge])

    def test_puts_and_deletes_share_one_budget(self):
        put_request = self.put('foo1')
        delete_request = self.delete('foo2')
        two = _request_items_byte_size(
            self.table_name, [put_request, delete_request]
        )
        writer = self.batch_writer(request_byte_budget=two - 1)
        writer.put_item(Item={'Hash': 'foo1'})
        writer.delete_item(Key={'Hash': 'foo2'})
        with writer:
            pass
        self.assertEqual(
            self.sent_batches(),
            [[put_request], [delete_request]],
        )

    def test_overwrite_by_pkeys_recomputes_budget_after_replace(self):
        big = {'pkey': 'foo1', 'data': 'Z' * 200}
        small = {'pkey': 'foo1', 'data': 'z'}
        big_request = {'PutRequest': {'Item': big}}
        small_request = {'PutRequest': {'Item': small}}
        big_size = _request_items_byte_size(self.table_name, [big_request])
        small_size = _request_items_byte_size(self.table_name, [small_request])
        self.assertGreater(big_size, small_size)
        # The big request alone exactly fits; the small replacement must
        # leave room and never force the big request to be sent.
        writer = self.batch_writer(
            request_byte_budget=big_size, overwrite_by_pkeys=['pkey']
        )
        with writer:
            writer.put_item(Item=big)
            writer.put_item(Item=small)
        self.assertEqual(self.sent_batches(), [[small_request]])

    def test_unprocessed_items_are_resplit_with_same_budget(self):
        # Every single request is exactly ``budget`` bytes, so no two can be
        # sent together even though flush_amount allows two.
        requests = [self.put(value) for value in ('foo1', 'foo2', 'foo3')]
        solo = _request_items_byte_size(self.table_name, [requests[0]])
        self.assertEqual(
            solo,
            _request_items_byte_size(self.table_name, [requests[1]]),
        )
        unprocessed_foo1 = {
            'UnprocessedItems': {self.table_name: [requests[0]]}
        }
        writer = self.batch_writer(
            flush_amount=2,
            request_byte_budget=solo,
            side_effect=[
                unprocessed_foo1,
                {'UnprocessedItems': {}},
                {'UnprocessedItems': {}},
                {'UnprocessedItems': {}},
            ],
        )
        with writer:
            for value in ('foo1', 'foo2', 'foo3'):
                writer.put_item(Item={'Hash': value})
        # The requeued unprocessed foo1 is retried by itself under the same
        # byte budget rather than being packed with another request.
        self.assertEqual(
            self.sent_batches(),
            [
                [requests[0]],
                [requests[1]],
                [requests[0]],
                [requests[2]],
            ],
        )

    def test_real_serialized_bytes_locked_for_special_types(self):
        # Multi-byte characters are ASCII escaped on the wire, numbers keep
        # their serialized string form and binaries are base64 encoded; the
        # budget is compared against these exact UTF-8 byte counts.
        cases = [
            (
                {'Hash': '你好'},
                '{"tablename": [{"PutRequest": {"Item": {"Hash": '
                '{"S": "\\u4f60\\u597d"}}}}]}',
            ),
            (
                {'n': Decimal('3.50')},
                '{"tablename": [{"PutRequest": {"Item": {"n": '
                '{"N": "3.50"}}}}]}',
            ),
            (
                {'b': Binary(b'\x00\x01')},
                '{"tablename": [{"PutRequest": {"Item": {"b": '
                '{"B": "AAE="}}}}]}',
            ),
        ]
        for item, expected_wire in cases:
            request = {'PutRequest': {'Item': item}}
            expected_size = len(expected_wire.encode('utf-8'))
            self.assertEqual(
                _request_items_byte_size(self.table_name, [request]),
                expected_size,
            )
            # Exact fit: nothing is sent yet while only this item is buffered.
            writer = self.batch_writer(request_byte_budget=expected_size)
            writer.put_item(Item=copy.deepcopy(item))
            self.assertEqual(self.client.batch_write_item.call_count, 0)
            # One byte less: the single request is rejected outright.
            writer = self.batch_writer(request_byte_budget=expected_size - 1)
            with self.assertRaises(
                DynamoDBBatchWriterByteBudgetExceededError
            ) as ctx:
                writer.put_item(Item=copy.deepcopy(item))
            self.assertEqual(ctx.exception.request_size, expected_size)

    def test_measurement_does_not_mutate_caller_or_buffer(self):
        item = {
            's': '你好',
            'n': Decimal('3.50'),
            'b': Binary(b'\x00\x01'),
            'bs': {Binary(b'\x02'), Binary(b'\x03')},
            'l': [1, 'two', Decimal('4')],
            'm': {'inner': Binary(b'\x04')},
            'none': None,
            'bool': True,
        }
        original = copy.deepcopy(item)
        budget = _request_items_byte_size(
            self.table_name, [{'PutRequest': {'Item': item}}]
        )
        writer = self.batch_writer(flush_amount=1, request_byte_budget=budget)
        buffered_before = copy.deepcopy(item)
        writer.put_item(Item=item)
        # The caller's Item object was sent as-is (not converted in place)...
        sent_item = self.sent_batches()[0][0]['PutRequest']['Item']
        self.assertIs(sent_item, item)
        # ...and its contents still use Python types rather than wire types.
        self.assertIsInstance(sent_item['n'], Decimal)
        self.assertIsInstance(sent_item['b'], Binary)
        self.assertIsInstance(sent_item['m']['inner'], Binary)
        self.assertEqual(sent_item, original)
        self.assertEqual(item, buffered_before)
        # The buffer is empty after the flush and was never left mutated.
        self.assertEqual(writer._items_buffer, [])
