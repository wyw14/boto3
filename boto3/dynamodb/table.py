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
import logging

from boto3.dynamodb.types import TypeSerializer
from boto3.exceptions import DynamoDBBatchWriterByteBudgetExceededError

logger = logging.getLogger(__name__)


def register_table_methods(base_classes, **kwargs):
    base_classes.insert(0, TableResource)


# This class can be used to add any additional methods we want
# onto a table resource.  Ideally to avoid creating a new
# base class for every method we can just update this
# class instead.  Just be sure to move the bulk of the
# actual method implementation to another class.
class TableResource:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def batch_writer(self, overwrite_by_pkeys=None, request_byte_budget=None):
        """Create a batch writer object.

        This method creates a context manager for writing
        objects to Amazon DynamoDB in batch.

        The batch writer will automatically handle buffering and sending items
        in batches.  In addition, the batch writer will also automatically
        handle any unprocessed items and resend them as needed.  All you need
        to do is call ``put_item`` for any items you want to add, and
        ``delete_item`` for any items you want to delete.

        Example usage::

            with table.batch_writer() as batch:
                for _ in range(1000000):
                    batch.put_item(Item={'HashKey': '...',
                                         'Otherstuff': '...'})
                # You can also delete_items in a batch.
                batch.delete_item(Key={'HashKey': 'SomeHashKey'})

        :type overwrite_by_pkeys: list(string)
        :param overwrite_by_pkeys: De-duplicate request items in buffer
            if match new request item on specified primary keys. i.e
            ``["partition_key1", "sort_key2", "sort_key3"]``

        :type request_byte_budget: int
        :param request_byte_budget: Optionally limit the size of each
            ``batch_write_item`` request, in uncompressed JSON UTF-8 bytes.
            The budget is measured against the serialized ``RequestItems``
            payload exactly as the client sends it: Python types are first
            converted to DynamoDB types (for example ``Decimal`` values are
            stringified and binary values are base64 encoded), the table name
            and JSON structure overhead are included, and multi-byte string
            content counts against the JSON body the client produces. Python
            character counts and raw object sizes are not used. Buffered
            requests are taken in insertion order and a request is included
            while the running total is less than or equal to the budget.
            Batches still contain at most the usual 25 requests. If a single
            request already exceeds the budget, an error is raised and the
            request is neither sent nor dropped. When de-duplicating with
            ``overwrite_by_pkeys`` and when ``UnprocessedItems`` are requeued,
            the budget is recomputed against the current requests. When not
            provided, only the 25 request limit applies, matching the default
            behavior.

        """
        return BatchWriter(
            self.name,
            self.meta.client,
            overwrite_by_pkeys=overwrite_by_pkeys,
            request_byte_budget=request_byte_budget,
        )


class BatchWriter:
    """Automatically handle batch writes to DynamoDB for a single table."""

    def __init__(
        self,
        table_name,
        client,
        flush_amount=25,
        overwrite_by_pkeys=None,
        request_byte_budget=None,
    ):
        """

        :type table_name: str
        :param table_name: The name of the table.  The class handles
            batch writes to a single table.

        :type client: ``botocore.client.Client``
        :param client: A botocore client.  Note this client
            **must** have the dynamodb customizations applied
            to it for transforming AttributeValues into the
            wire protocol.  What this means in practice is that
            you need to use a client that comes from a DynamoDB
            resource if you're going to instantiate this class
            directly, i.e
            ``boto3.resource('dynamodb').Table('foo').meta.client``.

        :type flush_amount: int
        :param flush_amount: The number of items to keep in
            a local buffer before sending a batch_write_item
            request to DynamoDB.

        :type overwrite_by_pkeys: list(string)
        :param overwrite_by_pkeys: De-duplicate request items in buffer
            if match new request item on specified primary keys. i.e
            ``["partition_key1", "sort_key2", "sort_key3"]``

        :type request_byte_budget: int
        :param request_byte_budget: Optional upper bound, in uncompressed
            JSON UTF-8 bytes, on the serialized ``RequestItems`` payload of
            each ``batch_write_item`` request (including the table name and
            JSON structure overhead). See
            ``TableResource.batch_writer`` for the full semantics.

        """
        self._table_name = table_name
        self._client = client
        self._items_buffer = []
        self._flush_amount = flush_amount
        self._overwrite_by_pkeys = overwrite_by_pkeys
        if request_byte_budget is not None:
            # ``bool`` is a subclass of ``int`` but is not a valid budget.
            if isinstance(request_byte_budget, bool) or not isinstance(
                request_byte_budget, int
            ):
                raise TypeError(
                    'request_byte_budget must be a positive integer or None, '
                    f'got {request_byte_budget!r}'
                )
            if request_byte_budget <= 0:
                raise ValueError(
                    'request_byte_budget must be a positive integer, got '
                    f'{request_byte_budget}'
                )
        self._request_byte_budget = request_byte_budget
        self._serializer = TypeSerializer()

    def put_item(self, Item):
        self._add_request_and_process({'PutRequest': {'Item': Item}})

    def delete_item(self, Key):
        self._add_request_and_process({'DeleteRequest': {'Key': Key}})

    def _add_request_and_process(self, request):
        if self._overwrite_by_pkeys:
            self._remove_dup_pkeys_request_if_any(request)
        self._items_buffer.append(request)
        self._flush_if_needed()

    def _remove_dup_pkeys_request_if_any(self, request):
        pkey_values_new = self._extract_pkey_values(request)
        for item in self._items_buffer:
            if self._extract_pkey_values(item) == pkey_values_new:
                self._items_buffer.remove(item)
                logger.debug(
                    "With overwrite_by_pkeys enabled, skipping request:%s",
                    item,
                )

    def _extract_pkey_values(self, request):
        if request.get('PutRequest'):
            return [
                request['PutRequest']['Item'][key]
                for key in self._overwrite_by_pkeys
            ]
        elif request.get('DeleteRequest'):
            return [
                request['DeleteRequest']['Key'][key]
                for key in self._overwrite_by_pkeys
            ]
        return None

    def _flush_if_needed(self):
        if not self._items_buffer:
            return
        batch_len = self._select_batch_len()
        if len(self._items_buffer) >= self._flush_amount or (
            self._request_byte_budget is not None
            and batch_len < len(self._items_buffer)
        ):
            self._flush(batch_len)
            # After sending a byte-bounded prefix, an item may be waiting at
            # the head of the buffer that cannot fit in any request. Fail
            # fast instead of silently keeping an unsendable request until
            # the context exits.
            if self._request_byte_budget is not None and self._items_buffer:
                self._select_batch_len()

    def _select_batch_len(self):
        """Return the number of buffered head requests to send next.

        The selection honors both the item count limit and, when configured,
        the serialized request byte budget in buffer order. A
        ``DynamoDBBatchWriterByteBudgetExceededError`` is raised when the head
        request alone (with the required table/JSON structure) does not fit.
        """
        max_len = min(self._flush_amount, len(self._items_buffer))
        if self._request_byte_budget is None:
            return max_len
        serialized_requests = []
        for index in range(max_len):
            serialized_requests.append(
                self._serialize_request(self._items_buffer[index])
            )
            request_size = self._measure_request_items(serialized_requests)
            if request_size > self._request_byte_budget:
                if index == 0:
                    raise DynamoDBBatchWriterByteBudgetExceededError(
                        self._table_name,
                        request_size,
                        self._request_byte_budget,
                    )
                # The request at ``index`` does not fit; the prefix built so
                # far is the next batch.
                return index
        return max_len

    def _serialize_request(self, request):
        """Convert one buffered WriteRequest to its wire DynamoDB shape.

        A deep copy is serialized so measuring the byte budget never mutates
        the caller's items or the buffered requests.
        """
        request_copy = copy.deepcopy(request)
        if request_copy.get('PutRequest'):
            attribute_values = request_copy['PutRequest']['Item']
        else:
            attribute_values = request_copy['DeleteRequest']['Key']
        for key, value in list(attribute_values.items()):
            attribute_values[key] = self._serializer.serialize(value)
        return self._encode_binary_values(request_copy)

    def _encode_binary_values(self, value):
        # botocore's JSON protocol serializer base64 encodes blob shapes
        # before calling json.dumps. After the DynamoDB type conversion,
        # binary data only appears at ``B`` / ``BS`` leaves, so mirroring the
        # blob conversion here keeps the measured payload byte for byte
        # identical to the request body the client actually sends.
        if isinstance(value, (bytes, bytearray)):
            return base64.b64encode(value).strip().decode('utf-8')
        if isinstance(value, list):
            return [self._encode_binary_values(item) for item in value]
        if isinstance(value, dict):
            return {
                key: self._encode_binary_values(item)
                for key, item in value.items()
            }
        return value

    def _measure_request_items(self, serialized_requests):
        # Match botocore's JSON serializer exactly: plain json.dumps (which
        # escapes non-ASCII via ensure_ascii and uses the same separators),
        # encoded to uncompressed UTF-8 bytes. The table name key and the
        # surrounding map/list JSON structure are part of the measurement.
        request_items = {self._table_name: serialized_requests}
        return len(json.dumps(request_items).encode('utf-8'))

    def _flush(self, batch_len=None):
        if batch_len is None:
            batch_len = self._select_batch_len()
        items_to_send = self._items_buffer[:batch_len]
        self._items_buffer = self._items_buffer[batch_len:]
        response = self._client.batch_write_item(
            RequestItems={self._table_name: items_to_send}
        )
        unprocessed_items = response['UnprocessedItems']
        if not unprocessed_items:
            unprocessed_items = {}
        item_list = unprocessed_items.get(self._table_name, [])
        # Any unprocessed_items are immediately added to the
        # next batch we send.
        self._items_buffer.extend(item_list)
        logger.debug(
            "Batch write sent %s, unprocessed: %s",
            len(items_to_send),
            len(self._items_buffer),
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        # When we exit, we need to keep flushing whatever's left
        # until there's nothing left in our items buffer.
        while self._items_buffer:
            self._flush()
