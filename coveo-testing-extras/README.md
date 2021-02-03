# coveo-testing-extras

Contains extra testing tools without dependency restrictions.


## temporary resource implementation: Docker Container

The docker container temporary resource can be used to prepare short-lived containers.

- Supports building from a dockerfile
- Supports pulling images
- Can signal on AWS ECR logout
- Dynamic port mapping retrieval
- Saves log output before removing the container


### Automatic AWS ECR login example

Here's how you can enhance `TemporaryDockerContainerResource` with automatic ECR login:

```python
from base64 import b64decode

import boto3
from coveo_testing_extras.temporary_resource.docker_container import (
    TemporaryDockerContainerResource, 
    ECRLogoutException,
    get_docker_client
)

class WithECR(TemporaryDockerContainerResource):
    def obtain_image(self) -> None:
        try:
            super().obtain_image()
        except ECRLogoutException:
            self._do_ecr_login()
            super().obtain_image()

    def _do_ecr_login(self) -> None:
        """ Performs an ecr login through awscli. """
        assert self.ecr_region
        ecr = boto3.client('ecr')
        account_id, *_ = self.image_name.split('.')
        assert account_id.isdigit()
        authorization_data = ecr.get_authorization_token(registryIds=[account_id])['authorizationData'][0]
        username, password = b64decode(authorization_data['authorizationToken']).decode().split(':')
        with get_docker_client() as client:
            login = client.login(username=username, password=password, registry=authorization_data['proxyEndpoint'])
        assert login['Status'] == 'Login Succeeded'
```


