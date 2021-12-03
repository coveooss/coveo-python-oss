# coveo-arnparse

Simple dataclass and parser around Amazon Resource Names (ARNs).

Ref: https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html

## Usage

### Parse from a string
```python
>>> from coveo_arnparse import arnparse
>>> arn = arnparse("arn:aws:sns:us-east-1:123456789012:my_topic")
>>> repr(arn)
Arn(partition='aws', service='sns', region='us-east-1', account='123456789012', resource='my_topic')
>>> str(arn)
"arn:aws:sns:us-east-1:123456789012:my_topic"
>>> arn.resource_type
''
>>> arn.resource_id
''
```

When a `:` or a `/` is in the resource, you can also obtain either parts:

```python
>>> from coveo_arnparse import arnparse
>>> arn = arnparse("arn:aws:ssm:us-east-1:123456789012:parameter/path/key")
>>> arn.resource_type
'parameter'
>>> arn.resource_id
'path/key'
>>> arn.resource
'parameter/path/key'
```


### Create an instance directly

```python
>>> from coveo_arnparse import Arn
>>> Arn(service="s3", resource="my_bucket/path/file.jpg")
Arn(partition='aws', service='s3', region='', account='', resource='my_bucket/path/file.jpg')
```
 