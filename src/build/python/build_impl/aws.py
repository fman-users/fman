from fbs import SETTINGS
from fbs_runtime.platform import is_windows
from os.path import join, relpath
from time import time

import os

def upload_to_s3(src_path, dest_path):
	_get_aws_bucket().upload_file(
		src_path, dest_path, ExtraArgs={'ACL': 'public-read'}
	)

def upload_directory_contents(dir_path, dest_path):
	result = []
	for file_path in _iter_files_recursive(dir_path):
		file_relpath = relpath(file_path, dir_path)
		if is_windows():
			file_relpath = file_relpath.replace('\\', '/')
		file_dest = dest_path + '/' + file_relpath
		upload_to_s3(file_path, file_dest)
		result.append(file_dest)
	return result

def _iter_files_recursive(dir_path):
	for subdir_path, dir_names, file_names in os.walk(dir_path):
		for file_name in file_names:
			yield join(subdir_path, file_name)

def list_files_on_s3(prefix=''):
	return [
		o.key for o in _get_aws_bucket().objects.filter(Prefix=prefix)
	]

def download_file_from_s3(src_path, dest_path):
	_get_aws_bucket().download_file(src_path, dest_path)

def create_cloudfront_invalidation(items):
	import boto3
	cloudfront = boto3.client('cloudfront', **_get_aws_credentials())
	cloudfront.create_invalidation(
		DistributionId=SETTINGS['aws_distribution_id'],
		InvalidationBatch={
			'Paths': {
				'Quantity': len(items),
				'Items': ['/' + item for item in items]
			},
			'CallerReference': '%s-%s' % (int(time()), id(items))
		}
	)

def _get_aws_bucket():
	import boto3
	s3 = boto3.resource('s3', **_get_aws_credentials())
	return s3.Bucket(SETTINGS['aws_bucket'])

def _get_aws_credentials():
	return {
		'aws_access_key_id': SETTINGS['aws_access_key_id'],
		'aws_secret_access_key': SETTINGS['aws_secret_access_key']
	}