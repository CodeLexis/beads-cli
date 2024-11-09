import subprocess

from .helpers import (
    establish_ssh_connection,
    execute_remote_command,
    get_path_to_script,
    read_env_file,
    requires_manifest_file,
    select_container_port,
    transfer_file,
    uses_ssh_connection
)
from .log_message import log_message
from .models import Manifest


def initialise_project(service_name: str):
    manifest = Manifest(service_name=service_name)
    manifest.save()

    log_message('SUCCESS', 'Bead initiated successfully!')


@requires_manifest_file
def set_host(manifest: Manifest, username: str, ip: str, ssh_key_file: str):
    manifest.host = Manifest.Host(**{'username': username, 'ip': ip, 'ssh_key_file': ssh_key_file})
    manifest.save()


@requires_manifest_file
@uses_ssh_connection
def put_bead_on_server(
    manifest,
    ssh_client,
    domain_name: str = None,
    env_file: str = None,
    image: str = None
):
    """Main function to deploy bead on the server."""
    # Validate inputs and set default values
    container_port = manifest.container_port or select_container_port()
    domain_name = domain_name or manifest.domain_name
    env_file = env_file or manifest.env_file
    image = image or manifest.image

    if not domain_name:
        raise ValueError('A domain name is required')
    if not image:
        raise ValueError('An image is required')

    try:
        with ssh_client.open_sftp() as sftp:
            # Transfer the bead setup script
            bead_script_local_path = get_path_to_script('add_bead_to_server.py')
            bead_script_remote_path = '/tmp/add_bead_to_server.py'
            transfer_file(sftp, bead_script_local_path, bead_script_remote_path)

            log_message()

            # Read environment file content
            env_file_content = read_env_file(env_file)

            # Construct the command to run on the remote server
            command = (
                f"sudo python3 {bead_script_remote_path} "
                f"--service-name {manifest.service_name} "
                f"--domain-name {domain_name} "
                f"--container-port {container_port} "
                f"--image {image} "
                f"{'--env-file-content ' + env_file_content if env_file_content else ''}"
            )

            # Execute the remote command
            execute_remote_command(ssh_client, command)

    finally:
        ssh_client.close()

    log_message()

    # Update and save manifest details
    manifest.container_port = container_port
    manifest.domain_name = domain_name
    manifest.env_file = env_file
    manifest.image = image
    manifest.save()

    log_message('SUCCESS', f"\n✅ Successfully added bead '{manifest.service_name}'. Run 'bead run' to launch the service")


@requires_manifest_file
@uses_ssh_connection
def obtain_ssl_certificate(manifest: Manifest, ssh_client):
    log_message('INITIATE', 'Obtaining SSL certificate')

    execute_remote_command(ssh_client, f"sudo certbot --nginx -d {manifest.domain_name}")

    log_message('SUCCESS', 'SSL certificate obtained')


@requires_manifest_file
def run(manifest: Manifest):
    ssh_client = establish_ssh_connection(
        manifest.host.ip,
        manifest.host.username,
        manifest.host.ssh_key_file
    )

    log_message('INFO', '----------------------------------------------\n')

    execute_remote_command(ssh_client, "docker-compose -f /beads/{manifest.service_name}.yml up -d")
    execute_remote_command(ssh_client, "sudo systemctl reload nginx")

    log_message('SUCCESS', f'🟢 Bead is now running: http://{manifest.domain_name}')


def setup_server():
    """
    INSTALLATIONS
    - Install Nginx
    - Install Docker
    - Install Docker Compose

    EXECUTIONS
    - Start Nginx
    """

    pass