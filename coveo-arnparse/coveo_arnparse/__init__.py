from dataclasses import dataclass
from functools import lru_cache

from typing import Final, Tuple

import re


class ArnException(ValueError):
    """Thrown when an arn cannot be parsed."""


AWS_ARN_REGEX: Final = re.compile(
    r"""
    ^arn:
    (?P<partition>.*?):
    (?P<service>.*?):
    (?P<region>.*?):
    (?P<account>.*?):
    (?P<resource>.*?)
    $
    """,
    re.VERBOSE,
)


@dataclass
class Arn:
    """
    Used to access individual components in an arn.
    https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html
    """

    partition: str = "aws"
    service: str = ""
    region: str = ""
    account: str = ""
    resource: str = ""

    @property
    def resource_type(self) -> str:
        """
        Some services provide 2 components in the resource, split on `:` or `/`.
        Return the suffix, or an empty string otherwise.

        E.g.:
         - "arn:aws:ssm:::parameter/some-param-folder/some-param    -> some-param-folder/some-param
         - "arn:aws:s3:::my-bucket/folder/file.jpg                  -> folder/file.jpg
         - "arn:aws:cloudwatch:::alarm:some-alarm                   -> some-alarm
         - "arn:aws:ec2:::vpc/vpc-12345                             -> vpc-12345
         - 'arn:aws:sns:::my_sns_topic                              -> ""
        """
        return _split_resource_type_and_id(self.resource)[0]

    @property
    def resource_id(self) -> str:
        """
        Some services provide 2 components in the resource, split on `:` or `/`.
        Return the prefix, or an empty string otherwise.

        E.g.:
         - arn:aws:ssm:::parameter/some-param-folder/some-param    -> parameter
         - arn:aws:s3:::my-bucket/folder/file.jpg                  -> my-bucket
         - arn:aws:cloudwatch:::alarm:some-alarm                   -> alarm
         - arn:aws:ec2:::vpc/vpc-12345                             -> vpc
         - arn:aws:sns:::my_sns_topic                              -> ""
        """
        return _split_resource_type_and_id(self.resource)[1]

    def __str__(self) -> str:
        """Return the arn as a string."""
        return ":".join(
            ("arn", self.partition, self.service, self.region, self.account, self.resource)
        )


@lru_cache(maxsize=64)
def _split_resource_type_and_id(resource: str) -> Tuple[str, str]:
    """Splits a resource into its type and id parts. Will return 2 empty strings if this resource cannot be split."""
    first_split_char = next((c for c in resource if c in ":/"), None)
    if not first_split_char:
        return "", ""

    resource_type, resource_id = resource.split(first_split_char, maxsplit=1)
    return resource_type, resource_id


def arnparse(arn: str) -> Arn:
    """Parse an arn string into an Arn instance."""
    if match := AWS_ARN_REGEX.match(arn):
        return Arn(**match.groupdict())
    raise ArnException(f"{arn} cannot be parsed.")
