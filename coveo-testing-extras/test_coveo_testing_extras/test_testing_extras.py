from coveo_testing_extras.temporary_resource.docker_container import find_ip_in_docker_inspect_info


def test_given_direct_ip_address_when_find_ip_in_docker_inspect_info_then_use_it() -> None:
    docker_info = {
        "HostConfig": {
            "NetworkMode": "github_network_5d5415361be8472499e665143c43a6b1",
        },
        "NetworkSettings": {
            "IPAddress": "1.2.3.4",
            "Networks": {
                "bridge": {
                    "IPAddress": "5.6.7.8",
                },
                "github_network_5d5415361be8472499e665143c43a6b1": {
                    "IPAddress": "9.10.11.12",
                },
            },
        },
    }
    assert "1.2.3.4" == find_ip_in_docker_inspect_info(docker_info)


def test_given_no_direct_ip_address_when_find_ip_in_docker_inspect_info_then_use_bridge() -> None:
    # This is the exact legacy behavior
    # https://github.com/moby/moby/blob/27cefe6c43b74d429bbfa01dfd106ca8837e8bfe/daemon/server/router/container/inspect.go#L40-L59
    docker_info = {
        "HostConfig": {
            "NetworkMode": "github_network_5d5415361be8472499e665143c43a6b1",
        },
        "NetworkSettings": {
            "Networks": {
                "bridge": {
                    "IPAddress": "5.6.7.8",
                },
                "github_network_5d5415361be8472499e665143c43a6b1": {
                    "IPAddress": "9.10.11.12",
                },
            },
        },
    }
    assert "5.6.7.8" == find_ip_in_docker_inspect_info(docker_info)


def test_given_no_direct_ip_address_or_bridge_when_find_ip_in_docker_inspect_info_then_use_network_mode() -> (
    None
):
    docker_info = {
        "HostConfig": {
            "NetworkMode": "github_network_5d5415361be8472499e665143c43a6b1",
        },
        "NetworkSettings": {
            "Networks": {
                "another_network": {
                    "IPAddress": "5.6.7.8",
                },
                "github_network_5d5415361be8472499e665143c43a6b1": {
                    "IPAddress": "9.10.11.12",
                },
            },
        },
    }
    assert "9.10.11.12" == find_ip_in_docker_inspect_info(docker_info)
