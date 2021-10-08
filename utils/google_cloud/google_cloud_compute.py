import os
from tenacity import retry, stop_after_attempt, wait_fixed
import time
import datetime
from pytz import timezone
import subprocess

import global_variables
import googleapiclient.discovery


class GoogleCloudCompute():

    def __init__(self, project) -> None:
        self.project = project
        self.compute = googleapiclient.discovery.build('compute', 'v1')

    def setup_networking(self, role):
        existing_nets = [net['name'] for net in self.compute.networks().list(
            project=self.project).execute()['items']]

        if global_variables.NETWORK_NAME not in existing_nets:
            self.create_network(global_variables.NETWORK_NAME)
            self.create_firewalls(global_variables.NETWORK_NAME)
        else:
            self.remove_peerings(self.project)
            self.remove_peerings(global_variables.SERVER_PROJECT)
            self.remove_old_subnets()
        self.create_subnet(global_variables.REGION, global_variables.NETWORK_NAME, role)

        # TODO: generalize to more than 2 networks
        if self.project != global_variables.SERVER_PROJECT:
            self.setup_vpc_peering(self.project, global_variables.SERVER_PROJECT)
            self.setup_vpc_peering(global_variables.SERVER_PROJECT, self.project)

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(30))
    def remove_old_subnets(self):
        for subnet in self.compute.subnetworks().list(
                project=self.project, region=global_variables.REGION).execute()['items']:
            if subnet['name'].split("-")[:2] == ["secure", "gwas"] and self.old(subnet['creationTimestamp'], 3):
                for instance in self.list_instances(global_variables.ZONE, subnetwork=subnet['selfLink']):
                    self.delete_instance(global_variables.ZONE, instance)

                print(f"Deleting subnet {subnet['name']}")
                self.compute.subnetworks().delete(
                    project=self.project, region=global_variables.REGION, subnetwork=subnet['name']).execute()
                time.sleep(20)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def remove_peerings(self, project):
        network_info = self.compute.networks().get(
            project=project, network=global_variables.NETWORK_NAME).execute()
        peerings = [peering['name'].replace(
            'peering-', '') for peering in network_info['peerings']] if 'peerings' in network_info else []
        for project2 in peerings:
            print(f"Deleting peering from {project} to {project2}")
            body = {
                'name': f"peering-{project2}"
            }
            self.compute.networks().removePeering(project=project, network=global_variables.NETWORK_NAME, body=body).execute()
            time.sleep(2)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
    def setup_vpc_peering(self, project1, project2):
        network_info = self.compute.networks().get(
            project=project1, network=global_variables.NETWORK_NAME).execute()
        peerings = [peering['name'].replace(
            'peering-', '') for peering in network_info['peerings']] if 'peerings' in network_info else []
        if project2 not in peerings:
            print("Creating peering from", project1, "to", project2)
            body = {
                'networkPeering': {
                    'name': 'peering-{}'.format(project2),
                    'network': 'https://www.googleapis.com/compute/v1/projects/{}/global/networks/{}'.format(project2, global_variables.NETWORK_NAME),
                    'exchangeSubnetRoutes': True
                }
            }
            self.compute.networks().addPeering(
                project=project1, network=global_variables.NETWORK_NAME, body=body).execute()

    def create_network(self, network_name):
        print(f"Creating new network {network_name}")
        req_body = {
            'name': network_name,
            'autoCreateSubnetworks': False,
            'routingConfig': {'routingMode': 'GLOBAL'}
        }
        operation = self.compute.networks().insert(
            project=self.project, body=req_body).execute()
        self.wait_for_operation(operation['name'])

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
    def create_subnet(self, region, network_name, role):
        subnet_name = global_variables.SUBNET_NAME + role
        print(f"Creating new subnetwork {subnet_name}")
        network_url = ''
        for net in self.compute.networks().list(project=self.project).execute()['items']:
            if net['name'] == network_name:
                network_url = net['selfLink']

        req_body = {
            'name': subnet_name,
            'network': network_url,
            'ipCidrRange': f'10.0.{role}.0/28'

        }
        operation = self.compute.subnetworks().insert(
            project=self.project, region=region, body=req_body).execute()
        self.wait_for_regionOperation(region, operation['name'])

    def create_firewalls(self, network_name):
        print(f"Creating new firewalls for network {network_name}")
        network_url = ''
        for net in self.compute.networks().list(project=self.project).execute()['items']:
            if net['name'] == network_name:
                network_url = net['selfLink']

        firewall_body = {
            'name': network_name + '-vm-ingress',
            'network': network_url,
            'sourceRanges': ['0.0.0.0/0'],
            'allowed': [{'ports': ['8000-8999', '22'], 'IPProtocol': 'tcp'}]
        }
        operation = self.compute.firewalls().insert(
            project=self.project, body=firewall_body).execute()
        self.wait_for_operation(operation['name'])

    def setup_instance(self, zone, name, role):
        existing_instances = self.list_instances(global_variables.ZONE)

        if existing_instances and name in existing_instances:
            self.delete_instance(zone, name)
        self.create_instance(zone, name, role)

        return self.get_vm_external_ip_address(zone, name)

    def create_instance(self, zone, name, role):
        print("Creating VM instance with name", name)

        image_response = self.compute.images().getFromFamily(
            project='debian-cloud', family='debian-11').execute()
        source_disk_image = image_response['selfLink']

        # Configure the machine
        machine_type = "zones/%s/machineTypes/c2-standard-4" % zone
        startup_script = open(
            os.path.join(
                os.path.dirname(__file__), '../../startup-script.sh'), 'r').read()

        instance_body = {
            "name": name,
            "machineType": machine_type,
            "networkInterfaces": [{
                'network': 'projects/{}/global/networks/{}'.format(self.project, global_variables.NETWORK_NAME),
                'subnetwork': 'regions/{}/subnetworks/{}'.format(global_variables.REGION, global_variables.SUBNET_NAME + role),
                'networkIP': f"10.0.{role}.10",
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],
            "disks": [{
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceImage": source_disk_image
                }
            }],
            # Allow the instance to access cloud storage and logging.
            # Logging access necessary for the startup-script to work.
            "serviceAccounts": [{
                'email': 'default',
                'scopes': [
                    'https://www.googleapis.com/auth/devstorage.read_write',
                    'https://www.googleapis.com/auth/logging.write',
                    'https://www.googleapis.com/auth/pubsub'
                ]
            }],
            'metadata': {
                'items': [{
                    # Startup script is automatically executed by the
                    # instance upon startup.
                    'key': 'startup-script',
                    'value': startup_script
                }]
            }
        }
        operation = self.compute.instances().insert(
            project=self.project, zone=zone, body=instance_body).execute()

        self.wait_for_zoneOperation(zone, operation['name'])

    def stop_instance(self, zone, instance):
        print("Stopping VM instance with name ", instance)
        operation = self.compute.instances().stop(
            project=self.project, zone=zone, instance=instance).execute()
        self.wait_for_zoneOperation(zone, operation['name'])

    def list_instances(self, zone, subnetwork=""):
        result = self.compute.instances().list(
            project=self.project, zone=zone).execute()
        return [instance['name'] for instance in result['items'] if subnetwork in instance['networkInterfaces'][0]['subnetwork']] if 'items' in result else []

    def delete_instance(self, zone, name):
        print("Deleting VM instance with name ", name)
        operation = self.compute.instances().delete(
            project=self.project, zone=zone, instance=name).execute()
        self.wait_for_zoneOperation(zone, operation['name'])

    def wait_for_operation(self, operation):
        print("Waiting for operation to finish...")
        while True:
            result = self.compute.globalOperations().get(
                project=self.project, operation=operation).execute()

            if result['status'] == 'DONE':
                print("done.")
                if "error" in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)

    def wait_for_zoneOperation(self, zone, operation):
        print("Waiting for operation to finish...")
        while True:
            result = self.compute.zoneOperations().get(project=self.project, zone=zone,
                                                       operation=operation).execute()

            if result['status'] == 'DONE':
                print("done.")
                if "error" in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)

    def wait_for_regionOperation(self, region, operation):
        print("Waiting for operation to finish...")
        while True:
            result = self.compute.regionOperations().get(
                project=self.project, region=region, operation=operation).execute()

            if result['status'] == 'DONE':
                print("done.")
                if "error" in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)

    def get_vm_external_ip_address(self, zone, instance):
        print("Getting the IP address for VM instance", instance)
        response = self.compute.instances().get(
            project=self.project, zone=zone, instance=instance).execute()
        return response['networkInterfaces'][0]['accessConfigs'][0]['natIP']

    def get_service_account_for_vm(self, zone, instance) -> str:
        print("Getting the service account for VM instance", instance)
        response = self.compute.instances().get(
            project=self.project, zone=zone, instance=instance).execute()
        return response['serviceAccounts'][0]['email']

    def old(self, timestamp, minutes=30):
        benchmark = (datetime.datetime.now(tz=timezone(
            'us/pacific')) - datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "-7:00"
        if timestamp < benchmark:
            return True
        print("Young...")
        return False
