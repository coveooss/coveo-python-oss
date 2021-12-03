import pytest
from coveo_testing.markers import UnitTest
from coveo_testing.parametrize import parametrize

from coveo_arnparse import arnparse, ArnException


@UnitTest
@parametrize(
    "arn",
    [
        "arn:aws:firehose:us-east-1:064790157154:deliverystream/ndev-document-status",
        "arn:aws:firehose:us-east-1::deliverystream/ndev-document-status",
        "arn:aws:firehose::064790157154:deliverystream/ndev-document-status",
        "arn:aws:firehose:::deliverystream/ndev-document-status",
        "arn:::::deliverystream/ndev-document-status",
        "arn:aws:firehose:us-east-1:064790157154:deliverystream/ndev-document-status:tag",
        "arn:::::064790157154:deliverystream/ndev-document-status",
    ],
)
def test_arn_parse(arn: str) -> None:
    """Tests the ability to parse correct arns."""
    parsed = arnparse(arn)
    assert arn == str(parsed)


@UnitTest
@parametrize(
    "arn",
    [
        # those have a missing colon
        "arnaws:firehose:us-east-1:064790157154:deliverystream/ndev-document-status",
        "arn:awsfirehose:us-east-1:064790157154:deliverystream/ndev-document-status",
        "arn:aws:firehoseus-east-1:064790157154:deliverystream/ndev-document-status",
        "arn:aws:firehose:us-east-1064790157154:deliverystream/ndev-document-status",
        "arn:aws:firehose:us-east-1:064790157154deliverystream/ndev-document-status",
        "arn::::deliverystream/ndev-document-status",
        # doesn't start with arn
        "arf:aws:firehose:us-east-1::deliverystream/ndev-document-status",
        ":aws:firehose::064790157154:deliverystream/ndev-document-status",
        # not arns
        "deliverystream/ndev-document-status",
        "ndev-document-status",
    ],
)
def test_arn_parse_exception(arn: str) -> None:
    """Make sure an exception is thrown on bad input."""
    with pytest.raises(ArnException):
        arnparse(arn)


@UnitTest
@parametrize(
    ("arn", "expected_type", "expected_id"),
    (
        (
            "arn:aws:ec2:us-east-1:064790157154:launch-template/lt-0a06e01e3851b854e",
            "launch-template",
            "lt-0a06e01e3851b854e",
        ),
        ("arn:aws:ssm:::parameter/path/to/param", "parameter", "path/to/param"),
        ("arn:aws:s3:::bucket-name/path/to/file.jpg", "bucket-name", "path/to/file.jpg"),
        ("arn:aws:cloudwatch:::alarm:my-alarm", "alarm", "my-alarm"),
        ("arn:aws:ecr:::repository/image:tag", "repository", "image:tag"),
        ("arn:aws:apigateway:::something-else", "", ""),
    ),
)
def test_arn_resource_split(arn: str, expected_type: str, expected_id: str) -> None:
    parsed = arnparse(arn)
    assert parsed.resource_type == expected_type
    assert parsed.resource_id == expected_id
