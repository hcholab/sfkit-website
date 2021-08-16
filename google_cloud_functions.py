import os
import subprocess
import time

from flask import flash
from google.cloud import storage

import constants


def create_network(compute, project, network_name):
    flash("Creating new network for GWAS")
    print("Creating new network for GWAS")
    req_body = {
        'name': network_name,
        'autoCreateSubnetworks': False,
        'routingConfig': {'routingMode': 'GLOBAL'}
    }
    operation = compute.networks().insert(project=project, body=req_body).execute()
    wait_for_operation(compute, project, operation['name'])


def create_subnet(compute, project, region, network_name):
    flash("Creating new subnetwork for GWAS")
    print("Creating new subnetwork for GWAS")
    network_url = ''
    for net in compute.networks().list(project=project).execute()['items']:
        if net['name'] == network_name:
            network_url = net['selfLink']

    req_body = {
        'name': constants.SUBNET_NAME,
        'network': network_url,
        'ipCidrRange': '10.0.0.0/28'

    }
    operation = compute.subnetworks().insert(
        project=project, region=region, body=req_body).execute()
    wait_for_regionOperation(compute, project, region, operation['name'])


def create_firewalls(compute, project, network_name):
    flash("Creating new firewalls for GWAS")
    print("Creating new firewalls for GWAS")
    network_url = ''
    for net in compute.networks().list(project=project).execute()['items']:
        if net['name'] == network_name:
            network_url = net['selfLink']

    firewall_body = {
        'name': network_name + '-vm-ingress',
        'network': network_url,
        'sourceRanges': ['0.0.0.0/0'],
        'allowed': [{'ports': ['8000-8999', '22'], 'IPProtocol': 'tcp'}]
    }
    operation = compute.firewalls().insert(
        project=project, body=firewall_body).execute()
    wait_for_operation(compute, project, operation['name'])


def create_instance(compute, project, zone, name):
    instance_body = {
        "name": name,
        "machineType": "zones/{}/machineTypes/{}".format(zone, constants.MACHINE_TYPE),
        "networkInterfaces": [{
            'network': 'projects/{}/global/networks/{}'.format(project, constants.NETWORK_NAME),
            'subnetwork': 'regions/{}/subnetworks/{}'.format(constants.REGION, constants.SUBNET_NAME),
            'accessConfigs': [
                {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
            ]
        }],
        "disks": [{
            "boot": True,
            "initializeParams": {
                "sourceImage": "projects/debian-cloud/global/images/family/debian-9"
            }
        }]
    }
    operation = compute.instances().insert(
        project=project, zone=zone, body=instance_body).execute()

    wait_for_zoneOperation(compute, project, zone, operation['name'])
    time.sleep(10)
    transfer_file_to_instance(project, name, 'startup-script.sh', '~/')

    execute_shell_script_on_instance(
        project, name, ['chmod u+x startup-script.sh', './startup-script.sh'])


def start_instance(compute, project, zone, instance):
    operation = compute.instances().start(
        project=project, zone=zone, instance=instance).execute()
    wait_for_zoneOperation(compute, project, zone, operation['name'])


def stop_instance(compute, project, zone, instance):
    operation = compute.instances().stop(
        project=project, zone=zone, instance=instance).execute()
    wait_for_zoneOperation(compute, project, zone, operation['name'])


def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    return [instance['name'] for instance in result['items']] if 'items' in result else None


def delete_instance(compute, project, zone, name):
    return compute.instances().delete(project=project, zone=zone, instance=name).execute()


def wait_for_operation(compute, project, operation):
    print("Waiting for operation to finish...")
    while True:
        result = compute.globalOperations().get(
            project=project, operation=operation).execute()

        if result['status'] == 'DONE':
            print("done.")
            if "error" in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)


def wait_for_zoneOperation(compute, project, zone, operation):
    print("Waiting for operation to finish...")
    while True:
        result = compute.zoneOperations().get(project=project, zone=zone,
                                              operation=operation).execute()

        if result['status'] == 'DONE':
            print("done.")
            if "error" in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)


def wait_for_regionOperation(compute, project, region, operation):
    print("Waiting for operation to finish...")
    while True:
        result = compute.regionOperations().get(
            project=project, region=region, operation=operation).execute()

        if result['status'] == 'DONE':
            print("done.")
            if "error" in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)


def get_vm_external_ip_address(compute, project, zone, instance):
    print("Getting the IP address for VM instance ", instance)
    response = compute.instances().get(
        project=project, zone=zone, instance=instance).execute()
    return response['networkInterfaces'][0]['accessConfigs'][0]['natIP']


def get_ip_addresses_from_bucket():
    print("Getting ip_addresses from bucket")
    storage_client = storage.Client(project=constants.PROJECT_NAME)
    for i in range(101):
        if len(list(storage_client.list_blobs(constants.BUCKET_NAME, prefix="ip_addresses/"))) < 4:
            time.sleep(1)
        else:
            break
        if i == 100:
            print("The other parties don't seem to be showing up...")
            raise Exception("The other parties don't seem to be showing up...")
    ip_addresses = []
    for role in ["0", "1", "2", "3"]:
        bucket = storage_client.bucket(constants.BUCKET_NAME)
        blob = bucket.blob("ip_addresses/IP_ADDR_P" + role)
        ip_address = blob.download_as_bytes()
        ip_addresses.append(("IP_ADDR_P" + role, ip_address.decode("utf-8")))
    return ip_addresses


def delete_blob(bucket_name, blob_name):
    """Deletes a blob from the bucket."""
    # bucket_name = "your-bucket-name"
    # blob_name = "your-object-name"

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()

    print("Blob {} deleted.".format(blob_name))

# Copy file from local machine to Google Cloud Compute Instance
def transfer_file_to_instance(project, instance, fname, path, zone="us-central1-a"):
    cmd = 'gcloud compute scp --project {} "{}" {}:{} --zone {}'.format(
        project, fname, instance, path, zone)
    os.system(cmd)

# Execute series of shell commands on Google Cloud Compute Instance
def execute_shell_script_on_instance(project, instance, cmds):
    cmd = '; '.join(cmds)
    script = 'gcloud compute ssh {} --project {} --command \'{}\''.format(
        instance, project, cmd)
    # os.system(script)
    return subprocess.Popen(script, shell=True).wait()
