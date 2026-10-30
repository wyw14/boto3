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
import pytest
from botocore.stub import Stubber

import boto3
from boto3.exceptions import (
    UnknownResourceActionError,
    UnsupportedResourceActionError,
)
from boto3.resources.base import ResourceMeta, ServiceResource
from boto3.resources.model import ResourceModel
from boto3.resources.preview import (
    ORIGIN_CONSTANT,
    ORIGIN_DATA,
    ORIGIN_IDENTIFIER,
    ORIGIN_INPUT,
    preview_resource_action,
)
from tests import mock

DEFINITION = {
    'identifiers': [{'name': 'Url'}],
    'load': {
        'request': {
            'operation': 'DescribeQueue',
            'params': [
                {'target': 'QueueUrl', 'source': 'identifier', 'name': 'Url'}
            ],
        },
        'path': '@',
    },
    'actions': {
        'DoStuff': {
            'request': {
                'operation': 'DoStuff',
                'params': [
                    {
                        'target': 'QueueUrl',
                        'source': 'identifier',
                        'name': 'Url',
                    },
                    {
                        'target': 'AttributeNames[]',
                        'source': 'string',
                        'value': 'All',
                    },
                    {
                        'target': 'Filter.Count',
                        'source': 'integer',
                        'value': 7,
                    },
                    {'target': 'DryRun', 'source': 'boolean', 'value': False},
                ],
            }
        },
        'SendPayload': {
            'request': {
                'operation': 'SendPayload',
                'params': [
                    {'target': 'MessageBody', 'source': 'input'},
                    {
                        'target': 'QueueUrl',
                        'source': 'identifier',
                        'name': 'Url',
                    },
                ],
            }
        },
        'NeedsData': {
            'request': {
                'operation': 'NeedsData',
                'params': [
                    {
                        'target': 'QueueUrl',
                        'source': 'identifier',
                        'name': 'Url',
                    },
                    {
                        'target': 'PublicIp',
                        'source': 'data',
                        'path': 'PublicIp',
                    },
                    {
                        'target': 'NestedId',
                        'source': 'data',
                        'path': 'Attachment.Id',
                    },
                ],
            }
        },
        'BadSource': {
            'request': {
                'operation': 'BadSource',
                'params': [{'target': 'X', 'source': 'mystery'}],
            }
        },
    },
}


class FakeQueue(ServiceResource):
    url = property(lambda self: getattr(self, '_url', None))


MODEL = ResourceModel('Queue', DEFINITION, {'Queue': DEFINITION})
FakeQueue.meta = ResourceMeta(
    'fake-sqs', identifiers=['url'], client=mock.Mock(), resource_model=MODEL
)


def make_queue(data=None):
    queue = FakeQueue(url='http://q.example', client=mock.Mock())
    queue.meta.data = data
    return queue


class TestPreviewModeledParams:
    def test_service_operation_and_merged_params(self):
        queue = make_queue()

        preview = preview_resource_action(
            queue, 'do_stuff', ExtraParam='extra'
        )

        assert preview.service_name == 'fake-sqs'
        assert preview.operation_name == 'do_stuff'
        assert preview.params == {
            'QueueUrl': 'http://q.example',
            'AttributeNames': ['All'],
            'Filter': {'Count': 7},
            'DryRun': False,
            'ExtraParam': 'extra',
        }
        assert preview.is_complete is True
        assert preview.unresolved == []

    def test_origins_mirror_nested_params(self):
        preview = preview_resource_action(make_queue(), 'do_stuff')

        assert preview.origins == {
            'QueueUrl': ORIGIN_IDENTIFIER,
            'AttributeNames': [ORIGIN_CONSTANT],
            'Filter': {'Count': ORIGIN_CONSTANT},
            'DryRun': ORIGIN_CONSTANT,
        }

    def test_input_source_only_present_when_supplied(self):
        preview = preview_resource_action(make_queue(), 'send_payload')

        assert 'MessageBody' not in preview.params
        assert 'MessageBody' not in preview.origins

        preview = preview_resource_action(
            make_queue(), 'send_payload', MessageBody='hi'
        )

        assert preview.params['MessageBody'] == 'hi'
        assert preview.params['QueueUrl'] == 'http://q.example'
        assert preview.origins['MessageBody'] == ORIGIN_INPUT
        assert preview.origins['QueueUrl'] == ORIGIN_IDENTIFIER

    def test_caller_overrides_top_level_model_param(self):
        # kwargs override is shallow: a whole model-built subtree is
        # replaced rather than deep-merged, matching the real action.
        preview = preview_resource_action(
            make_queue(),
            'do_stuff',
            QueueUrl='overridden',
            Filter={'Count': 9, 'Other': 1},
        )

        assert preview.params['QueueUrl'] == 'overridden'
        assert preview.params['Filter'] == {'Count': 9, 'Other': 1}
        assert preview.origins['QueueUrl'] == ORIGIN_INPUT
        assert preview.origins['Filter'] == {
            'Count': ORIGIN_INPUT,
            'Other': ORIGIN_INPUT,
        }
        assert preview.origins['AttributeNames'] == [ORIGIN_CONSTANT]


class TestPreviewDataSources:
    def test_resolves_data_from_cache_without_loading(self):
        queue = make_queue(
            data={'PublicIp': '1.2.3.4', 'Attachment': {'Id': 'eni-1'}}
        )
        queue.load = mock.Mock(
            side_effect=AssertionError('load must not be called')
        )

        preview = preview_resource_action(queue, 'needs_data')

        assert queue.load.called is False
        assert preview.unresolved == []
        assert preview.is_complete is True
        assert preview.params == {
            'QueueUrl': 'http://q.example',
            'PublicIp': '1.2.3.4',
            'NestedId': 'eni-1',
        }
        assert preview.origins['PublicIp'] == ORIGIN_DATA
        assert preview.origins['NestedId'] == ORIGIN_DATA

    def test_unloaded_data_targets_are_listed_not_fabricated(self):
        queue = make_queue(data=None)
        queue.load = mock.Mock(
            side_effect=AssertionError('load must not be called')
        )

        preview = preview_resource_action(queue, 'needs_data')

        assert queue.load.called is False
        assert preview.is_complete is False
        assert preview.unresolved == ['PublicIp', 'NestedId']
        # Resolvable params are still present; unresolved ones are not
        # fabricated.
        assert preview.params == {'QueueUrl': 'http://q.example'}
        assert preview.origins == {'QueueUrl': ORIGIN_IDENTIFIER}

    def test_loaded_cache_with_missing_path_resolves_to_none(self):
        # This matches get_data_member: with data loaded, a missing path
        # simply resolves to None rather than being "unresolved".
        queue = make_queue(data={'PublicIp': None})

        preview = preview_resource_action(queue, 'needs_data')

        assert preview.unresolved == []
        assert preview.params['PublicIp'] is None
        assert preview.params['NestedId'] is None
        assert preview.origins['PublicIp'] == ORIGIN_DATA


class TestPreviewSideEffects:
    def test_does_not_touch_client_or_cache(self):
        queue = make_queue(data={'PublicIp': '1.2.3.4'})
        original_data = queue.meta.data

        preview_resource_action(queue, 'needs_data')

        assert queue.meta.client.method_calls == []
        assert queue.meta.data is original_data

    def test_mutating_preview_params_does_not_affect_resource_cache(self):
        queue = make_queue(
            data={
                'PublicIp': '1.2.3.4',
                'Attachment': {'Id': 'eni-1', 'Tags': ['a']},
            }
        )

        preview = preview_resource_action(queue, 'needs_data')
        preview.params['NestedId'] = 'mutated'
        preview.params['New'] = {'nested': []}
        preview.params['New']['nested'].append('x')

        assert queue.meta.data == {
            'PublicIp': '1.2.3.4',
            'Attachment': {'Id': 'eni-1', 'Tags': ['a']},
        }

    def test_mutating_preview_params_does_not_affect_caller_kwargs(self):
        kwargs = {'Filter': {'Count': 1, 'List': [1, 2]}, 'Top': ['a']}
        queue = make_queue()

        preview = preview_resource_action(queue, 'do_stuff', **kwargs)
        preview.params['Filter']['Count'] = 999
        preview.params['Filter']['List'].append(3)
        preview.params['Top'].append('b')

        assert kwargs == {
            'Filter': {'Count': 1, 'List': [1, 2]},
            'Top': ['a'],
        }


class TestPreviewErrors:
    def test_unknown_action_raises(self):
        with pytest.raises(UnknownResourceActionError) as exc_info:
            preview_resource_action(make_queue(), 'no_such_action')

        error = exc_info.value
        assert error.action_name == 'no_such_action'
        assert 'do_stuff' in error.available_actions

    def test_custom_injected_method_raises(self):
        def custom_thing(self, **kwargs):
            raise AssertionError('must never be called')

        FakeQueue.custom_thing = custom_thing
        try:
            with pytest.raises(UnsupportedResourceActionError) as exc_info:
                preview_resource_action(make_queue(), 'custom_thing')

            assert exc_info.value.action_name == 'custom_thing'
        finally:
            del FakeQueue.custom_thing

    def test_non_action_property_raises(self):
        FakeQueue.some_collection = property(lambda self: None)
        try:
            with pytest.raises(UnsupportedResourceActionError):
                preview_resource_action(make_queue(), 'some_collection')
        finally:
            del FakeQueue.some_collection

    def test_unsupported_source_type_raises(self):
        with pytest.raises(NotImplementedError):
            preview_resource_action(make_queue(), 'bad_source')

    @pytest.mark.parametrize('action_name', ['load', 'reload'])
    def test_load_actions_are_previewable(self, action_name):
        queue = make_queue()

        preview = preview_resource_action(queue, action_name)

        assert preview.operation_name == 'describe_queue'
        assert preview.params == {'QueueUrl': 'http://q.example'}
        assert preview.origins == {'QueueUrl': ORIGIN_IDENTIFIER}
        assert queue.meta.client.method_calls == []


def _offline_session(service):
    return boto3.resource(
        service,
        region_name='us-east-1',
        aws_access_key_id='preview',
        aws_secret_access_key='preview',
    )


class TestPreviewWithRealModels:
    def test_sqs_queue_send_message(self):
        sqs = _offline_session('sqs')
        queue = sqs.Queue('http://queue.example')

        preview = preview_resource_action(
            queue, 'send_message', MessageBody='hi'
        )

        assert preview.service_name == 'sqs'
        assert preview.operation_name == 'send_message'
        assert preview.params == {
            'QueueUrl': 'http://queue.example',
            'MessageBody': 'hi',
        }
        assert preview.origins == {
            'QueueUrl': ORIGIN_IDENTIFIER,
            'MessageBody': ORIGIN_INPUT,
        }
        assert preview.unresolved == []

    def test_s3_object_load(self):
        s3 = _offline_session('s3')
        obj = s3.Object('bucket', 'key')

        preview = preview_resource_action(obj, 'load')

        assert preview.service_name == 's3'
        assert preview.operation_name == 'head_object'
        assert preview.params == {'Bucket': 'bucket', 'Key': 'key'}
        assert preview.origins == {
            'Bucket': ORIGIN_IDENTIFIER,
            'Key': ORIGIN_IDENTIFIER,
        }

    def test_s3_custom_injected_method_unsupported(self):
        s3 = _offline_session('s3')
        obj = s3.Object('bucket', 'key')

        with pytest.raises(UnsupportedResourceActionError):
            preview_resource_action(obj, 'download_file')

    def test_s3_bucket_custom_load_unsupported(self):
        s3 = _offline_session('s3')
        bucket = s3.Bucket('bucket')

        with pytest.raises(UnsupportedResourceActionError):
            preview_resource_action(bucket, 'load')

    def test_ec2_data_dependent_action_unresolved(self):
        ec2 = _offline_session('ec2')
        address = ec2.ClassicAddress('1.2.3.4')

        preview = preview_resource_action(address, 'release')

        assert preview.operation_name == 'release_address'
        assert preview.params == {}
        assert preview.unresolved == ['PublicIp']
        assert preview.is_complete is False

    def test_ec2_unknown_action(self):
        ec2 = _offline_session('ec2')
        address = ec2.ClassicAddress('1.2.3.4')

        with pytest.raises(UnknownResourceActionError):
            preview_resource_action(address, 'not_an_action')

    def test_preview_matches_real_sqs_call_params(self):
        sqs = _offline_session('sqs')
        stubber = Stubber(sqs.meta.client)
        queue = sqs.Queue('http://queue.example')
        kwargs = {'MessageBody': 'hi', 'DelaySeconds': 5}
        expected_params = {
            'QueueUrl': 'http://queue.example',
            'MessageBody': 'hi',
            'DelaySeconds': 5,
        }
        stubber.add_response('send_message', {}, expected_params)

        # Building the preview never touches the client, so the queued
        # stub response is left untouched (and can still be consumed by
        # the real call below).
        preview = preview_resource_action(queue, 'send_message', **kwargs)
        assert preview.params == expected_params
        assert len(stubber._queue) == 1

        # The real action must send exactly the previewed parameters;
        # the Stubber raises if the shapes or values do not match.
        with stubber:
            queue.send_message(**kwargs)
        stubber.assert_no_pending_responses()

    def test_preview_matches_real_sqs_load_list_param(self):
        sqs = _offline_session('sqs')
        stubber = Stubber(sqs.meta.client)
        queue = sqs.Queue('http://queue.example')
        expected_params = {
            'QueueUrl': 'http://queue.example',
            'AttributeNames': ['All'],
        }
        stubber.add_response(
            'get_queue_attributes', {'Attributes': {}}, expected_params
        )

        preview = preview_resource_action(queue, 'load')

        assert preview.params == expected_params
        assert preview.origins == {
            'QueueUrl': ORIGIN_IDENTIFIER,
            'AttributeNames': [ORIGIN_CONSTANT],
        }

        with stubber:
            queue.load()
        stubber.assert_no_pending_responses()

    def test_preview_matches_real_ec2_data_call_params(self):
        ec2 = _offline_session('ec2')
        stubber = Stubber(ec2.meta.client)
        address = ec2.ClassicAddress('1.2.3.4')
        address.meta.data = {'PublicIp': '1.2.3.4'}
        expected_params = {'PublicIp': '1.2.3.4'}
        stubber.add_response('release_address', {}, expected_params)

        preview = preview_resource_action(address, 'release')

        assert preview.params == expected_params
        assert preview.origins == {'PublicIp': ORIGIN_DATA}

        with stubber:
            address.release()
        stubber.assert_no_pending_responses()
