"""Automatically launches and sets up a Sky onprem cluster on AWS.

The script allocates a cloud cluster and setups up the cloud cluster to run an
'onprem' cluster on the cloud. It performs the following steps:
    1) Launches a cluster on the cloud with `sky launch -c on-prem-cluster-[ID]`.
     The Sky yaml sets up another user named `test`.
    2) Setups Sky dependencies for the admin user via `sky admin deploy ..`.
    3) Creates the local cluster config for the regular user, stored in `~/.sky/local/...`
To clean up the local cluster, run `sky down [LOCAL_CLUSTER]` and remove the corresponding
local cluster config file.

Usage:
    # Creates a Sky on-premise cluster named `my-local-cluster`
    python examples/local/launch_cloud_onprem.py -n my-local-cluster
"""

import argparse
import os
import subprocess
import tempfile
import textwrap
import uuid
import yaml

from click import testing as cli_testing

from sky import cli
from sky import global_user_state
from sky.backends import onprem_utils
from sky.utils import common_utils

parser = argparse.ArgumentParser()
parser.add_argument('-n',
                    '--local-cluster-name',
                    type=str,
                    required=True,
                    help='Name of the local cluster.')
args = parser.parse_args()

# Public and private keys (autogenerated by Sky)
public_key = '~/.ssh/sky-key.pub'
private_key = '~/.ssh/sky-key'

local_cluster_name = args.local_cluster_name

# Sky Task YAML to setup the user 'test'
sky_yaml_config = {
    'resources': {
        'cloud': 'aws'
    },
    'file_mounts': {
        '/user-key': public_key
    },
    'setup': textwrap.dedent("""\
              sudo adduser --disabled-password --gecos '' test
              sudo -H su test -c 'mkdir ~/.ssh'
              sudo -H su test -c 'chmod 700 ~/.ssh'
              sudo -H su test -c 'touch ~/.ssh/authorized_keys'
              sudo -H su test -c 'chmod 600 ~/.ssh/authorized_keys'
              sudo -H su test -c 'cat /user-key >> ~/.ssh/authorized_keys'
            """)
}

cli_runner = cli_testing.CliRunner()
onprem_name = f'onprem-cluster-{uuid.uuid4().hex[:6]}'
with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w') as f:
    yaml.dump(sky_yaml_config, f)
    file_path = f.name
    cli_runner.invoke(cli.launch, ['-c', onprem_name, file_path])

handle = global_user_state.get_handle_from_cluster_name(onprem_name)
head_ip = handle.head_ip

# Cluster config YAML to setup Sky Onprem on the admin account 'ubuntu'
cluster_yaml_config = {
    'cluster': {
        'ips': [head_ip],
        'name': local_cluster_name
    },
    'auth': {
        'ssh_user': 'ubuntu',
        'ssh_private_key': private_key
    }
}

with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w') as f:
    yaml.dump(cluster_yaml_config, f)
    file_path = f.name
    subprocess.run(f'sky admin deploy {file_path}', shell=True, check=True)

# Fill out the local config file in ~/.sky/local/...
local_config = onprem_utils.get_local_cluster_config_or_error(
    local_cluster_name)
local_config['auth']['ssh_user'] = 'test'
local_config['auth']['ssh_private_key'] = private_key
local_config_path = onprem_utils.SKY_USER_LOCAL_CONFIG_PATH.format(
    local_cluster_name)
common_utils.dump_yaml(os.path.expanduser(local_config_path), local_config)

print((
    f'Sky onprem cluster {local_cluster_name} is now ready for use! '
    f'You can launch jobs with `sky launch -c {local_cluster_name}  -- [CMD]. '
    f'After you are done, shut down the cluster by running `sky down {local_cluster_name}` '
    f'and removing the local cluster config in {local_config_path}.'))
